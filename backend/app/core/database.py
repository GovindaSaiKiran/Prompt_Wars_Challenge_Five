"""Database engine, declarative base, session factory, and FastAPI dependencies."""

import logging
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

logger = logging.getLogger("eventprice.database")
settings = get_settings()


class Base(DeclarativeBase):
    """Reusable SQLAlchemy 2.x Declarative Base for all future entity models."""
    pass


# SQLite-specific connect args
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

# Create database engine
# pool_pre_ping tests connection liveness, critical for production PostgreSQL pools
engine: Engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=settings.DB_ECHO_LOG,
    future=True,
    pool_pre_ping=not settings.DATABASE_URL.startswith("sqlite"),
)

# Enable foreign key enforcement for SQLite
if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# Session factory bound to the engine
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI route dependency yielding a transactional database session."""
    db: Session = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

