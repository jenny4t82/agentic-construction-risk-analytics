"""Read-only safety reports from persisted observations and existing analytics rules."""

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .analytics import (
    RISK_LEVELS, SUPPORTED_VIOLATION_LABELS, _named_work_area,
    summarize_violation_records, summarize_work_area_recurrence,
    validate_recurrence_window,
)
from .db_models import Alert, DetectedHazardRecord, Observation
from .risk_agent import LABEL_TO_HAZARD


REPORT_DISCLAIMER = (
    "This report summarizes recorded SafeSite observations and model-supported PPE "
    "findings. It does not certify regulatory compliance or establish overall site "
    "safety. Model-supported findings should be reviewed by a qualified safety professional."
)
UNASSIGNED = "Unassigned work area"


def available_work_areas(session: Session) -> list[str]:
    """List real named areas from persisted observations, preserving spelling and case."""
    values = session.execute(select(Observation.work_area)).scalars().all()
    return sorted({_named_work_area(value) for value in values} - {None})


def _latest_assessment(record: DetectedHazardRecord):
    return max(record.assessments, key=lambda item: item.assessment_version, default=None)


def summarize_report(
    observations: Iterable[Observation], *, start: datetime | None = None,
    end: datetime | None = None, scope: str = "all",
    work_areas: Iterable[str] = (), include_unassigned: bool = False,
    generated_by: dict[str, str], generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build one deterministic, filter-scoped payload shared by JSON and PDF."""
    start, end = validate_recurrence_window(start, end)
    if scope not in {"all", "selected"}:
        raise ValueError("scope must be all or selected")
    names = tuple(sorted(set(work_areas)))
    if any(not name or len(name) > 255 or _named_work_area(name) != name for name in names):
        raise ValueError("work_area values must be trimmed named areas of at most 255 characters")
    if scope == "all" and (names or include_unassigned):
        raise ValueError("work_area and include_unassigned require scope=selected")
    if scope == "selected" and not names and not include_unassigned:
        raise ValueError("Select at least one named work area or include unassigned observations")

    selected = []
    for observation in observations:
        if start is not None and observation.observed_at < start:
            continue
        if end is not None and observation.observed_at >= end:
            continue
        area = _named_work_area(observation.work_area)
        if scope == "selected" and not (area in names or (area is None and include_unassigned)):
            continue
        selected.append(observation)
    selected.sort(key=lambda item: (item.observed_at, item.observation_id))

    hazards = [
        hazard for observation in selected for hazard in observation.detected_hazards
        if hazard.source_label in SUPPORTED_VIOLATION_LABELS
        and LABEL_TO_HAZARD.get(hazard.source_label) == hazard.hazard_type
        and hazard.observation_id == observation.observation_id
    ]
    hazards.sort(key=lambda item: item.detected_hazard_id)
    analytics = summarize_violation_records(hazards)
    recurrence = summarize_work_area_recurrence(hazards, start=start, end=end)
    alerts = sorted(
        (alert for observation in selected for alert in observation.alerts),
        key=lambda item: item.alert_id,
    )
    decisions = Counter()
    for observation in selected:
        metadata = observation.raw_metadata or {}
        snapshot = metadata.get("safety_decision") if isinstance(metadata, dict) else None
        outcome = snapshot.get("outcome") if isinstance(snapshot, dict) else None
        decisions[outcome if outcome in {"alert", "warning", "pending", "no_alert"} else "unavailable"] += 1

    findings = []
    for hazard in hazards:
        assessment = _latest_assessment(hazard)
        related_alerts = sorted(hazard.alerts, key=lambda item: item.alert_id)
        metadata = hazard.observation.raw_metadata or {}
        snapshot = metadata.get("safety_decision") if isinstance(metadata, dict) else None
        findings.append({
            "observation_id": hazard.observation_id,
            "observed_at": hazard.observation.observed_at,
            "work_area": _named_work_area(hazard.observation.work_area) or UNASSIGNED,
            "detected_hazard_id": hazard.detected_hazard_id,
            "hazard_type": hazard.hazard_type,
            "detection_confidence": float(hazard.detection_confidence) if hazard.detection_confidence is not None else None,
            "assessment_status": assessment.status if assessment else "unavailable",
            "risk_score": assessment.risk_score if assessment and assessment.status == "completed" else None,
            "risk_band": assessment.risk_band if assessment and assessment.status == "completed" else None,
            "safety_decision": snapshot.get("outcome") if isinstance(snapshot, dict) else "unavailable",
            "alert_status": related_alerts[0].status if related_alerts else None,
        })
    finding_counts = Counter(hazard.hazard_type for hazard in hazards)
    area_by_name = {
        _named_work_area(observation.work_area) or UNASSIGNED: {
            "work_area": _named_work_area(observation.work_area) or UNASSIGNED,
            "violation_count": 0, "most_common_violation": None,
        }
        for observation in selected
    }
    for area in analytics.violations_by_work_area:
        name = UNASSIGNED if area.work_area == "Unspecified" else area.work_area
        area_by_name[name] = {
            "work_area": name, "violation_count": area.violation_count,
            "most_common_violation": area.most_common_violation.violation_type if area.most_common_violation else None,
        }
    area_metrics = [area_by_name[name] for name in sorted(area_by_name)]
    highest_count = max(
        (area["violation_count"] for area in area_metrics if area["work_area"] != UNASSIGNED),
        default=0,
    )
    status_counts = Counter(alert.status for alert in alerts)
    alert_rows = [
        {
            "alert_id": alert.alert_id,
            "observation_id": alert.observation_id,
            "work_area": _named_work_area(alert.observation.work_area) or UNASSIGNED,
            "hazard_type": alert.detected_hazard.hazard_type if alert.detected_hazard else None,
            "risk_band": alert.risk_band,
            "status": alert.status,
            "created_at": alert.created_at,
            "acknowledged_at": alert.acknowledged_at,
            "resolved_at": alert.resolved_at,
            "dismissed_at": alert.dismissed_at,
        }
        for alert in alerts
    ]
    return {
        "generated_at": generated_at or datetime.now(timezone.utc),
        "generated_by": generated_by,
        "scope": {
            "window_start": start, "window_end": end,
            "all_work_areas": scope == "all", "work_areas": list(names),
            "include_unassigned": scope == "all" or include_unassigned,
        },
        "summary": {
            "total_observations": len(selected),
            "supported_ppe_findings": len(hazards),
            "actionable_alerts": len(alerts),
            "warnings": decisions["warning"],
            "pending_assessments": sum(
                _latest_assessment(hazard) is not None
                and _latest_assessment(hazard).status == "pending" for hazard in hazards
            ),
            "resolved_alerts": status_counts["resolved"],
        },
        "decision_counts": {key: decisions[key] for key in ("alert", "warning", "pending", "no_alert", "unavailable")},
        "risk_distribution": {key: analytics.risk_level_distribution[key] for key in RISK_LEVELS},
        "violation_breakdown": [
            {"hazard_type": name, "count": count}
            for name, count in sorted(finding_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "work_areas": area_metrics,
        "highest_violation_work_areas": sorted(
            area["work_area"] for area in area_metrics
            if area["work_area"] != UNASSIGNED and highest_count and area["violation_count"] == highest_count
        ),
        "recurrence": [
            {"work_area": group.work_area, "hazard_type": group.hazard_type,
             "observation_count": group.observation_count, "observation_ids": list(group.observation_ids)}
            for group in recurrence.groups if group.is_repeated
        ],
        "repeated_work_area_count": recurrence.repeated_work_area_count,
        "alert_status_counts": {key: status_counts[key] for key in ("open", "acknowledged", "resolved", "dismissed")},
        "alerts": alert_rows,
        "findings": findings,
        "disclaimer": REPORT_DISCLAIMER,
    }


def get_safety_report(session: Session, **options: Any) -> dict[str, Any]:
    """Load persisted lineage once and apply the same filters to every metric."""
    records = session.execute(
        select(Observation).order_by(Observation.observed_at, Observation.observation_id)
        .options(
            selectinload(Observation.detected_hazards).selectinload(DetectedHazardRecord.assessments),
            selectinload(Observation.detected_hazards).selectinload(DetectedHazardRecord.alerts),
            selectinload(Observation.alerts).selectinload(Alert.detected_hazard),
        )
    ).scalars().all()
    return summarize_report(records, **options)
