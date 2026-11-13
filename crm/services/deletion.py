"""Soft delete of any record, shared by the API and the future agents.

Nothing is ever removed from the database: the row gets `deleted_at` / `deleted_by` and from then
on it is invisible to every ORM query and to the SQL views (see models.py). What happens to the
records that point at the deleted one is decided by DELETE_RULES:

* cascade: they are deleted too (they only make sense inside the parent);
* detach:  they stay, with the reference emptied (they are history that must be kept);
* block:   the deletion is refused while live records depend on it.
"""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..audit import current_actor
from .errors import ConflictError, NotFoundError

CASCADE, DETACH, BLOCK = "cascade", "detach", "block"

# parent model -> [(child model, foreign-key attribute of the child, action, what to call them)]
DELETE_RULES: dict[type, list[tuple[type, str, str, str]]] = {
    m.Company: [
        (m.Invoice, "company_id", BLOCK, "facturas"),  # fiscal documents are never hidden by accident
        (m.Contact, "company_id", CASCADE, "contactos"),
        (m.Interaction, "company_id", CASCADE, "interacciones"),
        (m.Order, "company_id", CASCADE, "pedidos"),
        (m.Lot, "supplier_company_id", DETACH, "lotes"),
        (m.OrderDraft, "company_id", DETACH, "borradores de pedido"),
    ],
    m.Contact: [
        (m.Interaction, "contact_id", DETACH, "interacciones"),
        (m.Order, "contact_id", DETACH, "pedidos"),
        (m.OrderDraft, "contact_id", DETACH, "borradores de pedido"),
    ],
    m.Interaction: [
        (m.Order, "source_interaction_id", DETACH, "pedidos"),
        (m.AgentExecution, "interaction_id", DETACH, "ejecuciones de agentes"),
        (m.OrderDraft, "interaction_id", CASCADE, "borradores de pedido"),
    ],
    m.Product: [
        (m.OrderItem, "product_id", BLOCK, "líneas de pedido"),
        (m.Lot, "product_id", BLOCK, "lotes"),
        (m.InvoiceItem, "product_id", DETACH, "líneas de factura"),
    ],
    m.Lot: [
        (m.LotAdjustment, "lot_id", CASCADE, "ajustes"),
        (m.LotAllocation, "lot_id", CASCADE, "reservas"),
    ],
    m.Order: [
        (m.OrderItem, "order_id", CASCADE, "líneas"),
        (m.Invoice, "order_id", DETACH, "facturas"),
        (m.OrderDraft, "order_id", DETACH, "borradores de pedido"),
    ],
    m.OrderItem: [
        (m.LotAllocation, "order_item_id", CASCADE, "reservas"),
        (m.InvoiceItem, "order_item_id", DETACH, "líneas de factura"),
    ],
    m.Invoice: [
        (m.InvoiceItem, "invoice_id", CASCADE, "líneas"),
        (m.Payment, "invoice_id", CASCADE, "cobros"),
    ],
}

LABELS = {
    m.Company: "Empresa", m.Contact: "Contacto", m.Interaction: "Interacción", m.Product: "Producto",
    m.Lot: "Lote", m.LotAdjustment: "Ajuste de lote", m.Order: "Pedido", m.OrderItem: "Línea de pedido",
    m.LotAllocation: "Reserva", m.Invoice: "Factura", m.InvoiceItem: "Línea de factura",
    m.Payment: "Cobro", m.AgentExecution: "Ejecución de agente", m.OrderDraft: "Borrador de pedido",
}


def _delete(session: Session, model: type, record, actor: str, now: datetime) -> None:
    """Mark `record` as deleted and apply the rules to the records that depend on it."""
    for child_model, column, action, label in DELETE_RULES.get(model, []):
        children = session.scalars(select(child_model).where(getattr(child_model, column) == record.id)).unique().all()
        if not children:
            continue
        if action == BLOCK:
            raise ConflictError(
                f"No se puede borrar: hay {len(children)} {label} que dependen de este registro"
            )
        for child in children:
            if action == CASCADE:
                _delete(session, child_model, child, actor, now)
            else:
                setattr(child, column, None)
    record.deleted_at = now
    record.deleted_by = actor


def delete_record(session: Session, model: type, record_id: uuid.UUID, deleted_by: str | None = None) -> None:
    """Soft-delete one record of any table (with its dependants, see DELETE_RULES).

    Raises NotFoundError when it does not exist (or was already deleted) and ConflictError when
    other records block the deletion; in both cases nothing changes.
    """
    record = session.get(model, record_id)
    if record is None:
        raise NotFoundError(f"{LABELS.get(model, model.__name__)} no encontrado")
    try:
        _delete(session, model, record, deleted_by or current_actor(), datetime.now())
        session.commit()
    except Exception:
        session.rollback()
        raise
