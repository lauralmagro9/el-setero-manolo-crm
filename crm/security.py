"""Lock the `public` schema so only the backend can touch the data.

Supabase exposes `public` through its REST API and grants `anon` / `authenticated` full access
by default. The frontend only uses Supabase for login, so every table is closed to those roles:

* Row Level Security is enabled on every table (no policies = nobody but the owner and roles
  with BYPASSRLS, such as the `postgres` user the backend connects with).
* Privileges are revoked from the API roles. This is also what protects the SQL views, which run
  with their owner's rights and therefore ignore RLS.

Call `secure_public_schema` at the end of every migration that creates tables or views.
"""

from sqlalchemy import Connection, text

from .config import settings


def _quote(conn: Connection, name: str) -> str:
    """Return `name` quoted as a SQL identifier."""
    return conn.dialect.identifier_preparer.quote(name)


def _existing_api_roles(conn: Connection) -> list[str]:
    """Return the configured API roles that exist in this database (none on plain Postgres)."""
    wanted = list(settings.security.api_roles)
    found = set(conn.execute(
        text("SELECT rolname FROM pg_roles WHERE rolname = ANY(:names)"), {"names": wanted}
    ).scalars())
    return [name for name in wanted if name in found]


def _public_tables(conn: Connection) -> list[str]:
    """Return the names of every table in the `public` schema."""
    return list(conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")).scalars())


def secure_public_schema(conn: Connection) -> None:
    """Enable RLS on every public table and revoke the API roles' access (idempotent)."""
    for table in _public_tables(conn):
        conn.execute(text(f"ALTER TABLE public.{_quote(conn, table)} ENABLE ROW LEVEL SECURITY"))
    roles = ", ".join(_quote(conn, r) for r in _existing_api_roles(conn))
    if not roles:
        return
    for kind in ("TABLES", "SEQUENCES"):
        conn.execute(text(f"REVOKE ALL ON ALL {kind} IN SCHEMA public FROM {roles}"))
        # Objects created later by this role must not be granted either
        conn.execute(text(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON {kind} FROM {roles}"))


def unsecure_public_schema(conn: Connection) -> None:
    """Undo `secure_public_schema`: disable RLS and give Supabase's default grants back."""
    for table in _public_tables(conn):
        conn.execute(text(f"ALTER TABLE public.{_quote(conn, table)} DISABLE ROW LEVEL SECURITY"))
    roles = ", ".join(_quote(conn, r) for r in _existing_api_roles(conn))
    if not roles:
        return
    for kind in ("TABLES", "SEQUENCES"):
        conn.execute(text(f"GRANT ALL ON ALL {kind} IN SCHEMA public TO {roles}"))
        conn.execute(text(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON {kind} TO {roles}"))
