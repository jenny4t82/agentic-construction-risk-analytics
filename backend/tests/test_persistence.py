"""Unit tests for observation and risk assessment persistence mapping."""

import sys
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.db_models import DetectedHazardRecord, Observation, RiskAssessment
from app.models import DetectedHazard, HazardAssessment
from app.persistence import (
    build_observation_bundle,
    get_observation_record,
    list_observation_records,
    persist_observation_bundle,
)


class PersistenceMappingUnitTests(unittest.TestCase):
    def test_completed_assessment_mapping(self) -> None:
        now = datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc)
        hazard = DetectedHazard(
            observation_id="obs-001",
            hazard_type="missing_safety_helmet",
            source_label="no_helmet",
            detection_confidence=0.92,
        )
        assessment = HazardAssessment(
            observation_id="obs-001",
            hazard_type="missing_safety_helmet",
            source_label="no_helmet",
            severity=5,
            likelihood=4,
            exposure=2,
            risk_score=40,
            risk_band="High",
            detection_confidence=0.92,
            explanation="no_helmet mapped to missing_safety_helmet. Severity=5, likelihood=4, exposure=2; score=40.",
        )

        obs_record = build_observation_bundle(
            observation_id="obs-001",
            timestamp=now,
            source="manual_test",
            work_area="Sector 7",
            people_count=3,
            duration_minutes=45,
            repeated_count=2,
            detection_confidence=0.92,
            detected_hazards=[hazard],
            assessments=[assessment],
            detector_name="MockDetector",
        )

        self.assertEqual(obs_record.observation_id, "obs-001")
        self.assertEqual(obs_record.observed_at, now)
        self.assertEqual(obs_record.work_area, "Sector 7")
        self.assertEqual(obs_record.people_count, 3)
        self.assertEqual(obs_record.duration_minutes, 45)
        self.assertEqual(obs_record.repeated_count, 2)
        self.assertEqual(obs_record.detection_confidence, Decimal("0.9200"))

        self.assertEqual(len(obs_record.detected_hazards), 1)
        h_rec = obs_record.detected_hazards[0]
        self.assertEqual(h_rec.hazard_type, "missing_safety_helmet")
        self.assertEqual(h_rec.source_label, "no_helmet")
        self.assertEqual(h_rec.detector_name, "MockDetector")

        self.assertEqual(len(h_rec.assessments), 1)
        a_rec = h_rec.assessments[0]
        self.assertEqual(a_rec.status, "completed")
        self.assertEqual(a_rec.assessment_version, 1)
        self.assertEqual(a_rec.severity, 5)
        self.assertEqual(a_rec.likelihood, 4)
        self.assertEqual(a_rec.exposure, 2)
        self.assertEqual(a_rec.risk_score, 40)
        self.assertEqual(a_rec.risk_band, "High")
        self.assertIsNone(a_rec.missing_inputs)
        self.assertIsNotNone(a_rec.assessed_at)

    def test_pending_assessment_mapping(self) -> None:
        now = datetime(2026, 3, 15, 11, 0, tzinfo=timezone.utc)
        hazard = DetectedHazard(
            observation_id="obs-002",
            hazard_type="missing_safety_vest",
            source_label="no_vest",
            detection_confidence=0.88,
        )

        obs_record = build_observation_bundle(
            observation_id="obs-002",
            timestamp=now,
            source="manual_test",
            work_area="Sector 2",
            people_count=1,
            duration_minutes=None,  # Missing duration
            repeated_count=None,   # Missing repetition
            detection_confidence=0.88,
            detected_hazards=[hazard],
            assessments=[],
            detector_name="YOLOv8HazardDetector",
        )

        self.assertEqual(len(obs_record.detected_hazards), 1)
        h_rec = obs_record.detected_hazards[0]
        self.assertEqual(len(h_rec.assessments), 1)

        a_rec = h_rec.assessments[0]
        # Strictly validates ck_risk_assessments_completion_fields constraint:
        # status='pending', risk_score is None, risk_band is None, assessed_at is None
        self.assertEqual(a_rec.status, "pending")
        self.assertIsNone(a_rec.risk_score)
        self.assertIsNone(a_rec.risk_band)
        self.assertIsNone(a_rec.assessed_at)
        self.assertEqual(a_rec.missing_inputs, ["duration_minutes", "repeated_count"])
        self.assertIn("duration_minutes", a_rec.explanation)

    def test_duplicate_observation_rejected_by_persist_bundle(self) -> None:
        session = MagicMock()
        session.get.return_value = Observation(
            observation_id="existing-obs",
            observed_at=datetime.now(timezone.utc),
            source="test",
        )

        with self.assertRaisesRegex(ValueError, "already exists"):
            persist_observation_bundle(
                session=session,
                observation_id="existing-obs",
                timestamp=datetime.now(timezone.utc),
                source="test",
            )

    def test_get_and_list_records_query_session(self) -> None:
        session = MagicMock()
        mock_obs = Observation(
            observation_id="obs-query-1",
            observed_at=datetime.now(timezone.utc),
            source="test",
        )

        session.execute.return_value.scalar_one_or_none.return_value = mock_obs
        result = get_observation_record(session, "obs-query-1")
        self.assertEqual(result.observation_id, "obs-query-1")

        session.execute.return_value.scalars.return_value.all.return_value = [mock_obs]
        records = list_observation_records(session, limit=10, offset=0)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].observation_id, "obs-query-1")

    def test_duplicate_hazard_type_and_source_label_mapping(self) -> None:
        """Regression test for two detected hazards sharing the same (hazard_type, source_label)."""
        now = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)
        hazard_1 = DetectedHazard(
            observation_id="obs-dup-001",
            hazard_type="missing_safety_helmet",
            source_label="no_helmet",
            detection_confidence=0.95,
        )
        hazard_2 = DetectedHazard(
            observation_id="obs-dup-001",
            hazard_type="missing_safety_helmet",
            source_label="no_helmet",
            detection_confidence=0.75,
        )
        assessment_1 = HazardAssessment(
            observation_id="obs-dup-001",
            hazard_type="missing_safety_helmet",
            source_label="no_helmet",
            severity=5,
            likelihood=3,
            exposure=2,
            risk_score=30,
            risk_band="Moderate",
            detection_confidence=0.95,
            explanation="Worker 1 without helmet; confidence 0.95",
        )
        assessment_2 = HazardAssessment(
            observation_id="obs-dup-001",
            hazard_type="missing_safety_helmet",
            source_label="no_helmet",
            severity=5,
            likelihood=3,
            exposure=2,
            risk_score=30,
            risk_band="Moderate",
            detection_confidence=0.75,
            explanation="Worker 2 without helmet; confidence 0.75",
        )

        obs_record = build_observation_bundle(
            observation_id="obs-dup-001",
            timestamp=now,
            source="site_camera",
            people_count=2,
            duration_minutes=30,
            repeated_count=1,
            detected_hazards=[hazard_1, hazard_2],
            assessments=[assessment_1, assessment_2],
        )

        self.assertEqual(len(obs_record.detected_hazards), 2)
        h1_rec, h2_rec = obs_record.detected_hazards

        self.assertEqual(h1_rec.detection_confidence, Decimal("0.9500"))
        self.assertEqual(len(h1_rec.assessments), 1)
        self.assertEqual(h1_rec.assessments[0].status, "completed")
        self.assertEqual(
            h1_rec.assessments[0].explanation,
            "Worker 1 without helmet; confidence 0.95",
        )

        self.assertEqual(h2_rec.detection_confidence, Decimal("0.7500"))
        self.assertEqual(len(h2_rec.assessments), 1)
        self.assertEqual(h2_rec.assessments[0].status, "completed")
        self.assertEqual(
            h2_rec.assessments[0].explanation,
            "Worker 2 without helmet; confidence 0.75",
        )

    def test_duplicate_hazard_pair_with_partial_completed_and_pending(self) -> None:
        """When one duplicate hazard has an assessment and another does not, one is completed and one is pending."""
        now = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)
        hazard_1 = DetectedHazard(
            observation_id="obs-dup-002",
            hazard_type="missing_safety_helmet",
            source_label="no_helmet",
            detection_confidence=0.90,
        )
        hazard_2 = DetectedHazard(
            observation_id="obs-dup-002",
            hazard_type="missing_safety_helmet",
            source_label="no_helmet",
            detection_confidence=0.70,
        )
        assessment_1 = HazardAssessment(
            observation_id="obs-dup-002",
            hazard_type="missing_safety_helmet",
            source_label="no_helmet",
            severity=5,
            likelihood=3,
            exposure=2,
            risk_score=30,
            risk_band="Moderate",
            detection_confidence=0.90,
            explanation="Worker 1 without helmet",
        )

        obs_record = build_observation_bundle(
            observation_id="obs-dup-002",
            timestamp=now,
            source="site_camera",
            people_count=None,
            duration_minutes=None,
            repeated_count=None,
            detected_hazards=[hazard_1, hazard_2],
            assessments=[assessment_1],
        )

        self.assertEqual(len(obs_record.detected_hazards), 2)
        h1_rec, h2_rec = obs_record.detected_hazards

        self.assertEqual(len(h1_rec.assessments), 1)
        self.assertEqual(h1_rec.assessments[0].status, "completed")
        self.assertEqual(h1_rec.assessments[0].explanation, "Worker 1 without helmet")

        self.assertEqual(len(h2_rec.assessments), 1)
        self.assertEqual(h2_rec.assessments[0].status, "pending")
        self.assertIsNone(h2_rec.assessments[0].risk_score)


if __name__ == "__main__":
    unittest.main()
