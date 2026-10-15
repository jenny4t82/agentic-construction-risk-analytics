"""API tests using the same synthetic fixtures as the agent tests."""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.main import app


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_endpoint(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_assessments_reuse_agent_and_scoring(self) -> None:
        response = self.client.post(
            "/assessments",
            json={
                "observation_id": "synthetic-api-001",
                "timestamp": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
                "source": "synthetic_test_fixture",
                "labels": ["no_helmet"],
                "people_count": 2,
                "duration_minutes": 45,
                "repeated_count": 3,
                "detection_confidence": 0.91,
            },
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["observation_id"], "synthetic-api-001")
        self.assertEqual(len(result["detected_hazards"]), 1)
        self.assertEqual(result["pending_hazards"], [])
        self.assertEqual(result["assessments"][0]["risk_score"], 40)
        self.assertEqual(result["assessments"][0]["risk_band"], "High")

    def test_detected_hazard_is_pending_when_scoring_inputs_are_missing(self) -> None:
        response = self.client.post(
            "/assessments",
            json={
                "observation_id": "synthetic-api-004",
                "timestamp": "2026-01-01T00:00:00Z",
                "source": "synthetic_test_fixture",
                "labels": ["no_helmet"],
            },
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(len(result["detected_hazards"]), 1)
        self.assertEqual(result["assessments"], [])
        self.assertEqual(result["pending_hazards"], result["detected_hazards"])

    def test_unknown_labels_return_no_assessments(self) -> None:
        response = self.client.post(
            "/assessments",
            json={
                "observation_id": "synthetic-api-002",
                "timestamp": "2026-01-01T00:00:00Z",
                "source": "synthetic_test_fixture",
                "labels": ["unknown_label"],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["detected_hazards"], [])
        self.assertEqual(response.json()["assessments"], [])

    def test_invalid_observation_is_rejected(self) -> None:
        response = self.client.post(
            "/assessments",
            json={
                "observation_id": "synthetic-api-003",
                "timestamp": "2026-01-01T00:00:00Z",
                "source": "synthetic_test_fixture",
                "labels": [],
            },
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
