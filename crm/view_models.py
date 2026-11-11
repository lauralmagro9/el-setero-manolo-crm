"""Read-only ORM mappings of the SQL views, so the interface can list them like tables.

They use their own declarative base so Alembic never tries to create them as tables.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, Numeric, String, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class ViewBase(DeclarativeBase):
    """Declarative base for the read-only view mappings."""


class LotStock(ViewBase):
    """Stock, cost and status of each lot (view lot_stock)."""

    __tablename__ = "lot_stock"

    lot_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    product_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    product_name: Mapped[str] = mapped_column(String)
    lot_code: Mapped[str] = mapped_column(String)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    is_blocked: Mapped[bool] = mapped_column(Boolean)
    quantity_received: Mapped[Decimal] = mapped_column(Numeric)
    reserved_quantity: Mapped[Decimal] = mapped_column(Numeric)
    consumed_quantity: Mapped[Decimal] = mapped_column(Numeric)
    adjusted_quantity: Mapped[Decimal] = mapped_column(Numeric)
    available_quantity: Mapped[Decimal] = mapped_column(Numeric)
    additional_costs_per_unit: Mapped[Decimal] = mapped_column(Numeric)
    total_cost_per_unit: Mapped[Decimal] = mapped_column(Numeric)
    total_cost: Mapped[Decimal] = mapped_column(Numeric)
    status: Mapped[str] = mapped_column(String)


class OrderItemPricing(ViewBase):
    """Average cost, suggested price and margin of each order line (view order_item_pricing)."""

    __tablename__ = "order_item_pricing"

    order_item_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    order_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    product_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    product_name: Mapped[str] = mapped_column(String)
    customer_name: Mapped[str] = mapped_column(String)
    requested_delivery_date: Mapped[date | None] = mapped_column(Date)
    quantity: Mapped[Decimal] = mapped_column(Numeric)
    agreed_unit_price_after_tax: Mapped[Decimal | None] = mapped_column(Numeric)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric)
    target_net_margin: Mapped[Decimal] = mapped_column(Numeric)
    allocated_quantity: Mapped[Decimal | None] = mapped_column(Numeric)
    avg_cost_per_unit: Mapped[Decimal | None] = mapped_column(Numeric)
    suggested_unit_price_before_tax: Mapped[Decimal | None] = mapped_column(Numeric)
    suggested_unit_price_after_tax: Mapped[Decimal | None] = mapped_column(Numeric)
    agreed_unit_price_before_tax: Mapped[Decimal | None] = mapped_column(Numeric)
    final_margin: Mapped[Decimal | None] = mapped_column(Numeric)


class InvoiceBalance(ViewBase):
    """Total, amount paid, outstanding amount and real status of each invoice (view invoice_balance)."""

    __tablename__ = "invoice_balance"

    invoice_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    customer_name: Mapped[str | None] = mapped_column(String)
    invoice_number: Mapped[str | None] = mapped_column(String)
    issue_date: Mapped[date | None] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date)
    stored_status: Mapped[str] = mapped_column(String)
    total_before_tax: Mapped[Decimal] = mapped_column(Numeric)
    total_amount: Mapped[Decimal] = mapped_column(Numeric)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric)
    outstanding_amount: Mapped[Decimal] = mapped_column(Numeric)
    status: Mapped[str] = mapped_column(String)
