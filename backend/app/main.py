"""FastAPI entry point for the Milestone 1 Site Risk Agent."""

from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .models import DetectedHazard, NormalizedObservation
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


app = FastAPI(
    title="Agentic Construction Risk Intelligence Platform",
    version="0.1.0",
)
agent = SiteRiskAgent()


@app.get("/health")
def health() -> dict[str, str]:
    """Return a simple liveness response."""

    return {"status": "ok"}


@app.post("/assessments", response_model=AssessmentsResponse)
def create_assessments(request: ObservationRequest) -> AssessmentsResponse:
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
    return AssessmentsResponse(
        observation_id=request.observation_id,
        detected_hazards=[
            DetectedHazardResponse.model_validate(hazard, from_attributes=True)
            for hazard in detected_hazards
        ],
        assessments=assessments,
        pending_hazards=pending_hazards,
    )
