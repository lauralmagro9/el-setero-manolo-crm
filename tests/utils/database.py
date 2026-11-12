"""Helpers to prepare the test database."""

from sqlalchemy import Engine, MetaData, create_engine, inspect, text
from sqlalchemy.engine import make_url


def reset_alembic_version(engine: Engine) -> None:
    """Set Alembic back to base (no revision) so the next `alembic upgrade head` rebuilds the schema.

    Call it after every `drop_all`: otherwise the tables are gone but `alembic_version` still says
    head, and the migration does nothing.
    """
    if inspect(engine).has_table("alembic_version"):
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM alembic_version"))


def drop_all_tables(engine: Engine, metadata: MetaData) -> None:
    """Drop every table in `metadata` and reset Alembic to base so the database can be rebuilt."""
    metadata.drop_all(engine)
    reset_alembic_version(engine)


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
