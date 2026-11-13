"""Order agent: reads pending voice notes and turns them into orders (or into an alert to review).

The model only decides which tools to call; every write goes through the existing services.
When anything is ambiguous the agent must not invent data: it flags the note instead.
"""

import json
import logging
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ... import enums as e
from ... import models as m
from ... import schemas as s
from ...config import settings
from .. import alerts as alerts_svc
from .. import interactions as interactions_svc
from .. import order_drafts as drafts_svc
from .. import orders as orders_svc
from ..errors import ServiceError
from .llm import LLM, get_llm
from .utils import WEEKDAYS, calendar_hint, match_score, system_actor

logger = logging.getLogger(__name__)

AGENT_NAME = "order_agent"

TOOLS = [
    {"type": "function", "function": {
        "name": "find_contact",
        "description": "Search customers by a person's name or a company name (fuzzy). "
                       "Returns candidates with ids and a score; 'ambiguous' is true when several fit equally.",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
    }},
    {"type": "function", "function": {
        "name": "find_product",
        "description": "Search products by name, species or alias (fuzzy). Returns candidates with ids.",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
    }},
    {"type": "function", "function": {
        "name": "create_order",
        "description": "Create the order. Call it at most once, only when customer, products and quantities are clear.",
        "parameters": {"type": "object", "properties": {
            "company_id": {"type": "string"},
            "contact_id": {"type": "string"},
            "items": {"type": "array", "items": {"type": "object", "properties": {
                "product_id": {"type": "string"},
                "quantity": {"type": "number"},
                "unit": {"type": "string"},
            }, "required": ["product_id", "quantity"]}},
            "delivery_date": {"type": "string", "description": "YYYY-MM-DD"},
        }, "required": ["company_id", "items"]},
    }},
    {"type": "function", "function": {
        "name": "save_order_draft",
        "description": "The note IS an order but something is missing, unknown or ambiguous (customer, product, "
                       "quantity). Save everything that is known; the user completes the rest and then the order "
                       "is created. Omit what you do not know: never guess. Call it at most once.",
        "parameters": {"type": "object", "properties": {
            "company_id": {"type": ["string", "null"], "description": "Only if the customer is certain"},
            "contact_id": {"type": ["string", "null"]},
            "items": {"type": "array", "items": {"type": "object", "properties": {
                "product_name": {"type": "string", "description": "The product as the customer called it"},
                "product_id": {"type": ["string", "null"], "description": "Only if the product is certain"},
                "quantity": {"type": ["number", "null"], "description": "Only if it was said clearly"},
                "unit": {"type": ["string", "null"]},
            }, "required": ["product_name"]}},
            "delivery_date": {"type": ["string", "null"], "description": "YYYY-MM-DD"},
            "reason": {"type": "string", "description": "What is missing or unclear, in Spanish"},
        }, "required": ["items", "reason"]},
    }},
    {"type": "function", "function": {
        "name": "link_interaction",
        "description": "Attach the voice note to a company (and optionally a contact).",
        "parameters": {"type": "object", "properties": {
            "company_id": {"type": "string"}, "contact_id": {"type": "string"},
        }, "required": ["company_id"]},
    }},
    {"type": "function", "function": {
        "name": "flag_for_review",
        "description": "Do not create an order: leave the note for a human with the reason (in Spanish).",
        "parameters": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]},
    }},
]


def _top_tier(candidates: list[dict]) -> list[dict]:
    """Return the candidates whose score is within 0.05 of the best one."""
    if not candidates:
        return []
    return [c for c in candidates if c["score"] >= candidates[0]["score"] - 0.05]


