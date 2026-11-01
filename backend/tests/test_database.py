"""Automated tests for database connectivity, session lifecycle, and PostgreSQL driver support."""

import psycopg
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session

from app.core.config import Settings, get_settings
from app.core.database import Base, SessionLocal, engine, get_db


def test_default_development_sqlite_database():
    """Verify that SQLite remains the default local development database."""
    settings = get_settings()
    assert settings.DATABASE_URL.startswith("sqlite")
    assert engine.dialect.name == "sqlite"


def test_database_engine_connection():
    """Verify that SQLAlchemy engine connects successfully to SQLite and executes simple queries."""
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1")).scalar()
        assert result == 1


def test_session_lifecycle_and_dependency():
    """Verify that get_db dependency yields a healthy session and closes properly."""
    db_gen = get_db()
    session = next(db_gen)

    try:
        assert isinstance(session, Session)
        assert session.is_active
        result = session.execute(text("SELECT 1")).scalar()
        assert result == 1
    finally:
        # Exhaust generator to trigger finally: db.close() block
        with pytest.raises(StopIteration):
            next(db_gen)

    # Session should now be closed
    assert not session.is_active or session.get_transaction() is None


def test_declarative_base_metadata():
    """Verify that Base is a valid SQLAlchemy DeclarativeBase subclass with metadata."""
    assert issubclass(Base, DeclarativeBase)
    assert hasattr(Base, "metadata")
    assert Base.metadata is not None


def test_psycopg_driver_version():
    """Verify that psycopg 3.x is installed as the PostgreSQL driver."""
    assert psycopg.__version__.startswith("3.")


def test_postgresql_url_scheme_normalization():
    """Verify that PostgreSQL connection URLs are normalized to use postgresql+psycopg://."""
    # Test legacy postgres://
    legacy_pg = "postgres://usr:pwd@localhost:5432/eventprice_db"
    settings_legacy = Settings(DATABASE_URL=legacy_pg)
    assert settings_legacy.DATABASE_URL == "postgresql+psycopg://usr:pwd@localhost:5432/eventprice_db"

    # Test standard postgresql://
    standard_pg = "postgresql://usr:pwd@localhost:5432/eventprice_db"
    settings_standard = Settings(DATABASE_URL=standard_pg)
    assert settings_standard.DATABASE_URL == "postgresql+psycopg://usr:pwd@localhost:5432/eventprice_db"

    # Test explicit postgresql+psycopg://
    explicit_pg = "postgresql+psycopg://usr:pwd@localhost:5432/eventprice_db"
    settings_explicit = Settings(DATABASE_URL=explicit_pg)
    assert settings_explicit.DATABASE_URL == "postgresql+psycopg://usr:pwd@localhost:5432/eventprice_db"


def test_postgresql_engine_construction_with_psycopg_driver():
    """Verify that SQLAlchemy engine constructs successfully with postgresql+psycopg without a live server."""
    pg_url = "postgresql://event_admin:secure_pass@db.example.com:5432/eventprice_prod"
    settings = Settings(DATABASE_URL=pg_url)

    # Construct SQLAlchemy engine using normalized URL
    pg_engine = create_engine(settings.DATABASE_URL)

    # Verify engine dialect and driver binding
    assert pg_engine.dialect.name == "postgresql"
    assert pg_engine.dialect.driver == "psycopg"
    assert str(pg_engine.url).startswith("postgresql+psycopg://")
