"""Optional integration tests for a disposable PostgreSQL test database."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

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
                "agent_workflow_runs",
            }.issubset(table_names)
        )

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


if __name__ == "__main__":
    unittest.main()
