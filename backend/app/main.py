"""FastAPI entry point for the Milestone 1 Site Risk Agent."""

from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .models import NormalizedObservation
from .risk_agent import SiteRiskAgent


class ObservationRequest(BaseModel):
    """JSON representation of one normalized monitoring observation."""

    observation_id: str = Field(min_length=1)
    timestamp: datetime
    source: str = Field(min_length=1)
    labels: list[str] = Field(min_length=1)
    people_count: int = Field(default=1, ge=1)
    duration_minutes: int = Field(default=1, ge=1)
    repeated_count: int = Field(default=0, ge=0)
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


class AssessmentsResponse(BaseModel):
    """Response containing all supported hazards found in an observation."""

    observation_id: str
    assessments: list[AssessmentResponse]


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

    assessments = [
        AssessmentResponse.model_validate(assessment, from_attributes=True)
        for assessment in agent.assess(observation)
    ]
    return AssessmentsResponse(
        observation_id=request.observation_id,
        assessments=assessments,
    )
