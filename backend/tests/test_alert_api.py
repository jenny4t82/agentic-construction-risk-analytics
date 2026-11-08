"""Focused API tests for persisted alert history and lifecycle transitions."""

import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parents[1]))
os.environ["DATABASE_URL"] = ""

from app.db_models import Alert, DetectedHazardRecord, Observation, RiskAssessment
from app.database import get_db
from app.main import app
from app.auth import get_current_user, require_safety_manager


def make_alert() -> Alert:
    observation = Observation(
        observation_id="api-alert-001",
        observed_at=datetime(2026, 3, 15, tzinfo=timezone.utc),
        source="camera",
        work_area="Zone A",
    )
    hazard = DetectedHazardRecord(
        detected_hazard_id=7,
        hazard_type="missing_safety_helmet",
        source_label="no_helmet",
        detection_confidence=0.95,
        detected_at=observation.observed_at,
        evidence={
            "detections": [{"class_name": "NO-Hardhat"}],
            "finding_decision": {
                "reason": "High-risk supported PPE violation",
                "priority": "high",
                "policy_version": "milestone2-decision-v1-provisional",
            },
        },
    )
    assessment = RiskAssessment(
        assessment_id=8,
        assessment_version=1,
        status="completed",
        risk_score=40,
        risk_band="High",
    )
    return Alert(
        alert_id=9,
        observation_id=observation.observation_id,
        detected_hazard_id=hazard.detected_hazard_id,
        assessment_id=assessment.assessment_id,
        alert_type=hazard.hazard_type,
        message="Detected missing safety helmet.",
        risk_band="High",
        status="open",
        created_at=observation.observed_at,
        observation=observation,
        detected_hazard=hazard,
        assessment=assessment,
    )


class AlertApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = MagicMock()
        app.dependency_overrides[get_db] = lambda: self.session
        app.dependency_overrides[get_current_user] = lambda: object()
        app.dependency_overrides[require_safety_manager] = lambda: object()
        self.client = TestClient(app)
        self.alert = make_alert()

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    @patch("app.main.list_alert_records")
    def test_alert_history_includes_lineage(self, list_alerts: MagicMock) -> None:
        list_alerts.return_value = [self.alert]

        response = self.client.get("/alerts?status=open&observation_id=api-alert-001")

        self.assertEqual(response.status_code, 200)
        payload = response.json()[0]
        self.assertEqual(payload["status"], "open")
        self.assertEqual(payload["observation"]["work_area"], "Zone A")
        self.assertEqual(payload["violation"]["source_label"], "no_helmet")
        self.assertEqual(payload["assessment"]["risk_band"], "High")
        self.assertEqual(payload["decision_reason"], "High-risk supported PPE violation")
        self.assertEqual(payload["notification_priority"], "high")
        self.assertEqual(payload["decision_policy_version"], "milestone2-decision-v1-provisional")
        self.assertIsNone(payload["dismissed_at"])

    @patch("app.main.get_alert_record")
    def test_status_transition_returns_updated_alert(self, get_alert: MagicMock) -> None:
        get_alert.return_value = self.alert
        self.session.get.return_value = self.alert

        response = self.client.patch(
            "/alerts/9/status", json={"status": "acknowledged"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "acknowledged")
        self.assertIsNone(response.json()["dismissed_at"])

    @patch("app.main.get_alert_record")
    @patch("app.main.list_alert_records")
    def test_dismissed_at_in_status_detail_and_history(self, list_alerts: MagicMock, get_alert: MagicMock) -> None:
        get_alert.return_value = self.alert
        list_alerts.return_value = [self.alert]
        self.session.get.return_value = self.alert
        dismissed = self.client.patch("/alerts/9/status", json={"status": "dismissed"})
        self.assertEqual(dismissed.status_code, 200, dismissed.text)
        timestamp = dismissed.json()["dismissed_at"]
        self.assertIsNotNone(timestamp)
        self.assertIsNone(dismissed.json()["resolved_at"])
        self.assertEqual(self.client.get("/alerts/9").json()["dismissed_at"], timestamp)
        self.assertEqual(self.client.get("/alerts?status=dismissed").json()[0]["dismissed_at"], timestamp)

    def test_alert_routes_require_database(self) -> None:
        app.dependency_overrides.pop(get_db, None)
        client = TestClient(app)

        self.assertEqual(client.get("/alerts").status_code, 503)

    @patch("app.main.create_alert_for_hazard", side_effect=ValueError("Shared safety policy does not permit an actionable alert for this finding"))
    def test_manager_cannot_force_warning_or_pending_into_alert(self, create_alert: MagicMock) -> None:
        response = self.client.post("/alerts/hazards/7")
        self.assertEqual(response.status_code, 422)
        self.assertIn("does not permit", response.json()["detail"])
        create_alert.assert_called_once_with(self.session, 7)


if __name__ == "__main__":
    unittest.main()
