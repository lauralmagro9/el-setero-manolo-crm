"""Shared pytest fixtures."""

import pytest
from fastapi.testclient import TestClient

from crm import models as m
from crm.api import auth
from crm.api.app import create_app
from crm.config import settings
from crm.db import get_engine, get_session
from crm.security import secure_public_schema
from crm.services import transcription
from crm.views import create_views, drop_views

from tests.utils.auth import generate_key, make_token
from tests.utils.database import drop_all_tables, ensure_database
from tests.utils.llm import ScriptedLLM


def pytest_configure(config):
    """Abort the whole run when APP_ENVIRONMENT is the protected one (prod): tests wipe databases."""
    if settings.app.environment == settings.app.protected_environment:
        pytest.exit(
            f"Tests are blocked when APP_ENVIRONMENT={settings.app.environment!r}; "
            "run them with APP_ENVIRONMENT=dev",
            returncode=2,
        )


def pytest_collection_modifyitems(config, items):
    """List the e2e tests everywhere but skip them unless they were selected on purpose.

    They empty the app database, so running the whole suite (or "Run all" in the test explorer)
    must not trigger them: use `-m e2e`, the tests/e2e path or a single test's node id.
    """
    markexpr = config.getoption("markexpr") or ""
    args = [str(arg) for arg in config.args]
    skip_e2e = not ("e2e" in markexpr or any("e2e" in arg for arg in args))
    # The llm tests call the real model (tokens, network): same rule, `-m llm` or the tests/dev path
    skip_llm = not ("llm" in markexpr or any("dev" in arg.replace("\\", "/").split("/") for arg in args))
    for item in items:
        if skip_e2e and "e2e" in item.keywords:
            item.add_marker(pytest.mark.skip(
                reason="e2e wipes the database: run it with `pytest -m e2e` or select it explicitly"))
        if skip_llm and "llm" in item.keywords:
            item.add_marker(pytest.mark.skip(
                reason="calls the real model: run it with `pytest -m llm` or `pytest tests/dev`"))


@pytest.fixture
def engine():
    """Yield an engine on the test database with all tables and views, and clean it afterwards."""
    # Never the app database: drop_all would remove its tables and leave alembic_version at head
    ensure_database(settings.database.url)
    engine = get_engine(settings.database.url)
    # Start from a clean slate even if a previous run was interrupted
    with engine.begin() as conn:
        drop_views(conn)
    drop_all_tables(engine, m.Base.metadata)
    m.Base.metadata.create_all(engine)
    with engine.begin() as conn:
        create_views(conn)
        secure_public_schema(conn)
    yield engine
    with engine.begin() as conn:
        drop_views(conn)
    drop_all_tables(engine, m.Base.metadata)
    engine.dispose()


@pytest.fixture
def session(engine):
    """Yield a session on the test database."""
    with get_session(engine) as s:
        yield s


@pytest.fixture
def signing_key(monkeypatch):
    """Return a throw-away EC key and make the API trust it instead of Supabase's keys."""
    key = generate_key()
    monkeypatch.setattr(auth, "get_signing_key", lambda token, algorithm: key.public_key())
    return key


@pytest.fixture
def anonymous_client(engine, signing_key):
    """Return a test client of the API that sends no token."""
    return TestClient(create_app(engine))


@pytest.fixture
def client(anonymous_client, signing_key):
    """Return a test client of the API authenticated as laura@example.com."""
    anonymous_client.headers["Authorization"] = f"Bearer {make_token(signing_key)}"
    return anonymous_client


@pytest.fixture
def fake_transcription(monkeypatch):
    """Replace the Groq call with a stub; return the list of calls it receives."""
    calls = []

    def fake(data, mime_type):
        calls.append((data, mime_type))
        return "Pide tres kilos de boletus para mañana"

    monkeypatch.setattr(transcription, "transcribe_audio", fake)
    return calls


@pytest.fixture
def issuer(monkeypatch):
    """Configure the seller's data that invoices print."""
    data = settings.issuer.as_dict()
    monkeypatch.setitem(data, "name", "Manuel Test Titular")
    monkeypatch.setitem(data, "tax_id", "VDA00000000X")
    monkeypatch.setitem(data, "address", "Parauta (España)")


@pytest.fixture
def email_enabled(monkeypatch):
    """Turn invoice emailing on with a configured recipient."""
    data = settings.email.as_dict()
    monkeypatch.setitem(data, "enabled", True)
    monkeypatch.setitem(data, "invoice_recipient", "facturas@example.com")


@pytest.fixture
def sent_emails(monkeypatch):
    """Replace the SMTP sender with a stub; return the list of emails it receives."""
    from crm.services import invoices

    sent = []
    monkeypatch.setattr(invoices, "send_email", lambda **kwargs: sent.append(kwargs))
    return sent


@pytest.fixture
def toml_file(tmp_path):
    """Return the path of a small settings.toml written in a temporary folder."""
    SETTINGS_TOML = """
        [app]
        environment = "dev"
        allowed_environments = ["dev", "prod"]

        [database]
        url = "sqlite:///default.db"

        [services]
        groq_api = "from-toml"
        timeout = 30
        debug = false
        tags = ["a"]
    """
    path = tmp_path / "settings.toml"
    path.write_text(SETTINGS_TOML, encoding="utf8")
    return path


@pytest.fixture
def scripted_llm():
    """Return the ScriptedLLM class: build one with the replies the agent should receive."""
    return ScriptedLLM


@pytest.fixture
def groq_key(monkeypatch):
    """Pretend the Groq key is configured (no call is ever made: the agents get a scripted model)."""
    monkeypatch.setitem(settings.transcription.as_dict(), "api_key", "test-key")

