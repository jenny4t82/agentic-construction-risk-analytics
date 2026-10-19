"""Database configuration and connectivity helpers.

This module intentionally does not create application tables. The engine is
created only when requested, so importing the FastAPI app does not require a
live database or a DATABASE_URL environment variable.
"""

import os
from typing import Generator, Optional

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker


DATABASE_URL_ENV = "DATABASE_URL"

_cached_database_url: Optional[str] = None
_cached_engine: Optional[Engine] = None
_cached_session_factory: Optional[sessionmaker[Session]] = None


def get_engine() -> Optional[Engine]:
    """Return the cached Engine for the current DATABASE_URL, or None if unset."""
    global _cached_database_url, _cached_engine, _cached_session_factory
    url = os.getenv(DATABASE_URL_ENV)
    if not url:
        if _cached_engine is not None:
            _cached_engine.dispose()
        _cached_engine = None
        _cached_database_url = None
        _cached_session_factory = None
        return None

    if _cached_engine is not None and _cached_database_url == url:
        return _cached_engine

    if _cached_engine is not None:
        _cached_engine.dispose()

    _cached_engine = create_database_engine(url)
    _cached_database_url = url
    _cached_session_factory = None
    return _cached_engine


def get_session_factory() -> Optional[sessionmaker[Session]]:
    """Return the session factory for the current engine, or None if unset."""
    global _cached_session_factory
    engine = get_engine()
    if engine is None:
        _cached_session_factory = None
        return None
    if (
        _cached_session_factory is None
        or _cached_session_factory.kw.get("bind") != engine
    ):
        _cached_session_factory = create_session_factory(engine)
    return _cached_session_factory


def get_db() -> Generator[Optional[Session], None, None]:
    """FastAPI dependency yielding an active SQLAlchemy session when DATABASE_URL is configured.

    If DATABASE_URL is not set, yields None so stateless operations and lightweight unit tests
    run without requiring a database.
    When a live session is yielded, commits on successful block execution, rolls back on
    unhandled exceptions, and always closes the session cleanly.
    """
    url = os.getenv(DATABASE_URL_ENV)
    if not url:
        yield None
        return

    factory = get_session_factory()
    if factory is None:
        yield None
        return

    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_database_url() -> str:
    """Return the configured PostgreSQL URL or explain what is missing."""

    database_url = os.getenv(DATABASE_URL_ENV)
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is required; expected "
            "postgresql+psycopg://USER:PASSWORD@HOST:PORT/DBNAME"
        )
    return database_url


def create_database_engine(database_url: Optional[str] = None) -> Engine:
    """Create a SQLAlchemy engine without connecting or creating tables."""

    return create_engine(database_url or get_database_url())


def create_session_factory(
    engine: Optional[Engine] = None,
) -> sessionmaker[Session]:
    """Create a SQLAlchemy session factory without creating tables."""

    return sessionmaker(
        bind=engine or create_database_engine(),
        autoflush=False,
        expire_on_commit=False,
    )


def check_database_connection(engine: Optional[Engine] = None) -> bool:
    """Return whether a simple ``SELECT 1`` succeeds.

    An engine can be supplied so this check can be unit-tested without a live
    PostgreSQL server. When no engine is supplied, the configured engine is
    created and disposed within this function.
    """

    owns_engine = engine is None
    database_engine = engine or create_database_engine()
    try:
        with database_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False
    finally:
        if owns_engine:
            database_engine.dispose()
