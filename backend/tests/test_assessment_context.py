"""Phase 8.1A contracts with isolated SQLite data; never uses application databases.

SQLite verifies transactions and SQL filtering, but not PostgreSQL row locking.
"""
import os
import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ["DATABASE_URL"] = ""
sys.path.insert(0, str(Path(__file__).parents[1]))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, BigInteger, select, func
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.db_models import Base, Observation, DetectedHazardRecord, RiskAssessment, Alert, UserAccount
from app.auth import get_current_user
from app.main import app
from sqlalchemy.exc import SQLAlchemyError


@compiles(JSONB, "sqlite")
def json_sqlite(_type, compiler, **kw):
    return "JSON"


@compiles(ARRAY, "sqlite")
def array_sqlite(_type, compiler, **kw):
    return "TEXT"


@compiles(BigInteger, "sqlite")
def bigint_sqlite(_type, compiler, **kw):
    return "INTEGER"


class AssessmentContextTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, expire_on_commit=False)
        self.client = TestClient(app)
        self.user = UserAccount(user_id="officer", email="officer@example.test", role="safety_officer", is_active=True)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.now = datetime(2026, 11, 8, tzinfo=timezone.utc)
        self.obs = Observation(observation_id="mixed", observed_at=self.now, source="test", work_area="North",
                               people_count=1, duration_minutes=1, repeated_count=0, raw_metadata={})
        self.db.add(self.obs)
        self.assessments = []
        for i, (score, band) in enumerate(((10, "Low"), (None, None), (40, "High"))):
            hazard = DetectedHazardRecord(observation=self.obs, hazard_type="missing_safety_helmet", source_label="no_helmet")
            assessment = RiskAssessment(detected_hazard=hazard, assessment_version=1,
                status="pending" if score is None else "completed", severity=5 if score else None,
                likelihood=2 if score else None, exposure=1 if score else None, risk_score=score,
                risk_band=band, assessed_at=self.now if score else None, scoring_rule_version="milestone1-v1")
            self.db.add_all([hazard, assessment]); self.assessments.append(assessment)
        self.db.commit()

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close(); self.engine.dispose()

    def request(self, assessment=None, revision=0, **values):
        target = assessment or self.assessments[0]
        return self.client.patch(f"/assessments/{target.assessment_id}/context", json={
            "expected_revision": revision, "people_count": 10, "duration_minutes": 240,
            "repeated_count": 5, **values})

    def test_mixed_filters_counts_and_pagination(self):
        for band in ("All", "Low", "Pending", "High"):
            response = self.client.get(f"/observation-query?risk={band}&limit=1")
            self.assertEqual(response.status_code, 200, response.text)
            result = response.json()
            self.assertEqual(result["total"], 1)
            self.assertEqual(result["assessment_counts"]["Pending"], 1)
            self.assertEqual(result["items"][0]["assessment_counts"], {"Pending": 1, "Low": 1, "Moderate": 0, "High": 1, "Critical": 0})
        for band in ("Moderate", "Critical"):
            self.assertEqual(self.client.get(f"/observation-query?risk={band}").json()["total"], 0)
        result = self.client.get("/observation-query?offset=1").json()
        self.assertEqual(result["items"], [])
        self.assertEqual(result["assessment_counts"]["Pending"], 1)

    def test_multi_pending_completion_recovery_and_duplicate_protection(self):
        observation = Observation(observation_id="isolated-multi-pending", observed_at=self.now,
            source="test", raw_metadata={"evidence_marker": "preserve-original-and-overlay"})
        self.db.add(observation)
        targets = []
        for kind, label in (("missing_safety_helmet", "no_helmet"), ("missing_safety_vest", "no_vest")):
            hazard = DetectedHazardRecord(observation=observation, hazard_type=kind, source_label=label)
            assessment = RiskAssessment(detected_hazard=hazard, assessment_version=1,
                status="pending", scoring_rule_version="milestone1-v1")
            self.db.add_all([hazard, assessment])
            targets.append(assessment)
        self.db.commit()
        ids = [a.assessment_id for a in targets]
        payload = {"people_count": 12, "duration_minutes": 5, "repeated_count": 1}
        first = self.client.patch(f"/assessments/{ids[0]}/complete", json=payload)
        self.assertEqual(first.status_code, 200, first.text)
        confirmed = first.json()["assessment"]
        self.assertEqual(confirmed["risk_score"], 60)
        self.assertEqual(confirmed["risk_band"], "High")
        self.assertEqual(first.json()["safety_decision"]["outcome"], "pending")
        # Reload both snapshots: SQLite discards timezone offsets on round trip.
        self.db.expire_all()
        recovery = self.client.get("/observation-query?observation_id=isolated-multi-pending").json()["items"][0]
        self.assertEqual(recovery["assessment_counts"]["Pending"], 1)
        self.assertEqual(recovery["assessment_counts"]["High"], 1)
        count_before = self.db.scalar(select(func.count()).select_from(Alert))
        self.assertEqual(self.client.patch(f"/assessments/{ids[0]}/complete", json=payload).status_code, 409)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Alert)), count_before)
        second = self.client.patch(f"/assessments/{ids[1]}/complete", json={})
        self.assertEqual(second.status_code, 200, second.text)
        self.assertNotEqual(second.json()["safety_decision"]["outcome"], "pending")
        after = self.client.get("/observation-query?observation_id=isolated-multi-pending").json()["items"][0]
        self.assertEqual(after["assessment_counts"]["Pending"], 0)
        helmet = next(a for h in after["detected_hazards"] for a in h["assessments"] if a["assessment_id"] == ids[0])
        recovered_helmet = next(a for h in recovery["detected_hazards"] for a in h["assessments"] if a["assessment_id"] == ids[0])
        self.assertEqual(helmet, recovered_helmet)
        self.assertEqual(after["raw_metadata"]["evidence_marker"], "preserve-original-and-overlay")
        self.assertEqual(len(after["raw_metadata"]["assessment_completions"]), 2)
        alert_count = self.db.scalar(select(func.count()).select_from(Alert))
        self.assertEqual(self.client.patch(f"/assessments/{ids[1]}/complete", json={}).status_code, 409)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Alert)), alert_count)

    def test_dates_area_lookup_sort(self):
        self.db.add(Observation(observation_id="older", observed_at=self.now - timedelta(days=1), source="test", work_area="South"))
        self.db.commit()
        for query in ("work_area=North", "observation_id=mixed", "start=2026-11-08T00:00:00Z", "start=2026-11-08T00:00:00Z&end=2026-11-09T00:00:00Z"):
            self.assertEqual(self.client.get(f"/observation-query?{query}").json()["total"], 1)
        self.assertEqual(self.client.get("/observation-query?end=2026-11-08T00:00:00Z").json()["items"][0]["observation_id"], "older")
        self.assertEqual(self.client.get("/observation-query?sort=oldest&limit=1").json()["items"][0]["observation_id"], "older")
        self.assertEqual(self.client.get("/observation-query?sort=newest&limit=1").json()["items"][0]["observation_id"], "mixed")

    def test_correction_recalculation_audit_and_sibling_preservation(self):
        response = self.request()
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["assessment"]["risk_score"], 100)
        self.assertEqual(data["assessment"]["risk_band"], "Critical")
        self.assertEqual(data["revision"], 1)
        self.assertEqual(data["audit_history"][0]["previous_values"]["people_count"], 1)
        self.assertEqual(data["audit_history"][0]["changed_by_user_id"], "officer")
        self.assertEqual(self.assessments[1].status, "pending")
        self.assertEqual(self.assessments[2].risk_score, 40)
        self.assertEqual(self.obs.people_count, 1)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Alert)), 0)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Observation)), 1)
        self.assertEqual(self.request().status_code, 409)
        self.assertEqual(self.request(revision=1).json()["revision"], 1)  # no-op
        self.assertEqual(self.client.get(f"/assessments/{self.assessments[0].assessment_id}").json()["revision"], 1)

    def test_pending_completion_enables_alerts_once(self):
        self.request()
        response = self.request(self.assessments[1])
        self.assertEqual(response.status_code, 200, response.text)
        count = self.db.scalar(select(func.count()).select_from(Alert))
        self.assertEqual(count, 3)
        self.db.expire_all()
        state = self.client.get(f"/assessments/{self.assessments[0].assessment_id}").json()
        self.assertEqual(state["reconciliation"]["state"], "linked")
        self.assertEqual(len(state["reconciliation"]["alert_ids"]), 1)
        self.assertEqual(self.request(self.assessments[1]).status_code, 409)
        self.request(self.assessments[1], revision=1)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Alert)), count)
        self.assertEqual(self.client.get("/observation-query?risk=Pending").json()["total"], 0)

    def test_alert_preservation_and_serialized_original_snapshot(self):
        self.request(); self.request(self.assessments[1])
        target = self.assessments[0]
        alert = self.db.scalar(select(Alert).where(Alert.assessment_id == target.assessment_id))
        alert.status = "dismissed"; alert.dismissed_at = self.now
        self.db.commit()
        response = self.request(revision=1, people_count=1, duration_minutes=1, repeated_count=0)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["reconciliation"]["review_required"])
        self.assertEqual(alert.status, "dismissed")
        self.assertEqual(alert.risk_band, "Critical")
        result = self.client.get(f"/alerts/{alert.alert_id}")
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["assessment"]["risk_band"], "Critical")
        self.assertEqual(result.json()["current_assessment"]["risk_band"], "Low")
        self.assertTrue(result.json()["review_required"])

    def test_transaction_failure_rolls_back_context_score_and_audit(self):
        with patch("app.assessment_context.create_alert_for_hazard", side_effect=SQLAlchemyError("private connection information")):
            response = self.request(self.assessments[1])
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("private", response.text)
        self.db.expire_all()
        self.assertEqual(self.assessments[1].status, "pending")
        self.assertNotIn("assessment_corrections", self.obs.raw_metadata)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Alert)), 0)

    def test_repeated_corrections_preserve_every_alert_lifecycle_and_original_snapshot(self):
        self.request()
        self.request(self.assessments[1])
        target_id = self.assessments[0].assessment_id
        alert = self.db.scalar(select(Alert).where(Alert.assessment_id == target_id))
        alert_id = alert.alert_id
        for revision, status in enumerate(("open", "acknowledged", "resolved", "dismissed"), start=1):
            with self.subTest(status=status):
                alert.status = status
                alert.acknowledged_at = self.now if status != "open" else None
                alert.resolved_at = self.now if status == "resolved" else None
                alert.dismissed_at = self.now if status == "dismissed" else None
                self.db.commit()
                # Compare persisted values on both sides: SQLite drops tzinfo on reload.
                self.db.expire_all()
                before = self.client.get(f"/alerts/{alert_id}").json()
                values = {"people_count": 1, "duration_minutes": 1, "repeated_count": 0} if revision % 2 else {}
                result = self.request(revision=revision, **values)
                self.assertEqual(result.status_code, 200, result.text)
                self.db.expire_all()
                after = self.client.get(f"/alerts/{alert_id}").json()
                for field in ("alert_id", "assessment_id", "risk_band", "message", "status",
                              "created_at", "acknowledged_at", "resolved_at", "dismissed_at"):
                    self.assertEqual(after[field], before[field], field)
                self.assertEqual(after["assessment"]["risk_band"], "Critical")
                self.assertTrue(after["review_required"])
                audit = self.client.get(f"/assessments/{target_id}").json()
                self.assertEqual(len(audit["audit_history"]), revision + 1)
                self.assertEqual(audit["revision"], revision + 1)
                self.assertEqual(self.request(revision=revision).status_code, 409)
                self.assertEqual(self.db.scalar(select(func.count()).select_from(Alert)), 3)

    def test_latest_only_and_all_completed_risk_bands(self):
        hazard = self.assessments[1].detected_hazard
        self.db.add(RiskAssessment(detected_hazard=hazard, assessment_version=2, status="completed",
            severity=5, likelihood=5, exposure=4, risk_score=100, risk_band="Critical",
            assessed_at=self.now, scoring_rule_version="milestone1-v1"))
        self.assessments[0].risk_score = 20; self.assessments[0].risk_band = "Moderate"
        self.db.commit()
        self.assertEqual(self.client.get("/observation-query?risk=Pending").json()["total"], 0)
        for band in ("Moderate", "High", "Critical"):
            self.assertEqual(self.client.get(f"/observation-query?risk={band}").json()["total"], 1)
        self.assertEqual(self.request(self.assessments[1]).status_code, 409)

    def test_validation_auth_missing_and_lookup(self):
        for field, value in (("people_count", 0), ("duration_minutes", -1), ("repeated_count", -1), ("people_count", True), ("people_count", 1.5)):
            self.assertEqual(self.request(**{field: value}).status_code, 422)
        for query in ("risk=bad", "limit=0", "offset=-1", "sort=bad", "start=2026-11-08", "start=2026-11-09T00:00:00Z&end=2026-11-08T00:00:00Z"):
            self.assertEqual(self.client.get(f"/observation-query?{query}").status_code, 422)
        self.assertEqual(self.client.get("/assessments/9999").status_code, 404)
        self.assertEqual(self.client.get("/observations/mixed").status_code, 200)
        self.user.role = "user"
        self.assertEqual(self.request().status_code, 403)
        self.user.role = "admin"
        self.assertEqual(self.request().status_code, 200)
        app.dependency_overrides.pop(get_current_user)
        self.assertEqual(self.request().status_code, 401)
        self.assertEqual(self.client.get("/observation-query").status_code, 401)
        self.assertEqual(self.client.get("/assessments/1").status_code, 401)
