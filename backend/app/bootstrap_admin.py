"""Operator-only first-admin creation: python -m backend.app.bootstrap_admin.

Requires DATABASE_URL and the applied user_accounts migration. Password is
entered via a hidden terminal prompt, never supplied in CLI arguments.
"""

import getpass
import sys

from .auth import find_user_by_email, hash_password, normalize_email
from .database import create_database_engine, create_session_factory
from .db_models import UserAccount


def bootstrap_admin(email: str, password: str) -> UserAccount:
    engine = create_database_engine()
    try:
        session_factory = create_session_factory(engine)
        with session_factory.begin() as session:
            normalized = normalize_email(email)
            if find_user_by_email(session, normalized) is not None:
                raise ValueError("Account already exists; bootstrap does not promote existing users")
            account = UserAccount(
                email=normalized, password_hash=hash_password(password),
                role="admin", is_active=True,
            )
            session.add(account)
            session.flush()
            return account
    finally:
        engine.dispose()


def main() -> int:
    try:
        email = input("Admin email: ")
        password = getpass.getpass("Admin password (8+ characters): ")
        account = bootstrap_admin(email, password)
    except (ValueError, RuntimeError) as error:
        print(f"Admin bootstrap failed: {error}", file=sys.stderr)
        return 1
    print(f"Created admin account: {account.email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
