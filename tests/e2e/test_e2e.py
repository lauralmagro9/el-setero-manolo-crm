"""Smoke tests of the locally deployed app (built frontend + API) on freshly seeded data."""

import httpx
import pytest
from sqlalchemy import func, select, text

from crm import models as m

pytestmark = pytest.mark.e2e


class TestDeployedApp:
    """The app answers once it is built and deployed."""

    def test_0_health(self, e2e_app):
        """The liveness probe answers."""
        assert httpx.get(f"{e2e_app}/health").json() == {"status": "ok"}

    def test_1_frontend_is_served(self, e2e_app):
        """The built frontend comes from the root and from client-side routes."""
        for path in ("/", "/empresas"):
            response = httpx.get(f"{e2e_app}{path}")
            assert response.status_code == 200 and 'id="root"' in response.text, path

    def test_2_api_requires_login(self, e2e_app):
        """The API refuses requests without a token."""
        assert httpx.get(f"{e2e_app}/api/companies").status_code == 401


class TestSeededDatabase:
    """The database holds the seed data and nothing else."""

    def test_0_seed_data_is_loaded(self, e2e_app, e2e_engine):
        """The demo companies, products and the reserved boletus stock are there."""
        with e2e_engine.connect() as conn:
            assert conn.scalar(select(func.count()).select_from(m.Company)) == 3
            assert conn.scalar(select(func.count()).select_from(m.Product)) == 3
            reserved = conn.scalar(text("SELECT reserved_quantity FROM lot_stock WHERE lot_code = 'BOL-001'"))
        assert reserved == 3

    def test_1_alembic_table_is_preserved(self, e2e_app, e2e_engine):
        """The wipe keeps the migration history."""
        with e2e_engine.connect() as conn:
            assert conn.scalar(text("SELECT count(*) FROM alembic_version")) == 1
