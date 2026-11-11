"""Tests for the interactions endpoints."""

import uuid

from tests.utils.factories import make_company, make_contact, make_interaction


class TestInteractions:
    """Tests for /api/interactions."""

    def test_0_create_manual_records_author(self, client, session):
        """A manual interaction is stored as processed and signed with the user's email."""
        company = make_company(session)
        response = client.post("/api/interactions", json={
            "company_id": str(company.id), "type": "Llamada", "summary": "Llamada de seguimiento"})
        assert response.status_code == 201
        body = response.json()
        assert body["created_by"] == "laura@example.com"
        assert body["source"] == "manual"
        assert body["processing_status"] == "procesada"

    def test_1_contact_of_another_company_is_rejected(self, client, session):
        """The contact must belong to the chosen company."""
        a, b = make_company(session, "A"), make_company(session, "B")
        contact = make_contact(session, b)
        response = client.post("/api/interactions", json={
            "company_id": str(a.id), "contact_id": str(contact.id), "type": "Llamada", "summary": "x"})
        assert response.status_code == 422

    def test_2_filters(self, client, session):
        """Listing filters by company, type and processing status; newest first."""
        a, b = make_company(session, "A"), make_company(session, "B")
        make_interaction(session, a, type="Llamada", summary="uno")
        make_interaction(session, a, type="WhatsApp", summary="dos", processing_status="pendiente")
        make_interaction(session, b, summary="tres")
        summaries = lambda **p: sorted(i["summary"] for i in client.get("/api/interactions", params=p).json()["items"])
        assert summaries(company_id=str(a.id)) == ["dos", "uno"]
        assert summaries(type="WhatsApp") == ["dos"]
        assert summaries(processing_status="pendiente") == ["dos"]
        assert summaries(search="tre") == ["tres"]

    def test_3_assign_company_to_unassigned_note(self, client, session):
        """PATCH links an unassigned voice note to a company."""
        company = make_company(session)
        note = make_interaction(session, None, source="nota_de_voz", summary=None,
                                transcript="hola", processing_status="pendiente")
        unassigned = client.get("/api/interactions", params={"unassigned": True}).json()
        assert unassigned["total"] == 1
        response = client.patch(f"/api/interactions/{note.id}", json={"company_id": str(company.id)})
        assert response.status_code == 200
        assert response.json()["company"]["name"] == company.name
        assert client.get("/api/interactions", params={"unassigned": True}).json()["total"] == 0

    def test_4_contact_implies_company(self, client, session):
        """Assigning only a contact fills in the company of that contact."""
        company = make_company(session)
        contact = make_contact(session, company)
        note = make_interaction(session, None, source="nota_de_voz", summary=None, transcript="hola")
        response = client.patch(f"/api/interactions/{note.id}", json={"contact_id": str(contact.id)})
        assert response.json()["company_id"] == str(company.id)

    def test_5_missing_interaction_is_404(self, client):
        """An unknown id returns 404."""
        assert client.get(f"/api/interactions/{uuid.uuid4()}").status_code == 404
