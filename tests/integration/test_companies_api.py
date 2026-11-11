"""Tests for the companies and contacts endpoints."""

import uuid

from tests.utils.factories import make_company, make_contact

NEW_COMPANY = {"name": "Bar Sol", "roles": ["Cliente"], "type": ["restaurante"], "address": "Calle Sol 1, Cádiz"}


class TestCompanies:
    """Tests for /api/companies."""

    def test_0_create_and_get(self, client):
        """A created company can be read back with an empty contact list."""
        created = client.post("/api/companies", json=NEW_COMPANY)
        assert created.status_code == 201
        detail = client.get(f"/api/companies/{created.json()['id']}").json()
        assert detail["name"] == "Bar Sol"
        assert detail["contacts"] == []

    def test_1b_address_is_mandatory_on_creation(self, client):
        """A company cannot be created without an address (or with a blank one)."""
        without = {k: v for k, v in NEW_COMPANY.items() if k != "address"}
        assert client.post("/api/companies", json=without).status_code == 422
        assert client.post("/api/companies", json={**NEW_COMPANY, "address": "  "}).status_code in (201, 422)
        assert client.post("/api/companies", json={**NEW_COMPANY, "address": ""}).status_code == 422

    def test_1_invalid_enum_is_rejected(self, client):
        """An unknown role fails validation."""
        response = client.post("/api/companies", json={**NEW_COMPANY, "roles": ["Alien"]})
        assert response.status_code == 422

    def test_2_missing_company_is_404(self, client):
        """Asking for an unknown id returns 404."""
        assert client.get(f"/api/companies/{uuid.uuid4()}").status_code == 404

    def test_3_duplicate_tax_id_is_409(self, client):
        """Two companies cannot share a tax id."""
        client.post("/api/companies", json={**NEW_COMPANY, "tax_id": "B123"})
        response = client.post("/api/companies", json={**NEW_COMPANY, "name": "Otro", "tax_id": "B123"})
        assert response.status_code == 409

    def test_4_partial_update_keeps_other_fields(self, client, session):
        """PATCH changes only the fields sent."""
        company = make_company(session, city="Algeciras")
        response = client.patch(f"/api/companies/{company.id}", json={"name": "Nuevo nombre"})
        assert response.status_code == 200
        assert response.json()["name"] == "Nuevo nombre"
        assert response.json()["city"] == "Algeciras"

    def test_5_required_field_cannot_be_nulled(self, client, session):
        """Sending name: null is rejected."""
        company = make_company(session)
        assert client.patch(f"/api/companies/{company.id}", json={"name": None}).status_code == 422

    def test_6_search_and_filters(self, client, session):
        """Search, role, status and city filters narrow the listing."""
        make_company(session, "Restaurante El Faro", city="Algeciras", customer_status="Interesado")
        make_company(session, "Frutería La Huerta", city="La Línea", type=["frutería"])
        make_company(session, "Recolector Antonio", roles=["Proveedor"], customer_status=None,
                     supplier_status="Activo")
        names = lambda **p: sorted(c["name"] for c in client.get("/api/companies", params=p).json()["items"])
        assert names(search="faro") == ["Restaurante El Faro"]
        assert names(role="Proveedor") == ["Recolector Antonio"]
        assert names(type="frutería") == ["Frutería La Huerta"]
        assert names(customer_status="Interesado") == ["Restaurante El Faro"]
        assert names(city="la línea") == ["Frutería La Huerta"]
        assert len(names()) == 3

    def test_7_pagination(self, client, session):
        """page and page_size split the listing and report the total."""
        for i in range(5):
            make_company(session, f"Empresa {i}")
        body = client.get("/api/companies", params={"page": 2, "page_size": 2}).json()
        assert body["total"] == 5
        assert [c["name"] for c in body["items"]] == ["Empresa 2", "Empresa 3"]

    def test_8_change_customer_status(self, client, session):
        """The pipeline endpoint moves a company to another status."""
        company = make_company(session)
        response = client.put(f"/api/companies/{company.id}/customer-status",
                              json={"customer_status": "Muy interesado"})
        assert response.status_code == 200
        assert response.json()["customer_status"] == "Muy interesado"

    def test_9_detail_includes_contacts(self, client, session):
        """The company detail lists its contacts."""
        company = make_company(session)
        make_contact(session, company, "Marta")
        detail = client.get(f"/api/companies/{company.id}").json()
        assert [c["first_name"] for c in detail["contacts"]] == ["Marta"]

    def test_10_billing_address_defaults_to_the_address(self, client):
        """A company created without billing address bills to its normal address."""
        created = client.post("/api/companies", json={**NEW_COMPANY, "address": "Calle Sol 5, Cádiz"}).json()
        assert created["billing_address"] == "Calle Sol 5, Cádiz"
        other = client.post("/api/companies", json={
            **NEW_COMPANY, "name": "Otro", "address": "Calle Sol 5", "billing_address": "Calle Luna 2"}).json()
        assert other["billing_address"] == "Calle Luna 2"


class TestContacts:
    """Tests for /api/contacts."""

    def test_0_create_update_delete(self, client, session):
        """A contact goes through its whole life cycle."""
        company = make_company(session)
        created = client.post("/api/contacts", json={"company_id": str(company.id), "first_name": "Luis"})
        assert created.status_code == 201
        cid = created.json()["id"]
        assert created.json()["company"]["name"] == company.name
        updated = client.patch(f"/api/contacts/{cid}", json={"position": "Chef"})
        assert updated.json()["position"] == "Chef"
        assert client.delete(f"/api/contacts/{cid}").status_code == 204
        assert client.get(f"/api/contacts/{cid}").status_code == 404

    def test_1_unknown_company_is_404(self, client):
        """Creating a contact in a company that does not exist fails."""
        response = client.post("/api/contacts", json={"company_id": str(uuid.uuid4()), "first_name": "X"})
        assert response.status_code == 404

    def test_2_only_one_primary_contact(self, client, session):
        """Marking a contact as primary unmarks the previous one."""
        company = make_company(session)
        first = make_contact(session, company, "Ana", is_primary=True)
        client.post("/api/contacts", json={"company_id": str(company.id), "first_name": "Bea", "is_primary": True})
        assert client.get(f"/api/contacts/{first.id}").json()["is_primary"] is False

    def test_3_list_by_company_and_search(self, client, session):
        """Listing can be limited to one company and searched by name."""
        a, b = make_company(session, "A"), make_company(session, "B")
        make_contact(session, a, "Ana")
        make_contact(session, b, "Bruno")
        by_company = client.get("/api/contacts", params={"company_id": str(a.id)}).json()
        assert [c["first_name"] for c in by_company["items"]] == ["Ana"]
        by_search = client.get("/api/contacts", params={"search": "brun"}).json()
        assert [c["first_name"] for c in by_search["items"]] == ["Bruno"]
        nested = client.get(f"/api/companies/{b.id}/contacts").json()
        assert [c["first_name"] for c in nested] == ["Bruno"]

    def test_4_delete_detaches_interactions(self, client, session):
        """Deleting a contact keeps its interactions, without contact."""
        from tests.utils.factories import make_interaction
        company = make_company(session)
        contact = make_contact(session, company)
        interaction = make_interaction(session, company, contact_id=contact.id)
        assert client.delete(f"/api/contacts/{contact.id}").status_code == 204
        assert client.get(f"/api/interactions/{interaction.id}").json()["contact"] is None
