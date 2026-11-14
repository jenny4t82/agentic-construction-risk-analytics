"""FastAPI entry point for the Milestone 1 Site Risk Agent."""

import email
import hashlib
import logging
import os
import tempfile
from dataclasses import replace
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .analytics import (
    SafetyAnalytics, WorkAreaRecurrenceAnalytics, get_finding_observation_page, get_safety_analytics,
    get_work_area_recurrence, validate_recurrence_window,
)
from .auth import (
    find_user_by_email, get_current_user, hash_password, issue_access_token,
    normalize_email, require_admin, require_safety_manager, verify_password,
)
from .database import get_db
from .detector import (
    BaseHazardDetector,
    MockHazardDetector,
    UnconfiguredHazardDetector,
    YOLOv8HazardDetector,
    normalize_detection_label,
)
from .decision_engine import evaluate_safety_decision
from .models import DetectedHazard, NormalizedObservation
from .db_models import Alert, DetectedHazardRecord, Observation, UserAccount
from .persistence import (
    AssessmentCompletionConflict,
    complete_pending_assessment,
    create_alert_for_hazard,
    get_alert_record,
    get_observation_record,
    list_alert_records,
    list_observation_records,
    persist_observation_bundle,
    update_alert_status,
)
from .utils.draw import draw_bounding_boxes
from .image_storage import get_observation_image_path, save_observation_images
from .risk_agent import LABEL_TO_HAZARD, SiteRiskAgent
from .reporting import available_work_areas, get_safety_report
from .report_pdf import render_safety_report_pdf
from .safety_agent import assess_safety, decide_alert, detect_objects, load_model
from .safety_graph import run_safety_graph
from .assessment_context import assessment_state, correct_assessment, find_assessment
from .assessment_queries import overall_risk_summary, query_observations, summarize
from .safety_cases import case_status, get_safety_case_alerts, group_safety_cases, list_safety_case_records


class ObservationRequest(BaseModel):
    """JSON representation of one normalized monitoring observation."""

    observation_id: str = Field(min_length=1)
    timestamp: datetime
    source: str = Field(min_length=1)
    labels: list[str] = Field(min_length=1)
    people_count: Optional[int] = Field(default=None, ge=1)
    duration_minutes: Optional[int] = Field(default=None, ge=1)
    repeated_count: Optional[int] = Field(default=None, ge=0)
    work_area: Optional[str] = None
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


class DecisionEvidenceResponse(BaseModel):
    hazard_type: str
    source_label: str
    detection_confidence: Optional[float]
    risk_score: Optional[int]
    risk_band: Optional[str]


class SafetyDecisionResponse(BaseModel):
    outcome: Literal["alert", "warning", "no_alert", "pending"]
    reason: str
    risk_band: Optional[str]
    priority: str
    supporting_evidence: list[DecisionEvidenceResponse]
    policy_version: str


class AssessmentsResponse(BaseModel):
    """Response separating detected hazards from completed assessments."""

    observation_id: str
    detected_hazards: list[DetectedHazardResponse]
    assessments: list[AssessmentResponse]
    pending_hazards: list[DetectedHazardResponse]
    safety_decision: SafetyDecisionResponse
    annotated_image: Optional[str] = None  # base64 PNG with YOLO boxes


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

    @computed_field
    @property
    def overall_risk_score(self) -> Optional[int]:
        return overall_risk_summary(self)["overall_risk_score"]

    @computed_field
    @property
    def overall_risk_band(self) -> Optional[str]:
        return overall_risk_summary(self)["overall_risk_band"]

    @computed_field
    @property
    def overall_risk_provisional(self) -> bool:
        return overall_risk_summary(self)["overall_risk_provisional"]

    @computed_field
    @property
    def overall_risk_status(self) -> str:
        return overall_risk_summary(self)["overall_risk_status"]

    @computed_field
    @property
    def completed_assessment_count(self) -> int:
        return overall_risk_summary(self)["completed_assessment_count"]

    @computed_field
    @property
    def pending_assessment_count(self) -> int:
        return overall_risk_summary(self)["pending_assessment_count"]

    @computed_field
    @property
    def incomplete_assessment_count(self) -> int:
        return overall_risk_summary(self)["incomplete_assessment_count"]

    @computed_field
    @property
    def total_assessed_findings(self) -> int:
        return overall_risk_summary(self)["total_assessed_findings"]


class WorkAreaUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    work_area: str = Field(min_length=1)

    @field_validator("work_area")
    @classmethod
    def normalize_work_area(cls, value: str) -> str:
        name = value.strip()
        if not name or name.casefold() in {"unknown", "unspecified", "unassigned work area"}:
            raise ValueError("A named work area is required")
        if len(name) > 255:
            raise ValueError("Work area must be at most 255 characters")
        return name


class AlertObservationSummary(BaseModel):
    observation_id: str
    observed_at: datetime
    source: str
    work_area: Optional[str] = None


class AlertViolationSummary(BaseModel):
    detected_hazard_id: int
    hazard_type: str
    source_label: str
    confidence: Optional[float] = None
    detected_at: datetime
    evidence: Optional[dict[str, Any]] = None


class AlertAssessmentSummary(BaseModel):
    assessment_id: int
    status: str
    risk_score: Optional[int] = None
    risk_band: Optional[str] = None


class AlertDetailResponse(BaseModel):
    review_required: bool = False
    reconciliation_reason: Optional[str] = None
    current_assessment: Optional[AlertAssessmentSummary] = None
    alert_id: int
    observation_id: str
    detected_hazard_id: Optional[int] = None
    assessment_id: Optional[int] = None
    alert_type: str
    message: str
    risk_band: Optional[str] = None
    decision_reason: Optional[str] = None
    notification_priority: Optional[str] = None
    decision_policy_version: Optional[str] = None
    status: str
    recipient: Optional[str] = None
    created_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    dismissed_at: Optional[datetime] = None
    observation: AlertObservationSummary
    violation: Optional[AlertViolationSummary] = None
    assessment: Optional[AlertAssessmentSummary] = None


class AlertStatusUpdateRequest(BaseModel):
    status: Literal["acknowledged", "resolved", "dismissed"]


class AlertCreateResponse(BaseModel):
    created: bool
    alert: AlertDetailResponse


SafetyCaseStatus = Literal["open", "acknowledged", "resolved", "dismissed", "mixed_closed"]


class SafetyCaseEvidence(BaseModel):
    original_available: bool
    annotated_available: bool


class SafetyCaseResponse(BaseModel):
    case_id: str
    observation_id: str
    observed_at: datetime
    work_area: Optional[str] = None
    evidence: SafetyCaseEvidence
    overall_risk_score: Optional[int] = None
    overall_risk_band: Optional[str] = None
    overall_risk_status: str
    overall_risk_provisional: bool
    case_status: SafetyCaseStatus
    alert_count: int
    alert_status_counts: dict[str, int]
    unresolved_alert_count: int
    review_required: bool
    alerts: list[AlertDetailResponse]
    findings: list[PersistedHazardResponse]
    assessment_corrections: list[dict[str, Any]]


class SafetyCaseListResponse(BaseModel):
    total_cases: int
    total_alerts: int
    limit: int
    offset: int
    items: list[SafetyCaseResponse]


class AssessmentCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    people_count: Optional[int] = Field(default=None, ge=1)
    duration_minutes: Optional[int] = Field(default=None, ge=1)
    repeated_count: Optional[int] = Field(default=None, ge=0)


class AssessmentCompletionResponse(BaseModel):
    assessment_id: int
    observation_id: str
    hazard_type: str
    source_label: str
    people_count: int
    duration_minutes: int
    repeated_count: int
    assessment: PersistedAssessmentResponse
    safety_decision: SafetyDecisionResponse
    alert_id: Optional[int] = None
    alert_ids: list[int]
    completion_audit: dict[str, Any]


class SignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=1024)


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    user_id: str
    email: str
    role: Literal["user", "safety_officer", "admin"]


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600


class RoleUpdateRequest(BaseModel):
    role: Literal["user", "safety_officer", "admin"]


class AnalyticsViolationMetric(BaseModel):
    violation_type: str
    count: int
    observation_ids: list[str]
    detected_hazard_ids: list[int]


class AnalyticsAreaMetric(BaseModel):
    work_area: str
    violation_count: int
    most_common_violation: Optional[AnalyticsViolationMetric] = None
    observation_ids: list[str]
    detected_hazard_ids: list[int]
    violation_metrics: list[AnalyticsViolationMetric]
    observation_count: int
    valid_latest_completed_assessment_count: int
    pending_latest_assessment_count: int
    incomplete_latest_assessment_count: int
    overall_observation_risk_distribution: dict[str, int]
    provisional_observation_count: int
    individual_alert_count: int
    alert_status_counts: dict[str, int]
    unresolved_individual_alert_count: int
    safety_case_count: int


class SafetyAnalyticsResponse(BaseModel):
    """Deterministic zone summary from persisted supported PPE violations."""

    total_violations: int
    violations_by_work_area: list[AnalyticsAreaMetric]
    highest_violation_area: Optional[AnalyticsAreaMetric] = None
    lowest_violation_area: Optional[AnalyticsAreaMetric] = None
    most_common_violation: Optional[AnalyticsViolationMetric] = None
    most_common_violation_by_area: list[AnalyticsAreaMetric]
    risk_level_distribution: dict[str, int]
    open_alert_count: int
    unresolved_alert_count: int
    resolved_alert_count: int
    unique_observation_count: int
    valid_latest_completed_assessment_count: int
    pending_latest_assessment_count: int
    incomplete_latest_assessment_count: int
    overall_observation_risk_distribution: dict[str, int]
    provisional_observation_count: int
    individual_alert_count: int
    alert_status_counts: dict[str, int]
    all_unresolved_alert_count: int
    safety_case_count: int
    scope: dict[str, Any]
    metric_units: dict[str, str]
    zone_identifier_source: str = "work_area"
    zone_identifier_is_validated_entity: bool = False
    zone_identifier_note: str = (
        "work_area is free text used as a temporary zone label; it is not a validated zone entity."
    )


class SupportingObservationEvidence(BaseModel):
    original_available: bool
    annotated_available: bool


class SupportingObservationResponse(ObservationDetailResponse):
    matching_detected_hazard_ids: list[int]
    evidence: SupportingObservationEvidence
    safety_case_id: Optional[str] = None


class SupportingObservationListResponse(BaseModel):
    total_observations: int
    total_matching_findings: int
    limit: int
    offset: int
    items: list[SupportingObservationResponse]


class WorkAreaRecurrenceGroupResponse(BaseModel):
    work_area: str
    hazard_type: str
    observation_count: int
    is_repeated: bool
    observation_ids: list[str]


class WorkAreaObservationMetricResponse(BaseModel):
    work_area: str
    observation_count: int
    observation_ids: list[str]


class WorkAreaRecurrenceResponse(BaseModel):
    """Informational recurrence of recorded PPE violations, not worker behavior."""

    window_start: Optional[datetime]
    window_end: Optional[datetime]
    groups: list[WorkAreaRecurrenceGroupResponse]
    work_areas_by_observation_count: list[WorkAreaObservationMetricResponse]
    repeated_work_area_count: int
    counting_unit: str = "distinct_observation_id"
    informational_only: bool = True
    work_area_note: str = (
        "Named work_area is trimmed free text, not a validated site or zone; "
        "blank and legacy unknown/unassigned placeholder values are excluded."
    )


class ExperimentalDetectionItem(BaseModel):
    """Raw model detection with bounding box coordinates and class info."""

    class_name: str
    confidence: float
    box: list[float]
    class_id: Optional[int] = None
    is_hazard: bool = False


class ExperimentalSafetyFinding(BaseModel):
    """Safety hazard finding derived from model detection."""

    hazard_type: str
    source_label: str
    confidence: Optional[float] = None


class ExperimentalRecommendation(BaseModel):
    """Safety recommendation proposed for a detected hazard."""

    hazard_type: str
    recommendation_text: str
    priority: str
    status: str = "proposed"


class ExperimentalAlertDecision(BaseModel):
    """Explainable alert proposal from the Safety Agent."""

    alert_recommended: bool
    reason: str
    priority: str


class ExperimentalSafetyDetectResponse(BaseModel):
    """Response from the experimental safety detection endpoint.

    Contains raw model detections with exact image coordinates, safety findings,
    recommendations, alert status, and indicates whether full risk scoring
    was performed or remains pending.
    """

    image_width: int
    image_height: int
    detections: list[ExperimentalDetectionItem]
    detected_hazards: list[ExperimentalSafetyFinding]
    assessments: list[AssessmentResponse] = []
    recommendations: list[ExperimentalRecommendation]
    alert: ExperimentalAlertDecision
    safety_decision: SafetyDecisionResponse
    routing_decision: str
    routing_status: str
    routing_reason: str
    is_risk_assessed: bool = False
    status_note: str


app = FastAPI(
    title="Agentic Construction Risk Intelligence Platform",
    version="0.1.0",
)


