"""Esquema de la base de datos de El Setero Manolo (ver El_Setero_Manolo_Data_Model_v2.xlsx).

Solo se guardan datos "de verdad". Todo lo calculado (stock disponible, costes medios,
precios sugeridos, márgenes, saldo de facturas) vive en las vistas de views.py.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, with_loader_criteria

from . import enums as e
from .audit import current_actor
from .config import settings
from .utils import enum_column, pk_column

QTY = Numeric(12, 3)  # cantidades (kg, etc.)
MONEY = Numeric(12, 4)  # precios y costes unitarios
PCT = Numeric(5, 4)  # porcentajes como fracción: 0.1000 = 10 %


def _now() -> datetime:
    """Current local time, as the other (naive) datetime columns store it."""
    return datetime.now()


class AuditMixin:
    """Columns every table has: who created the row and when, when it last changed, soft delete.

    `created_by` is the email of the logged-in user (or the default actor for scripts and agents).
    A deleted row keeps existing in the database with `deleted_at` set and disappears from every
    ORM query (see the filter at the end of the file).
    """

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    modified_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
    created_by: Mapped[str] = mapped_column(String(100))  # filled by the before_insert listener
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)
    deleted_by: Mapped[str | None] = mapped_column(String(100))


class Base(AuditMixin, DeclarativeBase):
    """Declarative base for all tables: they all inherit the audit and soft-delete columns."""


@event.listens_for(Base, "before_insert", propagate=True)
def _fill_created_by(mapper, connection, target) -> None:
    """Record the author of every new row, whatever code inserts it."""
    if not target.created_by:
        target.created_by = current_actor()


# Soft delete: rows with deleted_at set are invisible to every ORM select (also in relationships
# and sub-queries). Pass execution_options(include_deleted=True) to see them.
@event.listens_for(Session, "do_orm_execute")
def _hide_deleted(state) -> None:
    """Add `deleted_at IS NULL` to every ORM SELECT unless the query asks for deleted rows."""
    if state.is_select and not state.execution_options.get("include_deleted", False):
        state.statement = state.statement.options(
            with_loader_criteria(Base, lambda cls: cls.deleted_at.is_(None), include_aliases=True)
        )


# --------------------------------------------------------------------------- CRM


class Company(Base):
    """A business that is a customer, a supplier, or both."""

    __tablename__ = "company"
    __table_args__ = (Index("uq_company_tax_id", "tax_id", unique=True, postgresql_where=text("deleted_at IS NULL")),)

    id: Mapped[uuid.UUID] = pk_column()
    name: Mapped[str] = mapped_column(String(200))
    # Fiscal NIF/CIF: the one printed on invoices
    tax_id: Mapped[str | None] = mapped_column(String(30))
    # Billing data printed on invoices; it differs from the trade name when the business is a
    # self-employed person (the owner's name and address go on the invoice)
    billing_name: Mapped[str | None] = mapped_column(String(200))
    billing_address: Mapped[str | None] = mapped_column(String(300))
    website: Mapped[str | None] = mapped_column(String(300))
    phone: Mapped[str | None] = mapped_column(String(20))  # E.164
    email: Mapped[str | None] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(String(300))
    city: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(100))
    roles: Mapped[list[str]] = mapped_column(JSON)  # valores de enums.Role
    type: Mapped[list[str]] = mapped_column(JSON)  # valores de enums.CompanyType
    customer_status: Mapped[e.CustomerStatus | None] = mapped_column(enum_column(e.CustomerStatus))
    supplier_status: Mapped[e.SupplierStatus | None] = mapped_column(enum_column(e.SupplierStatus))
    description: Mapped[str | None] = mapped_column(Text)

    contacts: Mapped[list["Contact"]] = relationship(back_populates="company")
    def __str__(self) -> str:
        """Readable name shown in the interface."""
        return self.name


class Contact(Base):
    """A person working for a company."""

    __tablename__ = "contact"

    id: Mapped[uuid.UUID] = pk_column()
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("company.id"), index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    position: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(20), index=True)  # E.164; identifica en WhatsApp
    email: Mapped[str | None] = mapped_column(String(200))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    summary: Mapped[str | None] = mapped_column(Text)

    company: Mapped[Company] = relationship(back_populates="contacts", lazy="joined")
    def __str__(self) -> str:
        """Readable name shown in the interface."""
        return f"{self.first_name} {self.last_name or ''} ({self.company.name})".replace("  ", " ")


class Interaction(Base):
    """A call, email, meeting, WhatsApp exchange or other contact with a company."""

    __tablename__ = "interaction"
    # evita duplicados por canal (los borrados no cuentan)
    __table_args__ = (
        Index("uq_interaction_source_external_id", "source", "external_id", unique=True,
              postgresql_where=text("deleted_at IS NULL")),
    )

    id: Mapped[uuid.UUID] = pk_column()
    # Nullable: a voice note can be saved before it is linked to a company (an agent links it later)
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("company.id"), index=True)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contact.id"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    type: Mapped[e.InteractionType] = mapped_column(enum_column(e.InteractionType))
    direction: Mapped[e.Direction | None] = mapped_column(enum_column(e.Direction))
    summary: Mapped[str | None] = mapped_column(Text)  # empty for voice notes: only the transcript is kept
    notes: Mapped[str | None] = mapped_column(Text)
    source: Mapped[e.InteractionSource] = mapped_column(enum_column(e.InteractionSource))
    audio_url: Mapped[str | None] = mapped_column(String(500))
    transcript: Mapped[str | None] = mapped_column(Text)
    processing_status: Mapped[e.ProcessingStatus] = mapped_column(
        enum_column(e.ProcessingStatus), default=e.ProcessingStatus.PENDING, index=True
    )
    external_id: Mapped[str | None] = mapped_column(String(200))
    company: Mapped[Optional["Company"]] = relationship(foreign_keys=[company_id], lazy="joined")
    contact: Mapped[Optional["Contact"]] = relationship(foreign_keys=[contact_id], lazy="joined")

    def __str__(self) -> str:
        """Readable name shown in the interface."""
        company = self.company.name if self.company else "Sin asignar"
        return f"{self.occurred_at:%Y-%m-%d} · {company} · {self.type}"


# ------------------------------------------------------------------ Productos y stock


class Product(Base):
    """A commercial product offered for sale."""

    __tablename__ = "product"

    id: Mapped[uuid.UUID] = pk_column()
    name: Mapped[str] = mapped_column(String(200))
    species: Mapped[str | None] = mapped_column(String(200))
    format: Mapped[e.ProductFormat] = mapped_column(enum_column(e.ProductFormat))
    description: Mapped[str | None] = mapped_column(Text)
    base_unit: Mapped[str] = mapped_column(String(20), default=settings.inventory.default_unit)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    tax_rate: Mapped[Decimal] = mapped_column(PCT)
    target_net_margin: Mapped[Decimal] = mapped_column(PCT)

    __table_args__ = (
        Index("uq_product_name", "name", unique=True, postgresql_where=text("deleted_at IS NULL")),
        CheckConstraint("target_net_margin >= 0 AND target_net_margin < 1", name="ck_margin_range"),
        CheckConstraint("tax_rate >= 0 AND tax_rate < 1", name="ck_tax_range"),
    )
    def __str__(self) -> str:
        """Readable name shown in the interface."""
        return self.name


class Lot(Base):
    """A physical batch of a product, kept for stock control and traceability."""

    __tablename__ = "lot"

    id: Mapped[uuid.UUID] = pk_column()
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product.id"), index=True)
    supplier_company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("company.id"))
    lot_code: Mapped[str] = mapped_column(String(100))
    received_at: Mapped[datetime] = mapped_column(DateTime)
    quantity_received: Mapped[Decimal] = mapped_column(QTY)
    unit: Mapped[str] = mapped_column(String(20), default=settings.inventory.default_unit)
    purchase_cost_per_unit: Mapped[Decimal] = mapped_column(MONEY)
    additional_costs: Mapped[Decimal] = mapped_column(MONEY, default=0)  # total del lote
    expiry_date: Mapped[date | None] = mapped_column(Date)
    # Bloqueo manual (calidad, sanidad). Disponible/agotado/caducado se derivan en lot_stock.
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        Index("uq_lot_lot_code", "lot_code", unique=True, postgresql_where=text("deleted_at IS NULL")),
        CheckConstraint("quantity_received > 0", name="ck_lot_qty_positive"),
    )
    product: Mapped["Product"] = relationship(foreign_keys=[product_id], lazy="joined")
    supplier: Mapped[Optional["Company"]] = relationship(foreign_keys=[supplier_company_id], lazy="joined")

    def __str__(self) -> str:
        """Readable name shown in the interface."""
        return f"{self.lot_code} ({self.product.name})"


class LotAdjustment(Base):
    """A write-off or correction (shrinkage, expiry, sample, gift) applied to a lot."""

    __tablename__ = "lot_adjustment"

    id: Mapped[uuid.UUID] = pk_column()
    lot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lot.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(QTY)  # positivo = reducción
    reason: Mapped[e.AdjustmentReason] = mapped_column(enum_column(e.AdjustmentReason))
    adjusted_at: Mapped[datetime] = mapped_column(DateTime)
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (CheckConstraint("quantity > 0", name="ck_adj_qty_positive"),)
    lot: Mapped["Lot"] = relationship(foreign_keys=[lot_id], lazy="joined")

    def __str__(self) -> str:
        """Readable name shown in the interface."""
        return f"{self.reason} {self.quantity} · {self.lot.lot_code}"


# ------------------------------------------------------------------------ Pedidos


class Order(Base):
    """An explicit customer request; it can exist before a price is agreed."""

    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = pk_column()
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("company.id"), index=True)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contact.id"))
    requested_at: Mapped[datetime] = mapped_column(DateTime)
    requested_delivery_date: Mapped[date | None] = mapped_column(Date)  # NUEVO respecto al Excel
    status: Mapped[e.OrderStatus] = mapped_column(enum_column(e.OrderStatus), default=e.OrderStatus.NEW)
    notes: Mapped[str | None] = mapped_column(Text)
    source_interaction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("interaction.id"))
    created_by_agent: Mapped[bool] = mapped_column(Boolean, default=False)

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order")
    company: Mapped["Company"] = relationship(foreign_keys=[company_id], lazy="joined")
    contact: Mapped[Optional["Contact"]] = relationship(foreign_keys=[contact_id], lazy="joined")
    source_interaction: Mapped[Optional["Interaction"]] = relationship(foreign_keys=[source_interaction_id], lazy="joined")

    def __str__(self) -> str:
        """Readable name shown in the interface."""
        return f"{self.company.name} · {self.requested_at:%Y-%m-%d}"


class OrderItem(Base):
    """One requested product within an order."""

    __tablename__ = "order_item"

    id: Mapped[uuid.UUID] = pk_column()
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product.id"))
    quantity: Mapped[Decimal] = mapped_column(QTY)
    unit: Mapped[str] = mapped_column(String(20), default=settings.inventory.default_unit)
    notes: Mapped[str | None] = mapped_column(Text)
    # Único precio que se guarda: el acordado con el cliente (IVA incluido). Vacío hasta acordarlo.
    agreed_unit_price_after_tax: Mapped[Decimal | None] = mapped_column(MONEY)

    order: Mapped[Order] = relationship(back_populates="items", lazy="joined")

    __table_args__ = (CheckConstraint("quantity > 0", name="ck_item_qty_positive"),)
    product: Mapped["Product"] = relationship(foreign_keys=[product_id], lazy="joined")

    def __str__(self) -> str:
        """Readable name shown in the interface."""
        return f"{self.quantity} {self.unit} {self.product.name} · {self.order}"


class LotAllocation(Base):
    """Stock of a lot reserved for, or consumed by, an order line."""

    __tablename__ = "lot_allocation"

    id: Mapped[uuid.UUID] = pk_column()
    lot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lot.id"), index=True)
    order_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("order_item.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(QTY)
    status: Mapped[e.AllocationStatus] = mapped_column(
        enum_column(e.AllocationStatus), default=e.AllocationStatus.RESERVED
    )
    allocated_at: Mapped[datetime] = mapped_column(DateTime)

    __table_args__ = (CheckConstraint("quantity > 0", name="ck_alloc_qty_positive"),)
    lot: Mapped["Lot"] = relationship(foreign_keys=[lot_id], lazy="joined")
    order_item: Mapped["OrderItem"] = relationship(foreign_keys=[order_item_id], lazy="joined")

    def __str__(self) -> str:
        """Readable name shown in the interface."""
        return f"{self.quantity} from {self.lot.lot_code}"


# ------------------------------------------------------------ Facturación y cobros


class Invoice(Base):
    """A billing document; it may come from an order or be issued by hand."""

    __tablename__ = "invoice"
    __table_args__ = (UniqueConstraint("invoice_type", "fiscal_year", "sequence_number"),)

    id: Mapped[uuid.UUID] = pk_column()
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id"), index=True)
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("company.id"), index=True)
    invoice_type: Mapped[e.InvoiceType] = mapped_column(
        enum_column(e.InvoiceType), default=e.InvoiceType.VDA
    )
    invoice_number: Mapped[str | None] = mapped_column(String(50), unique=True)
    fiscal_year: Mapped[int | None] = mapped_column()
    sequence_number: Mapped[int | None] = mapped_column()
    issue_date: Mapped[date | None] = mapped_column(Date)  # fecha de expedición
    operation_date: Mapped[date | None] = mapped_column(Date)  # fecha de operación
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[e.InvoiceStatus] = mapped_column(
        enum_column(e.InvoiceStatus), default=e.InvoiceStatus.DRAFT
    )
    # Historical copy of the company billing data as issued: later edits to the company
    # never change an issued invoice.
    customer_name: Mapped[str | None] = mapped_column(String(200))
    customer_tax_id: Mapped[str | None] = mapped_column(String(30))
    customer_address: Mapped[str | None] = mapped_column(String(300))
    notes: Mapped[str | None] = mapped_column(Text)
    # Emailing of the PDF
    email_status: Mapped[e.EmailStatus] = mapped_column(
        enum_column(e.EmailStatus), default=e.EmailStatus.PENDING
    )
    email_recipient: Mapped[str | None] = mapped_column(String(200))
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    email_error: Mapped[str | None] = mapped_column(Text)
    # The total is NOT stored: it is calculated from the lines (view invoice_balance).

    items: Mapped[list["InvoiceItem"]] = relationship(back_populates="invoice", order_by="InvoiceItem.position")
    order: Mapped[Optional["Order"]] = relationship(foreign_keys=[order_id], lazy="joined")
    company: Mapped[Optional["Company"]] = relationship(foreign_keys=[company_id], lazy="joined")

    def __str__(self) -> str:
        """Readable name shown in the interface."""
        return f"{self.invoice_number or 'Draft'} · {self.customer_name or self.order}"


class InvoiceCounter(Base):
    """Last number issued per series and year; bumped atomically so numbers have no gaps."""

    __tablename__ = "invoice_counter"

    invoice_type: Mapped[e.InvoiceType] = mapped_column(enum_column(e.InvoiceType), primary_key=True)
    fiscal_year: Mapped[int] = mapped_column(primary_key=True)
    last_number: Mapped[int] = mapped_column(default=0)


class InvoiceItem(Base):
    """One line of an invoice."""

    __tablename__ = "invoice_item"

    id: Mapped[uuid.UUID] = pk_column()
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoice.id"), index=True)
    order_item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("order_item.id"))
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("product.id"))
    position: Mapped[int] = mapped_column(default=0)
    product_name: Mapped[str | None] = mapped_column(String(200))  # copy, as issued
    description: Mapped[str] = mapped_column(Text)
    quantity: Mapped[Decimal] = mapped_column(QTY)
    unit: Mapped[str] = mapped_column(String(20))
    unit_price: Mapped[Decimal] = mapped_column(MONEY)  # sin IVA; se copia del pedido al emitir
    tax_rate: Mapped[Decimal] = mapped_column(PCT)
    notes: Mapped[str | None] = mapped_column(Text)

    invoice: Mapped[Invoice] = relationship(back_populates="items")
    order_item: Mapped[Optional["OrderItem"]] = relationship(foreign_keys=[order_item_id], lazy="joined")

    def __str__(self) -> str:
        """Readable name shown in the interface."""
        return f"{self.description} × {self.quantity}"


class Payment(Base):
    """A payment received against an invoice."""

    __tablename__ = "payment"

    id: Mapped[uuid.UUID] = pk_column()
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoice.id"), index=True)
    paid_at: Mapped[datetime] = mapped_column(DateTime)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    method: Mapped[e.PaymentMethod | None] = mapped_column(enum_column(e.PaymentMethod))
    reference: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (CheckConstraint("amount > 0", name="ck_payment_positive"),)
    invoice: Mapped["Invoice"] = relationship(foreign_keys=[invoice_id], lazy="joined")

    def __str__(self) -> str:
        """Readable name shown in the interface."""
        return f"{self.amount} · {self.paid_at:%Y-%m-%d}"


# ----------------------------------------------------------------------- Agentes


class AgentExecution(Base):
    """Log of one run of an AI agent."""

    __tablename__ = "agent_execution"

    id: Mapped[uuid.UUID] = pk_column()
    agent_name: Mapped[str] = mapped_column(String(100))
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    interaction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("interaction.id"))
    input: Mapped[dict | None] = mapped_column(JSON)
    tool_calls: Mapped[list | None] = mapped_column(JSON)
    output: Mapped[dict | str | None] = mapped_column(JSON)
    status: Mapped[e.AgentStatus] = mapped_column(enum_column(e.AgentStatus))
    model: Mapped[str | None] = mapped_column(String(100))
    cost_eur: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    interaction: Mapped[Optional["Interaction"]] = relationship(foreign_keys=[interaction_id], lazy="joined")

    def __str__(self) -> str:
        """Readable name shown in the interface."""
        return f"{self.agent_name} · {self.started_at:%Y-%m-%d %H:%M}"
