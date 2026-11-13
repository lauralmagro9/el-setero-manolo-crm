"""Tests for the order drafts: orders found in a voice note that the user has to complete."""

import pytest
from sqlalchemy import select

from crm import models as m
from crm.services.agents import order_agent

from tests.utils.factories import make_company, make_contact, make_product, make_voice_note
from tests.utils.llm import call, say


@pytest.fixture
def draft(session, scripted_llm):
    """Return a pending draft: Alberto (Restaurante X) asked for "chantarelas" but the product is unknown."""
    company = make_company(session, "Restaurante X")
    contact = make_contact(session, company, "Alberto", last_name="García")
    note = make_voice_note(session, transcript="Alberto quiere unas chantarelas")
    llm = scripted_llm(
        call("save_order_draft", company_id=str(company.id), contact_id=str(contact.id),
             items=[{"product_name": "chantarelas", "quantity": 5, "unit": "kg"}],
             reason="No encuentro el producto «chantarelas»"),
        say("Borrador guardado"),
    )
    order_agent.process_interaction(session, note.id, llm)
    return session.scalars(select(m.OrderDraft)).unique().one()


class TestAgentCreatesDrafts:
    """Tests for the order agent when an order is incomplete."""

    def test_0_incomplete_order_becomes_a_draft_and_an_alert(self, session, draft):
        """The note is an order with an unknown product: a draft keeps what is known and the user is asked."""
        assert draft.status == "pendiente" and draft.company.name == "Restaurante X"
        assert draft.items == [{"product_id": None, "product_name": "chantarelas", "quantity": "5", "unit": "kg"}]
        assert session.scalars(select(m.Order)).unique().all() == []
        [alert] = session.scalars(select(m.Alert)).all()
        assert alert.type == "pedido_incompleto" and alert.severity == "aviso"
        assert alert.data["draft_id"] == str(draft.id) and alert.interaction_id == draft.interaction_id
        assert "producto" in alert.message and "chantarelas" in alert.message
        note = draft.interaction
        assert note.processing_status == "procesada" and note.company_id == draft.company_id

    def test_1_unknown_ids_are_dropped_not_stored(self, session, scripted_llm):
        """Invented ids from the model never reach the draft: the fields stay empty for the user."""
        note = make_voice_note(session)
        ghost = "00000000-0000-0000-0000-000000000001"
        llm = scripted_llm(
            call("save_order_draft", company_id=ghost, items=[{"product_name": "setas", "product_id": ghost,
                                                                 "quantity": "mucho"}], reason="Nada claro"),
            say("ok"),
        )
        execution = order_agent.process_interaction(session, note.id, llm)
        saved = session.scalars(select(m.OrderDraft)).unique().one()
        assert saved.company_id is None
        assert saved.items == [{"product_id": None, "product_name": "setas", "quantity": None, "unit": None}]
        assert execution.status == "requiere_revisión"
        assert execution.output["is_order"] is True and execution.output["draft_id"] == str(saved.id)

    def test_2_note_that_is_not_an_order_is_classified_as_such(self, session, scripted_llm):
        """A comment is just processed: no order, no draft and the output says it was not an order."""
        note = make_voice_note(session, transcript="Recuerda llamar al proveedor")
        execution = order_agent.process_interaction(session, note.id, scripted_llm(say("No es un pedido")))
        assert execution.output["is_order"] is False
        assert session.scalars(select(m.OrderDraft)).unique().all() == []

    def test_3_order_cannot_be_created_after_a_draft(self, session, scripted_llm):
        """One note gives a draft or an order, never both."""
        company = make_company(session)
        product = make_product(session)
        note = make_voice_note(session)
        llm = scripted_llm(
            call("save_order_draft", items=[{"product_name": "boletus"}], reason="Falta la cantidad"),
            call("create_order", company_id=str(company.id), items=[{"product_id": str(product.id), "quantity": 1}]),
            say("ok"),
        )
        execution = order_agent.process_interaction(session, note.id, llm)
        assert "error" in execution.tool_calls[1]["result"]
        assert session.scalars(select(m.Order)).unique().all() == []


