"""Database-backed safety analytics derived from persisted PPE violations.

``Observation.work_area`` is intentionally used as a temporary zone label. It
is free text and is not a validated site or zone entity.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .db_models import Alert, DetectedHazardRecord, Observation
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


def load_violation_records(session: Session) -> list[DetectedHazardRecord]:
    """Load supported persisted violation events and their evidence lineage."""

    statement = (
        select(DetectedHazardRecord)
        .join(Observation, Observation.observation_id == DetectedHazardRecord.observation_id)
        .where(DetectedHazardRecord.source_label.in_(SUPPORTED_VIOLATION_LABELS))
        .order_by(DetectedHazardRecord.detected_hazard_id)
        .options(
            selectinload(DetectedHazardRecord.observation),
            selectinload(DetectedHazardRecord.assessments),
            selectinload(DetectedHazardRecord.alerts),
        )
    )
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
    return AreaMetric(
        work_area=work_area,
        violation_count=len(records),
        most_common_violation=_most_common(records),
        observation_ids=tuple(sorted({record.observation_id for record in records})),
        detected_hazard_ids=tuple(
            sorted(record.detected_hazard_id for record in records)
        ),
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
    )


def get_safety_analytics(session: Session) -> SafetyAnalytics:
    """Query PostgreSQL-backed records and compute the zone analytics snapshot."""

    return summarize_violation_records(load_violation_records(session))
