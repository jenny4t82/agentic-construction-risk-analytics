"""Persistence service for site observations, detected hazards, and risk assessments.

Persists monitoring data to PostgreSQL using the existing SQLAlchemy schema.
Operations are atomic within the provided session transaction.
"""

from datetime import datetime, timezone
from dataclasses import asdict
from decimal import Decimal
from hashlib import sha256
from typing import Any, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .db_models import Alert, DetectedHazardRecord, Observation, RiskAssessment
from .decision_engine import SafetyDecision, evaluate_safety_decision
from .detector import normalize_detection_label
from .models import DetectedHazard, HazardAssessment, NormalizedObservation
from .risk_agent import LABEL_TO_HAZARD, SiteRiskAgent


def _decision_payload(decision: SafetyDecision) -> dict[str, Any]:
    """Store the policy outcome without adding a schema or losing source metadata."""

    payload = asdict(decision)
    payload["supporting_evidence"] = [asdict(item) for item in decision.supporting_evidence]
    return payload


def _domain_hazard(record: DetectedHazardRecord) -> DetectedHazard:
    return DetectedHazard(
        observation_id=record.observation_id,
        hazard_type=record.hazard_type,
        source_label=record.source_label,
        detection_confidence=(
            float(record.detection_confidence)
            if record.detection_confidence is not None else None
        ),
    )


def _completed_domain_assessment(
    record: DetectedHazardRecord, hazard: DetectedHazard
) -> Optional[HazardAssessment]:
    latest = max(record.assessments, key=lambda item: item.assessment_version, default=None)
    if latest is None or latest.status != "completed" or any(
        value is None for value in (
            latest.severity, latest.likelihood, latest.exposure,
            latest.risk_score, latest.risk_band,
        )
    ):
        return None
    return HazardAssessment(
        observation_id=hazard.observation_id,
        hazard_type=hazard.hazard_type,
        source_label=hazard.source_label,
        severity=latest.severity,
        likelihood=latest.likelihood,
        exposure=latest.exposure,
        risk_score=latest.risk_score,
        risk_band=latest.risk_band,
        detection_confidence=hazard.detection_confidence,
        explanation=latest.explanation or "",
    )


def _persisted_policy_inputs(
    records: Sequence[DetectedHazardRecord],
) -> tuple[list[DetectedHazard], list[HazardAssessment]]:
    """Reconstruct policy inputs from persisted evidence for guarded retries."""

    findings: list[DetectedHazard] = []
    assessments: list[HazardAssessment] = []
    for record in records:
        if LABEL_TO_HAZARD.get(record.source_label) != record.hazard_type:
            continue
        hazard = _domain_hazard(record)
        findings.append(hazard)
        assessment = _completed_domain_assessment(record, hazard)
        if assessment is not None:
            assessments.append(assessment)
    return findings, assessments


