"""Focused tests of the pure, shared provisional decision policy."""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.decision_engine import POLICY_VERSION, evaluate_safety_decision
from app.main import ObservationRequest, create_assessments
from app.models import DetectedHazard, HazardAssessment, NormalizedObservation
from app.safety_agent import Detection, DetectionResult, assess_safety, decide_alert


def finding(label="no_helmet", hazard_type="missing_safety_helmet", confidence=0.9):
    return DetectedHazard("obs", hazard_type, label, confidence)


def scored(hazard, score, band):
    return HazardAssessment(
        "obs", hazard.hazard_type, hazard.source_label,
        1, 1, 1, score, band, hazard.detection_confidence, "test score",
    )


def decide(findings, assessments):
    return evaluate_safety_decision(findings, assessments, detection_complete=True)


class DecisionEngineTests(unittest.TestCase):
    def test_no_supported_findings_is_not_confirmation_of_safety(self):
        decision = decide((), ())
        self.assertEqual(decision.outcome, "no_alert")
        self.assertIsNone(decision.risk_band)
        self.assertEqual(decision.priority, "none")
        self.assertIn("does not confirm site safety", decision.reason)

    def test_missing_or_incomplete_data_is_pending(self):
        self.assertEqual(evaluate_safety_decision(None, None, detection_complete=False).outcome, "pending")
        hazard = finding()
        decision = decide((hazard,), ())
        self.assertEqual(decision.outcome, "pending")
        self.assertFalse(decision.alert_recommended)
        self.assertEqual(len(decision.supporting_evidence), 1)
        self.assertIsNone(decision.supporting_evidence[0].risk_band)

    def test_all_existing_risk_bands_use_documented_notification_table(self):
        hazard = finding()
        for score, band, outcome, priority in (
            (19, "Low", "warning", "routine"),
            (20, "Moderate", "warning", "medium"),
            (40, "High", "alert", "high"),
            (70, "Critical", "alert", "urgent"),
        ):
            with self.subTest(band=band):
                decision = decide((hazard,), (scored(hazard, score, band),))
                self.assertEqual((decision.outcome, decision.risk_band, decision.priority), (outcome, band, priority))
                self.assertEqual(decision.policy_version, POLICY_VERSION)

    def test_multiple_findings_are_preserved_and_highest_band_wins(self):
        low = finding("no_mask", "missing_protective_mask", 0.8)
        high = finding()
        decision = decide((low, high), (scored(high, 40, "High"), scored(low, 19, "Low")))
        self.assertEqual((decision.outcome, decision.priority), ("alert", "high"))
        self.assertEqual(len(decision.supporting_evidence), 2)
        self.assertEqual({e.source_label for e in decision.supporting_evidence}, {"no_mask", "no_helmet"})
        self.assertIn("2 supported", decision.reason)

    def test_partial_multi_finding_is_pending_even_with_high_score(self):
        high = finding()
        other = finding("no_mask", "missing_protective_mask")
        decision = decide((high, other), (scored(high, 70, "Critical"),))
        self.assertEqual(decision.outcome, "pending")
        self.assertIsNone(decision.risk_band)

    def test_repeated_same_violation_keeps_both_evidence_items(self):
        first = finding(confidence=0.8)
        second = finding(confidence=0.9)
        decision = decide((first, second), (scored(second, 40, "High"), scored(first, 19, "Low")))
        self.assertEqual(decision.outcome, "alert")
        self.assertEqual(len(decision.supporting_evidence), 2)
        self.assertEqual(
            [(item.detection_confidence, item.risk_band) for item in decision.supporting_evidence],
            [(0.8, "Low"), (0.9, "High")],
        )

    def test_inconsistent_assessment_is_pending(self):
        hazard = finding()
        decision = decide((hazard,), (scored(hazard, 20, "Critical"),))
        self.assertEqual(decision.outcome, "pending")

    def test_reason_priority_and_evidence_are_deterministic(self):
        first = finding("no_mask", "missing_protective_mask", 0.8)
        second = finding()
        assessments = (scored(first, 19, "Low"), scored(second, 40, "High"))
        self.assertEqual(decide((first, second), assessments), decide((second, first), tuple(reversed(assessments))))

    def test_standard_and_experimental_entry_points_share_decision(self):
        observation = NormalizedObservation(
            "obs", datetime(2026, 1, 1, tzinfo=timezone.utc), "test", ("no_helmet",),
            people_count=2, duration_minutes=30, repeated_count=1,
        )
        standard = create_assessments(ObservationRequest(
            observation_id=observation.observation_id, timestamp=observation.timestamp,
            source=observation.source, labels=list(observation.labels), people_count=2,
            duration_minutes=30, repeated_count=1,
        ), db=None)
        experimental = assess_safety(DetectionResult(
            Path("image.png"), 100, 100, (Detection("NO-Hardhat", 0.9, (0, 0, 1, 1)),),
        ), observation)
        shared = decide_alert(experimental)
        self.assertEqual(standard.safety_decision.outcome, shared.outcome)
        self.assertEqual(standard.safety_decision.risk_band, shared.risk_band)
        self.assertEqual(standard.safety_decision.priority, shared.priority)
        self.assertEqual(standard.safety_decision.reason, shared.reason)
        self.assertEqual(standard.safety_decision.supporting_evidence[0].source_label, shared.supporting_evidence[0].source_label)


if __name__ == "__main__":
    unittest.main()
