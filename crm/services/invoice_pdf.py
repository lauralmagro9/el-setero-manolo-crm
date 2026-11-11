"""PDF of an invoice, laid out like the El Setero template."""

import io
from decimal import Decimal
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .. import models as m
from ..config import PROJECT_ROOT, settings
from ..utils import calculate_totals, format_money, format_quantity

GREY = colors.HexColor("#555555")
LIGHT = colors.HexColor("#EFEFEF")
LINE = colors.HexColor("#E3E3E3")


def _styles() -> dict[str, ParagraphStyle]:
    """Paragraph styles used by the document."""
    base = ParagraphStyle("base", fontName="Helvetica", fontSize=10, leading=14, textColor=GREY)
    return {
        "base": base,
        "bold": ParagraphStyle("bold", parent=base, fontName="Helvetica-Bold"),
        "number": ParagraphStyle("number", parent=base, fontSize=12, alignment=2, textColor=colors.black),
        "title": ParagraphStyle("title", parent=base, fontName="Helvetica-Bold", fontSize=28, leading=34,
                                textColor=colors.black),
        "head": ParagraphStyle("head", parent=base, fontName="Helvetica-Bold", fontSize=8, textColor=GREY),
        "cell": ParagraphStyle("cell", parent=base, fontSize=9, leading=12, textColor=colors.black),
        "right": ParagraphStyle("right", parent=base, alignment=2, textColor=colors.black),
        "total": ParagraphStyle("total", parent=base, fontName="Helvetica-Bold", fontSize=12, alignment=2,
                                textColor=colors.black),
    }


def _labelled(label: str, value: str | None, st: dict) -> Paragraph | None:
    """'Label: value' with the value in bold; None when there is no value."""
    if not value:
        return None
    return Paragraph(f"{escape(label)}: <b>{escape(value)}</b>", st["base"])


def render_invoice_pdf(invoice: m.Invoice) -> bytes:
    """Return the PDF of `invoice`, built only from what is stored in it (a historical copy)."""
    st = _styles()
    issuer = settings.issuer
    vat_rate = Decimal(str(invoice.items[0].tax_rate)) if invoice.items else Decimal(str(settings.invoicing.vat_rate))
    amounts, base, vat, total = calculate_totals(
        [(Decimal(i.quantity), Decimal(i.unit_price)) for i in invoice.items], vat_rate
    )
    story = []
    width = A4[0] - 4 * cm - 12  # frame width: page minus margins minus the frame padding

    logo_path = PROJECT_ROOT / issuer.logo_file
    logo = Image(str(logo_path), width=3 * cm, height=3 * cm, kind="proportional") if logo_path.is_file() else ""
    header = Table([[logo, Paragraph(f"Nº: {escape(invoice.invoice_number or '')}", st["number"])]],
                   colWidths=[width * 0.5, width * 0.5], hAlign="LEFT")
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (0, 0), 0)]))
    story += [header, Spacer(1, 1.2 * cm)]

    title = settings.invoicing.titles.as_dict().get(invoice.invoice_type.value, "Factura")
    story += [Paragraph(escape(title), st["title"]), Spacer(1, 0.8 * cm)]

    issue_date = invoice.issue_date.strftime("%d/%m/%Y") if invoice.issue_date else ""
    operation_date = invoice.operation_date.strftime("%d/%m/%Y") if invoice.operation_date else issue_date
    left = [
        Paragraph(escape(issuer.holder_label) + ":", st["base"]),
        Paragraph(escape(issuer.name), st["bold"]),
        Paragraph(escape(issuer.tax_id), st["bold"]),
        _labelled(issuer.address_label, issuer.address, st),
        _labelled("Fecha de expedición", issue_date, st),
        _labelled("Fecha de operación", operation_date, st),
    ]
    right = [
        _labelled("Cliente", invoice.customer_name, st),
        _labelled("NIF/CIF", invoice.customer_tax_id, st),
        _labelled("Dirección", invoice.customer_address, st),
    ]
    parties = Table([[[p for p in left if p], [p for p in right if p]]], colWidths=[width * 0.5, width * 0.5], hAlign="LEFT")
    parties.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (0, 0), 0)]))
    story += [parties, Spacer(1, 1 * cm)]

    cell, head = st["cell"], st["head"]
    rows = [[Paragraph(t, head) for t in ("PRODUCTO", "DESCRIPCIÓN", "PRECIO<br/>UNIDAD", "CANTIDAD", "IVA", "PRECIO TOTAL")]]
    for item, amount in zip(invoice.items, amounts):
        rows.append([
            Paragraph(escape(item.product_name or ""), cell),
            Paragraph(escape(item.description), cell),
            Paragraph(f"{format_money(item.unit_price)}/{escape(item.unit)}", cell),
            Paragraph(f"{format_quantity(item.quantity)} {escape(item.unit)}", cell),
            Paragraph(f"{format_quantity(Decimal(item.tax_rate) * 100)}%", cell),
            Paragraph(format_money(amount), cell),
        ])
    table = Table(rows, colWidths=[width * f for f in (0.18, 0.27, 0.17, 0.14, 0.09, 0.15)], repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [table, Spacer(1, 0.6 * cm)]

    pct = format_quantity(vat_rate * 100)
    totals = Table(
        [[Paragraph("Base imponible", st["right"]), Paragraph(format_money(base), st["right"])],
         [Paragraph(f"IVA ({pct}%)", st["right"]), Paragraph(format_money(vat), st["right"])],
         [Paragraph("Total", st["total"]), Paragraph(format_money(total), st["total"])]],
        colWidths=[width * 0.75, width * 0.25], hAlign="LEFT",
    )
    totals.setStyle(TableStyle([("LINEABOVE", (0, 2), (-1, 2), 0.5, LINE)]))
    story.append(totals)
    if invoice.notes:
        story += [Spacer(1, 0.8 * cm), Paragraph(escape(invoice.notes), st["base"])]

    buffer = io.BytesIO()
    SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        title=invoice.invoice_number or "Factura",
    ).build(story)
    return buffer.getvalue()
