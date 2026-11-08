"""Focused work-area correction and filtered report regression tests."""

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parents[1]))
os.environ["DATABASE_URL"] = ""

from app.auth import get_current_user, require_safety_manager
from app.database import get_db
from app.db_models import Alert, DetectedHazardRecord, Observation, RiskAssessment
from app.main import app
from app.report_pdf import render_safety_report_pdf
from app.reporting import REPORT_DISCLAIMER, available_work_areas, summarize_report


NOW = datetime(2026, 11, 6, 10, tzinfo=timezone.utc)
USER = SimpleNamespace(user_id="officer-id", email="officer@safesite.local", role="safety_officer")


def observation(name, area, when, label="no_helmet", outcome="warning", hazard_id=1):
    record = Observation(
        observation_id=name, observed_at=when, source="api_test", work_area=area,
        raw_metadata={"safety_decision": {"outcome": outcome}},
    )
    if label:
        hazard = DetectedHazardRecord(
            detected_hazard_id=hazard_id, observation_id=name,
            hazard_type={"no_helmet": "missing_safety_helmet", "no_vest": "missing_safety_vest"}.get(label, "bad_type"),
            source_label=label, detection_confidence=0.72,
            detected_at=when,
        )
        hazard.assessments = [RiskAssessment(
            assessment_id=hazard_id + 100, assessment_version=1,
            status="pending" if outcome == "pending" else "completed",
            risk_band=None if outcome == "pending" else "Moderate",
            risk_score=None if outcome == "pending" else 18,
            scoring_rule_version="milestone1-v1",
        )]
        record.detected_hazards.append(hazard)
    return record


class ReportingTests(unittest.TestCase):
    def setUp(self):
        self.observations = [
            observation("a", "Zone A", NOW, hazard_id=1),
            observation("b", "Zone A", NOW + timedelta(hours=1), hazard_id=2),
            observation("c", "Zone B", NOW + timedelta(hours=2), "no_vest", "alert", 3),
            observation("d", "Zone C", NOW + timedelta(hours=3), "no_helmet", "pending", 4),
            observation("e", None, NOW + timedelta(hours=4), "no_helmet", "warning", 5),
            observation("f", "Zone A", NOW + timedelta(hours=5), "unsupported", "warning", 6),
        ]
        alert = Alert(
            alert_id=55, observation_id="c", detected_hazard_id=3,
            alert_type="PPE", message="Review", status="resolved", risk_band="High",
            created_at=NOW, acknowledged_at=NOW + timedelta(minutes=5),
            resolved_at=NOW + timedelta(minutes=10),
        )
        self.observations[2].alerts.append(alert)
        self.observations[2].detected_hazards[0].alerts.append(alert)

    def report(self, **kwargs):
        return summarize_report(
            self.observations, generated_by={"email": USER.email, "role": USER.role},
            generated_at=NOW, **kwargs,
        )

    def test_all_history_counts_scoped_persisted_evidence(self):
        result = self.report()
        self.assertEqual(result["summary"], {
            "total_observations": 6, "supported_ppe_findings": 5,
            "actionable_alerts": 1, "warnings": 4,
            "pending_assessments": 1, "resolved_alerts": 1,
        })
        self.assertEqual(result["risk_distribution"]["pending"], 1)
        self.assertEqual(result["risk_distribution"]["Moderate"], 4)
        self.assertEqual(result["decision_counts"]["alert"], 1)
        self.assertEqual(result["alert_status_counts"]["resolved"], 1)
        self.assertEqual(result["recurrence"][0]["observation_ids"], ["a", "b"])
        self.assertEqual(result["disclaimer"], REPORT_DISCLAIMER)

    def test_one_and_multiple_areas_are_exactly_filtered(self):
        one = self.report(scope="selected", work_areas=("Zone A",))
        two = self.report(scope="selected", work_areas=("Zone A", "Zone B"))
        self.assertEqual(one["summary"]["total_observations"], 3)
        self.assertEqual({row["observation_id"] for row in one["findings"]}, {"a", "b"})
        self.assertEqual(two["summary"]["total_observations"], 4)
        self.assertEqual({row["observation_id"] for row in two["findings"]}, {"a", "b", "c"})
        self.assertEqual(two["summary"]["actionable_alerts"], 1)
        self.assertEqual(two["highest_violation_work_areas"], ["Zone A"])
        self.assertIn({"work_area": "Zone B", "violation_count": 1, "most_common_violation": "missing_safety_vest"}, two["work_areas"])

    def test_named_area_without_findings_has_zero_area_metric(self):
        result = self.report(scope="selected", work_areas=("Zone C",))
        self.assertEqual(result["work_areas"][0]["work_area"], "Zone C")
        self.assertEqual(result["work_areas"][0]["violation_count"], 1)
        empty_finding = observation("plain", "Zone D", NOW, label=None, outcome="no_alert")
        self.observations.append(empty_finding)
        result = self.report(scope="selected", work_areas=("Zone D",))
        self.assertEqual(result["work_areas"], [{"work_area": "Zone D", "violation_count": 0, "most_common_violation": None}])

    def test_half_open_time_filter_and_empty_results(self):
        result = self.report(start=NOW + timedelta(hours=1), end=NOW + timedelta(hours=2))
        self.assertEqual(result["summary"]["total_observations"], 1)
        self.assertEqual(result["findings"][0]["observation_id"], "b")
        empty = self.report(start=NOW + timedelta(days=1))
        self.assertEqual(empty["summary"]["total_observations"], 0)
        self.assertEqual(empty["risk_distribution"]["pending"], 0)

    def test_unassigned_and_area_correction_affect_scope_and_recurrence(self):
        before = self.report(scope="selected", work_areas=("Zone A",))
        self.assertEqual(before["recurrence"][0]["observation_count"], 2)
        unassigned = self.report(scope="selected", include_unassigned=True)
        self.assertEqual({row["observation_id"] for row in unassigned["findings"]}, {"e"})
        self.observations[4].work_area = "Zone A"
        after = self.report(scope="selected", work_areas=("Zone A",))
        self.assertEqual(after["recurrence"][0]["observation_count"], 3)
        self.assertEqual(after["recurrence"][0]["observation_ids"], ["a", "b", "e"])
        self.assertEqual(self.report(scope="selected", include_unassigned=True)["summary"]["total_observations"], 0)

    def test_duplicate_hazard_rows_count_once_for_recurrence(self):
        extra = observation("a", "Zone A", NOW, hazard_id=9).detected_hazards[0]
        self.observations[0].detected_hazards.append(extra)
        result = self.report(scope="selected", work_areas=("Zone A",))
        self.assertEqual(result["summary"]["supported_ppe_findings"], 3)
        self.assertEqual(result["recurrence"][0]["observation_count"], 2)

    def test_available_names_exclude_unassigned_and_keep_case(self):
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = [" Zone A ", "zone a", None, "Unspecified", "Unknown"]
        self.assertEqual(available_work_areas(session), ["Zone A", "zone a"])

    def test_pdf_is_valid_and_uses_selected_report_payload(self):
        content = render_safety_report_pdf(self.report(scope="selected", work_areas=("Zone B",)))
        self.assertTrue(content.startswith(b"%PDF-"))
        self.assertGreater(len(content), 1000)


