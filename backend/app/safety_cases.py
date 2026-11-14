"""Read-time grouping of persisted alerts into observation safety cases."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .db_models import Alert, DetectedHazardRecord, Observation


@dataclass(frozen=True)
class SafetyCaseRecord:
    observation: Observation
    alerts: tuple[Alert, ...]


def case_status(alerts: list[Alert] | tuple[Alert, ...]) -> str:
    """Summarize child states without making a mixed case look closed."""
    statuses = {alert.status for alert in alerts}
    if "open" in statuses:
        return "open"
    if "acknowledged" in statuses:
        return "acknowledged"
    if statuses == {"resolved"}:
        return "resolved"
    if statuses == {"dismissed"}:
        return "dismissed"
    return "mixed_closed"


def group_safety_cases(
    alerts: list[Alert],
    *,
    work_area: Optional[str] = None,
    status: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    search: Optional[str] = None,
    sort: str = "newest",
) -> list[SafetyCaseRecord]:
    """Group before filtering/paging so child alerts cannot split across pages."""
    grouped: dict[str, list[Alert]] = {}
    for alert in alerts:
        grouped.setdefault(alert.observation_id, []).append(alert)

    records: list[SafetyCaseRecord] = []
    needle = search.casefold().strip() if search else ""
    for observation_id, children in grouped.items():
        observation = children[0].observation
        if observation is None:
            continue
        if work_area is not None and observation.work_area != work_area:
            continue
        if start is not None and observation.observed_at < start:
            continue
        if end is not None and observation.observed_at >= end:
            continue
        identifier = f"observation:{observation_id}"
        if needle and needle not in observation_id.casefold() and needle not in identifier.casefold():
            continue
        ordered_children = tuple(sorted(children, key=lambda item: (item.created_at, item.alert_id)))
        if status is not None and case_status(ordered_children) != status:
            continue
        records.append(SafetyCaseRecord(observation, ordered_children))

    records.sort(key=lambda item: (item.observation.observed_at, item.observation.observation_id), reverse=sort == "newest")
    return records


def _alert_query():
    return (
        select(Alert)
        .order_by(Alert.observation_id, Alert.created_at, Alert.alert_id)
        .options(
            selectinload(Alert.observation)
            .selectinload(Observation.detected_hazards)
            .selectinload(DetectedHazardRecord.assessments),
            selectinload(Alert.detected_hazard).selectinload(DetectedHazardRecord.assessments),
            selectinload(Alert.assessment),
        )
    )


def list_safety_case_records(session: Session) -> list[Alert]:
    """Fetch all child alerts in bounded eager-load queries for grouping."""
    return list(session.execute(_alert_query()).scalars().unique().all())


def get_safety_case_alerts(session: Session, observation_id: str) -> list[Alert]:
    """Fetch all child alerts for one case with its complete observation graph."""
    stmt = _alert_query().where(Alert.observation_id == observation_id)
    return list(session.execute(stmt).scalars().unique().all())
