"""Pydantic schemas for the API input and output."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from . import enums as e
from .config import settings

T = TypeVar("T")


class ORMModel(BaseModel):
    """Base of the output schemas: they are built from SQLAlchemy objects."""

    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    """One page of a listing."""

    items: list[T]
    total: int
    page: int
    page_size: int


# --------------------------------------------------------------------- Companies


class CompanyIn(BaseModel):
    """Data to create a company."""

    name: str = Field(min_length=1, max_length=200)
    tax_id: str | None = Field(default=None, max_length=30)
    billing_name: str | None = Field(default=None, max_length=200)
    billing_address: str | None = Field(default=None, max_length=300)
    website: str | None = Field(default=None, max_length=300)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=200)
    # Mandatory when creating: it must include the city, from which province and country are found
    address: str = Field(min_length=1, max_length=300)
    city: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    roles: list[e.Role] = Field(min_length=1)
    type: list[e.CompanyType] = Field(min_length=1)
    customer_status: e.CustomerStatus | None = None
    supplier_status: e.SupplierStatus | None = None
    description: str | None = None

    @model_validator(mode="after")
    def _default_billing_address(self):
        """Bill to the normal address unless a different billing address is given."""
        if not self.billing_address:
            self.billing_address = self.address
        return self


class CompanyUpdate(BaseModel):
    """Partial update of a company: only the fields sent are changed."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    tax_id: str | None = Field(default=None, max_length=30)
    billing_name: str | None = Field(default=None, max_length=200)
    billing_address: str | None = Field(default=None, max_length=300)
    website: str | None = Field(default=None, max_length=300)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=200)
    address: str | None = Field(default=None, max_length=300)
    city: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    roles: list[e.Role] | None = Field(default=None, min_length=1)
    type: list[e.CompanyType] | None = Field(default=None, min_length=1)
    customer_status: e.CustomerStatus | None = None
    supplier_status: e.SupplierStatus | None = None
    description: str | None = None

    @field_validator("name", "roles", "type")
    @classmethod
    def _not_null(cls, value):
        """Required columns can be changed but not emptied."""
        if value is None:
            raise ValueError("No puede ser nulo")
        return value


class CustomerStatusUpdate(BaseModel):
    """Move a company to another step of the customer pipeline."""

    customer_status: e.CustomerStatus | None


class CompanyRef(ORMModel):
    """Minimal reference to a company, embedded in other records."""

    id: uuid.UUID
    name: str


class CompanyOut(ORMModel):
    """A company as returned by the API."""

    id: uuid.UUID
    name: str
    tax_id: str | None
    billing_name: str | None
    billing_address: str | None
    website: str | None
    phone: str | None
    email: str | None
    address: str | None
    city: str | None
    region: str | None
    country: str | None
    roles: list[str]
    type: list[str]
    customer_status: e.CustomerStatus | None
    supplier_status: e.SupplierStatus | None
    description: str | None


class AddressParts(BaseModel):
    """City, province and country found in a free-text address (None when unknown)."""

    city: str | None = None
    region: str | None = None
    country: str | None = None


# ---------------------------------------------------------------------- Contacts


class ContactIn(BaseModel):
    """Data to create a contact."""

    company_id: uuid.UUID
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    position: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=200)
    is_primary: bool = False
    summary: str | None = None


class ContactUpdate(BaseModel):
    """Partial update of a contact."""

    company_id: uuid.UUID | None = None
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    position: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=200)
    is_primary: bool | None = None
    summary: str | None = None

    @field_validator("company_id", "first_name", "is_primary")
    @classmethod
    def _not_null(cls, value):
        """Required columns can be changed but not emptied."""
        if value is None:
            raise ValueError("No puede ser nulo")
        return value


class ContactRef(ORMModel):
    """Minimal reference to a contact, embedded in other records."""

    id: uuid.UUID
    first_name: str
    last_name: str | None


