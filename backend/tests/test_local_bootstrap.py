"""Local account setup is scoped to safesite_local and preserves conflicts."""

import os
import secrets
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.auth import hash_password, verify_password
from app.bootstrap_local_accounts import LOCAL_ACCOUNTS, ensure_local_accounts, local_database_url, migration_head
from app.db_models import Base, UserAccount


class LocalBootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.passwords = {variable: secrets.token_urlsafe(24) for _, _, variable in LOCAL_ACCOUNTS}
        self.environment = patch.dict(os.environ, self.passwords)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine, tables=[UserAccount.__table__])

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_local_database_guard_and_current_migration_head(self) -> None:
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://local:local@127.0.0.1:5432/existing"}):
            self.assertEqual(local_database_url(), "postgresql://local:local@127.0.0.1:5432/safesite_local")
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://local:local@remote.example/existing"}):
            with self.assertRaisesRegex(ValueError, "local PostgreSQL"):
                local_database_url()
        self.assertEqual(migration_head(), "0003_alert_dismissed_at")

    def test_idempotent_accounts_and_roles(self) -> None:
        with Session(self.engine) as session:
            self.assertEqual(ensure_local_accounts(session), (3, 0))
            session.commit()
            self.assertEqual(ensure_local_accounts(session), (0, 3))
            session.commit()
            self.assertEqual(len(session.scalars(select(UserAccount)).all()), 3)
            for email, role, variable in LOCAL_ACCOUNTS:
                account = session.scalar(select(UserAccount).where(UserAccount.email == email))
                self.assertEqual(account.role, role)
                self.assertTrue(account.is_active)
                self.assertTrue(verify_password(self.passwords[variable], account.password_hash))

    def test_password_conflict_preserves_existing_hash(self) -> None:
        with Session(self.engine) as session:
            ensure_local_accounts(session)
            session.commit()
            account = session.scalar(select(UserAccount).where(UserAccount.role == "admin"))
            original = account.password_hash
            with patch.dict(os.environ, {LOCAL_ACCOUNTS[0][2]: secrets.token_urlsafe(24)}):
                with self.assertRaisesRegex(ValueError, "no account was changed"):
                    ensure_local_accounts(session)
            session.rollback()
            self.assertEqual(account.password_hash, original)

    def test_missing_secret_creates_no_accounts(self) -> None:
        variable = LOCAL_ACCOUNTS[-1][2]
        with patch.dict(os.environ, {variable: ""}), Session(self.engine) as session:
            with self.assertRaisesRegex(ValueError, variable):
                ensure_local_accounts(session)
            self.assertEqual(len(session.scalars(select(UserAccount)).all()), 0)

    def test_conflicting_existing_account_is_preserved(self) -> None:
        with Session(self.engine) as session:
            account = UserAccount(email="admin@safesite.local", role="user", password_hash=hash_password("DifferentLocal!2026"))
            session.add(account)
            session.commit()
            saved_hash = account.password_hash
            with self.assertRaisesRegex(ValueError, "no account was changed"):
                ensure_local_accounts(session)
            session.rollback()
            saved = session.scalar(select(UserAccount).where(UserAccount.email == account.email))
            self.assertEqual((saved.role, saved.password_hash), ("user", saved_hash))
            self.assertEqual(len(session.scalars(select(UserAccount)).all()), 1)


if __name__ == "__main__":
    unittest.main()