class OrderToolbox:
    """The tools of the order agent, bound to one voice note."""

    def __init__(self, session: Session, interaction: m.Interaction):
        self.session = session
        self.interaction = interaction
        self.order_id: uuid.UUID | None = None
        self.draft_id: uuid.UUID | None = None
        self.flag_reason: str | None = None

    def run(self, name: str, arguments: dict[str, Any]) -> dict:
        """Execute a tool; business errors are returned to the model instead of raised."""
        handler = getattr(self, f"_tool_{name}", None)
        if handler is None:
            return {"error": f"Herramienta desconocida: {name}"}
        try:
            return handler(**arguments)
        except (ServiceError, ValueError, TypeError, KeyError, InvalidOperation) as exc:
            self.session.rollback()
            return {"error": f"{type(exc).__name__}: {exc}"}

    @staticmethod
    def _ranked(scored: list[dict]) -> list[dict]:
        """Keep the candidates above the cutoff, best first, limited to max_candidates."""
        cfg = settings.agents
        kept = [c for c in scored if c["score"] >= cfg.match_cutoff]
        kept.sort(key=lambda c: -c["score"])
        return kept[: cfg.max_candidates]

    def _tool_find_contact(self, name: str) -> dict:
        """Fuzzy search over contacts (person or company name) and companies."""
        scored = []
        contacts = self.session.scalars(select(m.Contact)).unique().all()
        for contact in contacts:
            full_name = f"{contact.first_name} {contact.last_name or ''}".strip()
            score = max(match_score(name, full_name), match_score(name, contact.first_name),
                        match_score(name, contact.company.name))
            scored.append({
                "contact_id": str(contact.id), "contact_name": full_name,
                "company_id": str(contact.company_id), "company_name": contact.company.name,
                "score": round(score, 2),
            })
        with_contacts = {c.company_id for c in contacts}
        for company in self.session.scalars(select(m.Company)).unique().all():
            if company.id in with_contacts:
                continue  # already offered through its contacts
            scored.append({
                "contact_id": None, "contact_name": None, "company_id": str(company.id),
                "company_name": company.name, "score": round(match_score(name, company.name), 2),
            })
        candidates = self._ranked(scored)
        top = _top_tier(candidates)
        ambiguous = (
            len({c["company_id"] for c in top}) > 1
            or len({c["contact_id"] for c in top if c["contact_id"]}) > 1
        )
        return {"candidates": candidates, "ambiguous": ambiguous}

    def _tool_find_product(self, name: str) -> dict:
        """Fuzzy search over the active products (name, species and aliases)."""
        scored = []
        for product in self.session.scalars(select(m.Product).where(m.Product.is_active)):
            names = [product.name, product.species, *(product.aliases or [])]
            scored.append({
                "product_id": str(product.id), "name": product.name, "unit": product.base_unit,
                "score": round(max(match_score(name, n) for n in names), 2),
            })
        candidates = self._ranked(scored)
        return {"candidates": candidates, "ambiguous": len(_top_tier(candidates)) > 1}

    def _tool_create_order(self, company_id: str, items: list, contact_id: str | None = None,
                           delivery_date: str | None = None) -> dict:
        """Create the order and its lines, attributed to the agent and to the voice note."""
        if self.flag_reason:
            return {"error": "La nota ya está marcada para revisión: no se crea el pedido"}
        if self.draft_id:
            return {"error": "Ya se ha guardado un borrador para esta nota: no se crea el pedido"}
        if self.order_id:
            return {"error": "Ya se ha creado un pedido para esta nota"}
        order = orders_svc.create_order(
            self.session, company_id=uuid.UUID(company_id),
            contact_id=uuid.UUID(contact_id) if contact_id else None,
            delivery_date=date.fromisoformat(delivery_date) if delivery_date else None,
            items=[{"product_id": uuid.UUID(i["product_id"]), "quantity": Decimal(str(i["quantity"])),
                    "unit": i.get("unit")} for i in items],
            interaction=self.interaction, created_by_agent=True,
        )
        self.order_id = order.id
        return {"order_id": str(order.id), "items": len(order.items)}

    def _known_id(self, model: type, value: str | None) -> uuid.UUID | None:
        """Return the id when it points to an existing record, else None (the user will fill it in)."""
        try:
            record_id = uuid.UUID(str(value)) if value else None
        except ValueError:
            return None
        return record_id if record_id and self.session.get(model, record_id) else None

    def _tool_save_order_draft(self, items: list, reason: str, company_id: str | None = None,
                               contact_id: str | None = None, delivery_date: str | None = None) -> dict:
        """Save an incomplete order for the user to complete; whatever is not certain stays empty."""
        if self.order_id:
            return {"error": "Ya se ha creado un pedido para esta nota"}
        if self.draft_id:
            return {"error": "Ya se ha guardado un borrador para esta nota"}
        company = self._known_id(m.Company, company_id)
        contact = self._known_id(m.Contact, contact_id)
        if contact and (company is None or self.session.get(m.Contact, contact).company_id != company):
            contact = None
        lines = []
        for item in items:
            try:
                quantity = Decimal(str(item["quantity"])) if item.get("quantity") is not None else None
            except InvalidOperation:
                quantity = None
            product = self._known_id(m.Product, item.get("product_id"))
            lines.append({
                "product_id": str(product) if product else None, "product_name": item.get("product_name"),
                "quantity": str(quantity) if quantity and quantity > 0 else None, "unit": item.get("unit"),
            })
        try:
            when = date.fromisoformat(delivery_date) if delivery_date else None
        except ValueError:
            when = None
        draft = drafts_svc.create_draft(
            self.session, interaction=self.interaction, reason=reason, company_id=company,
            contact_id=contact, delivery_date=when, items=lines,
        )
        self.draft_id = draft.id
        if company and self.interaction.company_id is None:
            self._link(company, contact)
        return {"draft_id": str(draft.id), "missing": drafts_svc.missing_fields(draft)}

    def _link(self, company_id: uuid.UUID, contact_id: uuid.UUID | None) -> None:
        """Assign the voice note to a company/contact through the interactions service."""
        interactions_svc.update_interaction(
            self.session, self.interaction.id,
            s.InteractionUpdate(company_id=company_id, contact_id=contact_id),
        )

    def _tool_link_interaction(self, company_id: str, contact_id: str | None = None) -> dict:
        """Attach the note to a company/contact."""
        self._link(uuid.UUID(company_id), uuid.UUID(contact_id) if contact_id else None)
        return {"linked": True}

    def _tool_flag_for_review(self, reason: str) -> dict:
        """Record that a human must look at the note, and raise the alert."""
        self.flag_reason = reason
        alerts_svc.create_alert(
            self.session, type=e.AlertType.NOTE_NEEDS_REVIEW, severity=e.AlertSeverity.WARNING,
            message=reason, interaction_id=self.interaction.id, company_id=self.interaction.company_id,
            dedupe_key=f"{e.AlertType.NOTE_NEEDS_REVIEW}:interaction:{self.interaction.id}",
        )
        return {"flagged": True}


