"""Phase 2 policy/persistence regression tests without a live PostgreSQL server."""

import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.analytics import summarize_violation_records
from app.db_models import Alert, DetectedHazardRecord, Observation
from app.main import ObservationDetailResponse, ObservationRequest, create_assessments
from app.models import DetectedHazard, HazardAssessment, NormalizedObservation
from app.persistence import (
    build_observation_bundle,
    create_alert_for_hazard,
    persist_observation_bundle,
    update_alert_status,
)
from app.safety_agent import Detection, DetectionResult, assess_safety, decide_alert


NOW = datetime(2026, 11, 4, tzinfo=timezone.utc)


def hazard(observation_id: str, label: str = "no_helmet") -> DetectedHazard:
    return DetectedHazard(
        observation_id, {
            "no_helmet": "missing_safety_helmet",
            "no_mask": "missing_protective_mask",
            "no_vest": "missing_safety_vest",
        }[label], label, 0.9,
    )


def scored(item: DetectedHazard, score: int, band: str) -> HazardAssessment:
    return HazardAssessment(
        item.observation_id, item.hazard_type, item.source_label,
        5, 4, 2, score, band, item.detection_confidence, "scored from inputs",
    )


def bundle(
    observation_id: str, findings: list[DetectedHazard],
    assessments: list[HazardAssessment], *, work_area: str = "North",
) -> Observation:
    return build_observation_bundle(
        observation_id=observation_id, timestamp=NOW, source="unit camera",
        work_area=work_area, detected_hazards=findings, assessments=assessments,
        raw_metadata={"image": {"detections": [{"class_name": "NO-Hardhat", "box": [1, 2, 3, 4]}]}},
    )


