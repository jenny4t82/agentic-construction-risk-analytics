"""Create or verify the three local SafeSite demo accounts.

Run with ``python -m backend.app.bootstrap_demo_accounts``. This helper targets
only a local PostgreSQL database named ``safesite_demo`` and never changes an
existing account's password, role, or active state.
"""

import os
import sys
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .auth import hash_password, verify_password
from .database import create_database_engine
from .db_models import UserAccount


DEMO_DATABASE_NAME = "safesite_demo"
DEMO_MIGRATION_HEAD = "0003_alert_dismissed_at"
DEMO_ACCOUNTS = (
    ("admin@safesite.demo", "admin", "SAFESITE_DEMO_ADMIN_PASSWORD"),
    ("officer@safesite.demo", "safety_officer", "SAFESITE_DEMO_OFFICER_PASSWORD"),
    ("user@safesite.demo", "user", "SAFESITE_DEMO_USER_PASSWORD"),
)


def local_demo_database_url() -> str:
    """Point the configured local PostgreSQL server at the preserved demo DB."""
    configured = os.getenv("DATABASE_URL")
    if not configured:
        raise ValueError("DATABASE_URL is required")
    url = make_url(configured)
    if url.get_backend_name() != "postgresql" or url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Demo setup requires a local PostgreSQL server")
    return url.set(database=DEMO_DATABASE_NAME).render_as_string(hide_password=False)


def ensure_demo_accounts(session: Session) -> tuple[int, int]:
    """Create missing demo identities; refuse to overwrite conflicting rows."""
    # Load private bootstrap settings explicitly, including when DATABASE_URL
    # was supplied externally. Ordinary backend startup never needs these secrets.
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
    accounts = []
    for email, role, variable in DEMO_ACCOUNTS:
        password = os.getenv(variable)
        if not password or len(password) < 8:
            raise ValueError(f"Configure {variable} with at least eight characters; no account was changed")
        accounts.append((email, role, password))
    created = 0
    existing = 0
    for email, role, password in accounts:
        account = session.scalar(select(UserAccount).where(UserAccount.email == email))
        if account is None:
            session.add(UserAccount(email=email, role=role, password_hash=hash_password(password), is_active=True))
            created += 1
        elif account.role != role or not account.is_active or not verify_password(password, account.password_hash):
            raise ValueError(f"Existing demo account {email} differs from the documented role, active state, or password; no account was changed")
        else:
            existing += 1
    session.flush()
    return created, existing


def main() -> int:
    try:
        engine = create_database_engine(local_demo_database_url())
        try:
            with Session(engine) as session:
                if session.execute(text("SELECT current_database()")).scalar_one() != DEMO_DATABASE_NAME:
                    raise ValueError("Connected database is not safesite_demo")
                if session.execute(text("SELECT version_num FROM alembic_version")).scalar_one() != DEMO_MIGRATION_HEAD:
                    raise ValueError(f"Demo database must be migrated to {DEMO_MIGRATION_HEAD}")
                created, existing = ensure_demo_accounts(session)
                session.commit()
        finally:
            engine.dispose()
    except SQLAlchemyError:
        print("Demo account setup failed: database operation failed; check private connection configuration", file=sys.stderr)
        return 1
    except ValueError as error:
        print(f"Demo account setup failed: {error}", file=sys.stderr)
        return 1
    print(f"Demo accounts ready in {DEMO_DATABASE_NAME}: {created} created, {existing} already matched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
