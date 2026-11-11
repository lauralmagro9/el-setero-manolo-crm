"""Tests for the invoice PDF."""

import io
from datetime import date
from decimal import Decimal

from pypdf import PdfReader

from crm import enums as e
from crm import models as m
from crm.services.invoice_pdf import render_invoice_pdf


def build_invoice(number="VDA-2026-0001", invoice_type=e.InvoiceType.VDA) -> m.Invoice:
    """Return an in-memory invoice with one line (10 kg of boletus at 20 EUR/kg)."""
    invoice = m.Invoice(
        invoice_type=invoice_type, invoice_number=number, issue_date=date(2026, 11, 11),
        customer_name="Pedro Pérez García", customer_tax_id="12345678Z",
        customer_address="Calle Mayor 1, Algeciras", operation_date=date(2026, 11, 5),
    )
    invoice.items = [m.InvoiceItem(
        position=0, product_name="Boletus edulis", description="Boletus frescos de calidad extra",
        quantity=Decimal("10"), unit="kg", unit_price=Decimal("20"), tax_rate=Decimal("0.10"),
    )]
    return invoice


def pdf_text(data: bytes) -> str:
    """Extract the text of every page of a PDF, with line breaks collapsed into single spaces."""
    return " ".join(" ".join(page.extract_text().split()) for page in PdfReader(io.BytesIO(data)).pages)


class TestRenderInvoicePdf:
    """Tests for render_invoice_pdf."""

    def test_0_is_a_pdf(self, issuer):
        """The output is a valid one-page PDF."""
        data = render_invoice_pdf(build_invoice())
        assert data.startswith(b"%PDF")
        assert len(PdfReader(io.BytesIO(data)).pages) == 1

    def test_1_contains_the_spec_content(self, issuer):
        """Number, title, parties, line, base, VAT and total all appear."""
        text = pdf_text(render_invoice_pdf(build_invoice()))
        for expected in ("VDA-2026-0001", "Factura Venta Directa", "Manuel Test Titular", "VDA00000000X",
                         "Pedro Pérez García", "12345678Z", "Calle Mayor 1", "Boletus edulis",
                         "Boletus frescos de calidad extra", "10 kg", "Fecha de expedición: 11/11/2026",
                         "Fecha de operación: 05/11/2026", "10%",
                         "200,00 €", "20,00 €", "220,00 €"):
            assert expected in text, expected

    def test_2_no_email_or_phone_is_printed(self, issuer):
        """The customer block only has name, tax id and address."""
        text = pdf_text(render_invoice_pdf(build_invoice()))
        assert "Correo" not in text and "Teléfono" not in text and "@" not in text

    def test_3_special_characters_do_not_break_it(self, issuer):
        """Text with markup characters is escaped instead of crashing the layout."""
        invoice = build_invoice()
        invoice.customer_name = "Bar <Los & Amigos>"
        assert "Los & Amigos" in pdf_text(render_invoice_pdf(invoice))