class AlertPolicyPersistenceTests(unittest.TestCase):
    def test_high_and_critical_create_actionable_alerts_with_lineage(self):
        for score, band, priority in ((40, "High", "high"), (70, "Critical", "urgent")):
            with self.subTest(band=band):
                item = hazard(f"obs-{band}")
                record = bundle(item.observation_id, [item], [scored(item, score, band)])
                self.assertEqual(record.raw_metadata["safety_decision"]["outcome"], "alert")
                self.assertEqual(len(record.alerts), 1)
                alert = record.alerts[0]
                self.assertEqual(alert.status, "open")
                self.assertEqual(alert.risk_band, band)
                self.assertIs(alert.detected_hazard, record.detected_hazards[0])
                self.assertIs(alert.assessment, record.detected_hazards[0].assessments[0])
                self.assertEqual(alert.detected_hazard.evidence["finding_decision"]["priority"], priority)
                self.assertIn("reason", alert.detected_hazard.evidence["finding_decision"])
                self.assertEqual(alert.detected_hazard.evidence["detections"][0]["box"], [1, 2, 3, 4])
                self.assertTrue(alert.deduplication_key.startswith("observation-violation:"))
                json.dumps(record.raw_metadata)
                json.dumps(alert.detected_hazard.evidence)

    def test_low_moderate_warning_persists_without_actionable_alert(self):
        for score, band in ((19, "Low"), (20, "Moderate")):
            with self.subTest(band=band):
                item = hazard(f"obs-{band}")
                record = bundle(item.observation_id, [item], [scored(item, score, band)])
                self.assertEqual(record.raw_metadata["safety_decision"]["outcome"], "warning")
                self.assertEqual(record.alerts, [])
                self.assertEqual(record.detected_hazards[0].assessments[0].status, "completed")
                self.assertEqual(record.detected_hazards[0].assessments[0].risk_band, band)
                history = ObservationDetailResponse.model_validate(record, from_attributes=True)
                self.assertEqual(history.raw_metadata["safety_decision"]["outcome"], "warning")
                self.assertEqual(history.detected_hazards[0].assessments[0].risk_band, band)

    def test_pending_and_no_alert_preserve_non_safe_outcomes(self):
        item = hazard("obs-pending")
        pending = bundle(item.observation_id, [item], [])
        self.assertEqual(pending.alerts, [])
        self.assertEqual(pending.raw_metadata["safety_decision"]["outcome"], "pending")
        self.assertEqual(pending.detected_hazards[0].assessments[0].status, "pending")
        self.assertIn("people_count", pending.detected_hazards[0].assessments[0].missing_inputs)
        pending_history = ObservationDetailResponse.model_validate(pending, from_attributes=True)
        self.assertEqual(pending_history.raw_metadata["safety_decision"]["outcome"], "pending")
        self.assertEqual(pending_history.detected_hazards[0].assessments[0].status, "pending")
        empty = bundle("obs-no-finding", [], [])
        self.assertEqual(empty.alerts, [])
        self.assertEqual(empty.detected_hazards, [])
        self.assertEqual(empty.raw_metadata["safety_decision"]["outcome"], "no_alert")
        self.assertIn("does not confirm site safety", empty.raw_metadata["safety_decision"]["reason"])

    def test_mixed_risk_alerts_only_alert_grade_findings(self):
        high = hazard("obs-mixed")
        low = hazard("obs-mixed", "no_mask")
        record = bundle("obs-mixed", [high, low], [scored(high, 40, "High"), scored(low, 19, "Low")])
        self.assertEqual(len(record.detected_hazards), 2)
        self.assertEqual(len(record.alerts), 1)
        self.assertEqual(record.alerts[0].alert_type, high.hazard_type)
        self.assertEqual(record.detected_hazards[1].evidence["finding_decision"]["outcome"], "warning")

    def test_partial_mixed_observation_stays_pending_even_with_high_score(self):
        high = hazard("obs-partial")
        unscored = hazard("obs-partial", "no_vest")
        record = bundle("obs-partial", [high, unscored], [scored(high, 40, "High")])
        self.assertEqual(record.raw_metadata["safety_decision"]["outcome"], "pending")
        self.assertEqual(record.alerts, [])
        self.assertEqual([a.assessments[0].status for a in record.detected_hazards], ["completed", "pending"])

    def test_warning_pending_history_remains_in_analytics_without_alert_rows(self):
        warning_hazard = hazard("obs-warning")
        pending_hazard = hazard("obs-pending", "no_mask")
        warning = bundle("obs-warning", [warning_hazard], [scored(warning_hazard, 20, "Moderate")], work_area="A")
        pending = bundle("obs-pending", [pending_hazard], [], work_area="B")
        records = [warning.detected_hazards[0], pending.detected_hazards[0]]
        for number, record in enumerate(records, 1):
            record.detected_hazard_id = number
            record.observation_id = record.observation.observation_id
        result = summarize_violation_records(records)
        self.assertEqual(result.total_violations, 2)
        self.assertEqual(result.risk_level_distribution["Moderate"], 1)
        self.assertEqual(result.risk_level_distribution["pending"], 1)
        self.assertEqual((result.open_alert_count, result.unresolved_alert_count), (0, 0))
        self.assertEqual({area.work_area for area in result.violations_by_work_area}, {"A", "B"})
        self.assertEqual(set(result.violations_by_work_area[0].observation_ids), {"obs-warning"})

    def test_manual_creation_is_guarded_and_existing_rows_are_idempotent(self):
        item = hazard("obs-manual")
        record = bundle(item.observation_id, [item], [scored(item, 40, "High")])
        persisted_hazard = record.detected_hazards[0]
        persisted_hazard.detected_hazard_id = 17
        persisted_hazard.observation_id = record.observation_id
        session = MagicMock()
        session.get.side_effect = lambda model, key: persisted_hazard if model is DetectedHazardRecord else record
        session.execute.return_value.scalar_one_or_none.return_value = None
        created, was_created = create_alert_for_hazard(session, 17)
        self.assertTrue(was_created)
        self.assertIs(created.detected_hazard, persisted_hazard)
        self.assertEqual(created.risk_band, "High")
        session.execute.return_value.scalar_one_or_none.return_value = created
        same, was_created = create_alert_for_hazard(session, 17)
        self.assertIs(same, created)
        self.assertFalse(was_created)
        session.add.assert_called_once()

    def test_manual_creation_rejects_warning_and_pending_but_preserves_legacy_alert(self):
        for score, band in ((20, "Moderate"), (None, None)):
            with self.subTest(band=band):
                item = hazard(f"obs-manual-{band}")
                assessments = [scored(item, score, band)] if score is not None else []
                record = bundle(item.observation_id, [item], assessments)
                persisted_hazard = record.detected_hazards[0]
                persisted_hazard.detected_hazard_id = 18
                persisted_hazard.observation_id = record.observation_id
                session = MagicMock()
                session.get.side_effect = lambda model, key: persisted_hazard if model is DetectedHazardRecord else record
                session.execute.return_value.scalar_one_or_none.return_value = None
                with self.assertRaisesRegex(ValueError, "does not permit an actionable alert"):
                    create_alert_for_hazard(session, 18)
                session.add.assert_not_called()
                legacy = Alert(alert_id=42, status="acknowledged")
                session.execute.return_value.scalar_one_or_none.return_value = legacy
                returned, created = create_alert_for_hazard(session, 18)
                self.assertIs(returned, legacy)
                self.assertFalse(created)
                self.assertEqual(returned.status, "acknowledged")

    def test_alert_lifecycle_still_acknowledges_and_resolves(self):
        alert = Alert(alert_id=1, status="open")
        session = MagicMock()
        session.get.return_value = alert
        update_alert_status(session, 1, "acknowledged")
        self.assertIsNotNone(alert.acknowledged_at)
        update_alert_status(session, 1, "resolved")
        self.assertIsNotNone(alert.resolved_at)
        self.assertEqual(alert.status, "resolved")

    def test_standard_persisted_and_experimental_decisions_match(self):
        request = ObservationRequest(
            observation_id="obs-parity", timestamp=NOW, source="test",
            labels=["no_helmet"], people_count=2, duration_minutes=30,
            repeated_count=3, detection_confidence=0.9,
        )
        session = MagicMock()
        session.get.return_value = None
        standard = create_assessments(request, db=session)
        persisted = session.add.call_args.args[0]
        observation = NormalizedObservation(
            "obs-parity", NOW, "test", ("no_helmet",), 2, 30, 3,
            detection_confidence=0.9,
        )
        experimental = decide_alert(assess_safety(DetectionResult(
            Path("image.jpg"), 100, 100, (Detection("NO-Hardhat", 0.9, (1, 2, 3, 4)),),
        ), observation))
        self.assertEqual(standard.safety_decision.outcome, "alert")
        self.assertEqual(standard.safety_decision.reason, experimental.reason)
        self.assertEqual(persisted.raw_metadata["safety_decision"]["reason"], experimental.reason)
        self.assertEqual(len(persisted.alerts), 1)


if __name__ == "__main__":
    unittest.main()
