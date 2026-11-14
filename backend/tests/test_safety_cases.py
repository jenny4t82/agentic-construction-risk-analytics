"""Isolated API tests for observation-grouped alert cases; no saved DB access."""

import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ["DATABASE_URL"] = ""
sys.path.insert(0, str(Path(__file__).parents[1]))

from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.database import get_db
from app.db_models import Alert, Base, DetectedHazardRecord, Observation, RiskAssessment
from app.main import app
from app.safety_cases import case_status, get_safety_case_alerts, group_safety_cases, list_safety_case_records


@compiles(JSONB, "sqlite")
def json_sqlite(_type, compiler, **kw):
    return "JSON"


@compiles(ARRAY, "sqlite")
def array_sqlite(_type, compiler, **kw):
    return "TEXT"


@compiles(BigInteger, "sqlite")
def bigint_sqlite(_type, compiler, **kw):
    return "INTEGER"


NOW = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)


def assessment(identifier: int, status: str = "completed", score: int | None = 60, band: str | None = "High"):
    return SimpleNamespace(assessment_id=identifier, assessment_version=1, status=status,
        severity=5 if score else None, likelihood=3 if score else None, exposure=4 if score else None,
        risk_score=score, risk_band=band, explanation=None, missing_inputs=None,
        scoring_rule_version="milestone2-v1", assessed_at=NOW if score else None, created_at=NOW)


def observation(identifier: str, area: str = "North", when: datetime = NOW, corrections=None):
    return SimpleNamespace(observation_id=identifier, observed_at=when, source="site_image",
        work_area=area, people_count=3, duration_minutes=10, repeated_count=1,
        detection_confidence=None, raw_metadata={"assessment_corrections": corrections or []},
        created_at=when, updated_at=when, detected_hazards=[])


def add_finding(obs, hazard_id: int, assessment_rows=None):
    rows = assessment_rows or [assessment(hazard_id)]
    hazard = SimpleNamespace(detected_hazard_id=hazard_id, hazard_type="missing_safety_helmet",
        source_label="no_helmet", detection_confidence=0.9, detected_at=obs.observed_at,
        detector_name="test", evidence={}, assessments=rows)
    obs.detected_hazards.append(hazard)
    return hazard


def alert(obs, hazard, identifier: int, status: str = "open", original_assessment=None):
    current = max(hazard.assessments, key=lambda item: item.assessment_version)
    return SimpleNamespace(alert_id=identifier, observation_id=obs.observation_id,
        detected_hazard_id=hazard.detected_hazard_id, assessment_id=(original_assessment or current).assessment_id,
        alert_type=hazard.hazard_type, message="Persisted historical alert", risk_band="High",
        status=status, recipient=None, created_at=obs.observed_at, acknowledged_at=None,
        resolved_at=None, dismissed_at=None, observation=obs, detected_hazard=hazard,
        assessment=original_assessment or current)


