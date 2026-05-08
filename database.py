"""
SQLAlchemy database setup for WarmPath Intelligence Service.

Uses SQLite by default (DATABASE_URL env var to override).
Sync engine simpler than async for SQLite.
"""

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./warmpath.db")

# connect_args only needed for SQLite (allows multi-thread access)
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,  # set to True to log all SQL statements
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a DB session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Safe to call multiple times (CREATE TABLE IF NOT EXISTS)."""
    # Import models so they are registered on Base.metadata before create_all
    import models.all_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    print("[database] Tables created (or already exist)")
