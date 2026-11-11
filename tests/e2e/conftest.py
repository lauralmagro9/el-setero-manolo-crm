"""Fixtures of the e2e environment: wipe + seed the database, build the frontend, serve the app."""

import logging

import pytest

from crm.config import settings
from crm.db import get_engine, get_session

from tests.utils.seed import seed_demo
from tests.utils import e2e

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def e2e_engine():
    """Return an engine on the app database, after checking that it is a local one."""
    e2e.assert_local_database(settings.database.url)
    engine = get_engine(settings.database.url)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def e2e_app(e2e_engine):
    """Reset and seed the database, build the frontend and deploy the app; return its base URL.

    The app is left running (and the data in the database) once the tests end, so it can be used
    by hand; the next e2e run replaces it.
    """
    e2e.stop_previous_server()  # release the database before wiping it
    e2e.migrate_database()
    e2e.reset_database(e2e_engine)
    with get_session(e2e_engine) as session:
        assert seed_demo(session), "the seed must load into an empty database"
    logger.info("Seed data loaded")
    static_dir = e2e.build_frontend()
    e2e.start_server(static_dir)
    return e2e.base_url()
