"""Pure, provisional Milestone 2 notification policy (v1).

Risk scoring belongs to SiteRiskAgent. This policy consumes its completed
assessments and explicit supported PPE findings; it never infers compliance
from the absence of a positive PPE detection. The v1 band-to-outcome table is
an application policy pending mentor approval, not a scoring or OSHA rule.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Literal, Sequence

from .models import DetectedHazard, HazardAssessment
from .scoring import risk_band as band_for_score


Outcome = Literal["alert", "warning", "no_alert", "pending"]
POLICY_VERSION = "milestone2-decision-v1-provisional"
# Explicit application notification policy. Severity/score are not priorities.
# Low and Moderate findings request a warning; High and Critical request an
# alert. This table can be revised after mentor review without changing scores.
BAND_POLICY: dict[str, tuple[Outcome, str]] = {
    "Low": ("warning", "routine"),
    "Moderate": ("warning", "medium"),
    "High": ("alert", "high"),
    "Critical": ("alert", "urgent"),
}
BAND_ORDER = {"Low": 0, "Moderate": 1, "High": 2, "Critical": 3}


@dataclass(frozen=True)
class DecisionEvidence:
    hazard_type: str
    source_label: str
    detection_confidence: float | None
    risk_score: int | None
    risk_band: str | None


@dataclass(frozen=True)
class SafetyDecision:
    outcome: Outcome
    reason: str
    risk_band: str | None
    priority: str
    supporting_evidence: tuple[DecisionEvidence, ...]
    policy_version: str = POLICY_VERSION

    @property
    def alert_recommended(self) -> bool:
        """Compatibility for existing experimental API consumers."""
        return self.outcome == "alert"


def evaluate_safety_decision(
    findings: Sequence[DetectedHazard] | None,
    assessments: Sequence[HazardAssessment] | None,
    *,
    detection_complete: bool,
) -> SafetyDecision:
    """Decide once from explicit findings and matching completed assessments.

    Matching uses type, label, and occurrence order; duplicate findings are
    retained. Any missing/inconsistent score leaves the *overall* result
    pending, even if another finding has a completed high score.
    """
    if not detection_complete or findings is None or assessments is None:
        return SafetyDecision("pending", "Detection or assessment data is incomplete.", None, "pending", ())

    finding_counts = Counter((h.hazard_type, h.source_label) for h in findings)
    assessment_counts = Counter((a.hazard_type, a.source_label) for a in assessments)
    unmatched_assessments = any(
        assessment_counts[key] > finding_counts[key] for key in assessment_counts
    )

    pool: dict[tuple[str, str], list[HazardAssessment]] = defaultdict(list)
    for assessment in assessments:
        pool[(assessment.hazard_type, assessment.source_label)].append(assessment)
    for values in pool.values():
        values.sort(key=lambda a: (a.detection_confidence if a.detection_confidence is not None else -1, a.risk_score))

    evidence: list[DecisionEvidence] = []
    incomplete = unmatched_assessments
    for finding in sorted(findings, key=lambda h: (h.hazard_type, h.source_label, h.detection_confidence if h.detection_confidence is not None else -1)):
        candidates = pool[(finding.hazard_type, finding.source_label)]
        match_index = next(
            (index for index, item in enumerate(candidates)
             if item.detection_confidence == finding.detection_confidence),
            0,
        )
        assessment = candidates.pop(match_index) if candidates else None
        valid = (
            assessment is not None
            and assessment.risk_band in BAND_POLICY
            and isinstance(assessment.risk_score, int)
            and 1 <= assessment.risk_score <= 100
            and band_for_score(assessment.risk_score) == assessment.risk_band
        )
        if not valid:
            incomplete = True
        evidence.append(DecisionEvidence(
            finding.hazard_type,
            finding.source_label,
            finding.detection_confidence,
            assessment.risk_score if valid else None,
            assessment.risk_band if valid else None,
        ))

    supporting_evidence = tuple(evidence)
    if not findings:
        return SafetyDecision(
            "no_alert",
            "No supported explicit PPE violation was detected; this does not confirm site safety.",
            None, "none", supporting_evidence,
        )
    if incomplete:
        return SafetyDecision(
            "pending",
            "Supported PPE violation evidence exists, but a complete, consistent risk assessment is unavailable.",
            None, "pending", supporting_evidence,
        )

    highest_band = max((item.risk_band for item in evidence if item.risk_band), key=BAND_ORDER.__getitem__)
    outcome, priority = BAND_POLICY[highest_band]
    return SafetyDecision(
        outcome,
        f"{len(evidence)} supported PPE violation finding(s); highest assessed risk band is {highest_band}; provisional {POLICY_VERSION} policy selects {outcome} with {priority} notification priority.",
        highest_band,
        priority,
        supporting_evidence,
    )
