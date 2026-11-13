"""Assessment context corrections using existing observation audit metadata.

Observation inputs are submission defaults; per-assessment snapshots take precedence.
Corrections never run detection or alter evidence, siblings, or historical alert rows.
"""
from datetime import datetime, timezone

from sqlalchemy import select

from .db_models import Alert, DetectedHazardRecord, Observation, RiskAssessment
from .models import NormalizedObservation, HazardAssessment
from .risk_agent import SiteRiskAgent
from .decision_engine import evaluate_safety_decision
from .persistence import (
    AssessmentCompletionConflict, _domain_hazard, _completed_domain_assessment,
    _persisted_policy_inputs, _decision_payload, create_alert_for_hazard,
)

CONTEXT_FIELDS = ("people_count", "duration_minutes", "repeated_count")


def assessment_context(observation, assessment):
    metadata = observation.raw_metadata or {}
    stored = metadata.get("assessment_contexts", {}).get(str(assessment.assessment_id))
    if stored is not None:
        return stored
    completed = metadata.get("assessment_completions", {}).get(str(assessment.assessment_id), {})
    return completed.get("resolved_context", {key: getattr(observation, key) for key in CONTEXT_FIELDS})


def assessment_state(observation, hazard, assessment):
    metadata = observation.raw_metadata or {}
    history = [item for item in metadata.get("assessment_corrections", [])
               if item["assessment_id"] == assessment.assessment_id]
    domain = _domain_hazard(hazard)
    scored = None
    if assessment.status == "completed":
        scored = HazardAssessment(observation_id=observation.observation_id,
            hazard_type=hazard.hazard_type, source_label=hazard.source_label,
            detection_confidence=domain.detection_confidence,
            **{key: getattr(assessment, key) for key in (
                "severity", "likelihood", "exposure", "risk_score", "risk_band", "explanation")})
    decision = _decision_payload(evaluate_safety_decision(
        [domain], [scored] if scored else [], detection_complete=True))
    reconciliation = dict(metadata.get("assessment_reconciliation", {}).get(str(assessment.assessment_id),
        {"review_required": False, "alert_ids": [], "reason": None}))
    reconciliation["alert_ids"] = sorted(a.alert_id for a in hazard.alerts)
    reconciliation["state"] = (
        "review_required" if reconciliation["review_required"] else
        "linked" if reconciliation["alert_ids"] else
        "deferred_pending" if decision["outcome"] == "alert" and metadata.get("safety_decision", {}).get("outcome") == "pending" else "unchanged"
    )
    return {
        "observation_id": observation.observation_id,
        "detected_hazard_id": hazard.detected_hazard_id,
        "assessment_id": assessment.assessment_id,
        "revision": len(history) + int(str(assessment.assessment_id) in metadata.get("assessment_completions", {})),
        "context": assessment_context(observation, assessment),
        "assessment": assessment,
        "safety_decision": decision,
        "audit_history": history,
        "reconciliation": reconciliation,
    }


def find_assessment(session, assessment_id, *, lock=False):
    observation_id = session.execute(select(DetectedHazardRecord.observation_id)
        .join(RiskAssessment).where(RiskAssessment.assessment_id == assessment_id)).scalar_one_or_none()
    if observation_id is None:
        raise LookupError("Assessment not found")
    stmt = select(Observation).where(Observation.observation_id == observation_id)
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    observation = session.execute(stmt).scalar_one()
    # Reload children after acquiring the observation lock, including in reused sessions.
    session.expire(observation, ["detected_hazards"])
    found = None
    for hazard in observation.detected_hazards:
        session.expire(hazard, ["assessments"])
        for assessment in hazard.assessments:
            session.refresh(assessment)
            if assessment.assessment_id == assessment_id:
                found = observation, hazard, assessment
    if found is not None:
        return found
    raise LookupError("Assessment not found")


