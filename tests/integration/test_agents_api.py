"""Tests for the agents' endpoints and for their trigger after uploading a voice note."""

import uuid

from sqlalchemy import select

from crm import models as m
from crm.services.agents import order_agent, runner

from tests.integration.test_voice_notes_api import AUDIO, upload
from tests.utils.factories import make_company, make_contact, make_lot, make_product, make_voice_note
from tests.utils.llm import call, say


class TestProcessPendingEndpoint:
    """Tests for POST /api/agents/process-pending."""

    def test_0_processes_pending_notes(self, client, session, monkeypatch, scripted_llm):
        """The manual retry runs the agent over the pending notes and reports what happened."""
        company = make_company(session)
        product = make_product(session)
        make_voice_note(session)
        llm = scripted_llm(
            call("create_order", company_id=str(company.id), items=[{"product_id": str(product.id), "quantity": 2}]),
            say("hecho"),
        )
        monkeypatch.setattr(order_agent, "get_llm", lambda: llm)
        response = client.post("/api/agents/process-pending")
        assert response.status_code == 200
        assert response.json() == {"processed": 1, "orders_created": 1, "needs_review": 0, "errors": 0}
        assert session.scalars(select(m.Order)).unique().one().created_by_agent is True

    def test_1_without_groq_key_is_503(self, client, session, monkeypatch):
        """No Groq key: the endpoint explains it instead of failing silently."""
        monkeypatch.setitem(runner.settings.transcription.as_dict(), "api_key", "")
        make_voice_note(session)
        assert client.post("/api/agents/process-pending").status_code == 503

    def test_2_requires_login(self, anonymous_client):
        """Anonymous requests are rejected."""
        assert anonymous_client.post("/api/agents/process-pending").status_code == 401
        assert anonymous_client.post("/api/agents/run-stock").status_code == 401


class TestRunStockEndpoint:
    """Tests for POST /api/agents/run-stock."""

    def test_0_runs_the_rules_and_creates_alerts(self, client, session, monkeypatch):
        """A lot with 1 kg left raises a low-stock alert that the alerts API then lists."""
        monkeypatch.setitem(runner.settings.agents.stock.as_dict(), "use_llm_for_text", False)
        make_lot(session, quantity="1")
        assert client.post("/api/agents/run-stock").json() == {"alerts_created": 1}
        [alert] = client.get("/api/alerts").json()["items"]
        assert alert["type"] == "stock_bajo"


class TestVoiceNoteTrigger:
    """Tests for the background run after POST /api/voice-notes."""

    def test_0_upload_triggers_the_agent(self, client, session, fake_transcription, groq_key, monkeypatch, scripted_llm):
        """Once the answer is sent, the agent reads the note and creates the order."""
        company = make_company(session)
        contact = make_contact(session, company, "Alberto")
        product = make_product(session)
        llm = scripted_llm(
            call("create_order", company_id=str(company.id), contact_id=str(contact.id),
                 items=[{"product_id": str(product.id), "quantity": 3}]),
            say("hecho"),
        )
        monkeypatch.setattr(order_agent, "get_llm", lambda: llm)
        response = upload(client)
        assert response.status_code == 201
        assert response.json()["processing_status"] == "pendiente"  # the answer does not wait for the agent
        session.expire_all()
        note = session.get(m.Interaction, uuid.UUID(response.json()["id"]))
        assert note.processing_status == "procesada"
        order = session.scalars(select(m.Order)).unique().one()
        assert order.source_interaction_id == note.id
        assert order.created_by == "system"  # the agent, not the logged-in user

    def test_1_without_key_the_note_stays_pending(self, client, session, fake_transcription, monkeypatch):
        """With no Groq key the upload still works and the note waits for a manual retry."""
        monkeypatch.setitem(runner.settings.transcription.as_dict(), "api_key", "")
        response = upload(client, AUDIO)
        assert response.status_code == 201
        session.expire_all()
        assert session.get(m.Interaction, uuid.UUID(response.json()["id"])).processing_status == "pendiente"

    def test_2_auto_process_can_be_turned_off(self, client, session, fake_transcription, groq_key, monkeypatch):
        """agents.auto_process = false leaves every note pending."""
        monkeypatch.setitem(runner.settings.agents.as_dict(), "auto_process", False)
        response = upload(client)
        session.expire_all()
        assert session.get(m.Interaction, uuid.UUID(response.json()["id"])).processing_status == "pendiente"
