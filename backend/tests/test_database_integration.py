"""Optional integration tests for a disposable PostgreSQL test database."""

import os
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.database import create_database_engine


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


@unittest.skipUnless(
    TEST_DATABASE_URL,
    "set TEST_DATABASE_URL to run PostgreSQL integration tests",
)
class PostgreSQLIntegrationTests(unittest.TestCase):
    """Run migrations and inspect tables in an explicitly named test database."""

    @classmethod
    def setUpClass(cls) -> None:
        assert TEST_DATABASE_URL is not None
        cls.engine = create_database_engine(TEST_DATABASE_URL)
        alembic_config = Config(
            str(Path(__file__).parents[2] / "alembic.ini")
        )
        with patch.dict(os.environ, {"DATABASE_URL": TEST_DATABASE_URL}):
            command.upgrade(alembic_config, "head")

    @classmethod
    def tearDownClass(cls) -> None:
        alembic_config = Config(
            str(Path(__file__).parents[2] / "alembic.ini")
        )
        with patch.dict(os.environ, {"DATABASE_URL": TEST_DATABASE_URL or ""}):
            command.downgrade(alembic_config, "base")
        cls.engine.dispose()

    def test_initial_schema_tables_exist(self) -> None:
        table_names = set(inspect(self.engine).get_table_names())

        self.assertTrue(
            {
                "observations",
                "detected_hazards",
                "risk_assessments",
                "safety_recommendations",
                "alerts",
                "user_accounts",
                "agent_workflow_runs",
            }.issubset(table_names)
        )
        columns = {column["name"] for column in inspect(self.engine).get_columns("alerts")}
        self.assertIn("dismissed_at", columns)

    def test_image_route_persists_matching_hazard_confidences_and_evidence(self) -> None:
        from fastapi.testclient import TestClient
        from PIL import Image
        from app.auth import get_current_user
        from app.database import get_db
        from app.db_models import Observation
        from app.detector import BoundingBox, MockHazardDetector
        from app.main import app, get_hazard_detector

        image = BytesIO()
        Image.new("RGB", (4, 4), "white").save(image, format="PNG")
        detector = MockHazardDetector([
            BoundingBox(class_name="NO-Hardhat", confidence=0.61),
            BoundingBox(class_name="NO-Hardhat", confidence=0.73),
            BoundingBox(class_name="NO-Safety Vest", confidence=0.77),
            BoundingBox(class_name="Person", confidence=0.99),
        ])
        SessionLocal = sessionmaker(bind=self.engine)

        def disposable_db():
            with SessionLocal.begin() as session:
                yield session

        app.dependency_overrides[get_db] = disposable_db
        app.dependency_overrides[get_current_user] = lambda: object()
        app.dependency_overrides[get_hazard_detector] = lambda: detector
        try:
            with tempfile.TemporaryDirectory() as image_dir, patch(
                "app.image_storage.OBSERVATION_IMAGE_ROOT", Path(image_dir)
            ):
                response = TestClient(app).post(
                    "/assessments/image?observation_id=integration-confidence-001"
                    "&people_count=1&duration_minutes=20&repeated_count=0",
                    content=image.getvalue(), headers={"Content-Type": "image/png"},
                )
            self.assertEqual(response.status_code, 200, response.text)
            with SessionLocal() as session:
                observation = session.get(Observation, "integration-confidence-001")
                self.assertIsNotNone(observation)
                assert observation is not None
                expected = {"missing_safety_helmet": 0.73, "missing_safety_vest": 0.77}
                self.assertEqual(
                    {hazard.hazard_type: float(hazard.detection_confidence)
                     for hazard in observation.detected_hazards}, expected,
                )
                for hazard in observation.detected_hazards:
                    detections = hazard.evidence["detections"]
                    self.assertTrue(detections)
                    self.assertEqual(
                        max(box["confidence"] for box in detections),
                        expected[hazard.hazard_type],
                    )
                self.assertEqual(
                    len(observation.raw_metadata["image"]["detections"]), 4
                )
        finally:
            app.dependency_overrides.clear()

    def test_persist_and_retrieve_observation_bundle(self) -> None:
        from datetime import datetime, timezone
        from sqlalchemy.orm import sessionmaker
        from app.models import DetectedHazard, HazardAssessment
        from app.persistence import (
            get_observation_record,
            list_observation_records,
            persist_observation_bundle,
        )

        SessionLocal = sessionmaker(bind=self.engine)
        obs_id = "integration-obs-001"

        with SessionLocal() as session:
            with session.begin():
                hazard = DetectedHazard(
                    observation_id=obs_id,
                    hazard_type="missing_safety_helmet",
                    source_label="no_helmet",
                    detection_confidence=0.95,
                )
                assessment = HazardAssessment(
                    observation_id=obs_id,
                    hazard_type="missing_safety_helmet",
                    source_label="no_helmet",
                    severity=5,
                    likelihood=4,
                    exposure=2,
                    risk_score=40,
                    risk_band="High",
                    detection_confidence=0.95,
                    explanation="integration test",
                )
                persist_observation_bundle(
                    session=session,
                    observation_id=obs_id,
                    timestamp=datetime.now(timezone.utc),
                    source="integration_test",
                    work_area="Zone-A",
                    people_count=2,
                    duration_minutes=30,
                    repeated_count=1,
                    detection_confidence=0.95,
                    detected_hazards=[hazard],
                    assessments=[assessment],
                )

        with SessionLocal() as session:
            fetched = get_observation_record(session, obs_id)
            self.assertIsNotNone(fetched)
            assert fetched is not None
            self.assertEqual(fetched.observation_id, obs_id)
            self.assertEqual(len(fetched.detected_hazards), 1)
            self.assertEqual(fetched.detected_hazards[0].hazard_type, "missing_safety_helmet")
            self.assertEqual(len(fetched.detected_hazards[0].assessments), 1)
            self.assertEqual(fetched.detected_hazards[0].assessments[0].risk_score, 40)

            all_records = list_observation_records(session, limit=10, offset=0)
            self.assertTrue(any(r.observation_id == obs_id for r in all_records))

    def _completion_client(self, role: str = "safety_officer"):
        from fastapi.testclient import TestClient
        from app.auth import hash_password, issue_access_token
        from app.database import get_db
        from app.db_models import UserAccount
        from app.main import app

        SessionLocal = sessionmaker(bind=self.engine)
        user_id = str(uuid4())
        with SessionLocal.begin() as session:
            session.add(UserAccount(
                user_id=user_id, email=f"{user_id}@example.test",
                password_hash=hash_password("test-password"), role=role, is_active=True,
            ))

        def disposable_db():
            with SessionLocal.begin() as session:
                yield session

        app.dependency_overrides[get_db] = disposable_db
        self.addCleanup(app.dependency_overrides.clear)
        secret = patch.dict(os.environ, {"SAFESITE_JWT_SECRET": "test-secret-" * 4})
        secret.start()
        self.addCleanup(secret.stop)
        token = issue_access_token(user_id)
        return TestClient(app), {"Authorization": f"Bearer {token}"}, user_id

    def _seed_pending(self, labels, *, people_count=None, duration_minutes=None, repeated_count=None):
        from app.db_models import Observation
        from app.models import DetectedHazard
        from app.persistence import persist_observation_bundle
        from app.risk_agent import LABEL_TO_HAZARD

        observation_id = "phase6b-" + uuid4().hex
        with sessionmaker(bind=self.engine).begin() as session:
            record = persist_observation_bundle(
                session=session,
                observation_id=observation_id,
                timestamp=datetime.now(timezone.utc),
                source="phase6b-test",
                work_area="Completion Test Yard",
                people_count=people_count,
                duration_minutes=duration_minutes,
                repeated_count=repeated_count,
                detected_hazards=[DetectedHazard(
                    observation_id=observation_id,
                    hazard_type=LABEL_TO_HAZARD[label],
                    source_label=label,
                    detection_confidence=0.8,
                ) for label in labels],
                assessments=[],
                raw_metadata={"image": {"sha256": "original", "detections": [
                    {"class_name": {
                        "no_helmet": "NO-Hardhat",
                        "no_vest": "NO-Safety Vest",
                        "no_mask": "NO-Mask",
                    }[label], "confidence": 0.8, "box": [1, 2, 3, 4]}
                    for label in labels
                ]}},
            )
            ids = [hazard.assessments[0].assessment_id for hazard in record.detected_hazards]
        with sessionmaker(bind=self.engine)() as session:
            self.assertIsNotNone(session.get(Observation, observation_id))
        return observation_id, ids

    def test_pending_completion_warning_persists_context_audit_and_history(self) -> None:
        from app.db_models import Observation

        client, headers, user_id = self._completion_client()
        observation_id, [assessment_id] = self._seed_pending(
            ["no_mask"], people_count=1,
        )
        before_analytics = client.get("/analytics/zones", headers=headers).json()["risk_level_distribution"]
        response = client.patch(
            f"/assessments/{assessment_id}/complete",
            json={"duration_minutes": 10, "repeated_count": 0}, headers=headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["assessment_id"], assessment_id)
        self.assertEqual(body["safety_decision"]["outcome"], "warning")
        self.assertEqual(body["alert_ids"], [])
        self.assertEqual(body["assessment"]["status"], "completed")
        self.assertEqual(body["assessment"]["severity"], 2)
        self.assertEqual(body["assessment"]["risk_score"], 4)
        self.assertEqual(body["completion_audit"]["completed_by_user_id"], user_id)
        self.assertEqual(body["completion_audit"]["new_context"], {
            "duration_minutes": 10, "repeated_count": 0,
        })
        with sessionmaker(bind=self.engine)() as session:
            record = session.get(Observation, observation_id)
            self.assertEqual((record.people_count, record.duration_minutes, record.repeated_count), (1, 10, 0))
            self.assertEqual(record.raw_metadata["image"]["sha256"], "original")
            self.assertEqual(record.detected_hazards[0].evidence["detections"][0]["box"], [1, 2, 3, 4])
            self.assertEqual(record.raw_metadata["safety_decision"]["outcome"], "warning")
            self.assertIsNotNone(record.detected_hazards[0].assessments[0].assessed_at)
            self.assertEqual(len(record.alerts), 0)
        history = client.get(f"/observations/{observation_id}", headers=headers)
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual(history.json()["detected_hazards"][0]["assessments"][0]["status"], "completed")
        self.assertEqual(history.json()["raw_metadata"]["safety_decision"]["outcome"], "warning")
        after_analytics = client.get("/analytics/zones", headers=headers).json()["risk_level_distribution"]
        self.assertEqual(after_analytics["pending"], before_analytics["pending"] - 1)
        self.assertEqual(after_analytics["Low"], before_analytics["Low"] + 1)

    def test_pending_completion_alert_is_linked_and_second_request_conflicts(self) -> None:
        from app.db_models import Observation

        client, headers, _ = self._completion_client("admin")
        observation_id, [assessment_id] = self._seed_pending(["no_helmet"])
        payload = {"people_count": 2, "duration_minutes": 30, "repeated_count": 3}
        first = client.patch(f"/assessments/{assessment_id}/complete", json=payload, headers=headers)
        self.assertEqual(first.status_code, 200, first.text)
        body = first.json()
        self.assertEqual(body["safety_decision"]["outcome"], "alert")
        self.assertEqual(body["assessment"]["risk_band"], "High")
        self.assertEqual(body["assessment"]["risk_score"], 40)
        self.assertEqual(len(body["alert_ids"]), 1)
        self.assertEqual(body["alert_id"], body["alert_ids"][0])
        second = client.patch(f"/assessments/{assessment_id}/complete", json=payload, headers=headers)
        self.assertEqual(second.status_code, 409, second.text)
        self.assertEqual(second.json()["detail"]["code"], "assessment_already_completed")
        with sessionmaker(bind=self.engine)() as session:
            record = session.get(Observation, observation_id)
            self.assertEqual(len(record.detected_hazards), 1)
            self.assertEqual(len(record.detected_hazards[0].assessments), 1)
            self.assertEqual(len(record.alerts), 1)
            self.assertEqual(record.alerts[0].assessment_id, assessment_id)
            self.assertEqual(record.alerts[0].detected_hazard_id, record.detected_hazards[0].detected_hazard_id)

    def test_pending_completion_rejects_missing_conflicting_and_invalid_inputs(self) -> None:
        from app.db_models import Observation

        client, headers, _ = self._completion_client()
        observation_id, [assessment_id] = self._seed_pending(
            ["no_helmet"], people_count=2,
        )
        url = f"/assessments/{assessment_id}/complete"
        self.assertEqual(client.patch(url, json={}, headers=headers).status_code, 422)
        conflict = client.patch(url, json={
            "people_count": 9, "duration_minutes": 30, "repeated_count": 1,
        }, headers=headers)
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json()["detail"]["code"], "context_conflict")
        for invalid in ({"people_count": 0}, {"duration_minutes": 0},
                        {"repeated_count": -1}, {"severity": 5},
                        {"duration_minutes": "bad"}):
            self.assertEqual(client.patch(url, json=invalid, headers=headers).status_code, 422)
        self.assertEqual(client.patch("/assessments/99999999/complete", json={}, headers=headers).status_code, 404)
        with sessionmaker(bind=self.engine)() as session:
            record = session.get(Observation, observation_id)
            self.assertIsNone(record.duration_minutes)
            self.assertIsNone(record.repeated_count)
            self.assertEqual(record.detected_hazards[0].assessments[0].status, "pending")
            self.assertEqual(len(record.alerts), 0)

    def test_partial_observation_waits_for_last_finding_before_creating_alert(self) -> None:
        from app.db_models import Observation

        client, headers, _ = self._completion_client()
        observation_id, ids = self._seed_pending(["no_helmet", "no_vest"])
        first = client.patch(f"/assessments/{ids[0]}/complete", json={
            "people_count": 2, "duration_minutes": 30, "repeated_count": 3,
        }, headers=headers)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["safety_decision"]["outcome"], "pending")
        self.assertEqual(first.json()["alert_ids"], [])
        second = client.patch(f"/assessments/{ids[1]}/complete", json={}, headers=headers)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json()["safety_decision"]["outcome"], "alert")
        self.assertEqual(len(second.json()["alert_ids"]), 1)
        with sessionmaker(bind=self.engine)() as session:
            record = session.get(Observation, observation_id)
            self.assertEqual(len(record.alerts), 1)
            self.assertEqual(record.alerts[0].alert_type, "missing_safety_helmet")
            self.assertEqual(len(record.detected_hazards), 2)
            self.assertTrue(all(h.assessments[0].status == "completed" for h in record.detected_hazards))

    def test_pending_completion_preserves_historical_alert_without_duplication(self) -> None:
        from app.db_models import Alert, Observation

        client, headers, _ = self._completion_client()
        observation_id, [assessment_id] = self._seed_pending(["no_helmet"])
        with sessionmaker(bind=self.engine).begin() as session:
            observation = session.get(Observation, observation_id)
            hazard = observation.detected_hazards[0]
            legacy = Alert(
                observation_id=observation_id,
                detected_hazard_id=hazard.detected_hazard_id,
                assessment_id=assessment_id,
                alert_type=hazard.hazard_type,
                message="historical alert",
                status="acknowledged",
                acknowledged_at=datetime.now(timezone.utc),
            )
            session.add(legacy)
            session.flush()
            alert_id = legacy.alert_id
        response = client.patch(f"/assessments/{assessment_id}/complete", json={
            "people_count": 2, "duration_minutes": 30, "repeated_count": 3,
        }, headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["alert_id"], alert_id)
        with sessionmaker(bind=self.engine)() as session:
            record = session.get(Observation, observation_id)
            self.assertEqual(len(record.alerts), 1)
            self.assertEqual(record.alerts[0].status, "acknowledged")
            self.assertIsNotNone(record.alerts[0].acknowledged_at)

    def test_concurrent_completion_creates_one_alert(self) -> None:
        from app.db_models import Observation

        client, headers, _ = self._completion_client()
        observation_id, [assessment_id] = self._seed_pending(["no_helmet"])
        url = f"/assessments/{assessment_id}/complete"
        payload = {"people_count": 2, "duration_minutes": 30, "repeated_count": 3}
        with ThreadPoolExecutor(max_workers=2) as pool:
            requests = [pool.submit(client.patch, url, json=payload, headers=headers) for _ in range(2)]
            responses = [request.result() for request in requests]
        self.assertEqual(sorted(response.status_code for response in responses), [200, 409])
        self.assertEqual(next(response for response in responses if response.status_code == 409).json()["detail"]["code"], "assessment_already_completed")
        with sessionmaker(bind=self.engine)() as session:
            record = session.get(Observation, observation_id)
            self.assertEqual(len(record.alerts), 1)
            self.assertEqual(len(record.detected_hazards[0].assessments), 1)


if __name__ == "__main__":
    unittest.main()