def correct_assessment(session, assessment_id, *, expected_revision, actor_id, values):
    observation, hazard, assessment = find_assessment(session, assessment_id, lock=True)
    latest = max(hazard.assessments, key=lambda a: a.assessment_version)
    if latest.assessment_id != assessment_id:
        raise AssessmentCompletionConflict("assessment_superseded", "A newer assessment exists")
    before = assessment_state(observation, hazard, assessment)
    if before["revision"] != expected_revision:
        raise AssessmentCompletionConflict("stale_revision", "Assessment changed; reload before correcting")
    if values == before["context"] and assessment.status == "completed":
        return before
    context = NormalizedObservation(observation_id=observation.observation_id,
        timestamp=observation.observed_at, source=observation.source,
        labels=(hazard.source_label,), **values)
    scored = SiteRiskAgent().assess_hazard(_domain_hazard(hazard), context)
    if scored is None:
        raise ValueError("Complete scoring context is required")
    metadata = dict(observation.raw_metadata or {})
    contexts = dict(metadata.get("assessment_contexts", {}))
    # Freeze all existing effective contexts before any legacy completion changes defaults.
    for sibling in observation.detected_hazards:
        for item in sibling.assessments:
            contexts.setdefault(str(item.assessment_id), assessment_context(observation, item))
    contexts[str(assessment_id)] = values
    metadata["assessment_contexts"] = contexts
    old_score = {key: getattr(assessment, key) for key in ("status", "risk_score", "risk_band")}
    existing_alerts = list(session.execute(select(Alert).where(
        Alert.observation_id == observation.observation_id)).scalars().all())
    snapshots = dict(metadata.get("alert_correction_snapshots", {}))
    linked = [a for a in existing_alerts if a.assessment_id == assessment_id or a.detected_hazard_id == hazard.detected_hazard_id]
    for alert in linked:
        source = alert.assessment or assessment
        snapshots.setdefault(str(alert.alert_id), {
            "assessment": {"assessment_id": source.assessment_id,
                **{key: getattr(source, key) for key in ("status", "risk_score", "risk_band")}},
            "decision": before["safety_decision"],
        })
    metadata["alert_correction_snapshots"] = snapshots
    now = datetime.now(timezone.utc)
    for key in ("severity", "likelihood", "exposure", "risk_score", "risk_band", "explanation"):
        setattr(assessment, key, getattr(scored, key))
    assessment.status = "completed"
    assessment.missing_inputs = None
    assessment.assessed_at = now
    finding_decision = _decision_payload(evaluate_safety_decision(
        [_domain_hazard(hazard)], [scored], detection_complete=True))
    hazard.evidence = {**(hazard.evidence or {}), "finding_decision": finding_decision}
    findings, scores = _persisted_policy_inputs(observation.detected_hazards)
    decision = evaluate_safety_decision(findings, scores, detection_complete=True)
    previous_decision = metadata.get("safety_decision")
    metadata["safety_decision"] = _decision_payload(decision)
    history = list(metadata.get("assessment_corrections", []))
    history.append({"assessment_id": assessment_id, "revision": expected_revision + 1,
        "previous_values": before["context"], "updated_values": values,
        "previous_result": old_score,
        "updated_result": {"status": "completed", "risk_score": scored.risk_score, "risk_band": scored.risk_band},
        "previous_decision": before["safety_decision"], "updated_decision": finding_decision,
        "previous_observation_decision": previous_decision, "updated_observation_decision": metadata["safety_decision"],
        "changed_by_user_id": str(actor_id), "changed_at": now.isoformat()})
    metadata["assessment_corrections"] = history
    reconciliation = dict(metadata.get("assessment_reconciliation", {}))
    reconciliation[str(assessment_id)] = {"review_required": bool(linked),
        "alert_ids": [a.alert_id for a in linked],
        "reason": "Assessment corrected; historical alert retained for explicit review" if linked else None}
    metadata["assessment_reconciliation"] = reconciliation
    observation.raw_metadata = metadata
    observation.updated_at = now
    session.flush()
    # Overall pending still suppresses new alerts, exactly as in the existing policy.
    if decision.outcome == "alert":
        for item in observation.detected_hazards:
            domain = _domain_hazard(item)
            current = _completed_domain_assessment(item, domain)
            if current and evaluate_safety_decision([domain], [current], detection_complete=True).outcome == "alert":
                create_alert_for_hazard(session, item.detected_hazard_id)
    session.expire(hazard, ["alerts"])
    return assessment_state(observation, hazard, assessment)