class ContactOut(ORMModel):
    """A contact as returned by the API."""

    id: uuid.UUID
    company_id: uuid.UUID
    first_name: str
    last_name: str | None
    position: str | None
    phone: str | None
    email: str | None
    is_primary: bool
    summary: str | None
    company: CompanyRef


class CompanyDetail(CompanyOut):
    """A company with its contacts."""

    contacts: list[ContactOut]


# ------------------------------------------------------------------ Interactions


class InteractionIn(BaseModel):
    """Data to register an interaction by hand."""

    company_id: uuid.UUID
    contact_id: uuid.UUID | None = None
    occurred_at: datetime | None = None
    type: e.InteractionType
    direction: e.Direction | None = None
    summary: str = Field(min_length=1)
    notes: str | None = None


class InteractionUpdate(BaseModel):
    """Partial update of an interaction (e.g. assign a company to an unassigned voice note)."""

    company_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    occurred_at: datetime | None = None
    type: e.InteractionType | None = None
    direction: e.Direction | None = None
    summary: str | None = None
    notes: str | None = None

    @field_validator("occurred_at", "type")
    @classmethod
    def _not_null(cls, value):
        """Required columns can be changed but not emptied."""
        if value is None:
            raise ValueError("No puede ser nulo")
        return value


class InteractionOut(ORMModel):
    """An interaction as returned by the API."""

    id: uuid.UUID
    company_id: uuid.UUID | None
    contact_id: uuid.UUID | None
    occurred_at: datetime
    type: e.InteractionType
    direction: e.Direction | None
    summary: str | None
    notes: str | None
    source: e.InteractionSource
    transcript: str | None
    processing_status: e.ProcessingStatus
    created_by: str | None
    company: CompanyRef | None
    contact: ContactRef | None


# --------------------------------------------------------------------- Dashboard


class StatusCount(BaseModel):
    """Number of customers in one pipeline status."""

    customer_status: e.CustomerStatus
    count: int


class LotAlert(ORMModel):
    """A lot that needs attention (about to expire or running out)."""

    lot_id: uuid.UUID
    product_name: str
    lot_code: str
    expiry_date: date | None
    available_quantity: Decimal
    status: str


class DashboardOut(BaseModel):
    """Key figures shown on the home screen."""

    customers_by_status: list[StatusCount]
    interactions_short_window: int
    interactions_long_window: int
    short_window_days: int
    long_window_days: int
    pending_interactions: int
    unassigned_voice_notes: int
    expiring_lots: list[LotAlert]
    low_stock_lots: list[LotAlert]
    recent_interactions: list[InteractionOut]


# ---------------------------------------------------------------------- Products


class ProductIn(BaseModel):
    """Data to create a product; VAT and margin are fractions (0.10 = 10 %)."""

    name: str = Field(min_length=1, max_length=200)
    species: str | None = Field(default=None, max_length=200)
    format: e.ProductFormat
    description: str | None = None
    base_unit: str = Field(default_factory=lambda: settings.inventory.default_unit, min_length=1, max_length=20)
    is_active: bool = True
    tax_rate: Decimal = Field(default_factory=lambda: Decimal(str(settings.invoicing.vat_rate)), ge=0, lt=1, decimal_places=4)
    target_net_margin: Decimal = Field(ge=0, lt=1, decimal_places=4)


