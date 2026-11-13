"""Fixtures of the tests that run the agents against the real language model."""

import pytest

from crm.config import settings
from crm.services.agents.llm import AgentLLM

from tests.utils.factories import make_company, make_contact, make_product


@pytest.fixture(scope="session")
def real_llm():
    """Return the real chat model; skip the test when AGENTS_API_KEY is not configured."""
    if not settings.agents.api_key:
        pytest.skip("Set AGENTS_API_KEY (in .env) to run the tests against the real model")
    return AgentLLM(settings.agents.api_key)


@pytest.fixture
def catalog(session):
    """Seed a small, unambiguous customer and product catalog; return its records by name.

    Customers: Alberto García (Restaurante X) and Marta López (Bar Y).
    Products: Rebozuelos frescos (also "chantarelas", "girolles") and Boletus edulis fresco ("ceps", "porcini").
    """
    restaurant = make_company(session, "Restaurante X")
    bar = make_company(session, "Bar Y")
    make_contact(session, restaurant, "Alberto", last_name="García")
    make_contact(session, bar, "Marta", last_name="López")
    make_product(session, "Rebozuelos frescos", species="Cantharellus cibarius", aliases=["chantarelas", "girolles"])
    make_product(session, "Boletus edulis fresco", species="Boletus edulis", aliases=["ceps", "porcini"])
    return {"Restaurante X": restaurant, "Bar Y": bar}