def _alert_response(alert: Alert) -> AlertDetailResponse:
    """Map one persisted alert and its lineage into the public API shape."""

    observation = alert.observation
    if observation is None:
        raise ValueError(f"Alert '{alert.alert_id}' has no source observation")

    violation = alert.detected_hazard
    assessment = alert.assessment
    current_assessment = max(violation.assessments, key=lambda item: item.assessment_version,
                             default=assessment) if violation is not None else assessment
    metadata = observation.raw_metadata or {}
    snapshot = metadata.get("alert_correction_snapshots", {}).get(str(alert.alert_id))
    reconciliation = metadata.get("assessment_reconciliation", {}).get(str(alert.assessment_id), {})
    finding_decision = (
        (violation.evidence or {}).get("finding_decision")
        if violation is not None and isinstance(violation.evidence, dict)
        else None
    )
    if not isinstance(finding_decision, dict):
        finding_decision = {}
    if snapshot:
        finding_decision = snapshot["decision"]
    return AlertDetailResponse(
        review_required=bool(snapshot) or reconciliation.get("review_required", False),
        reconciliation_reason=("Assessment corrected; historical alert retained for explicit review" if snapshot else reconciliation.get("reason")),
        current_assessment=AlertAssessmentSummary.model_validate(current_assessment, from_attributes=True) if current_assessment else None,
        alert_id=alert.alert_id,
        observation_id=alert.observation_id,
        detected_hazard_id=alert.detected_hazard_id,
        assessment_id=alert.assessment_id,
        alert_type=alert.alert_type,
        message=alert.message,
        risk_band=alert.risk_band,
        decision_reason=finding_decision.get("reason"),
        notification_priority=finding_decision.get("priority"),
        decision_policy_version=finding_decision.get("policy_version"),
        status=alert.status,
        recipient=alert.recipient,
        created_at=alert.created_at,
        acknowledged_at=alert.acknowledged_at,
        resolved_at=alert.resolved_at,
        dismissed_at=alert.dismissed_at,
        observation=AlertObservationSummary(
            observation_id=observation.observation_id,
            observed_at=observation.observed_at,
            source=observation.source,
            work_area=observation.work_area,
        ),
        violation=(
            AlertViolationSummary(
                detected_hazard_id=violation.detected_hazard_id,
                hazard_type=violation.hazard_type,
                source_label=violation.source_label,
                confidence=(
                    float(violation.detection_confidence)
                    if violation.detection_confidence is not None
                    else None
                ),
                detected_at=violation.detected_at,
                evidence=violation.evidence,
            )
            if violation is not None
            else None
        ),
        assessment=(
            AlertAssessmentSummary(**snapshot["assessment"]) if snapshot else AlertAssessmentSummary(
                assessment_id=assessment.assessment_id,
                status=assessment.status,
                risk_score=assessment.risk_score,
                risk_band=assessment.risk_band,
            )
            if assessment is not None
            else None
        ),
    )


def _safety_case_response(observation: Observation, alerts: list[Alert]) -> SafetyCaseResponse:
    """Build a virtual case without changing any alert or observation row."""
    detail = ObservationDetailResponse.model_validate(observation, from_attributes=True)
    evidence = _observation_evidence(observation)

    child_responses = [_alert_response(alert) for alert in alerts]
    corrections = (observation.raw_metadata or {}).get("assessment_corrections", [])
    return SafetyCaseResponse(
        case_id=f"observation:{observation.observation_id}",
        observation_id=observation.observation_id,
        observed_at=observation.observed_at,
        work_area=observation.work_area,
        evidence=SafetyCaseEvidence(**evidence),
        overall_risk_score=detail.overall_risk_score,
        overall_risk_band=detail.overall_risk_band,
        overall_risk_status=detail.overall_risk_status,
        overall_risk_provisional=detail.overall_risk_provisional,
        case_status=case_status(alerts),
        alert_count=len(alerts),
        alert_status_counts={
            state: sum(alert.status == state for alert in alerts)
            for state in ("open", "acknowledged", "resolved", "dismissed")
        },
        unresolved_alert_count=sum(alert.status in {"open", "acknowledged"} for alert in alerts),
        review_required=any(alert.review_required for alert in child_responses),
        alerts=child_responses,
        findings=detail.detected_hazards,
        assessment_corrections=corrections if isinstance(corrections, list) else [],
    )


def _observation_evidence(observation: Observation) -> dict[str, bool]:
    image_metadata = (observation.raw_metadata or {}).get("image")
    evidence = {}
    for variant in ("original", "annotated"):
        try:
            get_observation_image_path(observation.observation_id, variant, image_metadata)
            available = True
        except (FileNotFoundError, ValueError):
            available = False
        evidence[f"{variant}_available"] = available
    return evidence


def _analytics_metric_response(metric: Any) -> AnalyticsViolationMetric:
    return AnalyticsViolationMetric(
        violation_type=metric.violation_type,
        count=metric.count,
        observation_ids=list(metric.observation_ids),
        detected_hazard_ids=list(metric.detected_hazard_ids),
    )


def _analytics_area_response(metric: Any) -> AnalyticsAreaMetric:
    return AnalyticsAreaMetric(
        work_area=metric.work_area,
        violation_count=metric.violation_count,
        most_common_violation=(
            _analytics_metric_response(metric.most_common_violation)
            if metric.most_common_violation is not None
            else None
        ),
        observation_ids=list(metric.observation_ids),
        detected_hazard_ids=list(metric.detected_hazard_ids),
        violation_metrics=[_analytics_metric_response(item) for item in metric.violation_metrics],
        observation_count=metric.observation_count,
        valid_latest_completed_assessment_count=metric.valid_latest_completed_assessment_count,
        pending_latest_assessment_count=metric.pending_latest_assessment_count,
        incomplete_latest_assessment_count=metric.incomplete_latest_assessment_count,
        overall_observation_risk_distribution=metric.overall_observation_risk_distribution,
        provisional_observation_count=metric.provisional_observation_count,
        individual_alert_count=metric.individual_alert_count,
        alert_status_counts=metric.alert_status_counts,
        unresolved_individual_alert_count=metric.unresolved_individual_alert_count,
        safety_case_count=metric.safety_case_count,
    )


def _safety_analytics_response(analytics: SafetyAnalytics, *, start: datetime | None = None, end: datetime | None = None) -> SafetyAnalyticsResponse:
    return SafetyAnalyticsResponse(
        total_violations=analytics.total_violations,
        violations_by_work_area=[
            _analytics_area_response(metric)
            for metric in analytics.violations_by_work_area
        ],
        highest_violation_area=(
            _analytics_area_response(analytics.highest_violation_area)
            if analytics.highest_violation_area is not None
            else None
        ),
        lowest_violation_area=(
            _analytics_area_response(analytics.lowest_violation_area)
            if analytics.lowest_violation_area is not None
            else None
        ),
        most_common_violation=(
            _analytics_metric_response(analytics.most_common_violation)
            if analytics.most_common_violation is not None
            else None
        ),
        most_common_violation_by_area=[
            _analytics_area_response(metric)
            for metric in analytics.most_common_violation_by_area
        ],
        risk_level_distribution=analytics.risk_level_distribution,
        open_alert_count=analytics.open_alert_count,
        unresolved_alert_count=analytics.unresolved_alert_count,
        resolved_alert_count=analytics.resolved_alert_count,
        unique_observation_count=analytics.unique_observation_count,
        valid_latest_completed_assessment_count=analytics.valid_latest_completed_assessment_count,
        pending_latest_assessment_count=analytics.pending_latest_assessment_count,
        incomplete_latest_assessment_count=analytics.incomplete_latest_assessment_count,
        overall_observation_risk_distribution=analytics.overall_observation_risk_distribution,
        provisional_observation_count=analytics.provisional_observation_count,
        individual_alert_count=analytics.individual_alert_count,
        alert_status_counts=analytics.alert_status_counts,
        all_unresolved_alert_count=analytics.all_unresolved_alert_count,
        safety_case_count=analytics.safety_case_count,
        scope={"start": start, "end": end, "interval": "[start,end)"},
        metric_units={
            "observations": "distinct observation_id with at least one supported detected hazard",
            "detected_hazards": "supported detected_hazard_id",
            "latest_assessments": "one effective assessment per supported detected_hazard_id",
            "alerts": "individual alert_id on observations with at least one supported finding",
            "safety_cases": "distinct observation_id with at least one persisted alert",
            "risk_level_distribution": "supported detected-hazard rows using latest stored completed band (legacy)",
            "overall_observation_risk_distribution": "distinct observation_id classified by Phase 8.1D maximum valid latest score",
        },
    )


