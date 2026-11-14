"""Database-backed safety analytics derived from persisted PPE violations.

``Observation.work_area`` is intentionally used as a temporary zone label. It
is free text and is not a validated site or zone entity.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from .db_models import DetectedHazardRecord, Observation
from .assessment_queries import latest_assessment_result, overall_risk_summary
from .risk_agent import LABEL_TO_HAZARD


SUPPORTED_VIOLATION_LABELS = frozenset(LABEL_TO_HAZARD)
RISK_LEVELS = ("Low", "Moderate", "High", "Critical", "pending")
UNRESOLVED_ALERT_STATUSES = frozenset({"open", "acknowledged"})


@dataclass(frozen=True)
class ViolationMetric:
    violation_type: str
    count: int
    observation_ids: tuple[str, ...]
    detected_hazard_ids: tuple[int, ...]


@dataclass(frozen=True)
class AreaMetric:
    work_area: str
    violation_count: int
    most_common_violation: Optional[ViolationMetric]
    observation_ids: tuple[str, ...]
    detected_hazard_ids: tuple[int, ...]
    violation_metrics: tuple[ViolationMetric, ...]
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


@dataclass(frozen=True)
class SafetyAnalytics:
    total_violations: int
    violations_by_work_area: tuple[AreaMetric, ...]
    highest_violation_area: Optional[AreaMetric]
    lowest_violation_area: Optional[AreaMetric]
    most_common_violation: Optional[ViolationMetric]
    most_common_violation_by_area: tuple[AreaMetric, ...]
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


@dataclass(frozen=True)
class WorkAreaRecurrenceGroup:
    """Distinct recorded observations of one supported PPE hazard in one named area."""

    work_area: str
    hazard_type: str
    observation_count: int
    is_repeated: bool
    observation_ids: tuple[str, ...]


@dataclass(frozen=True)
class WorkAreaObservationMetric:
    """Named areas ranked by distinct observations with any supported violation."""

    work_area: str
    observation_count: int
    observation_ids: tuple[str, ...]


@dataclass(frozen=True)
class WorkAreaRecurrenceAnalytics:
    window_start: datetime | None
    window_end: datetime | None
    groups: tuple[WorkAreaRecurrenceGroup, ...]
    work_areas_by_observation_count: tuple[WorkAreaObservationMetric, ...]
    repeated_work_area_count: int


def validate_recurrence_window(
    start: datetime | None, end: datetime | None,
) -> tuple[datetime | None, datetime | None]:
    """Normalize explicit, timezone-aware half-open observation-time bounds to UTC."""
    if start is not None and start.utcoffset() is None:
        raise ValueError("start must include a timezone offset")
    if end is not None and end.utcoffset() is None:
        raise ValueError("end must include a timezone offset")
    start_utc = start.astimezone(timezone.utc) if start is not None else None
    end_utc = end.astimezone(timezone.utc) if end is not None else None
    if start_utc is not None and end_utc is not None and start_utc >= end_utc:
        raise ValueError("start must be earlier than end")
    return start_utc, end_utc


def _named_work_area(value: str | None) -> str | None:
    """Apply only conservative area normalization; never promote unknowns to zones."""
    if not isinstance(value, str):
        return None
    name = value.strip()
    return name if name and name.casefold() not in {"unspecified", "unknown", "unassigned work area"} else None


def summarize_work_area_recurrence(
    records: Iterable[DetectedHazardRecord],
    *,
    start: datetime | None = None,
    end: datetime | None = None,
) -> WorkAreaRecurrenceAnalytics:
    """Count distinct persisted observations by named work area and hazard type.

    This informational view never derives or changes Observation.repeated_count,
    risk assessments, alerts, or the existing hazard-row analytics metrics.
    """
    start, end = validate_recurrence_window(start, end)
    grouped_ids: dict[tuple[str, str], set[str]] = defaultdict(set)
    area_ids: dict[str, set[str]] = defaultdict(set)
    for record in records:
        observation = record.observation
        if (
            observation is None
            or record.source_label not in SUPPORTED_VIOLATION_LABELS
            or LABEL_TO_HAZARD.get(record.source_label) != record.hazard_type
            or record.observation_id != observation.observation_id
        ):
            continue
        area = _named_work_area(observation.work_area)
        if area is None:
            continue
        observed_at = observation.observed_at
        if start is not None and observed_at < start:
            continue
        if end is not None and observed_at >= end:
            continue
        grouped_ids[(area, record.hazard_type)].add(observation.observation_id)
        area_ids[area].add(observation.observation_id)

    groups = tuple(sorted((
        WorkAreaRecurrenceGroup(
            work_area=area,
            hazard_type=hazard_type,
            observation_count=len(ids),
            is_repeated=len(ids) >= 2,
            observation_ids=tuple(sorted(ids)),
        )
        for (area, hazard_type), ids in grouped_ids.items()
    ), key=lambda group: (-group.observation_count, group.work_area, group.hazard_type)))
    areas = tuple(sorted((
        WorkAreaObservationMetric(
            work_area=area,
            observation_count=len(ids),
            observation_ids=tuple(sorted(ids)),
        )
        for area, ids in area_ids.items()
    ), key=lambda metric: (-metric.observation_count, metric.work_area)))
    return WorkAreaRecurrenceAnalytics(
        window_start=start,
        window_end=end,
        groups=groups,
        work_areas_by_observation_count=areas,
        repeated_work_area_count=len({group.work_area for group in groups if group.is_repeated}),
    )


def get_work_area_recurrence(
    session: Session,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
) -> WorkAreaRecurrenceAnalytics:
    """Read persisted PPE findings within optional observation-time bounds."""
    start, end = validate_recurrence_window(start, end)
    statement = (
        select(DetectedHazardRecord)
        .join(Observation, Observation.observation_id == DetectedHazardRecord.observation_id)
        .where(DetectedHazardRecord.source_label.in_(SUPPORTED_VIOLATION_LABELS))
        .order_by(DetectedHazardRecord.detected_hazard_id)
        .options(selectinload(DetectedHazardRecord.observation))
    )
    if start is not None:
        statement = statement.where(Observation.observed_at >= start)
    if end is not None:
        statement = statement.where(Observation.observed_at < end)
    records = session.execute(statement).scalars().all()
    return summarize_work_area_recurrence(records, start=start, end=end)


def load_violation_records(
    session: Session, *, start: datetime | None = None, end: datetime | None = None,
) -> list[DetectedHazardRecord]:
    """Load supported persisted violation events and their evidence lineage."""

    statement = (
        select(DetectedHazardRecord)
        .join(Observation, Observation.observation_id == DetectedHazardRecord.observation_id)
        .where(DetectedHazardRecord.source_label.in_(SUPPORTED_VIOLATION_LABELS))
        .order_by(DetectedHazardRecord.detected_hazard_id)
        .options(
            selectinload(DetectedHazardRecord.observation).selectinload(Observation.detected_hazards).selectinload(DetectedHazardRecord.assessments),
            selectinload(DetectedHazardRecord.observation).selectinload(Observation.alerts),
            selectinload(DetectedHazardRecord.assessments),
            selectinload(DetectedHazardRecord.alerts),
        )
    )
    if start is not None:
        statement = statement.where(Observation.observed_at >= start)
    if end is not None:
        statement = statement.where(Observation.observed_at < end)
    return list(session.execute(statement).scalars().all())


def _area_name(record: DetectedHazardRecord) -> str:
    """Return a stable display bucket for nullable/free-text work areas."""

    work_area = record.observation.work_area if record.observation is not None else None
    return _named_work_area(work_area) or "Unspecified"


def _latest_assessment(record: DetectedHazardRecord):
    return max(record.assessments, key=lambda item: item.assessment_version, default=None)


def _metric(records: Iterable[DetectedHazardRecord], violation_type: str) -> ViolationMetric:
    selected = [record for record in records if record.hazard_type == violation_type]
    return ViolationMetric(
        violation_type=violation_type,
        count=len(selected),
        observation_ids=tuple(sorted({record.observation_id for record in selected})),
        detected_hazard_ids=tuple(
            sorted(record.detected_hazard_id for record in selected)
        ),
    )


def _most_common(records: list[DetectedHazardRecord]) -> Optional[ViolationMetric]:
    if not records:
        return None
    counts = Counter(record.hazard_type for record in records)
    violation_type = min(counts, key=lambda value: (-counts[value], value))
    return _metric(records, violation_type)


def _area_metric(work_area: str, records: list[DetectedHazardRecord]) -> AreaMetric:
    observations = {record.observation_id: record.observation for record in records if record.observation is not None}
    observation_risk_distribution = {"Low": 0, "Moderate": 0, "High": 0, "Critical": 0, "pending": 0, "incomplete": 0, "no_supported_findings": 0}
    provisional_observation_count = 0
    for observation in observations.values():
        summary = overall_risk_summary(observation)
        band = summary["overall_risk_band"]
        if band:
            observation_risk_distribution[band] += 1
        elif summary["overall_risk_status"] == "pending":
            observation_risk_distribution["pending"] += 1
        elif summary["overall_risk_status"] == "no_supported_findings":
            observation_risk_distribution["no_supported_findings"] += 1
        else:
            observation_risk_distribution["incomplete"] += 1
        provisional_observation_count += int(summary["overall_risk_provisional"])
    results = [latest_assessment_result(record) for record in records]
    alert_by_id = {alert.alert_id: alert for observation in observations.values() for alert in observation.alerts}
    alert_by_id.update({alert.alert_id: alert for record in records for alert in record.alerts})
    alert_counts = {state: sum(alert.status == state for alert in alert_by_id.values()) for state in ("open", "acknowledged", "resolved", "dismissed")}
    return AreaMetric(
        work_area=work_area,
        violation_count=len(records),
        most_common_violation=_most_common(records),
        observation_ids=tuple(sorted({record.observation_id for record in records})),
        detected_hazard_ids=tuple(
            sorted(record.detected_hazard_id for record in records)
        ),
        violation_metrics=tuple(_metric(records, hazard_type) for hazard_type in sorted({record.hazard_type for record in records})),
        observation_count=len(observations),
        valid_latest_completed_assessment_count=sum(result["status"] == "completed" for result in results),
        pending_latest_assessment_count=sum(result["status"] == "pending" for result in results),
        incomplete_latest_assessment_count=sum(result["status"] in {"missing", "incomplete"} for result in results),
        overall_observation_risk_distribution=observation_risk_distribution,
        provisional_observation_count=provisional_observation_count,
        individual_alert_count=len(alert_by_id),
        alert_status_counts=alert_counts,
        unresolved_individual_alert_count=alert_counts["open"] + alert_counts["acknowledged"],
        safety_case_count=len({observation.observation_id for observation in observations.values() if observation.alerts} | {record.observation_id for record in records if record.alerts}),
    )


def summarize_violation_records(
    records: Iterable[DetectedHazardRecord],
) -> SafetyAnalytics:
    """Summarize persisted supported violations with deterministic tie-breaking."""

    relevant_records = [
        record
        for record in records
        if record.source_label in SUPPORTED_VIOLATION_LABELS
        and LABEL_TO_HAZARD.get(record.source_label) == record.hazard_type
    ]
    by_area: dict[str, list[DetectedHazardRecord]] = defaultdict(list)
    for record in relevant_records:
        by_area[_area_name(record)].append(record)

    area_metrics = tuple(
        sorted(
            (_area_metric(area, area_records) for area, area_records in by_area.items()),
            key=lambda item: item.work_area,
        )
    )
    ranked_areas = sorted(
        area_metrics, key=lambda item: (-item.violation_count, item.work_area)
    )
    lowest_areas = sorted(
        area_metrics, key=lambda item: (item.violation_count, item.work_area)
    )

    risk_distribution = {level: 0 for level in RISK_LEVELS}
    alert_statuses: list[str] = []
    for record in relevant_records:
        assessment = _latest_assessment(record)
        risk_level = (
            assessment.risk_band
            if assessment is not None and assessment.status == "completed" and assessment.risk_band
            else "pending"
        )
        risk_distribution[risk_level if risk_level in risk_distribution else "pending"] += 1
        alert_statuses.extend(alert.status for alert in record.alerts)

    observation_records: dict[str, Observation] = {}
    for record in relevant_records:
        if record.observation is not None:
            observation_records.setdefault(record.observation_id, record.observation)
    observation_summaries = [overall_risk_summary(observation) for observation in observation_records.values()]
    overall_distribution = {"Low": 0, "Moderate": 0, "High": 0, "Critical": 0, "pending": 0, "incomplete": 0, "no_supported_findings": 0}
    for summary in observation_summaries:
        if summary["overall_risk_band"]:
            overall_distribution[summary["overall_risk_band"]] += 1
        elif summary["overall_risk_status"] == "pending":
            overall_distribution["pending"] += 1
        elif summary["overall_risk_status"] == "no_supported_findings":
            overall_distribution["no_supported_findings"] += 1
        else:
            overall_distribution["incomplete"] += 1
    finding_results = [latest_assessment_result(record) for record in relevant_records]
    alert_by_id = {alert.alert_id: alert for observation in observation_records.values() for alert in observation.alerts}
    alert_by_id.update({alert.alert_id: alert for record in relevant_records for alert in record.alerts})
    all_alert_status_counts = {state: sum(alert.status == state for alert in alert_by_id.values()) for state in ("open", "acknowledged", "resolved", "dismissed")}
    return SafetyAnalytics(
        total_violations=len(relevant_records),
        violations_by_work_area=area_metrics,
        highest_violation_area=ranked_areas[0] if ranked_areas else None,
        lowest_violation_area=lowest_areas[0] if lowest_areas else None,
        most_common_violation=_most_common(relevant_records),
        most_common_violation_by_area=area_metrics,
        risk_level_distribution=risk_distribution,
        open_alert_count=alert_statuses.count("open"),
        unresolved_alert_count=sum(
            status in UNRESOLVED_ALERT_STATUSES for status in alert_statuses
        ),
        resolved_alert_count=alert_statuses.count("resolved"),
        unique_observation_count=len(observation_records),
        valid_latest_completed_assessment_count=sum(result["status"] == "completed" for result in finding_results),
        pending_latest_assessment_count=sum(result["status"] == "pending" for result in finding_results),
        incomplete_latest_assessment_count=sum(result["status"] in {"missing", "incomplete"} for result in finding_results),
        overall_observation_risk_distribution=overall_distribution,
        provisional_observation_count=sum(summary["overall_risk_provisional"] for summary in observation_summaries),
        individual_alert_count=len(alert_by_id),
        alert_status_counts=all_alert_status_counts,
        all_unresolved_alert_count=all_alert_status_counts["open"] + all_alert_status_counts["acknowledged"],
        safety_case_count=len({observation.observation_id for observation in observation_records.values() if observation.alerts} | {record.observation_id for record in relevant_records if record.alerts}),
    )


def get_safety_analytics(
    session: Session, *, start: datetime | None = None, end: datetime | None = None,
) -> SafetyAnalytics:
    """Query PostgreSQL-backed records and compute the zone analytics snapshot."""

    start, end = validate_recurrence_window(start, end)
    return summarize_violation_records(load_violation_records(session, start=start, end=end))


def get_finding_observation_page(
    session: Session, *, work_area: str | None = None, hazard_type: str | None = None,
    start: datetime | None = None, end: datetime | None = None,
    area_mode: str = "zone", sort: str = "newest", limit: int = 20, offset: int = 0,
) -> dict:
    """Page distinct observations with matching supported finding rows.

    Matching, counts and pagination are performed in SQL; the selected page is
    then hydrated with bounded select-in queries for evidence lineage.
    """
    start, end = validate_recurrence_window(start, end)
    source_pairs = [(label, category) for label, category in LABEL_TO_HAZARD.items()
                    if hazard_type is None or category == hazard_type]
    pairs_match = or_(*(and_(DetectedHazardRecord.source_label == label,
                             DetectedHazardRecord.hazard_type == category)
                        for label, category in source_pairs)) if source_pairs else False
    conditions = [DetectedHazardRecord.observation_id == Observation.observation_id, pairs_match]
    if start is not None:
        conditions.append(Observation.observed_at >= start)
    if end is not None:
        conditions.append(Observation.observed_at < end)
    trimmed_area = func.trim(Observation.work_area)
    unknown_area = or_(Observation.work_area.is_(None), trimmed_area == "",
                       func.lower(trimmed_area).in_(("unspecified", "unknown", "unassigned work area")))
    if area_mode == "recurrence":
        conditions.append(~unknown_area)
    if work_area is not None:
        conditions.append(unknown_area if area_mode == "zone" and work_area == "Unspecified"
                          else trimmed_area == work_area)
    matching = select(DetectedHazardRecord.observation_id).join(
        Observation, Observation.observation_id == DetectedHazardRecord.observation_id
    ).where(*conditions)
    total_observations = session.scalar(select(func.count()).select_from(matching.distinct().subquery())) or 0
    total_matching_findings = session.scalar(select(func.count()).select_from(matching.subquery())) or 0
    ordering = (Observation.observed_at.desc(), Observation.observation_id.desc()) if sort == "newest" else (Observation.observed_at.asc(), Observation.observation_id.asc())
    page_stmt = (select(Observation.observation_id, Observation.observed_at)
                 .join(DetectedHazardRecord, DetectedHazardRecord.observation_id == Observation.observation_id)
                 .where(*conditions).distinct().order_by(*ordering).offset(offset).limit(limit))
    page_ids = [row.observation_id for row in session.execute(page_stmt).all()]
    if not page_ids:
        observations = []
        matching_ids = {}
    else:
        detail_stmt = (select(Observation).where(Observation.observation_id.in_(page_ids))
                       .options(selectinload(Observation.detected_hazards).selectinload(DetectedHazardRecord.assessments),
                                selectinload(Observation.alerts)))
        by_id = {item.observation_id: item for item in session.execute(detail_stmt).scalars().all()}
        observations = [by_id[item_id] for item_id in page_ids if item_id in by_id]
        matching_stmt = (select(DetectedHazardRecord.observation_id, DetectedHazardRecord.detected_hazard_id)
                         .join(Observation, Observation.observation_id == DetectedHazardRecord.observation_id)
                         .where(*conditions, DetectedHazardRecord.observation_id.in_(page_ids)))
        matching_ids = defaultdict(list)
        for observation_id, hazard_id in session.execute(matching_stmt).all():
            matching_ids[observation_id].append(hazard_id)
    return {"items": [(item, sorted(matching_ids.get(item.observation_id, []))) for item in observations],
            "total_observations": total_observations, "total_matching_findings": total_matching_findings,
            "limit": limit, "offset": offset}