class ProductUpdate(BaseModel):
    """Partial update of a product: only the fields sent are changed."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    species: str | None = Field(default=None, max_length=200)
    format: e.ProductFormat | None = None
    description: str | None = None
    base_unit: str | None = Field(default=None, min_length=1, max_length=20)
    is_active: bool | None = None
    tax_rate: Decimal | None = Field(default=None, ge=0, lt=1, decimal_places=4)
    target_net_margin: Decimal | None = Field(default=None, ge=0, lt=1, decimal_places=4)

    @field_validator("name", "format", "base_unit", "is_active", "tax_rate", "target_net_margin")
    @classmethod
    def _not_null(cls, value):
        """Required columns can be changed but not emptied."""
        if value is None:
            raise ValueError("No puede ser nulo")
        return value


class ProductOut(ORMModel):
    """A product as returned by the API."""

    id: uuid.UUID
    name: str
    species: str | None
    format: e.ProductFormat
    description: str | None
    base_unit: str
    is_active: bool
    tax_rate: Decimal
    target_net_margin: Decimal


# ---------------------------------------------------------------------- Invoices


class InvoiceLineIn(BaseModel):
    """One line of an invoice (the unit price is before VAT); the product is mandatory."""

    product_id: uuid.UUID
    description: str = Field(min_length=1)
    unit: str = Field(min_length=1, max_length=20)
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    unit_price: Decimal = Field(ge=0, max_digits=12, decimal_places=4)


class PreviewLineIn(BaseModel):
    """What is needed to total a line before the product is even chosen."""

    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    unit_price: Decimal = Field(ge=0, max_digits=12, decimal_places=4)


class InvoicePreviewIn(BaseModel):
    """Lines to total before confirming."""

    lines: list[PreviewLineIn] = Field(min_length=1)


class NewInvoiceCompany(CompanyIn):
    """A company created while issuing an invoice.

    It is a customer by default (role and status "Cliente") and the fiscal data is mandatory:
    name, NIF/CIF and address (the billing address falls back to the normal one).
    """

    roles: list[e.Role] = Field(default_factory=lambda: [e.Role.CUSTOMER], min_length=1)
    customer_status: e.CustomerStatus | None = e.CustomerStatus.CUSTOMER
    tax_id: str = Field(min_length=1, max_length=30)
    billing_name: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def _billing_address_required(self):
        """An invoice needs an address: either the billing one or the normal one."""
        if not self.billing_address:
            raise ValueError("Falta la dirección fiscal")
        return self


class InvoiceCreate(BaseModel):
    """Everything needed to issue an invoice.

    The invoice belongs to a single company: either an existing one (`company_id`, whose billing
    data is copied into the invoice) or a new one (`new_company`). Dates default to today.
    """

    invoice_type: e.InvoiceType = e.InvoiceType.VDA
    issue_date: date | None = None  # fecha de expedición
    operation_date: date | None = None  # fecha de operación
    company_id: uuid.UUID | None = None
    new_company: NewInvoiceCompany | None = None
    notes: str | None = None
    lines: list[InvoiceLineIn] = Field(min_length=1)

    @model_validator(mode="after")
    def _exactly_one_company(self):
        """Choose an existing company or create a new one, not both and not neither."""
        if (self.company_id is None) == (self.new_company is None):
            raise ValueError("Indica una empresa existente o los datos de una empresa nueva")
        return self


class InvoiceTotals(BaseModel):
    """Amounts of an invoice."""

    line_amounts: list[Decimal]
    taxable_base: Decimal
    vat_rate: Decimal
    vat_amount: Decimal
    total: Decimal


class InvoiceConfig(BaseModel):
    """Settings the invoice form needs."""

    enabled_types: list[e.InvoiceType]
    vat_rate: Decimal


class InvoiceLineOut(ORMModel):
    """A line as stored."""

    id: uuid.UUID
    product_id: uuid.UUID | None
    product_name: str | None
    description: str
    unit: str
    quantity: Decimal
    unit_price: Decimal
    tax_rate: Decimal


class InvoiceOut(ORMModel):
    """An invoice with its lines and totals."""

    id: uuid.UUID
    invoice_number: str | None
    invoice_type: e.InvoiceType
    issue_date: date | None
    operation_date: date | None
    status: e.InvoiceStatus
    company_id: uuid.UUID | None
    customer_name: str | None
    customer_tax_id: str | None
    customer_address: str | None
    notes: str | None
    email_status: e.EmailStatus
    email_recipient: str | None
    email_sent_at: datetime | None
    email_error: str | None
    created_by: str | None
    items: list[InvoiceLineOut]
    totals: InvoiceTotals | None = None
