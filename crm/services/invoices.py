"""Business logic for manually issued invoices: numbering, saving, PDF and email."""

import logging
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from .. import enums as e
from .. import models as m
from .. import schemas as s
from ..audit import current_actor
from ..config import settings
from ..utils import calculate_totals, format_money, paginate
from .companies import get_company
from .errors import ConfigurationError, ConflictError, EmailError, InvalidReferenceError, NotFoundError
from .invoice_pdf import render_invoice_pdf
from .mailer import send_email

logger = logging.getLogger(__name__)


def vat_rate() -> Decimal:
    """Return the VAT rate applied to every line (settings invoicing.vat_rate)."""
    return Decimal(str(settings.invoicing.vat_rate))


def get_config() -> s.InvoiceConfig:
    """Return what the invoice form needs: the series that can be issued and the VAT rate."""
    return s.InvoiceConfig(
        enabled_types=[t for t in e.InvoiceType if t.value in settings.invoicing.enabled_types],
        vat_rate=vat_rate(),
    )


def preview_totals(lines: list[s.PreviewLineIn]) -> s.InvoiceTotals:
    """Compute the amounts of some lines without saving anything."""
    amounts, base, vat, total = calculate_totals([(l.quantity, l.unit_price) for l in lines], vat_rate())
    return s.InvoiceTotals(line_amounts=amounts, taxable_base=base, vat_rate=vat_rate(),
                           vat_amount=vat, total=total)


def to_out(invoice: m.Invoice) -> s.InvoiceOut:
    """Build the API representation of an invoice, totals included."""
    out = s.InvoiceOut.model_validate(invoice)
    rate = Decimal(str(invoice.items[0].tax_rate)) if invoice.items else vat_rate()
    amounts, base, vat, total = calculate_totals(
        [(Decimal(i.quantity), Decimal(i.unit_price)) for i in invoice.items], rate
    )
    out.totals = s.InvoiceTotals(line_amounts=amounts, taxable_base=base, vat_rate=rate,
                                 vat_amount=vat, total=total)
    return out


def _check_issuer() -> None:
    """Refuse to issue invoices while the seller's data is not configured."""
    if not settings.issuer.name or not settings.issuer.tax_id:
        raise ConfigurationError("Faltan los datos del emisor (ISSUER_NAME e ISSUER_TAX_ID en .env)")


def _next_number(session: Session, invoice_type: e.InvoiceType, year: int) -> tuple[int, str]:
    """Reserve the next sequence number of a series/year; return (sequence, formatted number).

    The counter row is locked until the surrounding transaction ends, so concurrent invoices
    never get the same number and a rolled-back invoice does not leave a gap.
    """
    sequence = session.execute(
        text(
            "INSERT INTO invoice_counter (invoice_type, fiscal_year, last_number, created_at, modified_at, created_by) "
            "VALUES (:t, :y, 1, :now, :now, :actor) ON CONFLICT (invoice_type, fiscal_year) "
            "DO UPDATE SET last_number = invoice_counter.last_number + 1, modified_at = :now "
            "RETURNING last_number"
        ),
        {"t": invoice_type.value, "y": year, "now": datetime.now(), "actor": current_actor()},
    ).scalar_one()
    prefix = settings.invoicing.series.as_dict()[invoice_type.value]
    digits = settings.invoicing.sequence_digits
    return sequence, f"{prefix}-{year}-{sequence:0{digits}d}"


def _resolve_company(session: Session, data: s.InvoiceCreate) -> m.Company:
    """Return the company to invoice: the chosen one, or a new one created from `new_company`."""
    if data.company_id:
        company = get_company(session, data.company_id)
        missing = [
            label for label, value in (
                ("nombre fiscal", company.billing_name), ("dirección fiscal", company.billing_address),
                ("NIF/CIF fiscal", company.tax_id),
            ) if not value
        ]
        if missing:
            raise InvalidReferenceError(
                f"Faltan los datos de facturación de la empresa: {', '.join(missing)}"
            )
        return company

    new = data.new_company
    if new.tax_id and session.scalar(select(m.Company.id).where(m.Company.tax_id == new.tax_id)):
        raise ConflictError("Ya existe una empresa con ese NIF/CIF: selecciónala en el buscador")
    company = m.Company(**new.model_dump(mode="json"))
    session.add(company)
    session.flush()
    return company


