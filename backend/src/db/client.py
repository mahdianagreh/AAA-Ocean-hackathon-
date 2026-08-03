"""
The one connection layer — everyone imports this instead of opening their own.

Per tasks/phase2/03-nizar.md §4: "Nobody opens their own connection. Two clients
means two sets of retry behaviour, two transaction assumptions, and two different
answers to the same question." Pulga's FastAPI app, Mahdi's model serving, and any
worker process all import `engine` / `get_session` / `session_scope` from here.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(REPO_ROOT / "backend" / ".env")

_DB_URL_ENV = "SUPABASE_DB_URL"


def _database_url() -> str:
    url = os.getenv(_DB_URL_ENV)
    if not url:
        raise RuntimeError(
            f"{_DB_URL_ENV} is not set in backend/.env. "
            "Copy the connection string from Supabase → Project Settings → Database."
        )
    # Force the psycopg3 driver explicitly — SQLAlchemy defaults bare "postgresql://"
    # to psycopg2, which isn't installed (this project standardizes on psycopg3).
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


# Module-level singleton — created once per process, on first import.
engine: Engine = create_engine(_database_url(), pool_pre_ping=True, future=True)
_SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_engine() -> Engine:
    """The one Engine everyone shares. Do not call create_engine() anywhere else."""
    return engine


def get_session() -> Session:
    """A new Session bound to the shared engine. Caller owns closing it — prefer
    `session_scope()` for anything that mutates data, so commit/rollback is automatic."""
    return _SessionLocal()


@contextmanager
def session_scope():
    """Transactional scope: commits on success, rolls back on any exception, always
    closes. Use this for every loader and every write path.

        with session_scope() as session:
            session.add(row)
    """
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