def build_observation_bundle(
    observation_id: str,
    timestamp: datetime,
    source: str,
    work_area: Optional[str] = None,
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

    decision = evaluate_safety_decision(
        detected_hazards, assessments, detection_complete=True
    )
    obs_record = Observation(
        observation_id=observation_id,
        observed_at=timestamp,
        source=source,
        work_area=work_area,
        people_count=people_count,
        duration_minutes=duration_minutes,
        repeated_count=repeated_count,
        detection_confidence=conf_decimal,
        raw_metadata={**(raw_metadata or {}), "safety_decision": _decision_payload(decision)},
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

    hazard_occurrences: dict[tuple[str, str], int] = {}
    image_detections = (
        (raw_metadata or {}).get("image", {}).get("detections", [])
        if isinstance((raw_metadata or {}).get("image", {}), dict)
        else []
    )

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
            evidence=evidence
            or _evidence_for_hazard(image_detections, hazard.source_label),
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

        if LABEL_TO_HAZARD.get(hazard.source_label) != hazard.hazard_type:
            raise ValueError(
                f"Unsupported violation source '{hazard.source_label}' for alert creation"
            )

        finding_decision = evaluate_safety_decision(
            (hazard,), (matched_assessment,) if matched_assessment is not None else (),
            detection_complete=True,
        )
        hazard_record.evidence = {
            **(hazard_record.evidence or {}),
            "finding_decision": _decision_payload(finding_decision),
        }
        # The overall outcome is authoritative. A partially scored observation
        # remains pending; within an alert observation, only alert-grade
        # findings get actionable rows (warning siblings remain history only).
        if decision.outcome != "alert" or finding_decision.outcome != "alert":
            continue

        occurrence_key = (hazard.observation_id, hazard.hazard_type)
        occurrence = hazard_occurrences.get(occurrence_key, 0) + 1
        hazard_occurrences[occurrence_key] = occurrence
        deduplication_key = _observation_violation_key(
            observation_id=observation_id,
            hazard_type=hazard.hazard_type,
            occurrence=occurrence,
        )
        obs_record.alerts.append(
            Alert(
                observation_id=observation_id,
                detected_hazard=hazard_record,
                assessment=assessment_record,
                alert_type=hazard.hazard_type,
                message=(
                    f"Detected {hazard.hazard_type.replace('_', ' ')} "
                    f"(source label: {hazard.source_label})."
                ),
                risk_band=assessment_record.risk_band,
                status="open",
                deduplication_key=deduplication_key,
            )
        )

    return obs_record


def persist_observation_bundle(
    session: Session,
    observation_id: str,
    timestamp: datetime,
    source: str,
    work_area: Optional[str] = None,
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


def _evidence_for_hazard(
    image_detections: Any, source_label: str
) -> Optional[dict[str, Any]]:
    """Keep the matching raw model boxes with the persisted hazard evidence."""

    if not isinstance(image_detections, list):
        return None
    matching = [
        detection
        for detection in image_detections
        if isinstance(detection, dict)
        and normalize_detection_label(str(detection.get("class_name", "")))
        == source_label
    ]
    return {"detections": matching} if matching else None


def _observation_violation_key(
    observation_id: str, hazard_type: str, occurrence: int
) -> str:
    """Build a bounded key scoped to one observation and repeated hazard occurrence."""

    identity = f"{observation_id}\0{hazard_type}\0{occurrence}".encode("utf-8")
    return f"observation-violation:{sha256(identity).hexdigest()}"


def create_alert_for_hazard(
    session: Session, detected_hazard_id: int
) -> tuple[Alert, bool]:
    """Create an actionable alert only when the shared policy permits it.

    Existing hazard IDs are the idempotency boundary. The check and unique
    deduplication key prevent repeat requests for the same source row from
    creating duplicate alerts. Existing historical rows are returned unchanged.
    """

    hazard = session.get(DetectedHazardRecord, detected_hazard_id)
    if hazard is None:
        raise LookupError(f"Detected hazard '{detected_hazard_id}' not found")
    if LABEL_TO_HAZARD.get(hazard.source_label) != hazard.hazard_type:
        raise ValueError("Detected hazard is not a supported PPE violation")
    observation = session.get(Observation, hazard.observation_id)
    if observation is None:
        raise LookupError(
            f"Source observation '{hazard.observation_id}' for detected hazard "
            f"'{detected_hazard_id}' not found"
        )

    existing = session.execute(
        select(Alert).where(Alert.detected_hazard_id == detected_hazard_id)
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False

    findings, assessments = _persisted_policy_inputs(observation.detected_hazards)
    observation_decision = evaluate_safety_decision(
        findings, assessments, detection_complete=True
    )
    domain_hazard = _domain_hazard(hazard)
    domain_assessment = _completed_domain_assessment(hazard, domain_hazard)
    finding_decision = evaluate_safety_decision(
        (domain_hazard,), (domain_assessment,) if domain_assessment is not None else (),
        detection_complete=True,
    )
    if observation_decision.outcome != "alert" or finding_decision.outcome != "alert":
        raise ValueError(
            "Shared safety policy does not permit an actionable alert for this finding"
        )

    assessment = max(
        hazard.assessments,
        key=lambda item: item.assessment_version,
        default=None,
    )
    risk_band = (
        assessment.risk_band
        if assessment is not None and assessment.status == "completed"
        else None
    )
    hazard.evidence = {
        **(hazard.evidence or {}),
        "finding_decision": _decision_payload(finding_decision),
    }
    alert = Alert(
        observation_id=hazard.observation_id,
        detected_hazard=hazard,
        assessment=assessment,
        alert_type=hazard.hazard_type,
        message=(
            f"Detected {hazard.hazard_type.replace('_', ' ')} "
            f"(source label: {hazard.source_label})."
        ),
        risk_band=risk_band,
        status="open",
        deduplication_key=f"detected-hazard:{detected_hazard_id}",
    )
    session.add(alert)
    session.flush()
    return alert, True


class AssessmentCompletionConflict(ValueError):
    """A completion request conflicts with persisted assessment or context state."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def complete_pending_assessment(
    session: Session,
    assessment_id: int,
    *,
    completed_by_user_id: str,
    people_count: int | None = None,
    duration_minutes: int | None = None,
    repeated_count: int | None = None,
) -> tuple[Observation, DetectedHazardRecord, RiskAssessment, SafetyDecision]:
    """Complete one pending row under its observation lock, then reapply shared policy.

    The observation lock serializes competing completion requests for all its
    findings. The caller owns the transaction and commits the row, decision,
    audit metadata, and any newly eligible alerts together.
    """
    observation_id = session.execute(
        select(DetectedHazardRecord.observation_id)
        .join(RiskAssessment, RiskAssessment.detected_hazard_id == DetectedHazardRecord.detected_hazard_id)
        .where(RiskAssessment.assessment_id == assessment_id)
    ).scalar_one_or_none()
    if observation_id is None:
        raise LookupError(f"Assessment '{assessment_id}' not found")

    observation = session.execute(
        select(Observation)
        .where(Observation.observation_id == observation_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one()
    assessment = session.execute(
        select(RiskAssessment)
        .where(RiskAssessment.assessment_id == assessment_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one()
    if assessment.status != "pending":
        raise AssessmentCompletionConflict(
            "assessment_already_completed", "This assessment is already completed."
        )
    hazard = session.get(DetectedHazardRecord, assessment.detected_hazard_id)
    if hazard is None or LABEL_TO_HAZARD.get(hazard.source_label) != hazard.hazard_type:
        raise ValueError("Assessment is not linked to a supported PPE violation")
    latest = max(hazard.assessments, key=lambda item: item.assessment_version, default=None)
    if latest is None or latest.assessment_id != assessment_id:
        raise AssessmentCompletionConflict(
            "assessment_superseded", "A newer assessment exists for this finding."
        )

    submitted = {
        key: value for key, value in (
            ("people_count", people_count),
            ("duration_minutes", duration_minutes),
            ("repeated_count", repeated_count),
        ) if value is not None
    }
    resolved: dict[str, int] = {}
    supplied_missing: dict[str, int] = {}
    for key in ("people_count", "duration_minutes", "repeated_count"):
        existing = getattr(observation, key)
        supplied = submitted.get(key)
        if existing is not None and supplied is not None and existing != supplied:
            raise AssessmentCompletionConflict(
                "context_conflict", f"{key} is already recorded and cannot be replaced here."
            )
        value = existing if existing is not None else supplied
        if value is not None:
            resolved[key] = value
            if existing is None:
                supplied_missing[key] = value
    absent = [key for key in ("people_count", "duration_minutes", "repeated_count") if key not in resolved]
    if absent:
        raise ValueError(f"Missing required scoring context: {', '.join(absent)}")

    domain_hazard = _domain_hazard(hazard)
    context = NormalizedObservation(
        observation_id=observation.observation_id,
        timestamp=observation.observed_at,
        source=observation.source,
        labels=(hazard.source_label,),
        people_count=resolved["people_count"],
        duration_minutes=resolved["duration_minutes"],
        repeated_count=resolved["repeated_count"],
        work_area=observation.work_area,
        detection_confidence=domain_hazard.detection_confidence,
    )
    scored = SiteRiskAgent().assess_hazard(domain_hazard, context)
    if scored is None:
        raise ValueError("Required scoring context remains incomplete")

    completed_at = datetime.now(timezone.utc)
    for key, value in supplied_missing.items():
        setattr(observation, key, value)
    assessment.status = "completed"
    assessment.severity = scored.severity
    assessment.likelihood = scored.likelihood
    assessment.exposure = scored.exposure
    assessment.risk_score = scored.risk_score
    assessment.risk_band = scored.risk_band
    assessment.explanation = scored.explanation
    assessment.missing_inputs = None
    assessment.assessed_at = completed_at
    observation.updated_at = completed_at

    metadata = dict(observation.raw_metadata or {})
    prior_completions = metadata.get("assessment_completions", {})
    if not isinstance(prior_completions, dict):
        raise ValueError("Existing assessment completion metadata is invalid")
    metadata["assessment_completions"] = {
        **prior_completions,
        str(assessment_id): {
            "previous_status": "pending",
            "completed_at": completed_at.isoformat(),
            "completed_by_user_id": completed_by_user_id,
            "provided_context": submitted,
            "new_context": supplied_missing,
            "resolved_context": resolved,
        },
    }
    session.flush()

    findings, scored_assessments = _persisted_policy_inputs(observation.detected_hazards)
    decision = evaluate_safety_decision(findings, scored_assessments, detection_complete=True)
    for item in observation.detected_hazards:
        if LABEL_TO_HAZARD.get(item.source_label) != item.hazard_type:
            continue
        item_hazard = _domain_hazard(item)
        item_assessment = _completed_domain_assessment(item, item_hazard)
        finding_decision = evaluate_safety_decision(
            (item_hazard,), (item_assessment,) if item_assessment is not None else (),
            detection_complete=True,
        )
        item.evidence = {
            **(item.evidence or {}),
            "finding_decision": _decision_payload(finding_decision),
        }
    metadata["safety_decision"] = _decision_payload(decision)
    observation.raw_metadata = metadata
    session.flush()

    if decision.outcome == "alert":
        for item in observation.detected_hazards:
            if LABEL_TO_HAZARD.get(item.source_label) != item.hazard_type:
                continue
            item_hazard = _domain_hazard(item)
            item_assessment = _completed_domain_assessment(item, item_hazard)
            finding_decision = evaluate_safety_decision(
                (item_hazard,), (item_assessment,) if item_assessment is not None else (),
                detection_complete=True,
            )
            if finding_decision.outcome == "alert":
                create_alert_for_hazard(session, item.detected_hazard_id)
    return observation, hazard, assessment, decision


def get_alert_record(session: Session, alert_id: int) -> Optional[Alert]:
    """Retrieve an alert with its observation, violation evidence, and assessment."""

    stmt = (
        select(Alert)
        .where(Alert.alert_id == alert_id)
        .options(
            selectinload(Alert.observation),
            selectinload(Alert.detected_hazard).selectinload(
                DetectedHazardRecord.assessments
            ),
            selectinload(Alert.assessment),
        )
    )
    return session.execute(stmt).scalar_one_or_none()


def list_alert_records(
    session: Session,
    limit: int = 20,
    offset: int = 0,
    status: Optional[str] = None,
    observation_id: Optional[str] = None,
) -> list[Alert]:
    """List alert history with source evidence loaded and stable ordering."""

    stmt = select(Alert)
    if status is not None:
        stmt = stmt.where(Alert.status == status)
    if observation_id is not None:
        stmt = stmt.where(Alert.observation_id == observation_id)
    stmt = (
        stmt.order_by(Alert.created_at.desc(), Alert.alert_id.desc())
        .limit(limit)
        .offset(offset)
        .options(
            selectinload(Alert.observation),
            selectinload(Alert.detected_hazard),
            selectinload(Alert.assessment),
        )
    )
    return list(session.execute(stmt).scalars().all())


_ALERT_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "open": frozenset({"acknowledged", "resolved", "dismissed"}),
    "acknowledged": frozenset({"resolved", "dismissed"}),
    "resolved": frozenset(),
    "dismissed": frozenset(),
}


def update_alert_status(session: Session, alert_id: int, status: str) -> Alert:
    """Apply one forward-only alert lifecycle transition and persist its timestamp."""

    if status not in {"open", "acknowledged", "resolved", "dismissed"}:
        raise ValueError(f"Unsupported alert status '{status}'")

    alert = session.get(Alert, alert_id)
    if alert is None:
        raise LookupError(f"Alert '{alert_id}' not found")
    if alert.status == status:
        return alert
    if status not in _ALERT_STATUS_TRANSITIONS.get(alert.status, frozenset()):
        raise ValueError(
            f"Alert '{alert_id}' cannot transition from '{alert.status}' to '{status}'"
        )

    now = datetime.now(timezone.utc)
    alert.status = status
    if status == "acknowledged":
        alert.acknowledged_at = now
    elif status == "resolved":
        alert.resolved_at = now
    elif status == "dismissed":
        alert.dismissed_at = now
    session.flush()
    return alert


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
