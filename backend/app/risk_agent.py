"""A small, explainable Site Risk Agent for Milestone 1.

The agent is deliberately rule-based. It does not call an LLM and does not
claim to perform computer-vision inference. A future YOLO adapter can produce
the labels consumed here.
"""

from typing import Iterable, List

from .models import HazardAssessment, NormalizedObservation
from .scoring import calculate_risk_score, risk_band


LABEL_TO_HAZARD = {
    "no_helmet": "missing_safety_helmet",
    "no_gloves": "missing_safety_gloves",
    "no_boots": "missing_safety_boots",
    "no_goggle": "missing_safety_goggles",
}


class SiteRiskAgent:
    """Detect supported hazards and assign project-defined risk values."""

    def detect_hazards(self, labels: Iterable[str]) -> List[tuple[str, str]]:
        """Map source labels to application hazard names.

        Unknown labels are ignored rather than guessed. This prevents the
        first version from inventing hazards that the rules do not support.
        """

        return [
            (LABEL_TO_HAZARD[label], label)
            for label in labels
            if label in LABEL_TO_HAZARD
        ]

    def assess(self, observation: NormalizedObservation) -> List[HazardAssessment]:
        """Return one explainable assessment for each supported hazard."""

        assessments: List[HazardAssessment] = []
        for hazard_type, source_label in self.detect_hazards(observation.labels):
            severity = self._severity_for(hazard_type)
            likelihood = self._likelihood_for(observation.repeated_count)
            exposure = self._exposure_for(
                observation.people_count, observation.duration_minutes
            )
            score = calculate_risk_score(severity, likelihood, exposure)
            assessments.append(
                HazardAssessment(
                    observation_id=observation.observation_id,
                    hazard_type=hazard_type,
                    source_label=source_label,
                    severity=severity,
                    likelihood=likelihood,
                    exposure=exposure,
                    risk_score=score,
                    risk_band=risk_band(score),
                    detection_confidence=observation.detection_confidence,
                    explanation=(
                        f"{source_label} was mapped to {hazard_type}. "
                        f"Severity={severity}, likelihood={likelihood}, "
                        f"and exposure={exposure}; score={score}."
                    ),
                )
            )
        return assessments

    @staticmethod
    def _severity_for(hazard_type: str) -> int:
        # Project-defined consequence assumptions for PPE violations.
        return {
            "missing_safety_helmet": 5,
            "missing_safety_gloves": 3,
            "missing_safety_boots": 3,
            "missing_safety_goggles": 4,
        }[hazard_type]

    @staticmethod
    def _likelihood_for(repeated_count: int) -> int:
        # Repetition is a simple Milestone 1 proxy for likelihood.
        if repeated_count >= 5:
            return 5
        if repeated_count >= 3:
            return 4
        if repeated_count >= 1:
            return 3
        return 2

    @staticmethod
    def _exposure_for(people_count: int, duration_minutes: int) -> int:
        # Exposure increases with affected people and duration.
        if people_count >= 10 or duration_minutes >= 240:
            return 4
        if people_count >= 5 or duration_minutes >= 120:
            return 3
        if people_count >= 2 or duration_minutes >= 30:
            return 2
        return 1
