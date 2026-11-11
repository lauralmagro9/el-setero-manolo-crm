"""Tests for the address lookup endpoint."""

from crm.services import geocoding


class TestAddressEndpoint:
    """Tests for GET /api/geocoding/address."""

    def test_0_returns_the_parts(self, client, monkeypatch):
        """The endpoint returns city, province and country."""
        monkeypatch.setattr(geocoding, "_search", lambda query: [{"address": {"city": "Cádiz", "country": "España"}}])
        body = client.get("/api/geocoding/address", params={"q": "Plaza de España, Cádiz"}).json()
        assert body == {"city": "Cádiz", "region": None, "country": "España"}

    def test_1_requires_authentication(self, anonymous_client):
        """Like every /api route, it needs a token."""
        assert anonymous_client.get("/api/geocoding/address", params={"q": "x"}).status_code == 401