class TestDraftsApi:
    """Tests for /api/order-drafts."""

    def test_0_lists_pending_drafts_with_what_is_missing(self, client, draft):
        """The draft lists what prevents the order from being created and the note it comes from."""
        [item] = client.get("/api/order-drafts").json()
        assert item["id"] == str(draft.id) and item["transcript"] == "Alberto quiere unas chantarelas"
        assert item["missing"] == ["el producto de «chantarelas»"]
        assert client.get(f"/api/order-drafts/{draft.id}").json()["company"]["name"] == "Restaurante X"

    def test_1_incomplete_draft_cannot_be_completed(self, client, draft):
        """Marking it as complete while something is missing is refused and lists what is missing."""
        response = client.post(f"/api/order-drafts/{draft.id}/complete")
        assert response.status_code == 422
        assert "el producto de «chantarelas»" in response.json()["detail"]

    def test_2_completing_creates_the_order(self, client, session, draft):
        """Once the user picks the product and completes it, the order is created and the notices follow."""
        product = make_product(session, "Rebozuelos frescos")
        body = {"requested_delivery_date": "2026-11-20", "items": [
            {"product_id": str(product.id), "product_name": "chantarelas", "quantity": "5", "unit": "kg"}]}
        response = client.post(f"/api/order-drafts/{draft.id}/complete", json=body)
        assert response.status_code == 200, response.text
        order = response.json()
        assert order["company"]["name"] == "Restaurante X" and order["contact"]["first_name"] == "Alberto"
        assert order["requested_delivery_date"] == "2026-11-20" and order["created_by_agent"] is False
        assert [(i["product_name"], float(i["quantity"])) for i in order["items"]] == [("Rebozuelos frescos", 5.0)]
        assert order["source_interaction_id"] == str(draft.interaction_id)
        session.refresh(draft)
        assert draft.status == "completada" and str(draft.order_id) == order["id"]
        alerts = {a.type: a for a in session.scalars(select(m.Alert))}
        assert alerts["pedido_incompleto"].read_at is not None  # no longer asks anything
        assert alerts["nota_procesada"].order_id == draft.order_id and alerts["nota_procesada"].read_at is None
        assert client.post(f"/api/order-drafts/{draft.id}/complete", json=body).status_code == 422  # only once

    def test_3_saving_keeps_it_pending_and_checks_references(self, client, session, draft):
        """Saving partial data does not create anything; a contact of another company is refused."""
        other = make_contact(session, make_company(session, "Bar Y"), "Marta")
        ok = client.patch(f"/api/order-drafts/{draft.id}", json={"notes": "Urgente"})
        assert ok.status_code == 200 and ok.json()["status"] == "pendiente" and ok.json()["notes"] == "Urgente"
        assert client.patch(f"/api/order-drafts/{draft.id}", json={"contact_id": str(other.id)}).status_code == 422
        assert session.scalars(select(m.Order)).unique().all() == []

    def test_4_missing_company_and_quantity_are_reported(self, client, session, scripted_llm):
        """Without customer or quantity those two things are listed as missing."""
        note = make_voice_note(session)
        order_agent.process_interaction(session, note.id, scripted_llm(
            call("save_order_draft", items=[{"product_name": "boletus"}], reason="Poco claro"), say("ok")))
        [item] = client.get("/api/order-drafts").json()
        assert item["missing"] == ["la empresa del pedido", "el producto de «boletus»", "la cantidad de «boletus»"]

    def test_5_discard_closes_the_draft_and_its_alert(self, client, session, draft):
        """A discarded draft leaves the pending list and its alert is marked as read."""
        assert client.post(f"/api/order-drafts/{draft.id}/discard").json()["status"] == "descartada"
        assert client.get("/api/order-drafts").json() == []
        assert session.scalars(select(m.Alert)).one().read_at is not None
        assert client.post(f"/api/order-drafts/{draft.id}/discard").status_code == 422

    def test_6_requires_login(self, anonymous_client):
        """Anonymous requests are rejected."""
        assert anonymous_client.get("/api/order-drafts").status_code == 401
