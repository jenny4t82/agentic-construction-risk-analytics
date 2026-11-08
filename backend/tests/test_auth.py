"""Persisted auth, token, and route authorization tests without PostgreSQL."""

import os
import hashlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).parents[1]))
os.environ["DATABASE_URL"] = ""

from app.auth import decode_access_token, hash_password, issue_access_token, verify_password
from app.bootstrap_admin import bootstrap_admin
from app.database import get_db
from app.db_models import Base, UserAccount
from app.main import app
from app.analytics import summarize_violation_records


class AuthApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.secret = patch.dict(os.environ, {"SAFESITE_JWT_SECRET": "test-secret-" * 4})
        self.secret.start()
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine, tables=[UserAccount.__table__])
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

        def test_db():
            with self.session_factory.begin() as session:
                yield session

        app.dependency_overrides[get_db] = test_db
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.engine.dispose()
        self.secret.stop()

    def _signup(self, email: str = "worker@example.com") -> dict:
        response = self.client.post(
            "/auth/signup",
            json={"email": email, "password": "correct horse battery staple"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def _token(self, email: str = "worker@example.com") -> str:
        response = self.client.post(
            "/auth/login",
            json={"email": email, "password": "correct horse battery staple"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["access_token"]

    def test_signup_persists_regular_user_and_hashes_password(self) -> None:
        payload = self._signup(" WORKER@EXAMPLE.COM ")
        self.assertEqual(payload["email"], "worker@example.com")
        self.assertEqual(payload["role"], "user")
        self.assertNotIn("password_hash", payload)
        with self.session_factory() as session:
            account = session.get(UserAccount, payload["user_id"])
            self.assertIsNotNone(account)
            self.assertNotEqual(account.password_hash, "correct horse battery staple")
            self.assertTrue(verify_password("correct horse battery staple", account.password_hash))
        self.assertEqual(self.client.post(
            "/auth/signup", json={"email": "worker@example.com", "password": "correct horse battery staple"}
        ).status_code, 409)
        self.assertEqual(self.client.post(
            "/auth/signup", json={
                "email": "other@example.com", "password": "correct horse battery staple", "role": "admin"
            }
        ).status_code, 422)

    def test_new_password_minimum_is_eight_characters(self) -> None:
        rejected = self.client.post(
            "/auth/signup", json={"email": "short@example.com", "password": "1234567"}
        )
        self.assertEqual(rejected.status_code, 422)
        for email, password in (("eight@example.com", "12345678"),
                                ("long@example.com", "longer password")):
            response = self.client.post(
                "/auth/signup", json={"email": email, "password": password}
            )
            self.assertEqual(response.status_code, 201, response.text)
            self.assertEqual(self.client.post(
                "/auth/login", json={"email": email, "password": password}
            ).status_code, 200)
        with self.assertRaisesRegex(ValueError, "at least 8"):
            hash_password("1234567")
        self.assertTrue(verify_password("12345678", hash_password("12345678")))

    def test_historical_short_password_can_still_log_in(self) -> None:
        password = "oldpass"
        salt = b"historical-salt!"
        digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
        with self.session_factory.begin() as session:
            session.add(UserAccount(
                email="legacy@example.com",
                password_hash=f"scrypt$16384$8$1${salt.hex()}${digest.hex()}",
                role="user", is_active=True,
            ))
        response = self.client.post(
            "/auth/login", json={"email": "legacy@example.com", "password": password}
        )
        self.assertEqual(response.status_code, 200, response.text)

    def test_login_and_token_authentication(self) -> None:
        user = self._signup()
        token = self._token()
        self.assertEqual(decode_access_token(token), user["user_id"])
        response = self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["role"], "user")

    def test_invalid_credentials_and_token_are_rejected(self) -> None:
        self._signup()
        self.assertEqual(self.client.post(
            "/auth/login", json={"email": "worker@example.com", "password": "wrong"}
        ).status_code, 401)
        self.assertEqual(self.client.post(
            "/auth/login", json={"email": "missing@example.com", "password": "wrong"}
        ).status_code, 401)
        self.assertEqual(self.client.get("/auth/me", headers={"Authorization": "Bearer invalid"}).status_code, 401)
        token = self._token()
        self.assertEqual(self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}x"}).status_code, 401)

    def test_unauthorized_safety_requests_and_regular_user_management_forbidden(self) -> None:
        self.assertEqual(self.client.get("/analytics/zones").status_code, 401)
        self.assertEqual(self.client.patch("/alerts/1/status", json={"status": "resolved"}).status_code, 401)
        self._signup()
        headers = {"Authorization": f"Bearer {self._token()}"}
        self.assertEqual(self.client.patch("/alerts/1/status", json={"status": "resolved"}, headers=headers).status_code, 403)
        self.assertEqual(self.client.post("/alerts/hazards/1", headers=headers).status_code, 403)
        self.assertEqual(self.client.patch("/auth/users/missing/role", json={"role": "admin"}, headers=headers).status_code, 403)

    def test_regular_user_can_read_zone_analytics(self) -> None:
        self._signup()
        headers = {"Authorization": f"Bearer {self._token()}"}
        with patch("app.main.get_safety_analytics", return_value=summarize_violation_records([])):
            response = self.client.get("/analytics/zones", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total_violations"], 0)

    def test_inactive_account_token_is_rejected(self) -> None:
        user = self._signup()
        token = self._token()
        with self.session_factory.begin() as session:
            session.get(UserAccount, user["user_id"]).is_active = False
        self.assertEqual(self.client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        ).status_code, 401)

    def test_operator_bootstrap_creates_admin_without_promoting_existing_user(self) -> None:
        with patch("app.bootstrap_admin.create_database_engine", return_value=self.engine), patch.object(
            self.engine, "dispose"
        ):
            with self.assertRaisesRegex(ValueError, "at least 8"):
                bootstrap_admin("short-admin@example.com", "1234567")
            eight = bootstrap_admin("eight-admin@example.com", "12345678")
            self.assertEqual(eight.role, "admin")
            admin = bootstrap_admin("FIRST@EXAMPLE.COM", "correct horse battery staple")
            self.assertEqual(admin.role, "admin")
            with self.assertRaisesRegex(ValueError, "already exists"):
                bootstrap_admin("first@example.com", "correct horse battery staple")
        with self.session_factory() as session:
            persisted = session.get(UserAccount, admin.user_id)
            self.assertEqual(persisted.role, "admin")

    def test_safety_officer_and_admin_can_manage_alerts(self) -> None:
        officer = self._signup("officer@example.com")
        admin = self._signup("admin@example.com")
        with self.session_factory.begin() as session:
            session.get(UserAccount, officer["user_id"]).role = "safety_officer"
            session.get(UserAccount, admin["user_id"]).role = "admin"
        with patch("app.main.update_alert_status", side_effect=LookupError("Alert not found")) as update:
            for email in ("officer@example.com", "admin@example.com"):
                headers = {"Authorization": f"Bearer {self._token(email)}"}
                response = self.client.patch("/alerts/99/status", json={"status": "acknowledged"}, headers=headers)
                self.assertEqual(response.status_code, 404, response.text)
            self.assertEqual(update.call_count, 2)
        admin_headers = {"Authorization": f"Bearer {self._token('admin@example.com')}"}
        response = self.client.patch(
            f"/auth/users/{officer['user_id']}/role", json={"role": "user"}, headers=admin_headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["role"], "user")
        self.assertEqual(self.client.patch(
            "/alerts/99/status", json={"status": "resolved"},
            headers={"Authorization": f"Bearer {self._token('officer@example.com')}"},
        ).status_code, 403)

    def test_pending_completion_requires_safety_manager_role(self) -> None:
        payload = {"people_count": 1, "duration_minutes": 30, "repeated_count": 0}
        url = "/assessments/999/complete"
        self.assertEqual(self.client.patch(url, json=payload).status_code, 401)
        self._signup("regular-completion@example.com")
        regular = {"Authorization": f"Bearer {self._token('regular-completion@example.com')}"}
        self.assertEqual(self.client.patch(url, json=payload, headers=regular).status_code, 403)

        for role in ("safety_officer", "admin"):
            email = f"{role}@completion.example.com"
            user = self._signup(email)
            with self.session_factory.begin() as session:
                session.get(UserAccount, user["user_id"]).role = role
            headers = {"Authorization": f"Bearer {self._token(email)}"}
            with patch("app.main.complete_pending_assessment", side_effect=LookupError("Assessment not found")):
                response = self.client.patch(url, json=payload, headers=headers)
            self.assertEqual(response.status_code, 404, response.text)

    def test_password_hash_and_expired_token(self) -> None:
        stored = hash_password("correct horse battery staple")
        self.assertFalse(verify_password("wrong password", stored))
        self.assertNotEqual(stored, hash_password("correct horse battery staple"))
        with patch("app.auth.time.time", return_value=100):
            token = issue_access_token("user-id")
        with patch("app.auth.time.time", return_value=3701):
            with self.assertRaises(HTTPException) as error:
                decode_access_token(token)
        self.assertEqual(error.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