def _recurrence_response(analytics: WorkAreaRecurrenceAnalytics) -> WorkAreaRecurrenceResponse:
    return WorkAreaRecurrenceResponse(
        window_start=analytics.window_start,
        window_end=analytics.window_end,
        groups=[
            WorkAreaRecurrenceGroupResponse(
                work_area=group.work_area,
                hazard_type=group.hazard_type,
                observation_count=group.observation_count,
                is_repeated=group.is_repeated,
                observation_ids=list(group.observation_ids),
            )
            for group in analytics.groups
        ],
        work_areas_by_observation_count=[
            WorkAreaObservationMetricResponse(
                work_area=area.work_area,
                observation_count=area.observation_count,
                observation_ids=list(area.observation_ids),
            )
            for area in analytics.work_areas_by_observation_count
        ],
        repeated_work_area_count=analytics.repeated_work_area_count,
    )


agent = SiteRiskAgent()
logger = logging.getLogger(__name__)


@app.get("/health")
def health() -> dict[str, str]:
    """Return a simple liveness response."""

    return {"status": "ok"}


@app.post("/auth/signup", response_model=UserResponse, status_code=201)
def signup(request: SignupRequest, db: Optional[Session] = Depends(get_db)) -> UserResponse:
    """Create a regular user; role elevation is never accepted at signup."""

    if db is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    try:
        email = normalize_email(request.email)
        if find_user_by_email(db, email) is not None:
            raise HTTPException(status_code=409, detail="Account already exists")
        account = UserAccount(email=email, password_hash=hash_password(request.password), role="user", is_active=True)
        db.add(account)
        db.flush()
        return UserResponse(user_id=account.user_id, email=account.email, role=account.role)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except IntegrityError as error:
        raise HTTPException(status_code=409, detail="Account already exists") from error
    except SQLAlchemyError as error:
        raise HTTPException(status_code=500, detail="Account creation failed") from error


