"""Endpoints of invoices."""

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from ... import enums as e
from ... import schemas as s
from ... import models as m
from ...services import deletion
from ...services import invoices as svc
from ...services.invoice_pdf import render_invoice_pdf
from ..auth import AuthUser, current_user
from ..deps import PageParams, get_db

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.get("/config", response_model=s.InvoiceConfig)
def invoice_config():
    """Series that can be issued today and the VAT rate."""
    return svc.get_config()


@router.post("/preview", response_model=s.InvoiceTotals)
def preview(data: s.InvoicePreviewIn):
    """Compute amounts, VAT and total of some lines without saving."""
    return svc.preview_totals(data.lines)


@router.get("", response_model=s.Page[s.InvoiceOut])
def list_invoices(
    invoice_type: e.InvoiceType | None = None,
    email_status: e.EmailStatus | None = None,
    company_id: uuid.UUID | None = None,
    search: str | None = None,
    paging: PageParams = Depends(),
    db: Session = Depends(get_db),
):
    """List invoices, newest first."""
    items, total = svc.list_invoices(
        db, invoice_type=invoice_type, email_status=email_status, company_id=company_id,
        search=search, page=paging.page, page_size=paging.page_size,
    )
    return s.Page(items=[svc.to_out(i) for i in items], total=total, page=paging.page, page_size=paging.page_size)


@router.post("", response_model=s.InvoiceOut, status_code=status.HTTP_201_CREATED)
def create_invoice(
    data: s.InvoiceCreate, db: Session = Depends(get_db), user: AuthUser = Depends(current_user)
):
    """Issue an invoice: save it, number it and email the PDF (the result is in `email_status`)."""
    invoice = svc.create_invoice(db, data, created_by=user.email)
    return svc.to_out(svc.send_invoice(db, invoice.id))


@router.get("/{invoice_id}", response_model=s.InvoiceOut)
def get_invoice(invoice_id: uuid.UUID, db: Session = Depends(get_db)):
    """Return one invoice."""
    return svc.to_out(svc.get_invoice(db, invoice_id))


@router.post("/{invoice_id}/send", response_model=s.InvoiceOut)
def send_invoice(invoice_id: uuid.UUID, db: Session = Depends(get_db)):
    """Email the invoice again (after a failure, or when it was pending)."""
    return svc.to_out(svc.send_invoice(db, invoice_id))


@router.get("/{invoice_id}/pdf")
def download_pdf(invoice_id: uuid.UUID, db: Session = Depends(get_db)):
    """Download the PDF of an invoice."""
    invoice = svc.get_invoice(db, invoice_id)
    return Response(
        render_invoice_pdf(invoice), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{invoice.invoice_number}.pdf"'},
    )


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_invoice(invoice_id: uuid.UUID, db: Session = Depends(get_db)):
    """Delete an invoice with its lines and payments (soft delete: it disappears from the app but stays in the database)."""
    deletion.delete_record(db, m.Invoice, invoice_id)
