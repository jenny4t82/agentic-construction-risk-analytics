"""History queries; count latest assessments independently of overall decisions."""
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .db_models import Observation, DetectedHazardRecord
from .scoring import risk_band

BANDS = ("Pending", "Low", "Moderate", "High", "Critical")


def overall_risk_summary(observation):
    """Aggregate the latest valid numeric result for each persisted finding.

    Invalid/missing results are incomplete, never guessed. Risk tabs and facet
    counts deliberately remain existential per-finding filters.
    """
    completed_scores = []
    completed_count = 0
    pending_count = 0
    incomplete_count = 0
    hazards = list(observation.detected_hazards or [])
    for hazard in hazards:
        latest = max(hazard.assessments or [], key=lambda item: item.assessment_version, default=None)
        if latest is None:
            incomplete_count += 1
            continue
        if latest.status == "pending":
            pending_count += 1
            continue
        if latest.status == "completed":
            completed_count += 1
        score = latest.risk_score
        if latest.status != "completed" or isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 100:
            incomplete_count += 1
            continue
        try:
            band = risk_band(score)
        except ValueError:
            incomplete_count += 1
            continue
        completed_scores.append((score, band))

    highest = max(completed_scores, key=lambda item: item[0], default=None)
    provisional = highest is not None and (pending_count > 0 or incomplete_count > 0)
    if not hazards:
        status = "no_supported_findings"
    elif highest is None and pending_count == len(hazards):
        status = "pending"
    elif highest is None:
        status = "incomplete"
    elif provisional:
        status = "provisional"
    else:
        status = "assessed"
    return {
        "overall_risk_score": highest[0] if highest else None,
        "overall_risk_band": highest[1] if highest else None,
        "overall_risk_provisional": provisional,
        "overall_risk_status": status,
        "completed_assessment_count": completed_count,
        "pending_assessment_count": pending_count,
        "incomplete_assessment_count": incomplete_count,
        "total_assessed_findings": len(hazards),
    }


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
