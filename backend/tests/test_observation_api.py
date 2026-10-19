"""API tests for observation persistence, retrieval, and error handling."""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.database import get_db
from app.db_models import DetectedHazardRecord, Observation, RiskAssessment
from app.detector import BoundingBox, MockHazardDetector
from app.main import app, get_hazard_detector


TINY_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\xff\xd9"


class ObservationApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.mock_db = MagicMock()
        self.mock_db.get.return_value = None

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_post_assessments_persists_when_db_configured(self) -> None:
        app.dependency_overrides[get_db] = lambda: self.mock_db

        payload = {
            "observation_id": "test-obs-persist-1",
            "timestamp": "2026-03-15T12:00:00Z",
            "source": "api_test",
            "labels": ["no_helmet"],
            "people_count": 2,
            "duration_minutes": 30,
            "repeated_count": 1,
            "work_area": "Building-A",
            "detection_confidence": 0.95,
        }

        response = self.client.post("/assessments", json=payload)
        self.assertEqual(response.status_code, 200)

        # Verify observation was persisted into db
        self.mock_db.add.assert_called_once()
        self.mock_db.flush.assert_called_once()
        saved_obs = self.mock_db.add.call_args[0][0]
        self.assertEqual(saved_obs.observation_id, "test-obs-persist-1")
        self.assertEqual(saved_obs.work_area, "Building-A")
        self.assertEqual(len(saved_obs.detected_hazards), 1)
        self.assertEqual(saved_obs.detected_hazards[0].hazard_type, "missing_safety_helmet")
        self.assertEqual(len(saved_obs.detected_hazards[0].assessments), 1)
        self.assertEqual(saved_obs.detected_hazards[0].assessments[0].status, "completed")

    def test_post_image_assessments_persists_when_db_configured(self) -> None:
        mock_detector = MockHazardDetector(
            canned_boxes=[
                BoundingBox(class_name="Person", confidence=0.92),
                BoundingBox(class_name="NO-Hardhat", confidence=0.89),
            ]
        )
        app.dependency_overrides[get_hazard_detector] = lambda: mock_detector
        app.dependency_overrides[get_db] = lambda: self.mock_db

        response = self.client.post(
            "/assessments/image?observation_id=img-test-1&duration_minutes=45&repeated_count=2",
            content=TINY_JPEG,
            headers={"Content-Type": "image/jpeg"},
        )
        self.assertEqual(response.status_code, 200)

        self.mock_db.add.assert_called_once()
        saved_obs = self.mock_db.add.call_args[0][0]
        self.assertEqual(saved_obs.observation_id, "img-test-1")
        self.assertEqual(len(saved_obs.detected_hazards), 1)

    def test_database_failure_returns_500_and_does_not_claim_success(self) -> None:
        app.dependency_overrides[get_db] = lambda: self.mock_db
        self.mock_db.flush.side_effect = OperationalError(
            "connection to server at 'db.internal.net' (10.0.0.5) failed", {}, Exception()
        )

        payload = {
            "observation_id": "test-obs-fail-1",
            "timestamp": "2026-03-15T12:00:00Z",
            "source": "api_test",
            "labels": ["no_helmet"],
            "people_count": 2,
            "duration_minutes": 30,
            "repeated_count": 1,
        }

        response = self.client.post("/assessments", json=payload)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["detail"], "Database persistence failed")
        self.assertNotIn("db.internal.net", response.text)
        self.assertNotIn("10.0.0.5", response.text)

    def test_duplicate_observation_id_returns_409(self) -> None:
        app.dependency_overrides[get_db] = lambda: self.mock_db
        self.mock_db.get.return_value = Observation(
            observation_id="existing-id",
            observed_at=datetime.now(timezone.utc),
            source="test",
        )

        payload = {
            "observation_id": "existing-id",
            "timestamp": "2026-03-15T12:00:00Z",
            "source": "api_test",
            "labels": ["no_helmet"],
        }

        response = self.client.post("/assessments", json=payload)
        self.assertEqual(response.status_code, 409)
        self.assertIn("already exists", response.json()["detail"].lower())

    def test_get_observations_unconfigured_db_returns_503(self) -> None:
        # Default get_db returns None when DATABASE_URL is not set
        app.dependency_overrides[get_db] = lambda: None
        response = self.client.get("/observations")
        self.assertEqual(response.status_code, 503)
        self.assertIn("not configured", response.json()["detail"].lower())

    def test_get_observation_by_id_unconfigured_db_returns_503(self) -> None:
        app.dependency_overrides[get_db] = lambda: None
        response = self.client.get("/observations/some-obs-id")
        self.assertEqual(response.status_code, 503)
        self.assertIn("not configured", response.json()["detail"].lower())

    def test_get_observation_by_id_404_when_missing(self) -> None:
        app.dependency_overrides[get_db] = lambda: self.mock_db
        self.mock_db.execute.return_value.scalar_one_or_none.return_value = None

        response = self.client.get("/observations/missing-id")
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"].lower())

    def test_get_observation_by_id_success(self) -> None:
        app.dependency_overrides[get_db] = lambda: self.mock_db

        obs = Observation(
            observation_id="obs-found-1",
            observed_at=datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc),
            source="manual",
            work_area="Sector 3",
            people_count=4,
            duration_minutes=60,
            repeated_count=2,
        )
        hazard = DetectedHazardRecord(
            detected_hazard_id=101,
            hazard_type="missing_safety_helmet",
            source_label="no_helmet",
            detected_at=datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc),
        )
        assessment = RiskAssessment(
            assessment_id=201,
            assessment_version=1,
            status="completed",
            severity=5,
            likelihood=4,
            exposure=2,
            risk_score=40,
            risk_band="High",
            scoring_rule_version="milestone1-v1",
        )
        hazard.assessments.append(assessment)
        obs.detected_hazards.append(hazard)

        self.mock_db.execute.return_value.scalar_one_or_none.return_value = obs

        response = self.client.get("/observations/obs-found-1")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["observation_id"], "obs-found-1")
        self.assertEqual(data["work_area"], "Sector 3")
        self.assertEqual(len(data["detected_hazards"]), 1)
        self.assertEqual(data["detected_hazards"][0]["hazard_type"], "missing_safety_helmet")
        self.assertEqual(data["detected_hazards"][0]["assessments"][0]["risk_score"], 40)

    def test_list_observations_with_pagination(self) -> None:
        app.dependency_overrides[get_db] = lambda: self.mock_db

        obs1 = Observation(
            observation_id="obs-list-1",
            observed_at=datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc),
            source="site_cam",
        )
        obs2 = Observation(
            observation_id="obs-list-2",
            observed_at=datetime(2026, 3, 15, 11, 0, tzinfo=timezone.utc),
            source="site_cam",
        )
        self.mock_db.execute.return_value.scalars.return_value.all.return_value = [obs1, obs2]

        response = self.client.get("/observations?limit=2&offset=0")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["observation_id"], "obs-list-1")
        self.assertEqual(data[1]["observation_id"], "obs-list-2")

    def test_list_observations_invalid_pagination_rejected(self) -> None:
        app.dependency_overrides[get_db] = lambda: self.mock_db
        response = self.client.get("/observations?limit=0")
        self.assertEqual(response.status_code, 422)

        response = self.client.get("/observations?offset=-1")
        self.assertEqual(response.status_code, 422)

    def test_post_image_database_failure_returns_sanitized_500(self) -> None:
        mock_detector = MockHazardDetector(
            canned_boxes=[
                BoundingBox(class_name="Person", confidence=0.92),
                BoundingBox(class_name="NO-Hardhat", confidence=0.89),
            ]
        )
        app.dependency_overrides[get_hazard_detector] = lambda: mock_detector
        app.dependency_overrides[get_db] = lambda: self.mock_db
        self.mock_db.flush.side_effect = OperationalError(
            "FATAL: password authentication failed for user 'secret_user'", {}, Exception()
        )

        response = self.client.post(
            "/assessments/image?observation_id=img-test-fail-1",
            content=TINY_JPEG,
            headers={"Content-Type": "image/jpeg"},
        )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["detail"], "Database persistence failed")
        self.assertNotIn("secret_user", response.text)

    def test_get_observations_database_failure_returns_sanitized_500(self) -> None:
        app.dependency_overrides[get_db] = lambda: self.mock_db
        self.mock_db.execute.side_effect = OperationalError(
            "relation 'observations' does not exist at postgres://user:pass@host/db", {}, Exception()
        )

        response = self.client.get("/observations")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json()["detail"],
            "Failed to query observations from database",
        )
        self.assertNotIn("pass@host", response.text)

    def test_get_observation_by_id_database_failure_returns_sanitized_500(self) -> None:
        app.dependency_overrides[get_db] = lambda: self.mock_db
        self.mock_db.execute.side_effect = OperationalError(
            "SELECT * FROM observations WHERE id='obs-fail' failed: server closed connection", {}, Exception()
        )

        response = self.client.get("/observations/obs-fail")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json()["detail"],
            "Failed to query observation from database",
        )
        self.assertNotIn("server closed connection", response.text)


if __name__ == "__main__":
    unittest.main()
