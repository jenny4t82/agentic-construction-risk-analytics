"""Automated tests using synthetic fixtures only.

These fixtures are not OSHA records, construction-site records, or downloaded
dataset contents. They exist only to test the current software behavior.
"""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.models import NormalizedObservation
from app.risk_agent import SiteRiskAgent
from app.scoring import calculate_risk_score, risk_band


class RiskScoringTests(unittest.TestCase):
    def test_formula_and_project_bands(self) -> None:
        self.assertEqual(calculate_risk_score(5, 5, 4), 100)
        self.assertEqual(risk_band(19), "Low")
        self.assertEqual(risk_band(20), "Moderate")
        self.assertEqual(risk_band(40), "High")
        self.assertEqual(risk_band(70), "Critical")

    def test_invalid_scale_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            calculate_risk_score(6, 1, 1)


class SiteRiskAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = SiteRiskAgent()

    def test_synthetic_missing_helmet_fixture(self) -> None:
        observation = NormalizedObservation(
            observation_id="synthetic-001",
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            source="synthetic_test_fixture",
            labels=("no_helmet",),
            people_count=2,
            duration_minutes=45,
            repeated_count=3,
            detection_confidence=0.91,
        )

        assessments = self.agent.assess(observation)

        self.assertEqual(len(assessments), 1)
        result = assessments[0]
        self.assertEqual(result.hazard_type, "missing_safety_helmet")
        self.assertEqual(result.severity, 5)
        self.assertEqual(result.likelihood, 4)
        self.assertEqual(result.exposure, 2)
        self.assertEqual(result.risk_score, 40)
        self.assertEqual(result.risk_band, "High")
        self.assertEqual(result.detection_confidence, 0.91)
        self.assertIn("score=40", result.explanation)

    def test_unknown_labels_are_not_guessed(self) -> None:
        observation = NormalizedObservation(
            observation_id="synthetic-002",
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            source="synthetic_test_fixture",
            labels=("unknown_label",),
        )

        self.assertEqual(self.agent.assess(observation), [])


if __name__ == "__main__":
    unittest.main()
