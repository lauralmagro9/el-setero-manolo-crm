"""Business logic for customer orders."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import enums as e
from .. import models as m
from .. import schemas as s
from ..utils import paginate
from . import alerts as alerts_svc
from . import deletion
from . import interactions as interactions_svc
from .errors import InvalidReferenceError, NotFoundError


def list_orders(
    session: Session,
    *,
    status: e.OrderStatus | None = None,
    company_id: uuid.UUID | None = None,
    created_by_agent: bool | None = None,
    page: int = 1,
    page_size: int = 25,
):
    """Return (orders, total) matching the filters, newest request first."""
    query = select(m.Order).order_by(m.Order.requested_at.desc(), m.Order.id)
    if status:
        query = query.where(m.Order.status == status)
    if company_id:
        query = query.where(m.Order.company_id == company_id)
    if created_by_agent is not None:
        query = query.where(m.Order.created_by_agent.is_(created_by_agent))
    return paginate(session, query, page, page_size)


def get_order(session: Session, order_id: uuid.UUID) -> m.Order:
    """Return an order or raise NotFoundError."""
    order = session.get(m.Order, order_id)
    if order is None:
        raise NotFoundError("Pedido no encontrado")
    return order


def _check_customer(session: Session, company_id: uuid.UUID, contact_id: uuid.UUID | None) -> m.Company:
    """Return the company and verify that the contact (if any) belongs to it."""
    company = session.get(m.Company, company_id)
    if company is None:
        raise NotFoundError("Empresa no encontrada")
    if contact_id:
        contact = session.get(m.Contact, contact_id)
        if contact is None or contact.company_id != company.id:
            raise InvalidReferenceError("El contacto no existe o no pertenece a la empresa")
    return company


def _check_product(session: Session, product_id: uuid.UUID, quantity: Decimal) -> m.Product:
    """Return the active product and verify the quantity is positive."""
    product = session.get(m.Product, product_id)
    if product is None or not product.is_active:
        raise InvalidReferenceError(f"Producto no encontrado: {product_id}")
    if quantity <= 0:
        raise InvalidReferenceError(f"Cantidad no válida para {product.name}")
    return product


def create_order(
    session: Session,
    *,
    company_id: uuid.UUID,
    items: list[dict],
    contact_id: uuid.UUID | None = None,
    delivery_date: date | None = None,
    interaction: m.Interaction | None = None,
    created_by_agent: bool = False,
    force_link: bool = False,
) -> m.Order:
    """Create an order with its lines and commit it; every id and quantity is validated first.

    `items` are dicts with `product_id` (UUID), `quantity` (Decimal) and optionally `unit`.
    `interaction` is the voice note the order comes from: it is linked to the customer when it has
    none yet (or always when `force_link`). Without a delivery date an alert asks the user for it.
    """
    company = _check_customer(session, company_id, contact_id)
    if not items:
        raise InvalidReferenceError("El pedido no tiene líneas")
    lines = []
    for item in items:
        product = _check_product(session, item["product_id"], item["quantity"])
        lines.append(m.OrderItem(
            product_id=product.id, quantity=item["quantity"], unit=item.get("unit") or product.base_unit,
        ))
    order = m.Order(
        company_id=company.id, contact_id=contact_id, requested_at=datetime.now().replace(microsecond=0),
        requested_delivery_date=delivery_date, status=e.OrderStatus.NEW,
        source_interaction_id=interaction.id if interaction else None,
        created_by_agent=created_by_agent, items=lines,
    )
    session.add(order)
    session.commit()
    if delivery_date is None:
        # The order is kept: the user is asked to fill in the date instead of losing the request
        alerts_svc.create_alert(
            session, type=e.AlertType.MISSING_DELIVERY_DATE, severity=e.AlertSeverity.WARNING,
            message=f"El pedido de {company.name} no tiene fecha de entrega: complétala.",
            order_id=order.id, company_id=company.id, interaction_id=interaction.id if interaction else None,
            dedupe_key=f"{e.AlertType.MISSING_DELIVERY_DATE}:order:{order.id}",
        )
    if interaction and (force_link or interaction.company_id is None):
        interactions_svc.update_interaction(
            session, interaction.id, s.InteractionUpdate(company_id=company.id, contact_id=contact_id)
        )
    return order


def notify_note_processed(session: Session, interaction: m.Interaction, order_id: uuid.UUID | None) -> None:
    """Raise the "note processed" alert: who the note was linked to and the order created, if any.

    The alert carries the data (`data`) so the user can check it and edit it from the notification.
    """
    session.refresh(interaction)
    company, contact = interaction.company, interaction.contact
    order = session.get(m.Order, order_id) if order_id else None
    contact_name = f"{contact.first_name} {contact.last_name or ''}".strip() if contact else None
    parts = [f"Nota procesada: vinculada a {company.name}" if company else "Nota procesada: sin empresa vinculada"]
    if contact_name:
        parts[0] += f" ({contact_name})"
    if order:
        lines = ", ".join(f"{i.quantity.normalize():f} {i.unit} de {i.product.name}" for i in order.items)
        delivery = f"{order.requested_delivery_date:%d/%m/%Y}" if order.requested_delivery_date else "sin fecha"
        parts.append(f"Pedido creado: {lines} (entrega: {delivery}).")
    alerts_svc.create_alert(
        session, type=e.AlertType.NOTE_PROCESSED, severity=e.AlertSeverity.INFO, message=" ".join(parts),
        interaction_id=interaction.id, company_id=company.id if company else None, order_id=order_id,
        data={
            "company_name": company.name if company else None,
            "contact_id": str(contact.id) if contact else None,
            "contact_name": contact_name,
        },
        dedupe_key=f"{e.AlertType.NOTE_PROCESSED}:interaction:{interaction.id}",
    )


def _update_items(session: Session, order: m.Order, items: list[s.OrderItemIn]) -> None:
    """Make the lines of `order` match `items`: change the ones with id, add the new, remove the rest."""
    if not items:
        raise InvalidReferenceError("El pedido no tiene líneas")
    by_id = {line.id: line for line in order.items}
    for item in items:
        _check_product(session, item.product_id, item.quantity)
        if item.id is not None and item.id not in by_id:
            raise InvalidReferenceError("Una de las líneas no pertenece al pedido")
    kept = {item.id for item in items if item.id}
    for line_id in by_id.keys() - kept:
        deletion.delete_record(session, m.OrderItem, line_id)
    for item in items:
        product = session.get(m.Product, item.product_id)
        unit = item.unit or product.base_unit
        if item.id is None:
            session.add(m.OrderItem(order_id=order.id, product_id=product.id, quantity=item.quantity, unit=unit))
        else:
            line = by_id[item.id]
            line.product_id, line.quantity, line.unit = product.id, item.quantity, unit
    session.flush()


def update_order(session: Session, order_id: uuid.UUID, data: s.OrderUpdate) -> m.Order:
    """Apply the fields sent in `data`; the contact must belong to the (new) company."""
    order = get_order(session, order_id)
    changes = data.model_dump(exclude_unset=True)
    items = data.items if "items" in changes else None
    changes.pop("items", None)
    company_id = changes.get("company_id", order.company_id)
    contact_id = changes.get("contact_id", order.contact_id)
    _check_customer(session, company_id, contact_id)
    if items is not None:
        _update_items(session, order, items)
    for key, value in changes.items():
        setattr(order, key, value)
    session.commit()
    session.expire(order)
    return session.get(m.Order, order_id)
