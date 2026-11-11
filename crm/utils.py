"""Helpers shared by several modules."""

import uuid
from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from sqlalchemy import Enum, Select, Uuid, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column


def enum_column(cls: type[StrEnum]) -> Enum:
    """Return a column type storing a StrEnum as text, restricted by a CHECK to its values."""
    return Enum(
        cls,
        native_enum=False,
        create_constraint=True,
        values_callable=lambda c: [m.value for m in c],
        length=40,
        name=f"ck_{cls.__name__.lower()}",
    )


def pk_column() -> Mapped[uuid.UUID]:
    """Return a UUID primary-key column generated in Python."""
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


def normalize_mime_type(mime_type: str | None) -> str:
    """Return a MIME type lower-cased and without parameters ('audio/webm;codecs=opus' -> 'audio/webm')."""
    return (mime_type or "").split(";", 1)[0].strip().lower()


def clamp_page_size(page_size: int | None, default: int, maximum: int) -> int:
    """Return `page_size` limited to [1, maximum], or `default` when it is not given."""
    if page_size is None:
        return default
    return max(1, min(page_size, maximum))


def paginate(session: Session, query: Select, page: int, page_size: int) -> tuple[list, int]:
    """Return (rows, total) for one page (1-based) of `query`."""
    total = session.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    rows = session.scalars(query.limit(page_size).offset((page - 1) * page_size)).unique().all()
    return list(rows), total or 0


CENT = Decimal("0.01")


def round_money(value: Decimal) -> Decimal:
    """Round an amount to cents, halves away from zero (the usual rule on invoices)."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_totals(
    lines: Iterable[tuple[Decimal, Decimal]], vat_rate: Decimal
) -> tuple[list[Decimal], Decimal, Decimal, Decimal]:
    """Return (line amounts, taxable base, VAT amount, total) for (quantity, unit price) lines.

    Each line is rounded to cents, the base is their sum and the VAT is computed once on the base.
    """
    amounts = [round_money(Decimal(quantity) * Decimal(price)) for quantity, price in lines]
    base = sum(amounts, Decimal("0.00"))
    vat = round_money(base * Decimal(vat_rate))
    return amounts, base, vat, base + vat


def format_money(value: Decimal | float, symbol: str = "€") -> str:
    """Format an amount the Spanish way: 1.234,50 €."""
    text = f"{Decimal(value):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{text} {symbol}"


def format_quantity(value: Decimal) -> str:
    """Format a quantity without useless zeros, with a decimal comma (10,5 / 3)."""
    text = f"{Decimal(value):f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace(".", ",")
