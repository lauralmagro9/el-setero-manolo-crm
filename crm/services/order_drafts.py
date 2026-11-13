"""Order drafts: orders the agent found in a voice note but could not complete by itself.

The user fills in what is missing and marks the draft as complete; only then is the order created.
"""

import uuid
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import enums as e
from .. import models as m
from .. import schemas as s
from . import alerts as alerts_svc
from . import orders as orders_svc
from .errors import InvalidReferenceError, NotFoundError


def alert_key(draft_id: uuid.UUID) -> str:
    """Return the dedupe key of the alert that asks the user to complete a draft."""
    return f"{e.AlertType.INCOMPLETE_ORDER}:draft:{draft_id}"


def _quantity(item: dict) -> Decimal | None:
    """Return the quantity of a stored line as a Decimal, or None when it is missing or not a number."""
    try:
        return Decimal(str(item["quantity"])) if item.get("quantity") not in (None, "") else None
    except InvalidOperation:
        return None


def missing_fields(draft: m.OrderDraft) -> list[str]:
    """Return what still prevents the draft from becoming an order (in Spanish, for the user)."""
    missing = []
    if draft.company_id is None:
        missing.append("la empresa del pedido")
    if not draft.items:
        missing.append("los productos del pedido")
    for number, item in enumerate(draft.items or [], start=1):
        label = item.get("product_name") or f"línea {number}"
        if not item.get("product_id"):
            missing.append(f"el producto de «{label}»")
        quantity = _quantity(item)
        if quantity is None or quantity <= 0:
            missing.append(f"la cantidad de «{label}»")
    return missing


def to_out(draft: m.OrderDraft) -> s.OrderDraftOut:
    """Build the API view of a draft, with what is missing and the transcript of its note."""
    return s.OrderDraftOut(
        id=draft.id, interaction_id=draft.interaction_id, company_id=draft.company_id,
        contact_id=draft.contact_id, requested_delivery_date=draft.requested_delivery_date, notes=draft.notes,
        reason=draft.reason, status=draft.status, order_id=draft.order_id,
        items=[s.DraftItem(**item) for item in draft.items or []], missing=missing_fields(draft),
        transcript=draft.interaction.transcript if draft.interaction else None,
        company=draft.company, contact=draft.contact,
    )


def get_draft(session: Session, draft_id: uuid.UUID) -> m.OrderDraft:
    """Return a draft or raise NotFoundError."""
    draft = session.get(m.OrderDraft, draft_id)
    if draft is None:
        raise NotFoundError("Borrador de pedido no encontrado")
    return draft


def list_drafts(session: Session, status: e.OrderDraftStatus | None = e.OrderDraftStatus.PENDING) -> list[m.OrderDraft]:
    """Return the drafts in `status` (all when None), newest first."""
    query = select(m.OrderDraft).order_by(m.OrderDraft.created_at.desc(), m.OrderDraft.id)
    if status:
        query = query.where(m.OrderDraft.status == status)
    return list(session.scalars(query).unique())


def _dump_items(items: list[s.DraftItem]) -> list[dict]:
    """Turn the lines of a request into the JSON stored in the draft."""
    return [
        {"product_id": str(i.product_id) if i.product_id else None, "product_name": i.product_name,
         "quantity": str(i.quantity) if i.quantity is not None else None, "unit": i.unit}
        for i in items
    ]