@app.post("/auth/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Optional[Session] = Depends(get_db)) -> TokenResponse:
    if db is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    try:
        email = normalize_email(request.email)
    except ValueError:
        email = ""
    account = find_user_by_email(db, email) if email else None
    if account is None or not account.is_active or not verify_password(request.password, account.password_hash):
        raise HTTPException(
            status_code=401, detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=issue_access_token(account.user_id))


@app.get("/auth/me", response_model=UserResponse)
def get_me(user: UserAccount = Depends(get_current_user)) -> UserResponse:
    return UserResponse(user_id=user.user_id, email=user.email, role=user.role)


@app.patch("/auth/users/{user_id}/role", response_model=UserResponse)
def set_user_role(
    user_id: str,
    request: RoleUpdateRequest,
    db: Optional[Session] = Depends(get_db),
    _: UserAccount = Depends(require_admin),
) -> UserResponse:
    """An Admin may assign a persisted account's application role."""

    if db is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    user = db.get(UserAccount, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = request.role
    db.flush()
    return UserResponse(user_id=user.user_id, email=user.email, role=user.role)


@app.get("/analytics/zones", response_model=SafetyAnalyticsResponse, dependencies=[Depends(get_current_user)])
def get_zone_analytics(
    start: Optional[datetime] = Query(default=None),
    end: Optional[datetime] = Query(default=None),
    db: Optional[Session] = Depends(get_db),
) -> SafetyAnalyticsResponse:
    """Return zone-level safety analytics from persisted violation records.

    The current schema has no zone entity. ``work_area`` is used as a
    temporary, free-text zone identifier and is not validated or canonicalized.
    """

    try:
        start, end = validate_recurrence_window(start, end)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if db is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    try:
        return _safety_analytics_response(get_safety_analytics(db, start=start, end=end), start=start, end=end)
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=500, detail="Failed to calculate zone analytics"
        ) from error


@app.get("/analytics/finding-observations", response_model=SupportingObservationListResponse,
         dependencies=[Depends(get_current_user)])
def get_finding_observations(
    work_area: Optional[str] = Query(default=None, min_length=1),
    hazard_type: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    area_mode: Literal["zone", "recurrence"] = "zone",
    sort: Literal["newest", "oldest"] = "newest",
    limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
    db: Optional[Session] = Depends(get_db),
) -> SupportingObservationListResponse:
    if hazard_type is not None and hazard_type not in set(LABEL_TO_HAZARD.values()):
        raise HTTPException(status_code=422, detail="Unsupported PPE hazard category")
    try:
        start, end = validate_recurrence_window(start, end)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if db is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    try:
        result = get_finding_observation_page(db, work_area=work_area, hazard_type=hazard_type,
            start=start, end=end, area_mode=area_mode, sort=sort, limit=limit, offset=offset)
        items = []
        for observation, hazard_ids in result["items"]:
            detail = ObservationDetailResponse.model_validate(observation, from_attributes=True).model_dump()
            items.append(SupportingObservationResponse(
                **detail, matching_detected_hazard_ids=hazard_ids,
                evidence=SupportingObservationEvidence(**_observation_evidence(observation)),
                safety_case_id=f"observation:{observation.observation_id}" if observation.alerts else None,
            ))
        return SupportingObservationListResponse(**{**result, "items": items})
    except SQLAlchemyError as error:
        raise HTTPException(status_code=500, detail="Failed to query supporting observations") from error


@app.get(
    "/analytics/work-area-recurrence",
    response_model=WorkAreaRecurrenceResponse,
    dependencies=[Depends(get_current_user)],
)
def get_recurrence_analytics(
    start: Optional[datetime] = Query(default=None),
    end: Optional[datetime] = Query(default=None),
    db: Optional[Session] = Depends(get_db),
) -> WorkAreaRecurrenceResponse:
    """Report distinct recorded PPE-violation observations by named work area."""
    try:
        start, end = validate_recurrence_window(start, end)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if db is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    try:
        return _recurrence_response(get_work_area_recurrence(db, start=start, end=end))
    except SQLAlchemyError as error:
        raise HTTPException(status_code=500, detail="Failed to calculate work-area recurrence") from error


@app.get("/reports/work-areas", dependencies=[Depends(get_current_user)])
def get_report_work_areas(db: Optional[Session] = Depends(get_db)) -> dict[str, list[str]]:
    if db is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    try:
        return {"work_areas": available_work_areas(db)}
    except SQLAlchemyError as error:
        raise HTTPException(status_code=500, detail="Failed to load report work areas") from error


def _report_payload(
    *, db: Optional[Session], user: UserAccount, start: datetime | None,
    end: datetime | None, scope: str, work_area: list[str] | None,
    include_unassigned: bool,
) -> dict[str, Any]:
    if db is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    try:
        return get_safety_report(
            db, start=start, end=end, scope=scope, work_areas=work_area or (),
            include_unassigned=include_unassigned,
            generated_by={"email": user.email, "role": user.role},
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except SQLAlchemyError as error:
        raise HTTPException(status_code=500, detail="Failed to generate safety report") from error


@app.get("/reports/safety")
def get_report(
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    scope: Literal["all", "selected"] = Query(default="all"),
    work_area: list[str] | None = Query(default=None),
    include_unassigned: bool = Query(default=False),
    db: Optional[Session] = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
) -> dict[str, Any]:
    return _report_payload(
        db=db, user=user, start=start, end=end, scope=scope,
        work_area=work_area, include_unassigned=include_unassigned,
    )


@app.get("/reports/safety.pdf")
def download_report(
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    scope: Literal["all", "selected"] = Query(default="all"),
    work_area: list[str] | None = Query(default=None),
    include_unassigned: bool = Query(default=False),
    db: Optional[Session] = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
) -> Response:
    report = _report_payload(
        db=db, user=user, start=start, end=end, scope=scope,
        work_area=work_area, include_unassigned=include_unassigned,
    )
    filename = f"SafeSite_Safety_Report_{report['generated_at']:%Y-%m-%d_%H%M}.pdf"
    return Response(
        content=render_safety_report_pdf(report), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/safety-cases", response_model=SafetyCaseListResponse, dependencies=[Depends(get_current_user)])
def get_safety_cases(
    work_area: Optional[str] = None,
    status: Optional[SafetyCaseStatus] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    search: Optional[str] = Query(default=None, min_length=1, max_length=255),
    sort: Literal["newest", "oldest"] = "newest",
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Optional[Session] = Depends(get_db),
) -> SafetyCaseListResponse:
    """List observation-derived alert cases; counts distinguish cases/alerts."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    for value in (start, end):
        if value is not None and value.utcoffset() is None:
            raise HTTPException(status_code=422, detail="Date filters require a timezone")
    if start is not None and end is not None and start >= end:
        raise HTTPException(status_code=422, detail="start must precede end")
    if search is not None and not search.strip():
        raise HTTPException(status_code=422, detail="search must contain an observation or case ID")
    try:
        alerts = list_safety_case_records(db)
        cases = group_safety_cases(alerts, work_area=work_area, status=status,
            start=start, end=end, search=search, sort=sort)
        page = cases[offset:offset + limit]
        return SafetyCaseListResponse(
            total_cases=len(cases),
            total_alerts=sum(len(case.alerts) for case in cases),
            limit=limit,
            offset=offset,
            items=[_safety_case_response(case.observation, list(case.alerts)) for case in page],
        )
    except SQLAlchemyError as error:
        raise HTTPException(status_code=500, detail="Failed to query safety cases") from error


@app.get("/safety-cases/{observation_id}", response_model=SafetyCaseResponse,
         dependencies=[Depends(get_current_user)])
def get_safety_case(observation_id: str, db: Optional[Session] = Depends(get_db)) -> SafetyCaseResponse:
    """Return a complete observation case, including every child alert."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    try:
        alerts = get_safety_case_alerts(db, observation_id)
        if not alerts:
            raise HTTPException(status_code=404, detail="Safety case not found")
        return _safety_case_response(alerts[0].observation, alerts)
    except SQLAlchemyError as error:
        raise HTTPException(status_code=500, detail="Failed to query safety case") from error


@app.get("/alerts", response_model=list[AlertDetailResponse], dependencies=[Depends(get_current_user)])
def get_alerts(
    status: Optional[Literal["open", "acknowledged", "resolved", "dismissed"]] = Query(
        default=None
    ),
    observation_id: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Optional[Session] = Depends(get_db),
) -> list[AlertDetailResponse]:
    """Return persisted alert history with source observation and evidence."""

    if db is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    try:
        return [
            _alert_response(alert)
            for alert in list_alert_records(
                db,
                limit=limit,
                offset=offset,
                status=status,
                observation_id=observation_id,
            )
        ]
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=500, detail="Failed to query alerts from database"
        ) from error


@app.get("/alerts/{alert_id}", response_model=AlertDetailResponse, dependencies=[Depends(get_current_user)])
def get_alert(alert_id: int, db: Optional[Session] = Depends(get_db)) -> AlertDetailResponse:
    """Return one persisted alert with its observation, violation, and assessment."""

    if db is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    try:
        alert = get_alert_record(db, alert_id)
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=500, detail="Failed to query alert from database"
        ) from error
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return _alert_response(alert)


@app.post(
    "/alerts/hazards/{detected_hazard_id}",
    response_model=AlertCreateResponse,
    status_code=201,
    dependencies=[Depends(require_safety_manager)],
)
def create_alert(
    detected_hazard_id: int, db: Optional[Session] = Depends(get_db)
) -> AlertCreateResponse:
    """Create the idempotent alert for one persisted supported PPE violation."""

    if db is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    try:
        alert, created = create_alert_for_hazard(db, detected_hazard_id)
        if alert.observation is None:
            alert = get_alert_record(db, alert.alert_id) or alert
        return AlertCreateResponse(created=created, alert=_alert_response(alert))
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except SQLAlchemyError as error:
        raise HTTPException(status_code=500, detail="Alert persistence failed") from error


@app.patch("/alerts/{alert_id}/status", response_model=AlertDetailResponse, dependencies=[Depends(require_safety_manager)])
def change_alert_status(
    alert_id: int,
    request: AlertStatusUpdateRequest,
    db: Optional[Session] = Depends(get_db),
) -> AlertDetailResponse:
    """Advance an alert through its forward-only review lifecycle."""

    if db is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    try:
        update_alert_status(db, alert_id, request.status)
        alert = get_alert_record(db, alert_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except SQLAlchemyError as error:
        raise HTTPException(status_code=500, detail="Alert update failed") from error
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return _alert_response(alert)


@app.patch("/assessments/{assessment_id}/complete", response_model=AssessmentCompletionResponse)
def complete_assessment(
    assessment_id: int,
    request: AssessmentCompletionRequest,
    actor: UserAccount = Depends(require_safety_manager),
    db: Optional[Session] = Depends(get_db),
) -> AssessmentCompletionResponse:
    """Finish one persisted pending finding without re-uploading its evidence."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    try:
        observation, hazard, assessment, decision = complete_pending_assessment(
            db,
            assessment_id,
            completed_by_user_id=actor.user_id,
            people_count=request.people_count,
            duration_minutes=request.duration_minutes,
            repeated_count=request.repeated_count,
        )
        alert_ids = list(db.execute(
            select(Alert.alert_id)
            .where(Alert.observation_id == observation.observation_id)
            .order_by(Alert.alert_id)
        ).scalars().all())
        linked_alert_id = db.execute(
            select(Alert.alert_id)
            .where(Alert.detected_hazard_id == hazard.detected_hazard_id)
            .order_by(Alert.alert_id)
        ).scalars().first()
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except AssessmentCompletionConflict as error:
        raise HTTPException(
            status_code=409, detail={"code": error.code, "message": str(error)}
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except SQLAlchemyError as error:
        raise HTTPException(status_code=500, detail="Assessment completion failed") from error

    audit = observation.raw_metadata["assessment_completions"][str(assessment_id)]
    return AssessmentCompletionResponse(
        assessment_id=assessment.assessment_id,
        observation_id=observation.observation_id,
        hazard_type=hazard.hazard_type,
        source_label=hazard.source_label,
        people_count=observation.people_count,
        duration_minutes=observation.duration_minutes,
        repeated_count=observation.repeated_count,
        assessment=PersistedAssessmentResponse.model_validate(assessment, from_attributes=True),
        safety_decision=SafetyDecisionResponse.model_validate(decision, from_attributes=True),
        alert_id=linked_alert_id,
        alert_ids=alert_ids,
        completion_audit=audit,
    )


@app.post("/assessments", response_model=AssessmentsResponse, dependencies=[Depends(get_current_user)])
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
                "Database persistence failed for observation %s (%s)",
                request.observation_id,
                type(err).__name__,
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
        safety_decision=SafetyDecisionResponse.model_validate(
            evaluate_safety_decision(detected_hazards, assessments, detection_complete=True),
            from_attributes=True,
        ),
    )


MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB limit
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WEIGHTS_PATH = PROJECT_ROOT / "weights" / "best.pt"


def get_hazard_detector() -> BaseHazardDetector:
    """Dependency provider for hazard detector implementation.

    In explicit mock mode (HAZARD_DETECTOR_MODE=mock), returns MockHazardDetector.
    If model weights are provided via HAZARD_DETECTOR_WEIGHTS, returns YOLOv8HazardDetector.
    Relative weights paths are resolved from the repository root. When the
    variable is unset, the repository's local weights/best.pt is used when it
    exists. In unconfigured environments, returns UnconfiguredHazardDetector.
    In unconfigured environments, returns UnconfiguredHazardDetector which safely raises
    an error upon invocation rather than returning false zero-hazard compliance results.
    Can be overridden in tests via FastAPI's app.dependency_overrides.
    """
    mode = os.getenv("HAZARD_DETECTOR_MODE", "").strip().lower()
    if mode == "mock":
        return MockHazardDetector()

    weights_path = os.getenv("HAZARD_DETECTOR_WEIGHTS", "").strip()
    if weights_path:
        configured_path = Path(weights_path)
        if not configured_path.is_absolute():
            configured_path = PROJECT_ROOT / configured_path
        return _get_yolo_detector(str(configured_path))

    if DEFAULT_WEIGHTS_PATH.is_file():
        return _get_yolo_detector(str(DEFAULT_WEIGHTS_PATH))

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


def _serialized_detections(boxes: Any) -> list[dict[str, Any]]:
    """Keep source boxes available for observation and hazard evidence."""
    return [
        {
            "class_name": box.class_name,
            "confidence": box.confidence,
            "x_min": box.x_min,
            "y_min": box.y_min,
            "x_max": box.x_max,
            "y_max": box.y_max,
            "class_id": box.class_id,
        }
        for box in boxes
    ]


def _hazard_confidences(boxes: Any) -> dict[str, float]:
    """Use only boxes mapping to each supported canonical hazard."""
    confidences: dict[str, float] = {}
    for box in boxes:
        label = normalize_detection_label(box.class_name)
        hazard_type = LABEL_TO_HAZARD.get(label) if label is not None else None
        if hazard_type is not None:
            confidences[hazard_type] = max(
                confidences.get(hazard_type, box.confidence), box.confidence
            )
    return confidences


def _build_image_metadata(
    observation_id: str,
    image_bytes: bytes,
    image_media_type: str,
    annotated_image: Optional[str],
    boxes: Any,
) -> dict[str, Any]:
    """Persist image files and detection geometry in safe observation metadata."""

    metadata = save_observation_images(
        observation_id=observation_id,
        original_bytes=image_bytes,
        original_media_type=image_media_type,
        annotated_image_base64=annotated_image,
    )
    metadata["detections"] = _serialized_detections(boxes)
    return {"image": metadata}


def _image_submission_conflict(
    existing: Observation, fingerprint: str, submission_context: dict[str, Any]
) -> HTTPException:
    """Classify a retry only when the ID, original bytes, and inputs match."""
    metadata = existing.raw_metadata or {}
    image = metadata.get("image")
    if (
        isinstance(image, dict)
        and image.get("sha256") == fingerprint
        and metadata.get("image_submission") == submission_context
    ):
        return HTTPException(
            status_code=409,
            detail={
                "code": "duplicate_image_submission",
                "observation_id": existing.observation_id,
                "message": "This exact image submission already exists.",
            },
        )
    return HTTPException(
        status_code=409,
        detail=f"Observation '{existing.observation_id}' already exists",
    )


@app.post("/assessments/image", response_model=AssessmentsResponse, dependencies=[Depends(get_current_user)])
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

    image_media_type = _validate_image_bytes(image_bytes)

    # Normalize observation ID: empty or whitespace-only inputs consistently generate a UUID
    raw_obs_id = (
        (observation_id.strip() if observation_id else "")
        or (form_fields.get("observation_id", "").strip())
    )
    resolved_obs_id = raw_obs_id if raw_obs_id else f"img-obs-{uuid4().hex[:8]}"

    resolved_work_area = (
        (work_area.strip() if work_area else "")
        or (form_fields.get("work_area", "").strip())
        or None
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

    # observation_id is the only stable submission identity in the current model.
    # A generated ID represents a new submission, even when its bytes match.
    fingerprint = hashlib.sha256(image_bytes).hexdigest()
    submission_context = {
        "work_area": resolved_work_area,
        "people_count_override": _parse_int_param(str(raw_pc), "people_count", 1)
        if raw_pc is not None else None,
        "duration_minutes": resolved_duration,
        "repeated_count": resolved_repeated,
    }
    if db is not None:
        try:
            existing = db.get(Observation, resolved_obs_id)
        except SQLAlchemyError as err:
            logger.error("Duplicate lookup failed for image observation %s (%s)", resolved_obs_id, type(err).__name__)
            raise HTTPException(status_code=500, detail="Database lookup failed") from err
        if existing is not None:
            raise _image_submission_conflict(existing, fingerprint, submission_context)

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

    annotated_image = draw_bounding_boxes(image_bytes, detection.boxes)
    timestamp = datetime.now(timezone.utc)
    source = f"image_upload:{request.headers.get('x-filename', 'site_image')}"
    detected_hazards = []
    assessments = []
    pending_hazards = []
    if detection.hazard_labels:
        try:
            observation = NormalizedObservation(
                observation_id=resolved_obs_id,
                timestamp=timestamp,
                source=source,
                labels=tuple(detection.hazard_labels),
                people_count=resolved_people_count,
                duration_minutes=resolved_duration,
                repeated_count=resolved_repeated,
                work_area=resolved_work_area,
                detection_confidence=detection.max_confidence,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        confidences_by_hazard = _hazard_confidences(detection.boxes)
        detected_hazards = [
            replace(hazard, detection_confidence=confidences_by_hazard.get(hazard.hazard_type))
            for hazard in agent.detect_hazards(observation)
        ]
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
            # Flush the PK and child rows before touching files. A concurrent
            # request for this ID loses at the database constraint and cannot
            # overwrite the winning observation's original/annotated images.
            record = persist_observation_bundle(
                session=db,
                observation_id=resolved_obs_id,
                timestamp=timestamp,
                source=source,
                work_area=resolved_work_area,
                people_count=resolved_people_count,
                duration_minutes=resolved_duration,
                repeated_count=resolved_repeated,
                detection_confidence=detection.max_confidence,
                detected_hazards=detected_hazards,
                assessments=assessments,
                detector_name=type(detector).__name__,
                raw_metadata={
                    "image": {
                        "sha256": fingerprint,
                        "detections": _serialized_detections(detection.boxes),
                    },
                    "image_submission": submission_context,
                },
            )
        except ValueError as err:
            existing = db.get(Observation, resolved_obs_id)
            if existing is not None:
                raise _image_submission_conflict(existing, fingerprint, submission_context) from err
            raise HTTPException(status_code=409, detail=str(err)) from err
        except IntegrityError as err:
            db.rollback()
            existing = db.get(Observation, resolved_obs_id)
            if existing is not None:
                raise _image_submission_conflict(existing, fingerprint, submission_context) from err
            logger.error("Image observation integrity failure for %s (%s)", resolved_obs_id, type(err).__name__)
            raise HTTPException(status_code=500, detail="Database persistence failed") from err
        except SQLAlchemyError as err:
            logger.error("Database persistence failed for image observation %s (%s)", resolved_obs_id, type(err).__name__)
            raise HTTPException(status_code=500, detail="Database persistence failed") from err

        try:
            image_metadata = _build_image_metadata(
                observation_id=resolved_obs_id,
                image_bytes=image_bytes,
                image_media_type=image_media_type,
                annotated_image=annotated_image,
                boxes=detection.boxes,
            )
        except (OSError, ValueError) as err:
            logger.error("Failed to persist image for observation %s: %s", resolved_obs_id, err)
            raise HTTPException(status_code=500, detail="Image persistence failed") from err
        record.raw_metadata = {
            **record.raw_metadata,
            "image": {**image_metadata["image"], "sha256": fingerprint},
        }
        try:
            db.flush()
        except SQLAlchemyError as err:
            logger.error(
                "Database persistence failed for image observation %s (%s)",
                resolved_obs_id,
                type(err).__name__,
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
        safety_decision=SafetyDecisionResponse.model_validate(
            evaluate_safety_decision(detected_hazards, assessments, detection_complete=True),
            from_attributes=True,
        ),
        annotated_image=annotated_image,
    )


class AssessmentContextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0, strict=True)
    people_count: int = Field(ge=1, strict=True)
    duration_minutes: int = Field(ge=1, strict=True)
    repeated_count: int = Field(ge=0, strict=True)


class AssessmentContextResponse(BaseModel):
    observation_id: str
    detected_hazard_id: int
    assessment_id: int
    revision: int
    context: dict[str, Optional[int]]
    assessment: PersistedAssessmentResponse
    safety_decision: SafetyDecisionResponse
    audit_history: list[dict[str, Any]]
    reconciliation: dict[str, Any]


class ObservationQueryItem(ObservationDetailResponse):
    assessment_counts: dict[str, int]


class ObservationQueryResponse(BaseModel):
    items: list[ObservationQueryItem]
    total: int
    limit: int
    offset: int
    assessment_counts: dict[str, int]
    observation_counts: dict[str, int]
    unfiltered_risk_total: int


@app.get("/assessments/{assessment_id}", response_model=AssessmentContextResponse, dependencies=[Depends(get_current_user)])
def get_assessment_context(assessment_id: int, db: Optional[Session] = Depends(get_db)):
    if db is None:
        raise HTTPException(503, "Database is not configured")
    try:
        return assessment_state(*find_assessment(db, assessment_id))
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except SQLAlchemyError as error:
        raise HTTPException(500, "Failed to query assessment") from error


@app.patch("/assessments/{assessment_id}/context", response_model=AssessmentContextResponse)
def update_assessment_context(assessment_id: int, request: AssessmentContextRequest,
                              actor: UserAccount = Depends(require_safety_manager),
                              db: Optional[Session] = Depends(get_db)):
    if db is None:
        raise HTTPException(503, "Database is not configured")
    try:
        result = correct_assessment(db, assessment_id, expected_revision=request.expected_revision,
            actor_id=actor.user_id, values=request.model_dump(exclude={"expected_revision"}))
        response = AssessmentContextResponse.model_validate(result)
        db.commit()
        return response
    except LookupError as error:
        db.rollback()
        raise HTTPException(404, str(error)) from error
    except AssessmentCompletionConflict as error:
        db.rollback()
        raise HTTPException(409, {"code": error.code, "message": str(error)}) from error
    except ValueError as error:
        db.rollback()
        raise HTTPException(422, str(error)) from error
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(500, "Assessment correction failed") from error


@app.get("/observation-query", response_model=ObservationQueryResponse, dependencies=[Depends(get_current_user)])
def search_observations(
    risk: Literal["All", "Pending", "Low", "Moderate", "High", "Critical"] = "All",
    work_area: Optional[str] = None, start: Optional[datetime] = None,
    end: Optional[datetime] = None, observation_id: Optional[str] = None,
    sort: Literal["newest", "oldest"] = "newest",
    limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
    db: Optional[Session] = Depends(get_db),
):
    for value in (start, end):
        if value is not None and value.utcoffset() is None:
            raise HTTPException(422, "Date filters require a timezone")
    if start is not None and end is not None and start >= end:
        raise HTTPException(422, "start must precede end")
    if db is None:
        raise HTTPException(503, "Database is not configured")
    try:
        result = query_observations(db, risk=risk, work_area=work_area, start=start,
            end=end, observation_id=observation_id, sort=sort, limit=limit, offset=offset)
        result["items"] = [ObservationQueryItem(
            **ObservationDetailResponse.model_validate(item).model_dump(),
            assessment_counts=summarize(item)) for item in result["items"]]
        return result
    except SQLAlchemyError as error:
        raise HTTPException(500, "Failed to query observations") from error


@app.get("/observations", response_model=list[ObservationDetailResponse], dependencies=[Depends(get_current_user)])
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
        logger.error("Failed to query observations from database (%s)", type(err).__name__)
        raise HTTPException(
            status_code=500, detail="Failed to query observations from database"
        ) from err


@app.get("/observations/{observation_id}", response_model=ObservationDetailResponse, dependencies=[Depends(get_current_user)])
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
            "Failed to query observation %s from database (%s)",
            observation_id,
            type(err).__name__,
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


@app.patch("/observations/{observation_id}/work-area", response_model=ObservationDetailResponse)
def update_observation_work_area(
    observation_id: str,
    request: WorkAreaUpdateRequest,
    db: Optional[Session] = Depends(get_db),
    user: UserAccount = Depends(require_safety_manager),
) -> ObservationDetailResponse:
    """Correct only the operator-entered area; preserve assessment and alert history."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    try:
        record = db.execute(
            select(Observation).where(Observation.observation_id == observation_id).with_for_update()
        ).scalar_one_or_none()
        if record is None:
            raise HTTPException(status_code=404, detail=f"Observation '{observation_id}' not found")
        if record.work_area != request.work_area:
            now = datetime.now(timezone.utc)
            metadata = dict(record.raw_metadata or {})
            previous_changes = metadata.get("work_area_changes")
            changes = list(previous_changes) if isinstance(previous_changes, list) else []
            changes.append({
                "previous_work_area": record.work_area,
                "new_work_area": request.work_area,
                "changed_by_user_id": user.user_id,
                "changed_by_email": user.email,
                "changed_at": now.isoformat(),
            })
            metadata["work_area_changes"] = changes
            record.work_area = request.work_area
            record.raw_metadata = metadata
            record.updated_at = now
            db.commit()
        refreshed = get_observation_record(db, observation_id=observation_id)
        return ObservationDetailResponse.model_validate(refreshed, from_attributes=True)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update work area") from error


@app.get("/observations/{observation_id}/image/{variant}", dependencies=[Depends(get_current_user)])
def get_observation_image(
    observation_id: str,
    variant: str,
    db: Optional[Session] = Depends(get_db),
) -> FileResponse:
    """Return a retained original or annotated image for one observation."""

    if db is None:
        raise HTTPException(
            status_code=503,
            detail="Database persistence is not configured. Set DATABASE_URL to enable persistence.",
        )
    try:
        record = get_observation_record(db, observation_id=observation_id)
    except SQLAlchemyError as err:
        logger.error("Failed to query image metadata for observation %s (%s)", observation_id, type(err).__name__)
        raise HTTPException(
            status_code=500, detail="Failed to query observation from database"
        ) from err

    if record is None:
        raise HTTPException(status_code=404, detail="Observation not found")

    metadata = (record.raw_metadata or {}).get("image")
    try:
        image_path, media_type = get_observation_image_path(
            observation_id=observation_id,
            variant=variant,
            image_metadata=metadata,
        )
    except (FileNotFoundError, ValueError) as err:
        raise HTTPException(
            status_code=404,
            detail="Image unavailable for this observation",
        ) from err

    return FileResponse(path=image_path, media_type=media_type)


@app.post(
    "/experimental/safety/detect",
    response_model=ExperimentalSafetyDetectResponse,
    dependencies=[Depends(get_current_user)],
)
@app.post(
    "/experimental/detect-safety",
    response_model=ExperimentalSafetyDetectResponse,
    include_in_schema=False,
    dependencies=[Depends(get_current_user)],
)
async def experimental_safety_detect(
    request: Request,
    work_area: Optional[str] = Query(default=None),
    people_count: Optional[int] = Query(default=None),
    duration_minutes: Optional[int] = Query(default=None),
    repeated_count: Optional[int] = Query(default=None),
) -> ExperimentalSafetyDetectResponse:
    """Run trained YOLO model and Safety Agent on an uploaded image without DB persistence.

    Accepts raw binary or multipart/form-data image upload. Reuses the trained
    YOLO checkpoint and safety_agent functions. Never writes to database,
    modifies history, or sends alerts.
    """
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

    image_media_type = _validate_image_bytes(image_bytes)
    ext = (
        ".jpg"
        if image_media_type == "image/jpeg"
        else (".png" if image_media_type == "image/png" else ".webp")
    )

    raw_wa = (
        (work_area.strip() if work_area else "")
        or (form_fields.get("work_area", "").strip())
        or None
    )
    raw_pc = (
        people_count
        if people_count is not None
        else form_fields.get("people_count")
    )
    resolved_people_count = (
        _parse_int_param(str(raw_pc), "people_count", 1)
        if raw_pc is not None
        else None
    )
    raw_dur = (
        duration_minutes
        if duration_minutes is not None
        else form_fields.get("duration_minutes")
    )
    resolved_duration = (
        _parse_int_param(str(raw_dur), "duration_minutes", 1)
        if raw_dur is not None
        else None
    )
    raw_rep = (
        repeated_count
        if repeated_count is not None
        else form_fields.get("repeated_count")
    )
    resolved_repeated = (
        _parse_int_param(str(raw_rep), "repeated_count", 0)
        if raw_rep is not None
        else None
    )

    try:
        model = load_model()
    except (FileNotFoundError, RuntimeError) as err:
        raise HTTPException(
            status_code=503,
            detail=f"Hazard detection service unavailable: {err}",
        ) from err

    temp_file = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    temp_path = Path(temp_file.name)
    try:
        temp_file.write(image_bytes)
        temp_file.close()

        detection_result = detect_objects(temp_path, model)
    except ValueError as err:
        raise HTTPException(
            status_code=400,
            detail=f"Image decoding failed: {err}",
        ) from err
    except (RuntimeError, Exception) as err:
        raise HTTPException(
            status_code=503,
            detail=f"Hazard detection inference failed: {err}",
        ) from err
    finally:
        if temp_path.is_file():
            try:
                temp_path.unlink()
            except OSError:
                pass

    observation = None
    if (
        resolved_people_count is not None
        and resolved_duration is not None
        and resolved_repeated is not None
    ):
        try:
            hazard_labels = [
                normalize_detection_label(d.class_name)
                for d in detection_result.detections
                if normalize_detection_label(d.class_name) is not None
            ]
            observation = NormalizedObservation(
                observation_id="experimental-preview",
                timestamp=datetime.now(timezone.utc),
                source="experimental_viewer",
                labels=tuple(hazard_labels),
                people_count=resolved_people_count,
                duration_minutes=resolved_duration,
                repeated_count=resolved_repeated,
                work_area=raw_wa,
            )
        except ValueError:
            observation = None

    safety_assessment = assess_safety(detection_result, observation=observation)
    alert_decision = decide_alert(safety_assessment)
    routing_state = run_safety_graph(safety_assessment, alert_decision)

    detection_items = [
        ExperimentalDetectionItem(
            class_name=d.class_name,
            confidence=round(d.confidence, 4),
            box=[round(c, 2) for c in d.bounding_box],
            class_id=d.class_id,
            is_hazard=normalize_detection_label(d.class_name) is not None,
        )
        for d in detection_result.detections
    ]

    safety_findings = [
        ExperimentalSafetyFinding(
            hazard_type=h.hazard_type,
            source_label=h.source_label,
            confidence=round(h.detection_confidence, 4)
            if h.detection_confidence is not None
            else None,
        )
        for h in safety_assessment.detected_hazards
    ]

    assessments_response = [
        AssessmentResponse.model_validate(a, from_attributes=True)
        for a in safety_assessment.assessments
    ]

    recommendations_response = [
        ExperimentalRecommendation(
            hazard_type=r.hazard_type,
            recommendation_text=r.recommendation_text,
            priority=r.priority,
            status=r.status,
        )
        for r in safety_assessment.recommendations
    ]

    alert_response = ExperimentalAlertDecision(
        alert_recommended=alert_decision.alert_recommended,
        reason=alert_decision.reason,
        priority=alert_decision.priority,
    )

    is_risk_assessed = bool(safety_assessment.detected_hazards) and alert_decision.outcome != "pending"
    if is_risk_assessed:
        status_note = (
            "Model detections and full numerical risk assessment completed with "
            "supplied operational exposure inputs."
        )
    else:
        status_note = (
            "Visual model detections and safety findings are active. Numerical risk scoring "
            "(Severity x Likelihood x Exposure) remains pending/unscored because operational "
            "exposure parameters (people count, duration, recurrence) were not supplied."
        )

    return ExperimentalSafetyDetectResponse(
        image_width=detection_result.image_width or 0,
        image_height=detection_result.image_height or 0,
        detections=detection_items,
        detected_hazards=safety_findings,
        assessments=assessments_response,
        recommendations=recommendations_response,
        alert=alert_response,
        safety_decision=SafetyDecisionResponse.model_validate(
            alert_decision, from_attributes=True
        ),
        routing_decision=routing_state["routing_decision"],
        routing_status=routing_state["routing_status"],
        routing_reason=routing_state["routing_reason"],
        is_risk_assessed=is_risk_assessed,
        status_note=status_note,
    )