def _claim(session: Session, interaction_id: uuid.UUID) -> bool:
    """Atomically move a pending voice note to 'processing'; False if someone else got it first."""
    result = session.execute(
        update(m.Interaction)
        .where(m.Interaction.id == interaction_id,
               m.Interaction.processing_status == e.ProcessingStatus.PENDING,
               m.Interaction.source == e.InteractionSource.VOICE_NOTE)
        .values(processing_status=e.ProcessingStatus.PROCESSING)
    )
    session.commit()
    return result.rowcount == 1


def _system_prompt(today: date) -> str:
    """Return the system prompt with today's date and a calendar of the coming days filled in."""
    cfg = settings.agents.order
    return cfg.system_prompt.format(
        today=today.isoformat(), weekday=WEEKDAYS[today.weekday()],
        calendar=calendar_hint(today, cfg.calendar_days),
    )


def _note_text(interaction: m.Interaction) -> str:
    """Return the user message: the transcript plus the customer already linked, if any."""
    text = f"Transcripción de la nota de voz:\n{interaction.transcript}"
    if interaction.company_id:
        text += f"\n\n(La nota ya está asignada a la empresa {interaction.company.name} [{interaction.company_id}])"
    return text


def process_interaction(
    session: Session, interaction_id: uuid.UUID, llm: LLM | None = None
) -> m.AgentExecution | None:
    """Run the agent on one pending voice note and return its AgentExecution (None if not claimed).

    The note ends 'procesada' (also when it was flagged for review, with an alert) or 'error'.
    """
    llm = llm or get_llm()  # before claiming: a missing key must not leave the note 'procesando'
    if not _claim(session, interaction_id):
        return None
    interaction = session.get(m.Interaction, interaction_id, populate_existing=True)
    # Pessimistic default: the execution stays 'error' if the process dies half way
    execution = m.AgentExecution(
        agent_name=AGENT_NAME, started_at=datetime.now(), interaction_id=interaction.id,
        input={"transcript": interaction.transcript}, tool_calls=[], status=e.AgentStatus.ERROR,
        model=llm.model,
    )
    session.add(execution)
    session.commit()
    execution_id = execution.id

    toolbox = OrderToolbox(session, interaction)
    log: list[dict] = []
    usage = {"prompt_tokens": 0, "completion_tokens": 0}
    messages: list[dict] = [
        {"role": "system", "content": _system_prompt(date.today())},
        {"role": "user", "content": _note_text(interaction)},
    ]
    try:
        final_text = ""
        for _ in range(settings.agents.max_tool_rounds):
            reply = llm.complete(messages, TOOLS)
            for key in usage:
                usage[key] += reply.usage.get(key, 0)
            if not reply.tool_calls:
                final_text = reply.content or ""
                break
            messages.append({"role": "assistant", "content": reply.content, "tool_calls": [
                {"id": c.id, "type": "function",
                 "function": {"name": c.name, "arguments": json.dumps(c.arguments)}} for c in reply.tool_calls
            ]})
            for call in reply.tool_calls:
                result = toolbox.run(call.name, call.arguments)
                log.append({"tool": call.name, "arguments": call.arguments, "result": result})
                messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})
        else:
            toolbox.run("flag_for_review", {"reason": "El agente no terminó de procesar la nota; revísala a mano."})
            final_text = "Límite de pasos alcanzado"
        needs_user = toolbox.flag_reason or toolbox.draft_id
        status = e.AgentStatus.NEEDS_REVIEW if needs_user else e.AgentStatus.SUCCESS
        interaction.processing_status = e.ProcessingStatus.PROCESSED
        output = {"message": final_text, "order_id": str(toolbox.order_id) if toolbox.order_id else None,
                  "draft_id": str(toolbox.draft_id) if toolbox.draft_id else None,
                  "is_order": bool(toolbox.order_id or toolbox.draft_id),
                  "flag_reason": toolbox.flag_reason, "usage": usage}
    except Exception as exc:  # noqa: BLE001 - any failure must leave the note in 'error', not 'procesando'
        logger.exception("Order agent failed on interaction %s", interaction_id)
        session.rollback()
        interaction = session.get(m.Interaction, interaction_id, populate_existing=True)
        interaction.processing_status = e.ProcessingStatus.ERROR
        status = e.AgentStatus.ERROR
        output = {"error": str(exc), "usage": usage}
    execution = session.get(m.AgentExecution, execution_id)
    execution.status, execution.output, execution.tool_calls = status, output, log
    execution.finished_at = datetime.now()
    session.commit()
    if status == e.AgentStatus.SUCCESS:  # a flagged note or a draft already has its own alert, and an error is retried
        orders_svc.notify_note_processed(session, session.get(m.Interaction, interaction_id), toolbox.order_id)
    return execution


def process_pending(session: Session, llm: LLM | None = None, limit: int | None = None) -> s.OrderAgentRunOut:
    """Process up to `limit` (default agents.batch_size) pending voice notes, oldest first."""
    llm = llm or get_llm()
    ids = session.scalars(
        select(m.Interaction.id)
        .where(m.Interaction.processing_status == e.ProcessingStatus.PENDING,
               m.Interaction.source == e.InteractionSource.VOICE_NOTE)
        .order_by(m.Interaction.occurred_at).limit(limit or settings.agents.batch_size)
    ).all()
    result = s.OrderAgentRunOut(processed=0, orders_created=0, needs_review=0, errors=0)
    with system_actor():
        for interaction_id in ids:
            execution = process_interaction(session, interaction_id, llm)
            if execution is None:
                continue
            result.processed += 1
            result.orders_created += bool(isinstance(execution.output, dict) and execution.output.get("order_id"))
            result.needs_review += execution.status == e.AgentStatus.NEEDS_REVIEW
            result.errors += execution.status == e.AgentStatus.ERROR
    return result
