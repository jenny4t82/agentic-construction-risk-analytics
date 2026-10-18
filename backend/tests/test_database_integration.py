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


if __name__ == "__main__":
    unittest.main()