class ReportApiTests(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_db] = lambda: MagicMock()
        app.dependency_overrides[get_current_user] = lambda: USER
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    @patch("app.main.get_safety_report")
    def test_json_and_pdf_endpoints_require_auth_and_share_filters(self, get_report):
        result = summarize_report([], scope="selected", work_areas=("Zone A",), generated_by={"email": USER.email, "role": USER.role}, generated_at=NOW)
        get_report.return_value = result
        query = "?scope=selected&work_area=Zone+A"
        preview = self.client.get("/reports/safety" + query)
        pdf = self.client.get("/reports/safety.pdf" + query)
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.json()["scope"]["work_areas"], ["Zone A"])
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf.headers["content-type"], "application/pdf")
        self.assertTrue(pdf.content.startswith(b"%PDF-"))
        self.assertEqual(get_report.call_count, 2)
        app.dependency_overrides.pop(get_current_user)
        self.assertEqual(self.client.get("/reports/safety").status_code, 401)
        self.assertEqual(self.client.get("/reports/safety.pdf").status_code, 401)

    @patch("app.main.get_observation_record")
    def test_work_area_patch_trims_and_preserves_other_fields(self, get_record):
        record = observation("edit-me", None, NOW)
        record.people_count = 2
        record.repeated_count = 4
        old_metadata = dict(record.raw_metadata)
        database = MagicMock()
        database.execute.return_value.scalar_one_or_none.return_value = record
        app.dependency_overrides[get_db] = lambda: database
        app.dependency_overrides[require_safety_manager] = lambda: USER
        get_record.return_value = record
        response = self.client.patch("/observations/edit-me/work-area", json={"work_area": "  Zone A  "})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["work_area"], "Zone A")
        self.assertEqual(record.raw_metadata["work_area_changes"][0]["previous_work_area"], None)
        self.assertEqual(record.raw_metadata["work_area_changes"][0]["changed_by_email"], USER.email)
        self.assertEqual(record.raw_metadata["safety_decision"], old_metadata["safety_decision"])
        self.assertEqual(record.people_count, 2)
        self.assertEqual(record.repeated_count, 4)
        self.assertEqual(record.detected_hazards[0].assessments[0].risk_score, 18)
        database.commit.assert_called_once()
        self.assertEqual(self.client.patch("/observations/edit-me/work-area", json={"work_area": "  "}).status_code, 422)
        self.assertEqual(self.client.patch("/observations/edit-me/work-area", json={"work_area": "Unknown"}).status_code, 422)
        self.assertEqual(self.client.patch("/observations/edit-me/work-area", json={"work_area": "A" * 256}).status_code, 422)
        database.commit.assert_called_once()

    def test_patch_missing_and_regular_user_forbidden(self):
        database = MagicMock()
        database.execute.return_value.scalar_one_or_none.return_value = None
        app.dependency_overrides[get_db] = lambda: database
        app.dependency_overrides[require_safety_manager] = lambda: USER
        self.assertEqual(self.client.patch("/observations/missing/work-area", json={"work_area": "Zone A"}).status_code, 404)
        app.dependency_overrides.pop(require_safety_manager)
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role="user")
        self.assertEqual(self.client.patch("/observations/missing/work-area", json={"work_area": "Zone A"}).status_code, 403)

    @patch("app.main.get_observation_record")
    def test_admin_can_update(self, get_record):
        record = observation("admin-edit", "Zone B", NOW)
        database = MagicMock()
        database.execute.return_value.scalar_one_or_none.return_value = record
        app.dependency_overrides[get_db] = lambda: database
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(user_id="admin", email="admin@safesite.local", role="admin")
        get_record.return_value = record
        response = self.client.patch("/observations/admin-edit/work-area", json={"work_area": "Zone C"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["work_area"], "Zone C")


if __name__ == "__main__":
    unittest.main()
