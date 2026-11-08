"""Create or verify local development accounts in safesite_local only.

Run with ``python -m backend.app.bootstrap_local_accounts`` after applying
Alembic migrations. Existing accounts are never silently changed.
"""

import os
import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .auth import hash_password, verify_password
from .database import create_database_engine
from .db_models import UserAccount


LOCAL_DATABASE_NAME = "safesite_local"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCAL_ACCOUNTS = (
    ("admin@safesite.local", "admin", "SAFESITE_LOCAL_ADMIN_PASSWORD"),
    ("officer@safesite.local", "safety_officer", "SAFESITE_LOCAL_OFFICER_PASSWORD"),
    ("user@safesite.local", "user", "SAFESITE_LOCAL_USER_PASSWORD"),
)


def local_database_url() -> str:
    """Derive the named local database without changing the repository .env."""
    configured = os.getenv("DATABASE_URL")
    if not configured:
        raise ValueError("DATABASE_URL is required")
    url = make_url(configured)
    if url.get_backend_name() != "postgresql" or url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Local setup requires a local PostgreSQL server")
    return url.set(database=LOCAL_DATABASE_NAME).render_as_string(hide_password=False)


def migration_head() -> str:
    """Read the single current revision from the repository, not a fixed ID."""
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    heads = ScriptDirectory.from_config(config).get_heads()
    if len(heads) != 1:
        raise ValueError("Expected exactly one Alembic head for local setup")
    return heads[0]


def ensure_local_accounts(session: Session) -> tuple[int, int]:
    """Create missing local identities; refuse to overwrite conflicts."""
    # Load private bootstrap settings explicitly, including when DATABASE_URL
    # was supplied externally. Ordinary backend startup never needs these secrets.
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
    accounts = []
    for email, role, variable in LOCAL_ACCOUNTS:
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
            raise ValueError(f"Existing local account {email} differs from the documented role, active state, or password; no account was changed")
        else:
            existing += 1
    session.flush()
    return created, existing


def main() -> int:
    try:
        engine = create_database_engine(local_database_url())
        try:
            with Session(engine) as session:
                if session.execute(text("SELECT current_database()")).scalar_one() != LOCAL_DATABASE_NAME:
                    raise ValueError("Connected database is not safesite_local")
                if session.execute(text("SELECT version_num FROM alembic_version")).scalar_one() != migration_head():
                    raise ValueError("Local database must first be migrated to the repository head")
                created, existing = ensure_local_accounts(session)
                session.commit()
        finally:
            engine.dispose()
    except SQLAlchemyError:
        print("Local account setup failed: database operation failed; check private connection configuration", file=sys.stderr)
        return 1
    except ValueError as error:
        print(f"Local account setup failed: {error}", file=sys.stderr)
        return 1
    print(f"Local accounts ready in {LOCAL_DATABASE_NAME}: {created} created, {existing} already matched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
