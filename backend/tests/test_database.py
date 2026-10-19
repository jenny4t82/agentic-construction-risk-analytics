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
    get_engine,
    get_session_factory,
)


class DatabaseConfigurationTests(unittest.TestCase):
    def tearDown(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            get_engine()

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

    def test_get_engine_reuses_cached_instance_when_url_has_password(self) -> None:
        db_url_with_pass = "postgresql+psycopg://risk_admin:super_secret_p@ss_99@localhost:5432/risk_db"

        with patch.dict(os.environ, {"DATABASE_URL": db_url_with_pass}):
            engine_1 = get_engine()
            self.assertIsNotNone(engine_1)
            engine_2 = get_engine()
            self.assertIs(engine_1, engine_2)

            factory_1 = get_session_factory()
            self.assertIsNotNone(factory_1)
            factory_2 = get_session_factory()
            self.assertIs(factory_1, factory_2)

    def test_get_engine_recreates_and_disposes_previous_when_url_changes(self) -> None:
        url_1 = "postgresql+psycopg://user1:pass1@localhost:5432/db1"
        url_2 = "postgresql+psycopg://user2:pass2@localhost:5432/db2"

        with patch.dict(os.environ, {"DATABASE_URL": url_1}):
            engine_1 = get_engine()
            self.assertIsNotNone(engine_1)

        with patch.object(engine_1, "dispose", wraps=engine_1.dispose) as mock_dispose:
            with patch.dict(os.environ, {"DATABASE_URL": url_2}):
                engine_2 = get_engine()
                self.assertIsNotNone(engine_2)
                self.assertIsNot(engine_1, engine_2)
                mock_dispose.assert_called_once()

    def test_get_engine_returns_none_and_cleans_up_when_unset(self) -> None:
        url = "postgresql+psycopg://user:pass@localhost:5432/db"
        with patch.dict(os.environ, {"DATABASE_URL": url}):
            engine = get_engine()
            self.assertIsNotNone(engine)

        with patch.object(engine, "dispose", wraps=engine.dispose) as mock_dispose:
            with patch.dict(os.environ, {}, clear=True):
                self.assertIsNone(get_engine())
                mock_dispose.assert_called_once()
                self.assertIsNone(get_session_factory())


if __name__ == "__main__":
    unittest.main()
