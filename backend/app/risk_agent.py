"""A small, explainable Site Risk Agent for Milestone 1.

The agent is deliberately rule-based. It does not call an LLM and does not
claim to perform computer-vision inference. A future YOLO adapter can produce
the labels consumed here.
"""

from typing import List, Optional

from .models import DetectedHazard, HazardAssessment, NormalizedObservation
from .scoring import calculate_risk_score, risk_band


LABEL_TO_HAZARD = {
    "no_helmet": "missing_safety_helmet",
    "no_gloves": "missing_safety_gloves",
    "no_boots": "missing_safety_boots",
    "no_goggle": "missing_safety_goggles",
}


class SiteRiskAgent:
    """Detect supported hazards and assign project-defined risk values."""

    def detect_hazards(
        self, observation: NormalizedObservation
    ) -> List[DetectedHazard]:
        """Record supported hazards without requiring scoring inputs.

        Unknown labels are ignored rather than guessed. This prevents the
        first version from inventing hazards that the rules do not support.
        """

        return [
            DetectedHazard(
                observation_id=observation.observation_id,
                hazard_type=LABEL_TO_HAZARD[label],
                source_label=label,
                detection_confidence=observation.detection_confidence,
            )
            for label in observation.labels
            if label in LABEL_TO_HAZARD
        ]

    def assess_hazard(
        self, hazard: DetectedHazard, observation: NormalizedObservation
    ) -> Optional[HazardAssessment]:
        """Score one detected hazard when all required inputs are present."""

        if (
            observation.people_count is None
            or observation.duration_minutes is None
            or observation.repeated_count is None
        ):
            return None

        severity = self._severity_for(hazard.hazard_type)
        likelihood = self._likelihood_for(observation.repeated_count)
        exposure = self._exposure_for(
            observation.people_count, observation.duration_minutes
        )
        score = calculate_risk_score(severity, likelihood, exposure)
        return HazardAssessment(
            observation_id=hazard.observation_id,
            hazard_type=hazard.hazard_type,
            source_label=hazard.source_label,
            severity=severity,
            likelihood=likelihood,
            exposure=exposure,
            risk_score=score,
            risk_band=risk_band(score),
            detection_confidence=hazard.detection_confidence,
            explanation=(
                f"{hazard.source_label} was mapped to {hazard.hazard_type}. "
                f"Severity={severity}, likelihood={likelihood}, "
                f"and exposure={exposure}; score={score}."
            ),
        )

    def assess(self, observation: NormalizedObservation) -> List[HazardAssessment]:
        """Return completed assessments for detected hazards only."""

        assessments: List[HazardAssessment] = []
        for hazard in self.detect_hazards(observation):
            assessment = self.assess_hazard(hazard, observation)
            if assessment is not None:
                assessments.append(assessment)
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
