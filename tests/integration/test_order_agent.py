"""Tests for the order agent (the language model is always scripted)."""

from decimal import Decimal

import pytest
from sqlalchemy import select

from crm import models as m
from crm.services import errors
from crm.services.agents import order_agent

from tests.utils.factories import make_company, make_contact, make_interaction, make_product, make_voice_note
from tests.utils.llm import call, say


@pytest.fixture
def mushroom_shop(session):
    """Return (company, contact, product): Alberto García of Restaurante X, who buys rebozuelos (a.k.a. chantarelas)."""
    company = make_company(session, "Restaurante X")
    contact = make_contact(session, company, "Alberto", last_name="García")
    product = make_product(session, "Rebozuelos frescos", species="Cantharellus", aliases=["chantarelas"])
    make_product(session, "Boletus edulis fresco")
    return company, contact, product


def orders(session) -> list[m.Order]:
    """Return every order in the database."""
    return list(session.scalars(select(m.Order)).unique())


class TestProcessInteraction:
    """Tests for order_agent.process_interaction."""

    def test_0_voice_note_becomes_an_order(self, session, scripted_llm, mushroom_shop):
        """Alberto asks for 5 kg of chantarelas: one order with one 5 kg line made by the agent."""
        company, contact, product = mushroom_shop
        note = make_voice_note(session)
        llm = scripted_llm(
            call("find_contact", name="Alberto"),
            call("find_product", name="chantarelas"),
            call("create_order", company_id=str(company.id), contact_id=str(contact.id),
                 items=[{"product_id": str(product.id), "quantity": 5}], delivery_date="2026-11-20"),
            say("Pedido creado"),
        )
        execution = order_agent.process_interaction(session, note.id, llm)

        [order] = orders(session)
        assert order.created_by_agent is True
        assert order.source_interaction_id == note.id
        assert order.company_id == company.id and order.contact_id == contact.id
        assert order.status == "Nuevo"
        assert str(order.requested_delivery_date) == "2026-11-20"
        [item] = order.items
        assert item.product_id == product.id and item.quantity == Decimal("5") and item.unit == "kg"
        session.refresh(note)
        assert note.processing_status == "procesada"
        assert note.company_id == company.id and note.contact_id == contact.id  # linked by the agent
        assert execution.status == "correcta"
        assert execution.model == "scripted-model"
        assert [c["tool"] for c in execution.tool_calls] == ["find_contact", "find_product", "create_order"]
        assert execution.tool_calls[1]["result"]["candidates"][0]["name"] == "Rebozuelos frescos"  # alias matched
        assert execution.output["order_id"] == str(order.id)
        [alert] = session.scalars(select(m.Alert)).all()  # the date was given: only the "processed" notice
        assert alert.type == "nota_procesada"

    def test_1_ambiguity_flags_the_note_and_creates_no_order(self, session, scripted_llm, mushroom_shop):
        """Two Albertos: the tool reports the ambiguity, the note is flagged, an alert appears and no order exists."""
        other = make_company(session, "Bar Y")
        make_contact(session, other, "Alberto", last_name="Pérez")
        note = make_voice_note(session)
        llm = scripted_llm(
            call("find_contact", name="Alberto"),
            call("flag_for_review", reason="Hay dos Alberto: García (Restaurante X) y Pérez (Bar Y)"),
            say("Necesita revisión"),
        )
        execution = order_agent.process_interaction(session, note.id, llm)

        assert execution.tool_calls[0]["result"]["ambiguous"] is True
        assert orders(session) == []
        [alert] = session.scalars(select(m.Alert)).all()
        assert alert.type == "nota_en_revision" and alert.interaction_id == note.id
        assert "dos Alberto" in alert.message
        assert execution.status == "requiere_revisión"
        session.refresh(note)
        assert note.processing_status == "procesada"

    def test_2_create_order_is_refused_after_flagging(self, session, scripted_llm, mushroom_shop):
        """Once flagged for review the agent cannot create an order anyway."""
        company, _, product = mushroom_shop
        note = make_voice_note(session)
        llm = scripted_llm(
            call("flag_for_review", reason="Cantidad dudosa"),
            call("create_order", company_id=str(company.id), items=[{"product_id": str(product.id), "quantity": 5}]),
            say("ok"),
        )
        execution = order_agent.process_interaction(session, note.id, llm)
        assert "error" in execution.tool_calls[1]["result"]
        assert orders(session) == []

    def test_3_invalid_quantity_or_product_creates_nothing(self, session, scripted_llm, mushroom_shop):
        """A zero quantity, an unknown product and a malformed id are rejected without writing anything."""
        company, _, product = mushroom_shop
        note = make_voice_note(session)
        unknown = "00000000-0000-0000-0000-000000000001"
        llm = scripted_llm(
            call("create_order", company_id=str(company.id), items=[{"product_id": str(product.id), "quantity": 0}]),
            call("create_order", company_id=str(company.id), items=[{"product_id": unknown, "quantity": 2}]),
            call("create_order", company_id=str(company.id), items=[{"product_id": "not-a-uuid", "quantity": 2}]),
            say("no puedo"),
        )
        execution = order_agent.process_interaction(session, note.id, llm)
        assert all("error" in c["result"] for c in execution.tool_calls)
        assert orders(session) == []

    def test_4_contact_of_another_company_is_rejected(self, session, scripted_llm, mushroom_shop):
        """The contact must belong to the company of the order."""
        _, contact, product = mushroom_shop
        other = make_company(session, "Bar Y")
        note = make_voice_note(session)
        llm = scripted_llm(
            call("create_order", company_id=str(other.id), contact_id=str(contact.id),
                 items=[{"product_id": str(product.id), "quantity": 2}]),
            say("no"),
        )
        execution = order_agent.process_interaction(session, note.id, llm)
        assert "no pertenece" in execution.tool_calls[0]["result"]["error"]
        assert orders(session) == []

    def test_5_model_failure_leaves_the_note_in_error(self, session, scripted_llm, mushroom_shop):
        """If the model fails the note becomes error (so it can be retried) and the run is logged."""
        note = make_voice_note(session)
        execution = order_agent.process_interaction(session, note.id, scripted_llm(RuntimeError("Groq caído")))
        session.refresh(note)
        assert note.processing_status == "error"
        assert execution.status == "error" and "Groq caído" in execution.output["error"]
        assert execution.finished_at is not None

    def test_6_note_already_claimed_is_skipped(self, session, scripted_llm, mushroom_shop):
        """A note that is not pending (another worker has it) is left alone and the model is not called."""
        note = make_voice_note(session, processing_status="procesando")
        llm = scripted_llm()
        assert order_agent.process_interaction(session, note.id, llm) is None
        assert llm.calls == []

    def test_7_missing_key_raises_without_claiming(self, session, monkeypatch, mushroom_shop):
        """Without a Groq key the note stays pending."""
        monkeypatch.setitem(order_agent.settings.transcription.as_dict(), "api_key", "")
        note = make_voice_note(session)
        with pytest.raises(errors.ConfigurationError):
            order_agent.process_interaction(session, note.id)
        session.refresh(note)
        assert note.processing_status == "pendiente"

    def test_8_note_without_order_is_only_linked(self, session, scripted_llm, mushroom_shop):
        """A note that is not an order can just be assigned to the customer."""
        company, contact, _ = mushroom_shop
        note = make_voice_note(session, transcript="He hablado con Alberto, quiere que le llame el lunes")
        llm = scripted_llm(
            call("find_contact", name="Alberto"),
            call("link_interaction", company_id=str(company.id), contact_id=str(contact.id)),
            say("Nota asignada"),
        )
        execution = order_agent.process_interaction(session, note.id, llm)
        assert orders(session) == []
        session.refresh(note)
        assert note.company_id == company.id and note.processing_status == "procesada"
        assert execution.status == "correcta"

    def test_9_endless_tool_loop_is_flagged(self, session, scripted_llm, monkeypatch, mushroom_shop):
        """A model that never stops calling tools is cut off and the note is flagged."""
        monkeypatch.setitem(order_agent.settings.agents.as_dict(), "max_tool_rounds", 2)
        note = make_voice_note(session)
        llm = scripted_llm(call("find_contact", name="x"), call("find_contact", name="y"))
        execution = order_agent.process_interaction(session, note.id, llm)
        assert execution.status == "requiere_revisión"
        assert session.scalars(select(m.Alert)).all()[0].type == "nota_en_revision"

    def test_10_order_without_delivery_date_is_kept_and_the_user_is_asked(self, session, scripted_llm, mushroom_shop):
        """No date in the note: the order is created anyway and an alert asks the user to fill it in."""
        company, _, product = mushroom_shop
        note = make_voice_note(session)
        llm = scripted_llm(
            call("create_order", company_id=str(company.id), items=[{"product_id": str(product.id), "quantity": 5}]),
            say("Pedido creado sin fecha"),
        )
        execution = order_agent.process_interaction(session, note.id, llm)

        [order] = orders(session)
        assert order.requested_delivery_date is None
        alert = session.scalars(select(m.Alert).where(m.Alert.type == "pedido_sin_fecha_entrega")).one()
        assert alert.severity == "aviso"
        assert alert.order_id == order.id and alert.company_id == company.id and alert.interaction_id == note.id
        assert "Restaurante X" in alert.message
        assert execution.status == "correcta"  # not ambiguity: no review needed
        session.refresh(note)
        assert note.processing_status == "procesada"

    def test_11_processed_note_raises_an_alert_with_the_links(self, session, scripted_llm, mushroom_shop):
        """The user is notified of how the note was linked: company, contact and the order created."""
        company, contact, product = mushroom_shop
        note = make_voice_note(session)
        llm = scripted_llm(
            call("create_order", company_id=str(company.id), contact_id=str(contact.id),
                 items=[{"product_id": str(product.id), "quantity": 5}], delivery_date="2026-11-20"),
            say("Pedido creado"),
        )
        order_agent.process_interaction(session, note.id, llm)

        [order] = orders(session)
        alert = session.scalars(select(m.Alert).where(m.Alert.type == "nota_procesada")).one()
        assert alert.severity == "info" and alert.read_at is None
        assert alert.interaction_id == note.id and alert.company_id == company.id and alert.order_id == order.id
        assert alert.data == {
            "company_name": "Restaurante X", "contact_id": str(contact.id), "contact_name": "Alberto García",
        }
        assert "Restaurante X (Alberto García)" in alert.message
        assert "5 kg de Rebozuelos frescos" in alert.message and "20/11/2026" in alert.message

    def test_12_processed_note_without_customer_is_still_notified(self, session, scripted_llm, mushroom_shop):
        """A note that could not be linked to anyone still raises the notice, so the user can assign it."""
        note = make_voice_note(session, transcript="Recuerda llamar al proveedor")
        order_agent.process_interaction(session, note.id, scripted_llm(say("Nada que hacer")))
        alert = session.scalars(select(m.Alert).where(m.Alert.type == "nota_procesada")).one()
        assert alert.company_id is None and alert.order_id is None
        assert "sin empresa vinculada" in alert.message

    def test_13_flagged_or_failed_note_gets_no_processed_notice(self, session, scripted_llm, mushroom_shop):
        """A flagged note has its own review alert and a failed one is retried: neither says processed."""
        flagged = make_voice_note(session)
        order_agent.process_interaction(
            session, flagged.id, scripted_llm(call("flag_for_review", reason="Dudas"), say("ok")))
        failed = make_voice_note(session, transcript="Otra")
        order_agent.process_interaction(session, failed.id, scripted_llm(RuntimeError("caído")))
        assert [a.type for a in session.scalars(select(m.Alert))] == ["nota_en_revision"]


class TestProcessPending:
    """Tests for order_agent.process_pending."""

    def test_0_processes_only_pending_voice_notes(self, session, scripted_llm, mushroom_shop):
        """Two pending voice notes are processed; a manual note is ignored. The summary counts each outcome."""
        company, _, product = mushroom_shop
        make_voice_note(session)
        make_voice_note(session, transcript="Otra nota")
        make_interaction(session, company, processing_status="pendiente")  # manual: not for the agent
        llm = scripted_llm(
            call("create_order", company_id=str(company.id), items=[{"product_id": str(product.id), "quantity": 3}]),
            say("hecho"),
            call("flag_for_review", reason="No entiendo la nota"),
            say("revisar"),
        )
        result = order_agent.process_pending(session, llm)
        assert result.model_dump() == {"processed": 2, "orders_created": 1, "needs_review": 1, "errors": 0}
        assert len(orders(session)) == 1

    def test_1_respects_the_limit(self, session, scripted_llm, mushroom_shop):
        """Only `limit` notes are processed per call."""
        make_voice_note(session)
        make_voice_note(session)
        result = order_agent.process_pending(session, scripted_llm(say("nada")), limit=1)
        assert result.processed == 1
