"""Local demo account setup leaves existing identities untouched."""

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
from app.bootstrap_demo_accounts import DEMO_ACCOUNTS, ensure_demo_accounts, local_demo_database_url
from app.db_models import Base, UserAccount


class DemoBootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.passwords = {variable: secrets.token_urlsafe(24) for _, _, variable in DEMO_ACCOUNTS}
        self.environment = patch.dict(os.environ, self.passwords)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine, tables=[UserAccount.__table__])

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_local_database_guard(self) -> None:
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://demo:demo@127.0.0.1:5432/development"}):
            self.assertEqual(local_demo_database_url(), "postgresql://demo:demo@127.0.0.1:5432/safesite_demo")
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://demo:demo@remote.example/safesite_demo"}):
            with self.assertRaisesRegex(ValueError, "local PostgreSQL"):
                local_demo_database_url()

    def test_idempotent_accounts_and_roles(self) -> None:
        with Session(self.engine) as session:
            self.assertEqual(ensure_demo_accounts(session), (3, 0))
            session.commit()
            self.assertEqual(ensure_demo_accounts(session), (0, 3))
            session.commit()
            accounts = session.scalars(select(UserAccount)).all()
            self.assertEqual(len(accounts), 3)
            for email, role, variable in DEMO_ACCOUNTS:
                account = session.scalar(select(UserAccount).where(UserAccount.email == email))
                self.assertEqual(account.role, role)
                self.assertTrue(account.is_active)
                self.assertTrue(verify_password(self.passwords[variable], account.password_hash))

    def test_password_conflict_preserves_existing_hash(self) -> None:
        with Session(self.engine) as session:
            ensure_demo_accounts(session)
            session.commit()
            account = session.scalar(select(UserAccount).where(UserAccount.role == "admin"))
            original = account.password_hash
            with patch.dict(os.environ, {DEMO_ACCOUNTS[0][2]: secrets.token_urlsafe(24)}):
                with self.assertRaisesRegex(ValueError, "no account was changed"):
                    ensure_demo_accounts(session)
            session.rollback()
            self.assertEqual(account.password_hash, original)

    def test_missing_secret_creates_no_accounts(self) -> None:
        variable = DEMO_ACCOUNTS[-1][2]
        with patch.dict(os.environ, {variable: ""}), Session(self.engine) as session:
            with self.assertRaisesRegex(ValueError, variable):
                ensure_demo_accounts(session)
            self.assertEqual(len(session.scalars(select(UserAccount)).all()), 0)

    def test_conflicting_existing_account_is_preserved(self) -> None:
        with Session(self.engine) as session:
            account = UserAccount(email="admin@safesite.demo", role="user", password_hash=hash_password("DifferentDemo!2026"))
            session.add(account)
            session.commit()
            saved_hash = account.password_hash
            with self.assertRaisesRegex(ValueError, "no account was changed"):
                ensure_demo_accounts(session)
            session.rollback()
            saved = session.scalar(select(UserAccount).where(UserAccount.email == account.email))
            self.assertEqual((saved.role, saved.password_hash), ("user", saved_hash))
            self.assertEqual(len(session.scalars(select(UserAccount)).all()), 1)


if __name__ == "__main__":
    unittest.main()
