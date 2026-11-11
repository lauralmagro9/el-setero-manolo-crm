"""Tests that the public schema is closed to the Supabase API roles."""

from sqlalchemy import text

from crm.config import settings
from crm.security import secure_public_schema

TABLES_WITHOUT_RLS = """
    SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relkind = 'r' AND NOT c.relrowsecurity
"""
RELATIONS = """
    SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relkind IN ('r', 'v')
"""


def existing_roles(conn) -> list[str]:
    """Return the configured API roles that exist in the test database."""
    found = set(conn.execute(text("SELECT rolname FROM pg_roles")).scalars())
    return [r for r in settings.security.api_roles if r in found]


class TestSecurePublicSchema:
    """Tests for secure_public_schema."""

    def test_0_every_table_has_row_level_security(self, engine):
        """No table of the public schema may be left without RLS (also catches future tables)."""
        with engine.connect() as conn:
            assert conn.execute(text(TABLES_WITHOUT_RLS)).scalars().all() == []

    def test_1_api_roles_cannot_read_tables_or_views(self, engine):
        """anon and authenticated have no SELECT on any table or view, views included."""
        with engine.connect() as conn:
            roles = existing_roles(conn)
            names = conn.execute(text(RELATIONS)).scalars().all()
            assert "lot_stock" in names and "company" in names  # views and tables are both checked
            leaks = [
                (role, name) for role in roles for name in names
                if conn.execute(text("SELECT has_table_privilege(:r, :t, 'SELECT')"),
                                {"r": role, "t": f"public.{name}"}).scalar()
            ]
            assert leaks == []

    def test_2_is_idempotent(self, engine):
        """Running it again changes nothing and does not fail."""
        with engine.begin() as conn:
            secure_public_schema(conn)
            secure_public_schema(conn)
        with engine.connect() as conn:
            assert conn.execute(text(TABLES_WITHOUT_RLS)).scalars().all() == []

    def test_3_backend_role_still_reads_everything(self, engine):
        """The role the backend uses keeps working on tables and views despite RLS."""
        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM company")).scalar() == 0
            assert conn.execute(text("SELECT count(*) FROM lot_stock")).scalar() == 0
