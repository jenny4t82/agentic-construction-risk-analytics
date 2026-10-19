"""FastAPI entry point for the Milestone 1 Site Risk Agent."""

import email
import logging
import os
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .database import get_db
from .detector import (
    BaseHazardDetector,
    MockHazardDetector,
    UnconfiguredHazardDetector,
    YOLOv8HazardDetector,
)
from .models import DetectedHazard, NormalizedObservation
from .persistence import (
    get_observation_record,
    list_observation_records,
    persist_observation_bundle,
)
from .risk_agent import SiteRiskAgent


class ObservationRequest(BaseModel):
    """JSON representation of one normalized monitoring observation."""

    observation_id: str = Field(min_length=1)
    timestamp: datetime
    source: str = Field(min_length=1)
    labels: list[str] = Field(min_length=1)
    people_count: Optional[int] = Field(default=None, ge=1)
    duration_minutes: Optional[int] = Field(default=None, ge=1)
    repeated_count: Optional[int] = Field(default=None, ge=0)
    work_area: str = "unspecified"
    detection_confidence: Optional[float] = Field(default=None, ge=0, le=1)


class AssessmentResponse(BaseModel):
    """JSON representation of one hazard assessment."""

    observation_id: str
    hazard_type: str
    source_label: str
    severity: int
    likelihood: int
    exposure: int
    risk_score: int
    risk_band: str
    detection_confidence: Optional[float]
    explanation: str


class DetectedHazardResponse(BaseModel):
    """JSON representation of a detected hazard, scored or pending."""

    observation_id: str
    hazard_type: str
    source_label: str
    detection_confidence: Optional[float]


class AssessmentsResponse(BaseModel):
    """Response separating detected hazards from completed assessments."""

    observation_id: str
    detected_hazards: list[DetectedHazardResponse]
    assessments: list[AssessmentResponse]
    pending_hazards: list[DetectedHazardResponse]


class PersistedAssessmentResponse(BaseModel):
    """JSON representation of a persisted risk assessment."""

    model_config = ConfigDict(from_attributes=True)

    assessment_id: Optional[int] = None
    assessment_version: int
    status: str
    severity: Optional[int] = None
    likelihood: Optional[int] = None
    exposure: Optional[int] = None
    risk_score: Optional[int] = None
    risk_band: Optional[str] = None
    explanation: Optional[str] = None
    missing_inputs: Optional[list[str]] = None
    scoring_rule_version: str
    assessed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class PersistedHazardResponse(BaseModel):
    """JSON representation of a persisted hazard detection with assessments."""

    model_config = ConfigDict(from_attributes=True)

    detected_hazard_id: Optional[int] = None
    hazard_type: str
    source_label: str
    detection_confidence: Optional[float] = None
    detected_at: Optional[datetime] = None
    detector_name: Optional[str] = None
    evidence: Optional[dict[str, Any]] = None
    assessments: list[PersistedAssessmentResponse] = []


