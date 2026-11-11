"""Tests for the products endpoints."""

import uuid

from tests.utils.factories import make_product

NEW_PRODUCT = {"name": "Níscalos frescos", "species": "Lactarius deliciosus", "format": "Fresco", "target_net_margin": "0.25"}


class TestProducts:
    """Tests for /api/products."""

    def test_0_create_with_defaults(self, client):
        """Base unit and VAT default to the configured values."""
        response = client.post("/api/products", json=NEW_PRODUCT)
        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Níscalos frescos" and body["base_unit"] == "kg"
        assert float(body["tax_rate"]) == 0.10 and float(body["target_net_margin"]) == 0.25
        assert body["is_active"] is True

    def test_1_validation(self, client):
        """Margin and VAT must be fractions below 1, the format must be known and the name present."""
        assert client.post("/api/products", json={**NEW_PRODUCT, "target_net_margin": "1.2"}).status_code == 422
        assert client.post("/api/products", json={**NEW_PRODUCT, "tax_rate": "10"}).status_code == 422
        assert client.post("/api/products", json={**NEW_PRODUCT, "format": "Líquido"}).status_code == 422
        assert client.post("/api/products", json={**NEW_PRODUCT, "name": ""}).status_code == 422
        assert client.post("/api/products", json={k: v for k, v in NEW_PRODUCT.items() if k != "target_net_margin"}).status_code == 422

    def test_2_duplicate_name_is_409(self, client, session):
        """Two products cannot share a name."""
        make_product(session, "Níscalos frescos")
        assert client.post("/api/products", json=NEW_PRODUCT).status_code == 409

    def test_3_partial_update(self, client, session):
        """PATCH changes only what is sent and refuses nulls in required fields."""
        product = make_product(session, "Boletus")
        response = client.patch(f"/api/products/{product.id}", json={"species": "Boletus edulis"})
        assert response.status_code == 200
        assert response.json()["species"] == "Boletus edulis" and response.json()["name"] == "Boletus"
        assert client.patch(f"/api/products/{product.id}", json={"name": None}).status_code == 422

    def test_4_deactivated_products_leave_the_default_list(self, client, session):
        """Inactive products are hidden unless active_only=false is requested."""
        product = make_product(session, "Antiguo")
        make_product(session, "Vigente")
        client.patch(f"/api/products/{product.id}", json={"is_active": False})
        assert [p["name"] for p in client.get("/api/products").json()] == ["Vigente"]
        assert [p["name"] for p in client.get("/api/products", params={"active_only": False}).json()] == ["Antiguo", "Vigente"]

    def test_5_search_by_name_or_species(self, client, session):
        """The search matches the name and the species, ignoring case."""
        make_product(session, "Boletus edulis fresco", species="Boletus edulis")
        make_product(session, "Colmenilla", species="Morchella esculenta")
        names = lambda q: [p["name"] for p in client.get("/api/products", params={"search": q}).json()]
        assert names("BOLETUS") == ["Boletus edulis fresco"]
        assert names("morchella") == ["Colmenilla"]

    def test_6_get_one_and_unknown(self, client, session):
        """A product can be read by id; an unknown id is 404."""
        product = make_product(session)
        assert client.get(f"/api/products/{product.id}").json()["name"] == product.name
        assert client.get(f"/api/products/{uuid.uuid4()}").status_code == 404

    def test_7_requires_authentication(self, anonymous_client):
        """No token, no products."""
        assert anonymous_client.get("/api/products").status_code == 401
