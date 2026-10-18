"""Unit tests for database configuration without a live PostgreSQL server."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import SQLAlchemyError

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.database import (
    check_database_connection,
    create_database_engine,
    get_database_url,
)


class DatabaseConfigurationTests(unittest.TestCase):
    def test_database_url_is_read_from_environment(self) -> None:
        database_url = "postgresql+psycopg://test_user@localhost:5432/construction_risk_db"

        with patch.dict(os.environ, {"DATABASE_URL": database_url}):
            self.assertEqual(get_database_url(), database_url)

    def test_missing_database_url_is_rejected(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "DATABASE_URL is required"):
                get_database_url()

    def test_engine_uses_postgresql_psycopg_url_without_connecting(self) -> None:
        database_url = "postgresql+psycopg://test_user@localhost:5432/construction_risk_db"

        engine = create_database_engine(database_url)
        try:
            self.assertEqual(engine.url.drivername, "postgresql+psycopg")
            self.assertEqual(engine.url.database, "construction_risk_db")
        finally:
            engine.dispose()

    def test_connectivity_check_succeeds_with_mock_engine(self) -> None:
        engine = MagicMock()
        connection = engine.connect.return_value.__enter__.return_value

        self.assertTrue(check_database_connection(engine))
        connection.execute.assert_called_once()

    def test_connectivity_check_returns_false_for_database_error(self) -> None:
        engine = MagicMock()
        engine.connect.side_effect = SQLAlchemyError("database unavailable")

        self.assertFalse(check_database_connection(engine))


if __name__ == "__main__":
    unittest.main()