class ObservationDetailResponse(BaseModel):
    """JSON representation of a persisted site observation."""

    model_config = ConfigDict(from_attributes=True)

    observation_id: str
    observed_at: datetime
    source: str
    work_area: Optional[str] = None
    people_count: Optional[int] = None
    duration_minutes: Optional[int] = None
    repeated_count: Optional[int] = None
    detection_confidence: Optional[float] = None
    raw_metadata: Optional[dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    detected_hazards: list[PersistedHazardResponse] = []


app = FastAPI(
    title="Agentic Construction Risk Intelligence Platform",
    version="0.1.0",
)
agent = SiteRiskAgent()
logger = logging.getLogger(__name__)


@app.get("/health")
def health() -> dict[str, str]:
    """Return a simple liveness response."""

    return {"status": "ok"}


@app.post("/assessments", response_model=AssessmentsResponse)
def create_assessments(
    request: ObservationRequest,
    db: Optional[Session] = Depends(get_db),
) -> AssessmentsResponse:
    """Assess the supported hazards in one normalized observation."""

    try:
        observation = NormalizedObservation(
            observation_id=request.observation_id,
            timestamp=request.timestamp,
            source=request.source,
            labels=tuple(request.labels),
            people_count=request.people_count,
            duration_minutes=request.duration_minutes,
            repeated_count=request.repeated_count,
            work_area=request.work_area,
            detection_confidence=request.detection_confidence,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    detected_hazards = agent.detect_hazards(observation)
    assessments = []
    pending_hazards = []
    for hazard in detected_hazards:
        assessment = agent.assess_hazard(hazard, observation)
        if assessment is None:
            pending_hazards.append(
                DetectedHazardResponse.model_validate(hazard, from_attributes=True)
            )
        else:
            assessments.append(
                AssessmentResponse.model_validate(
                    assessment, from_attributes=True
                )
            )

    if db is not None:
        try:
            persist_observation_bundle(
                session=db,
                observation_id=request.observation_id,
                timestamp=request.timestamp,
                source=request.source,
                work_area=request.work_area,
                people_count=request.people_count,
                duration_minutes=request.duration_minutes,
                repeated_count=request.repeated_count,
                detection_confidence=request.detection_confidence,
                detected_hazards=detected_hazards,
                assessments=assessments,
            )
        except ValueError as err:
            raise HTTPException(status_code=409, detail=str(err)) from err
        except SQLAlchemyError as err:
            logger.error(
                "Database persistence failed for observation %s: %s",
                request.observation_id,
                err,
            )
            raise HTTPException(
                status_code=500, detail="Database persistence failed"
            ) from err

    return AssessmentsResponse(
        observation_id=request.observation_id,
        detected_hazards=[
            DetectedHazardResponse.model_validate(hazard, from_attributes=True)
            for hazard in detected_hazards
        ],
        assessments=assessments,
        pending_hazards=pending_hazards,
    )


MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB limit


def get_hazard_detector() -> BaseHazardDetector:
    """Dependency provider for hazard detector implementation.

    In explicit mock mode (HAZARD_DETECTOR_MODE=mock), returns MockHazardDetector.
    If model weights are provided via HAZARD_DETECTOR_WEIGHTS, returns YOLOv8HazardDetector.
    In unconfigured environments, returns UnconfiguredHazardDetector which safely raises
    an error upon invocation rather than returning false zero-hazard compliance results.
    Can be overridden in tests via FastAPI's app.dependency_overrides.
    """
    mode = os.getenv("HAZARD_DETECTOR_MODE", "").strip().lower()
    if mode == "mock":
        return MockHazardDetector()

    weights_path = os.getenv("HAZARD_DETECTOR_WEIGHTS", "").strip()
    if weights_path:
        return _get_yolo_detector(weights_path)

    return UnconfiguredHazardDetector()


@lru_cache(maxsize=4)
def _get_yolo_detector(weights_path: str) -> YOLOv8HazardDetector:
    """Reuse one lazy-loading YOLO detector per configured weights path."""

    return YOLOv8HazardDetector(weights_path=weights_path)


def _validate_image_bytes(image_data: bytes) -> str:
    """Validate image bytes and return detected MIME format or raise HTTPException."""
    if not image_data or len(image_data) == 0:
        raise HTTPException(status_code=400, detail="Image file must not be empty")

    if len(image_data) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=413, detail="Image file exceeds maximum allowed size of 10MB"
        )

    if image_data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image_data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if (
        image_data.startswith(b"RIFF")
        and len(image_data) >= 12
        and image_data[8:12] == b"WEBP"
    ):
        return "image/webp"

    raise HTTPException(
        status_code=400,
        detail="Unsupported or corrupt image format. Supported formats: JPEG, PNG, WebP.",
    )


def _extract_image_payload(
    body: bytes, content_type: str
) -> tuple[bytes, dict[str, str]]:
    """Extract raw image bytes and optional form fields from request body."""
    if not body:
        return b"", {}

    if "multipart/form-data" in content_type.lower():
        mime_msg = email.message_from_bytes(
            b"Content-Type: "
            + content_type.encode("latin1", errors="replace")
            + b"\r\n\r\n"
            + body
        )
        fields: dict[str, str] = {}
        image_data = b""
        file_count = 0
        if mime_msg.is_multipart():
            for part in mime_msg.get_payload():
                name = part.get_param("name", header="content-disposition")
                filename = part.get_filename()
                payload = part.get_payload(decode=True) or b""
                if filename or (name and name.lower() in ("file", "image")):
                    file_count += 1
                    if file_count > 1:
                        raise HTTPException(
                            status_code=400,
                            detail="Multiple image files uploaded. Exactly one image file is accepted.",
                        )
                    image_data = payload
                elif name:
                    fields[name] = payload.decode("utf-8", errors="replace").strip()
        return image_data, fields

    return body, {}


def _parse_int_param(value: Optional[str], name: str, min_value: int) -> Optional[int]:
    if value is None or str(value).strip() == "":
        return None
    try:
        val = int(str(value).strip())
    except ValueError as err:
        raise HTTPException(
            status_code=422, detail=f"{name} must be a valid integer"
        ) from err
    if val < min_value:
        raise HTTPException(
            status_code=422, detail=f"{name} must be at least {min_value} when provided"
        )
    return val


@app.post("/assessments/image", response_model=AssessmentsResponse)
async def create_image_assessments(
    request: Request,
    observation_id: Optional[str] = Query(default=None),
    work_area: Optional[str] = Query(default=None),
    people_count: Optional[int] = Query(default=None),
    duration_minutes: Optional[int] = Query(default=None),
    repeated_count: Optional[int] = Query(default=None),
    detector: BaseHazardDetector = Depends(get_hazard_detector),
    db: Optional[Session] = Depends(get_db),
) -> AssessmentsResponse:
    """Detect supported hazards in an uploaded image and produce risk assessments.

    Accepts raw image binary or multipart form upload. Non-hazards and compliant
    gear are filtered out, while detected persons are counted for site exposure.
    """
    # Early request-size check via Content-Length header
    content_length_header = request.headers.get("content-length")
    if content_length_header:
        try:
            if int(content_length_header) > MAX_IMAGE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail="Request entity exceeds maximum allowed size of 10MB",
                )
        except ValueError:
            pass

    # Read body with streaming size enforcement to prevent unbounded memory allocation.
    # Note: Application-level streaming limit prevents excessive in-memory buffering
    # for missing or misleading Content-Length headers, but does not replace web-server
    # or reverse-proxy limits (e.g., Nginx client_max_body_size) in production.
    chunks = []
    total_size = 0
    async for chunk in request.stream():
        total_size += len(chunk)
        if total_size > MAX_IMAGE_SIZE:
            raise HTTPException(
                status_code=413,
                detail="Request body exceeds maximum allowed size of 10MB",
            )
        chunks.append(chunk)
    raw_body = b"".join(chunks)

    content_type = request.headers.get("content-type", "")
    image_bytes, form_fields = _extract_image_payload(raw_body, content_type)

    _validate_image_bytes(image_bytes)

    # Normalize observation ID: empty or whitespace-only inputs consistently generate a UUID
    raw_obs_id = (
        (observation_id.strip() if observation_id else "")
        or (form_fields.get("observation_id", "").strip())
    )
    resolved_obs_id = raw_obs_id if raw_obs_id else f"img-obs-{uuid4().hex[:8]}"

    resolved_work_area = (
        (work_area.strip() if work_area else "")
        or (form_fields.get("work_area", "").strip())
        or "unspecified"
    )

    raw_pc = people_count if people_count is not None else form_fields.get("people_count")
    resolved_people_count = (
        _parse_int_param(str(raw_pc), "people_count", 1) if raw_pc is not None else None
    )

    raw_dur = (
        duration_minutes
        if duration_minutes is not None
        else form_fields.get("duration_minutes")
    )
    resolved_duration = (
        _parse_int_param(str(raw_dur), "duration_minutes", 1) if raw_dur is not None else None
    )

    raw_rep = (
        repeated_count
        if repeated_count is not None
        else form_fields.get("repeated_count")
    )
    resolved_repeated = (
        _parse_int_param(str(raw_rep), "repeated_count", 0) if raw_rep is not None else None
    )

    try:
        detection = detector.detect(image_bytes)
    except (RuntimeError, FileNotFoundError, OSError) as err:
        raise HTTPException(
            status_code=503,
            detail=f"Hazard detection service unavailable: {err}",
        ) from err
    except ValueError as err:
        raise HTTPException(
            status_code=400,
            detail=f"Image decoding failed: {err}",
        ) from err

    if resolved_people_count is None and detection.people_count >= 1:
        resolved_people_count = detection.people_count

    if not detection.hazard_labels:
        if db is not None:
            try:
                persist_observation_bundle(
                    session=db,
                    observation_id=resolved_obs_id,
                    timestamp=datetime.now(timezone.utc),
                    source=f"image_upload:{request.headers.get('x-filename', 'site_image')}",
                    work_area=resolved_work_area,
                    people_count=resolved_people_count,
                    duration_minutes=resolved_duration,
                    repeated_count=resolved_repeated,
                    detection_confidence=detection.max_confidence,
                    detected_hazards=[],
                    assessments=[],
                    detector_name=type(detector).__name__,
                )
            except ValueError as err:
                raise HTTPException(status_code=409, detail=str(err)) from err
            except SQLAlchemyError as err:
                logger.error(
                    "Database persistence failed for image observation %s: %s",
                    resolved_obs_id,
                    err,
                )
                raise HTTPException(
                    status_code=500, detail="Database persistence failed"
                ) from err

        return AssessmentsResponse(
            observation_id=resolved_obs_id,
            detected_hazards=[],
            assessments=[],
            pending_hazards=[],
        )

    try:
        observation = NormalizedObservation(
            observation_id=resolved_obs_id,
            timestamp=datetime.now(timezone.utc),
            source=f"image_upload:{request.headers.get('x-filename', 'site_image')}",
            labels=tuple(detection.hazard_labels),
            people_count=resolved_people_count,
            duration_minutes=resolved_duration,
            repeated_count=resolved_repeated,
            work_area=resolved_work_area,
            detection_confidence=detection.max_confidence,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    detected_hazards = agent.detect_hazards(observation)
    assessments = []
    pending_hazards = []
    for hazard in detected_hazards:
        assessment = agent.assess_hazard(hazard, observation)
        if assessment is None:
            pending_hazards.append(
                DetectedHazardResponse.model_validate(hazard, from_attributes=True)
            )
        else:
            assessments.append(
                AssessmentResponse.model_validate(assessment, from_attributes=True)
            )

    if db is not None:
        try:
            persist_observation_bundle(
                session=db,
                observation_id=resolved_obs_id,
                timestamp=observation.timestamp,
                source=observation.source,
                work_area=resolved_work_area,
                people_count=resolved_people_count,
                duration_minutes=resolved_duration,
                repeated_count=resolved_repeated,
                detection_confidence=detection.max_confidence,
                detected_hazards=detected_hazards,
                assessments=assessments,
                detector_name=type(detector).__name__,
            )
        except ValueError as err:
            raise HTTPException(status_code=409, detail=str(err)) from err
        except SQLAlchemyError as err:
            logger.error(
                "Database persistence failed for image observation %s: %s",
                resolved_obs_id,
                err,
            )
            raise HTTPException(
                status_code=500, detail="Database persistence failed"
            ) from err

    return AssessmentsResponse(
        observation_id=resolved_obs_id,
        detected_hazards=[
            DetectedHazardResponse.model_validate(hazard, from_attributes=True)
            for hazard in detected_hazards
        ],
        assessments=assessments,
        pending_hazards=pending_hazards,
    )


@app.get("/observations", response_model=list[ObservationDetailResponse])
def get_observations(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Optional[Session] = Depends(get_db),
) -> list[ObservationDetailResponse]:
    """List recent site observations with detected hazards and assessments."""
    if db is None:
        raise HTTPException(
            status_code=503,
            detail="Database persistence is not configured. Set DATABASE_URL to enable persistence.",
        )
    try:
        records = list_observation_records(db, limit=limit, offset=offset)
        return [
            ObservationDetailResponse.model_validate(rec, from_attributes=True)
            for rec in records
        ]
    except SQLAlchemyError as err:
        logger.error("Failed to query observations from database: %s", err)
        raise HTTPException(
            status_code=500, detail="Failed to query observations from database"
        ) from err


@app.get("/observations/{observation_id}", response_model=ObservationDetailResponse)
def get_observation(
    observation_id: str,
    db: Optional[Session] = Depends(get_db),
) -> ObservationDetailResponse:
    """Retrieve one saved observation with its detected hazards and assessments."""
    if db is None:
        raise HTTPException(
            status_code=503,
            detail="Database persistence is not configured. Set DATABASE_URL to enable persistence.",
        )
    try:
        record = get_observation_record(db, observation_id=observation_id)
    except SQLAlchemyError as err:
        logger.error(
            "Failed to query observation %s from database: %s",
            observation_id,
            err,
        )
        raise HTTPException(
            status_code=500, detail="Failed to query observation from database"
        ) from err

    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Observation '{observation_id}' not found",
        )
    return ObservationDetailResponse.model_validate(record, from_attributes=True)
