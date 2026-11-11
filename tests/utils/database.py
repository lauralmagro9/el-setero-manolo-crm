"""Helpers to prepare the test database."""

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def ensure_database(url: str) -> None:
    """Create the database named in `url` on its server if it does not exist yet."""
    if not url:
        raise RuntimeError("Set DATABASE_URL")
    target = make_url(url)
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": target.database}
            )
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    finally:
        admin.dispose()
