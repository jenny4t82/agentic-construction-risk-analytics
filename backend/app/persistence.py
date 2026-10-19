"""Persistence service for site observations, detected hazards, and risk assessments.

Persists monitoring data to PostgreSQL using the existing SQLAlchemy schema.
Operations are atomic within the provided session transaction.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .db_models import DetectedHazardRecord, Observation, RiskAssessment
from .models import DetectedHazard, HazardAssessment


def build_observation_bundle(
    observation_id: str,
    timestamp: datetime,
    source: str,
    work_area: Optional[str] = "unspecified",
    people_count: Optional[int] = None,
    duration_minutes: Optional[int] = None,
    repeated_count: Optional[int] = None,
    detection_confidence: Optional[float] = None,
    detected_hazards: Sequence[DetectedHazard] = (),
    assessments: Sequence[Any] = (),
    raw_metadata: Optional[dict[str, Any]] = None,
    detector_name: Optional[str] = None,
    detector_version: Optional[str] = None,
    evidence: Optional[dict[str, Any]] = None,
) -> Observation:
    """Construct an Observation ORM instance with associated hazards and assessments.

    Builds the complete in-memory ORM object hierarchy without committing.
    Completed assessments contain calculated scores, likelihood, exposure, and assessed_at.
    Pending assessments contain null scores/band/assessed_at and explicit missing_inputs.
    """
    conf_decimal = (
        Decimal(str(round(detection_confidence, 4)))
        if detection_confidence is not None
        else None
    )

    obs_record = Observation(
        observation_id=observation_id,
        observed_at=timestamp,
        source=source,
        work_area=work_area or "unspecified",
        people_count=people_count,
        duration_minutes=duration_minutes,
        repeated_count=repeated_count,
        detection_confidence=conf_decimal,
        raw_metadata=raw_metadata or {},
    )

    # Group completed assessments by (hazard_type, source_label) preserving order
    completed_pool: dict[tuple[str, str], list[Any]] = {}
    for a in assessments:
        key = (a.hazard_type, a.source_label)
        if key not in completed_pool:
            completed_pool[key] = []
        completed_pool[key].append(a)

    # Identify missing scoring inputs for pending assessments
    missing_inputs: list[str] = []
    if people_count is None:
        missing_inputs.append("people_count")
    if duration_minutes is None:
        missing_inputs.append("duration_minutes")
    if repeated_count is None:
        missing_inputs.append("repeated_count")

    for hazard in detected_hazards:
        h_conf = (
            Decimal(str(round(hazard.detection_confidence, 4)))
            if hazard.detection_confidence is not None
            else None
        )
        hazard_record = DetectedHazardRecord(
            hazard_type=hazard.hazard_type,
            source_label=hazard.source_label,
            detection_confidence=h_conf,
            detected_at=timestamp,
            detector_name=detector_name,
            detector_version=detector_version,
            evidence=evidence,
        )
        obs_record.detected_hazards.append(hazard_record)

        hazard_key = (hazard.hazard_type, hazard.source_label)
        candidates = completed_pool.get(hazard_key)
        matched_assessment = None
        if candidates:
            if hazard.detection_confidence is not None:
                for idx, cand in enumerate(candidates):
                    if (
                        cand.detection_confidence is not None
                        and abs(cand.detection_confidence - hazard.detection_confidence) < 1e-4
                    ):
                        matched_assessment = candidates.pop(idx)
                        break
            if matched_assessment is None:
                matched_assessment = candidates.pop(0)

        if matched_assessment is not None:
            assessment_record = RiskAssessment(
                assessment_version=1,
                status="completed",
                severity=matched_assessment.severity,
                likelihood=matched_assessment.likelihood,
                exposure=matched_assessment.exposure,
                risk_score=matched_assessment.risk_score,
                risk_band=matched_assessment.risk_band,
                explanation=matched_assessment.explanation,
                missing_inputs=None,
                scoring_rule_version="milestone1-v1",
                assessed_at=datetime.now(timezone.utc),
            )
        else:
            # Pending assessment satisfies ck_risk_assessments_completion_fields:
            # status='pending', risk_score=None, risk_band=None, assessed_at=None
            missing_list = list(missing_inputs) if missing_inputs else ["scoring_inputs"]
            assessment_record = RiskAssessment(
                assessment_version=1,
                status="pending",
                severity=None,
                likelihood=None,
                exposure=None,
                risk_score=None,
                risk_band=None,
                explanation=f"Pending required scoring inputs: {', '.join(missing_list)}",
                missing_inputs=missing_list,
                scoring_rule_version="milestone1-v1",
                assessed_at=None,
            )

        hazard_record.assessments.append(assessment_record)

    return obs_record


def persist_observation_bundle(
    session: Session,
    observation_id: str,
    timestamp: datetime,
    source: str,
    work_area: Optional[str] = "unspecified",
    people_count: Optional[int] = None,
    duration_minutes: Optional[int] = None,
    repeated_count: Optional[int] = None,
    detection_confidence: Optional[float] = None,
    detected_hazards: Sequence[DetectedHazard] = (),
    assessments: Sequence[Any] = (),
    raw_metadata: Optional[dict[str, Any]] = None,
    detector_name: Optional[str] = None,
    detector_version: Optional[str] = None,
    evidence: Optional[dict[str, Any]] = None,
) -> Observation:
    """Persist an observation with all detected hazards and assessments into the session.

    Checks for duplicate observation IDs and flushes changes to ensure foreign keys
    and constraints validate atomically within the session transaction.
    """
    existing = session.get(Observation, observation_id)
    if existing is not None:
        raise ValueError(f"Observation '{observation_id}' already exists")

    obs = build_observation_bundle(
        observation_id=observation_id,
        timestamp=timestamp,
        source=source,
        work_area=work_area,
        people_count=people_count,
        duration_minutes=duration_minutes,
        repeated_count=repeated_count,
        detection_confidence=detection_confidence,
        detected_hazards=detected_hazards,
        assessments=assessments,
        raw_metadata=raw_metadata,
        detector_name=detector_name,
        detector_version=detector_version,
        evidence=evidence,
    )

    session.add(obs)
    session.flush()
    return obs


def get_observation_record(
    session: Session, observation_id: str
) -> Optional[Observation]:
    """Retrieve an observation and eagerly load all child hazards and assessments."""
    stmt = (
        select(Observation)
        .where(Observation.observation_id == observation_id)
        .options(
            selectinload(Observation.detected_hazards).selectinload(
                DetectedHazardRecord.assessments
            )
        )
    )
    return session.execute(stmt).scalar_one_or_none()


def list_observation_records(
    session: Session, limit: int = 20, offset: int = 0
) -> list[Observation]:
    """List observations ordered by observation timestamp with eager child loading."""
    stmt = (
        select(Observation)
        .order_by(Observation.observed_at.desc(), Observation.created_at.desc())
        .limit(limit)
        .offset(offset)
        .options(
            selectinload(Observation.detected_hazards).selectinload(
                DetectedHazardRecord.assessments
            )
        )
    )
    return list(session.execute(stmt).scalars().all())
