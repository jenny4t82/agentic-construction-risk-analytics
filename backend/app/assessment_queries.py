"""History queries; count latest assessments independently of overall decisions."""
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .db_models import Observation, DetectedHazardRecord

BANDS = ("Pending", "Low", "Moderate", "High", "Critical")


def summarize(observation):
    counts = dict.fromkeys(BANDS, 0)
    for hazard in observation.detected_hazards:
        latest = max(hazard.assessments, key=lambda a: a.assessment_version, default=None)
        if latest:
            band = "Pending" if latest.status == "pending" else latest.risk_band
            if band in counts:
                counts[band] += 1
    return counts


def query_observations(session, *, risk="All", work_area=None, start=None, end=None,
                       observation_id=None, sort="newest", limit=20, offset=0):
    stmt = select(Observation)
    if work_area is not None:
        stmt = stmt.where(Observation.work_area == work_area)
    if start is not None:
        stmt = stmt.where(Observation.observed_at >= start)
    if end is not None:
        stmt = stmt.where(Observation.observed_at < end)
    if observation_id is not None:
        stmt = stmt.where(Observation.observation_id == observation_id)
    order = (Observation.observed_at, Observation.observation_id)
    stmt = stmt.order_by(*(field.desc() if sort == "newest" else field.asc() for field in order))
    stmt = stmt.options(selectinload(Observation.detected_hazards).selectinload(DetectedHazardRecord.assessments))
    # Like existing reporting, aggregate the complete filtered set on the server.
    # This deliberately does not infer totals from a paginated client response.
    records = list(session.execute(stmt).scalars().all())
    counts = dict.fromkeys(BANDS, 0)
    observation_counts = dict.fromkeys(BANDS, 0)
    matched = []
    for record in records:
        summary = summarize(record)
        for band, count in summary.items():
            counts[band] += count
            observation_counts[band] += int(count > 0)
        if risk == "All" or summary[risk] > 0:
            matched.append(record)
    return {"items": matched[offset:offset + limit], "total": len(matched),
            "limit": limit, "offset": offset, "assessment_counts": counts,
            "observation_counts": observation_counts, "unfiltered_risk_total": len(records)}
