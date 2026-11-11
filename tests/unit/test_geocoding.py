"""Tests for the address lookup."""

from crm.services import geocoding

RESULT = [{"address": {
    "town": "Algeciras", "province": "Cádiz", "state": "Andalucía", "country": "España",
}}]


class TestParseAddress:
    """Tests for geocoding.parse_address."""

    def test_0_extracts_city_province_and_country(self, monkeypatch):
        """City, province and country come from the preferred keys of the result."""
        monkeypatch.setattr(geocoding, "_search", lambda query: RESULT)
        parts = geocoding.parse_address("Calle Mayor 1, Algeciras")
        assert (parts.city, parts.region, parts.country) == ("Algeciras", "Cádiz", "España")

    def test_1_unknown_address_gives_empty_fields(self, monkeypatch):
        """No match is not an error."""
        monkeypatch.setattr(geocoding, "_search", lambda query: [])
        parts = geocoding.parse_address("zzzz")
        assert (parts.city, parts.region, parts.country) == (None, None, None)

    def test_2_unreachable_server_gives_empty_fields(self, monkeypatch):
        """Network failures never break the form."""
        def fail(query):
            raise OSError("no network")
        monkeypatch.setattr(geocoding, "_search", fail)
        assert geocoding.parse_address("Calle Mayor 1").city is None

    def test_3_blank_query_is_not_searched(self, monkeypatch):
        """An empty address does not call the server."""
        def fail(query):
            raise AssertionError("must not be called")
        monkeypatch.setattr(geocoding, "_search", fail)
        assert geocoding.parse_address("   ").country is None