class SafetyCaseApiTests(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.user = SimpleNamespace(user_id="officer", role="safety_officer")
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_single_alert_maps_to_one_stable_case_and_preserves_summary(self):
        obs = observation("one-alert")
        hazard = add_finding(obs, 1)
        child = alert(obs, hazard, 11)
        with patch("app.main.list_safety_case_records", return_value=[child]):
            response = self.client.get("/safety-cases")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual((payload["total_cases"], payload["total_alerts"]), (1, 1))
        case = payload["items"][0]
        self.assertEqual(case["case_id"], "observation:one-alert")
        self.assertEqual(case["case_status"], "open")
        self.assertEqual(case["alert_status_counts"], {"open": 1, "acknowledged": 0, "resolved": 0, "dismissed": 0})
        self.assertEqual(case["overall_risk_score"], 60)
        self.assertEqual(case["findings"][0]["assessments"][0]["assessment_id"], 1)
        self.assertEqual(case["alerts"][0]["alert_id"], 11)
        self.assertEqual(case["evidence"], {"original_available": False, "annotated_available": False})
        self.db.commit.assert_not_called()
        self.db.add.assert_not_called()

    def test_multiple_child_states_never_summarize_as_fully_resolved(self):
        obs = observation("mixed-states")
        first = add_finding(obs, 1)
        second = add_finding(obs, 2)
        third = add_finding(obs, 3)
        children = [alert(obs, first, 11, "open"), alert(obs, second, 12, "resolved"),
                    alert(obs, third, 13, "dismissed")]
        with patch("app.main.list_safety_case_records", return_value=children):
            payload = self.client.get("/safety-cases").json()
        case = payload["items"][0]
        self.assertEqual(payload["total_cases"], 1)
        self.assertEqual(payload["total_alerts"], 3)
        self.assertEqual(case["case_status"], "open")
        self.assertEqual(case["alert_status_counts"], {"open": 1, "acknowledged": 0, "resolved": 1, "dismissed": 1})
        self.assertEqual(case["unresolved_alert_count"], 1)
        self.assertEqual([item["status"] for item in case["alerts"]], ["open", "resolved", "dismissed"])
        self.assertEqual(case_status([alert(obs, first, 11, "acknowledged"), alert(obs, second, 12, "resolved")]), "acknowledged")
        self.assertEqual(case_status([alert(obs, first, 11, "resolved"), alert(obs, second, 12, "dismissed")]), "mixed_closed")
        self.assertEqual(case_status([alert(obs, first, 11, "resolved"), alert(obs, second, 12, "resolved")]), "resolved")

    def test_case_filters_counts_sort_pagination_and_search_use_unique_cases(self):
        rows = []
        for index, (area, day, state) in enumerate((
            ("North", 10, "open"), ("South", 11, "resolved"), ("North", 12, "dismissed")), 1):
            obs = observation(f"obs-{index}", area, datetime(2026, 11, day, tzinfo=timezone.utc))
            h1 = add_finding(obs, index * 10)
            h2 = add_finding(obs, index * 10 + 1)
            rows.extend([alert(obs, h1, index * 10, state), alert(obs, h2, index * 10 + 1, state)])
        with patch("app.main.list_safety_case_records", return_value=rows), \
             patch("app.main.get_safety_case_alerts", side_effect=lambda _db, identifier: [
                 child for child in rows if child.observation_id == identifier
             ]):
            page = self.client.get("/safety-cases?limit=1&sort=oldest").json()
            self.assertEqual((page["total_cases"], page["total_alerts"], len(page["items"])), (3, 6, 1))
            self.assertEqual(page["items"][0]["observation_id"], "obs-1")
            self.assertEqual(len(self.client.get("/safety-cases?status=open&work_area=North").json()["items"]), 1)
            date_result = self.client.get("/safety-cases?start=2026-11-11T00:00:00Z&end=2026-11-13T00:00:00Z").json()
            self.assertEqual((date_result["total_cases"], date_result["total_alerts"]), (2, 4))
            search = self.client.get("/safety-cases?search=observation%3Aobs-2").json()
            self.assertEqual([case["observation_id"] for case in search["items"]], ["obs-2"])
            self.assertEqual(self.client.get("/safety-cases?search=%20%20%20").status_code, 422)
            detail = self.client.get("/safety-cases/obs-2")
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.json()["alert_count"], 2)
            self.assertEqual(self.client.get("/safety-cases/not-a-case").status_code, 404)

    def test_review_required_lineage_and_historical_alert_snapshot_are_retained(self):
        original = assessment(21, score=60, band="High")
        corrected = assessment(22, score=30, band="Moderate")
        corrected.assessment_version = 2
        audit = {"assessment_id": 21, "previous_values": {"people_count": 2},
                 "updated_values": {"people_count": 4}, "changed_by_user_id": "officer"}
        obs = observation("corrected", corrections=[audit])
        hazard = add_finding(obs, 2, [original, corrected])
        obs.raw_metadata["alert_correction_snapshots"] = {"77": {
            "assessment": {"assessment_id": 21, "status": "completed", "risk_score": 60, "risk_band": "High"},
            "decision": {"reason": "Original decision", "priority": "high", "policy_version": "v1"},
        }}
        child = alert(obs, hazard, 77, "resolved", original)
        with patch("app.main.get_safety_case_alerts", return_value=[child]):
            result = self.client.get("/safety-cases/corrected")
        self.assertEqual(result.status_code, 200, result.text)
        case = result.json()
        self.assertTrue(case["review_required"])
        self.assertEqual(case["case_status"], "resolved")
        self.assertEqual(case["alerts"][0]["risk_band"], "High")
        self.assertEqual(case["alerts"][0]["current_assessment"]["risk_band"], "Moderate")
        self.assertEqual(case["assessment_corrections"], [audit])
        self.assertEqual([row["assessment_id"] for row in case["findings"][0]["assessments"]], [21, 22])

    def test_case_reads_require_auth_and_do_not_change_legacy_lifecycle_contract(self):
        app.dependency_overrides.pop(get_current_user, None)
        client = TestClient(app)
        self.assertEqual(client.get("/safety-cases").status_code, 401)
        self.assertEqual(client.get("/safety-cases/obs").status_code, 401)

    def test_eager_case_queries_load_the_complete_observation_and_alert_graph(self):
        engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
        try:
            with Session(engine, expire_on_commit=False) as session:
                obs = Observation(observation_id="eager-case", observed_at=NOW, source="test",
                    work_area="North", raw_metadata={})
                hazard = DetectedHazardRecord(observation=obs, hazard_type="missing_safety_helmet",
                    source_label="no_helmet", evidence={})
                score = RiskAssessment(detected_hazard=hazard, assessment_version=1,
                    status="completed", severity=5, likelihood=3, exposure=4,
                    risk_score=60, risk_band="High", assessed_at=NOW,
                    scoring_rule_version="milestone2-v1")
                child = Alert(observation=obs, detected_hazard=hazard, assessment=score,
                    alert_type=hazard.hazard_type, message="test", risk_band="High", status="open")
                session.add_all([obs, hazard, score, child])
                session.commit()
                listing = list_safety_case_records(session)
                detail = get_safety_case_alerts(session, "eager-case")
                self.assertEqual([row.alert_id for row in listing], [child.alert_id])
                self.assertEqual([row.alert_id for row in detail], [child.alert_id])
                self.assertEqual(len(detail[0].observation.detected_hazards[0].assessments), 1)
        finally:
            Base.metadata.drop_all(engine)
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
