"""Conexión a la base de datos (Postgres / Supabase). La URL sale de config.py (database.url / DATABASE_URL)."""

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import settings


def get_engine(url: str | None = None) -> Engine:
    """Create an engine for `url` (default: database.url from settings); fail if none is configured."""
    url = url or settings.database.url
    if not url:
        raise RuntimeError("Set DATABASE_URL (in .env or the environment)")
    return create_engine(url, pool_pre_ping=True)


def get_session(engine: Engine | None = None) -> Session:
    """Open a new session on `engine` (default: the configured database)."""
    return sessionmaker(engine or get_engine(), expire_on_commit=False)()