def create_draft(
    session: Session,
    *,
    interaction: m.Interaction,
    reason: str | None,
    company_id: uuid.UUID | None = None,
    contact_id: uuid.UUID | None = None,
    delivery_date: date | None = None,
    items: list[dict] | None = None,
) -> m.OrderDraft:
    """Save a draft and raise the alert that asks the user to complete it."""
    draft = m.OrderDraft(
        interaction_id=interaction.id, company_id=company_id, contact_id=contact_id,
        requested_delivery_date=delivery_date, items=items or [], reason=reason,
        status=e.OrderDraftStatus.PENDING,
    )
    session.add(draft)
    session.commit()
    who = draft.company.name if draft.company else "un cliente sin identificar"
    missing = ", ".join(missing_fields(draft)) or "revisar los datos"
    alerts_svc.create_alert(
        session, type=e.AlertType.INCOMPLETE_ORDER, severity=e.AlertSeverity.WARNING,
        message=f"Pedido incompleto de {who}: falta {missing}. Complétalo para crearlo.",
        interaction_id=interaction.id, company_id=company_id, data={"draft_id": str(draft.id), "reason": reason},
        dedupe_key=alert_key(draft.id),
    )
    return draft


def _pending(session: Session, draft_id: uuid.UUID) -> m.OrderDraft:
    """Return a draft that is still waiting for the user."""
    draft = get_draft(session, draft_id)
    if draft.status != e.OrderDraftStatus.PENDING:
        raise InvalidReferenceError("Este borrador ya está cerrado")
    return draft


def update_draft(session: Session, draft_id: uuid.UUID, data: s.OrderDraftUpdate) -> m.OrderDraft:
    """Save what the user filled in (it does not have to be complete yet)."""
    draft = _pending(session, draft_id)
    changes = data.model_dump(exclude_unset=True)
    company_id = changes.get("company_id", draft.company_id)
    contact_id = changes.get("contact_id", draft.contact_id)
    if company_id and session.get(m.Company, company_id) is None:
        raise NotFoundError("Empresa no encontrada")
    if contact_id:
        contact = session.get(m.Contact, contact_id)
        if contact is None or contact.company_id != company_id:
            raise InvalidReferenceError("El contacto no existe o no pertenece a la empresa")
    if data.items is not None:
        for item in data.items:
            if item.product_id and session.get(m.Product, item.product_id) is None:
                raise InvalidReferenceError(f"Producto no encontrado: {item.product_id}")
        draft.items = _dump_items(data.items)
    for key in ("company_id", "contact_id", "requested_delivery_date", "notes"):
        if key in changes:
            setattr(draft, key, changes[key])
    session.commit()
    session.refresh(draft)
    return draft


def complete_draft(session: Session, draft_id: uuid.UUID, data: s.OrderDraftUpdate | None = None) -> m.Order:
    """Mark the draft as complete: save the last changes and create the order.

    Raises InvalidReferenceError listing what is still missing. The alert that asked for it is
    marked as read and the usual "note processed" alert is raised so the order can still be edited.
    """
    if data is not None:
        update_draft(session, draft_id, data)
    draft = _pending(session, draft_id)
    missing = missing_fields(draft)
    if missing:
        raise InvalidReferenceError("Faltan datos: " + ", ".join(missing))
    order = orders_svc.create_order(
        session, company_id=draft.company_id, contact_id=draft.contact_id,
        delivery_date=draft.requested_delivery_date, interaction=draft.interaction, force_link=True,
        items=[{"product_id": uuid.UUID(i["product_id"]), "quantity": _quantity(i), "unit": i.get("unit")}
               for i in draft.items],
    )
    if draft.notes:
        order.notes = draft.notes
    draft.status, draft.order_id = e.OrderDraftStatus.COMPLETED, order.id
    session.commit()
    _close_alert(session, draft.id)
    if draft.interaction:
        orders_svc.notify_note_processed(session, draft.interaction, order.id)
    return order


def discard_draft(session: Session, draft_id: uuid.UUID) -> m.OrderDraft:
    """Throw the draft away (the note was not an order after all)."""
    draft = _pending(session, draft_id)
    draft.status = e.OrderDraftStatus.DISCARDED
    session.commit()
    _close_alert(session, draft.id)
    return draft


def _close_alert(session: Session, draft_id: uuid.UUID) -> None:
    """Mark the "incomplete order" alert of a draft as read."""
    alerts_svc.mark_read_by_key(session, alert_key(draft_id))
