"""Database configuration and connectivity helpers.

This module intentionally does not create application tables. The engine is
created only when requested, so importing the FastAPI app does not require a
live database or a DATABASE_URL environment variable.
"""

import os
from typing import Optional

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker


DATABASE_URL_ENV = "DATABASE_URL"


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