def create_invoice(session: Session, data: s.InvoiceCreate, created_by: str | None) -> m.Invoice:
    """Validate, number and save an invoice with its lines (one transaction).

    The company's billing data is copied into the invoice so later edits to the company do not
    alter it. Emailing is a separate step (`send_invoice`) so a mail failure never loses the invoice.
    """
    if data.invoice_type.value not in settings.invoicing.enabled_types:
        raise InvalidReferenceError(f"El tipo de factura {data.invoice_type.value} no está disponible todavía")
    _check_issuer()
    products = {}
    for line in data.lines:
        product = session.get(m.Product, line.product_id)
        if product is None:
            raise InvalidReferenceError("Producto no encontrado")
        products[line.product_id] = product
    try:
        company = _resolve_company(session, data)
        today = date.today()
        issue_date = data.issue_date or today
        sequence, number = _next_number(session, data.invoice_type, issue_date.year)
        invoice = m.Invoice(
            company_id=company.id, invoice_type=data.invoice_type, invoice_number=number,
            fiscal_year=issue_date.year, sequence_number=sequence, issue_date=issue_date,
            operation_date=data.operation_date or today, status=e.InvoiceStatus.ISSUED,
            customer_name=company.billing_name, customer_tax_id=company.tax_id,
            customer_address=company.billing_address, notes=data.notes,
            email_status=e.EmailStatus.PENDING, created_by=created_by,
            created_at=datetime.now().replace(microsecond=0),
        )
        invoice.items = [
            m.InvoiceItem(
                position=index, product_id=line.product_id, product_name=products[line.product_id].name,
                description=line.description, quantity=line.quantity, unit=line.unit,
                unit_price=line.unit_price, tax_rate=vat_rate(),
            )
            for index, line in enumerate(data.lines)
        ]
        session.add(invoice)
        session.commit()
    except Exception:
        session.rollback()
        raise
    logger.info("Invoice %s issued for company %s (by %s)", invoice.invoice_number, company.id, created_by)
    return get_invoice(session, invoice.id)


def get_invoice(session: Session, invoice_id: uuid.UUID) -> m.Invoice:
    """Return an invoice with its lines or raise NotFoundError."""
    invoice = session.get(m.Invoice, invoice_id)
    if invoice is None:
        raise NotFoundError("Factura no encontrada")
    return invoice


def list_invoices(
    session: Session,
    *,
    invoice_type: e.InvoiceType | None = None,
    email_status: e.EmailStatus | None = None,
    company_id: uuid.UUID | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 25,
):
    """Return (invoices, total), newest first."""
    query = select(m.Invoice).order_by(m.Invoice.issue_date.desc(), m.Invoice.created_at.desc(), m.Invoice.id)
    if invoice_type:
        query = query.where(m.Invoice.invoice_type == invoice_type)
    if email_status:
        query = query.where(m.Invoice.email_status == email_status)
    if company_id:
        query = query.where(m.Invoice.company_id == company_id)
    if search:
        like = f"%{search.strip()}%"
        query = query.where(or_(m.Invoice.invoice_number.ilike(like), m.Invoice.customer_name.ilike(like)))
    return paginate(session, query, page, page_size)


def send_invoice(session: Session, invoice_id: uuid.UUID) -> m.Invoice:
    """Email the PDF to the configured address and record the outcome (sent / failed).

    With email.enabled = false nothing is sent and the status stays "pending".
    """
    invoice = get_invoice(session, invoice_id)
    if invoice.email_status == e.EmailStatus.SENT:
        raise ConflictError("La factura ya se envió")
    cfg = settings.email
    if not cfg.enabled:
        logger.info("Email disabled: invoice %s stays pending", invoice.invoice_number)
        return invoice
    try:
        if not cfg.invoice_recipient:
            raise EmailError("Falta la dirección de destino (EMAIL_INVOICE_RECIPIENT)")
        total = to_out(invoice).totals.total
        send_email(
            recipient=cfg.invoice_recipient,
            subject=cfg.invoice_subject.format(number=invoice.invoice_number),
            body=cfg.invoice_body.format(
                number=invoice.invoice_number, customer=invoice.customer_name, total=format_money(total)
            ),
            attachments=[(f"{invoice.invoice_number}.pdf", render_invoice_pdf(invoice), "application/pdf")],
        )
    except EmailError as exc:
        invoice.email_status = e.EmailStatus.FAILED
        invoice.email_error = str(exc)[:1000]
        logger.warning("Invoice %s could not be emailed: %s", invoice.invoice_number, exc)
    else:
        invoice.email_status = e.EmailStatus.SENT
        invoice.email_sent_at = datetime.now().replace(microsecond=0)
        invoice.email_recipient = cfg.invoice_recipient
        invoice.email_error = None
        logger.info("Invoice %s emailed to %s", invoice.invoice_number, cfg.invoice_recipient)
    session.commit()
    return invoice
