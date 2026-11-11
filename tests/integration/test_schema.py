"""Tests for the database schema: stock, pricing and invoice views, and table constraints."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from crm import models as m
from crm.enums import AllocationStatus

from tests.utils.seed import NOW, seed_order_with_lot


class TestLotStockView:
    """Tests for the lot_stock view."""

    def test_0_reservation_reduces_available_stock(self, session):
        """Buying 5 kg and reserving 3 kg leaves 2 kg available at 21 EUR/kg."""
        _, lot, _, item = seed_order_with_lot(session)
        session.add(m.LotAllocation(
            lot_id=lot.id, order_item_id=item.id, quantity=Decimal("3"), allocated_at=NOW
        ))
        session.commit()
        row = session.execute(text("SELECT * FROM lot_stock")).mappings().one()
        assert row["reserved_quantity"] == 3
        assert row["available_quantity"] == 2
        assert row["status"] == "disponible"
        assert float(row["total_cost_per_unit"]) == pytest.approx(21)

    def test_1_released_allocation_returns_stock(self, session):
        """Releasing a reservation makes the full 5 kg available again."""
        _, lot, _, item = seed_order_with_lot(session)
        allocation = m.LotAllocation(
            lot_id=lot.id, order_item_id=item.id, quantity=Decimal("3"), allocated_at=NOW
        )
        session.add(allocation)
        session.commit()
        allocation.status = AllocationStatus.RELEASED
        session.commit()
        row = session.execute(text("SELECT * FROM lot_stock")).mappings().one()
        assert row["available_quantity"] == 5

    def test_2_adjustment_reduces_stock(self, session):
        """A 1 kg shrinkage adjustment leaves 4 kg available."""
        _, lot, *_ = seed_order_with_lot(session)
        session.add(m.LotAdjustment(
            lot_id=lot.id, quantity=Decimal("1"), reason="merma", adjusted_at=NOW
        ))
        session.commit()
        row = session.execute(text("SELECT * FROM lot_stock")).mappings().one()
        assert row["adjusted_quantity"] == 1
        assert row["available_quantity"] == 4


class TestOrderItemPricingView:
    """Tests for the order_item_pricing view."""

    def test_0_suggested_price_and_final_margin(self, session):
        """Cost 21 and margin 30% suggest 30 before tax and 33 after; agreeing 33 gives 30% margin."""
        _, lot, _, item = seed_order_with_lot(session)
        session.add(m.LotAllocation(
            lot_id=lot.id, order_item_id=item.id, quantity=Decimal("3"), allocated_at=NOW
        ))
        session.commit()
        row = session.execute(text("SELECT * FROM order_item_pricing")).mappings().one()
        assert float(row["avg_cost_per_unit"]) == pytest.approx(21)
        assert float(row["suggested_unit_price_before_tax"]) == pytest.approx(30)
        assert float(row["suggested_unit_price_after_tax"]) == pytest.approx(33)
        assert row["agreed_unit_price_after_tax"] is None  # an order may exist without a price
        assert row["final_margin"] is None

        item.agreed_unit_price_after_tax = Decimal("33")
        session.commit()
        row = session.execute(text("SELECT * FROM order_item_pricing")).mappings().one()
        assert float(row["agreed_unit_price_before_tax"]) == pytest.approx(30)
        assert float(row["final_margin"]) == pytest.approx(0.30)

    def test_1_zero_agreed_price_does_not_break_the_view(self, session):
        """A free line (agreed price 0) gives an empty margin instead of a division error."""
        _, lot, _, item = seed_order_with_lot(session)
        session.add(m.LotAllocation(
            lot_id=lot.id, order_item_id=item.id, quantity=Decimal("3"), allocated_at=NOW
        ))
        item.agreed_unit_price_after_tax = Decimal("0")
        session.commit()
        row = session.execute(text("SELECT * FROM order_item_pricing")).mappings().one()
        assert row["final_margin"] is None


class TestInvoiceBalanceView:
    """Tests for the invoice_balance view."""

    def test_0_total_paid_and_status(self, session):
        """An overdue 99 EUR invoice becomes paid once 40 + 59 EUR have been received."""
        _, _, order, _ = seed_order_with_lot(session)
        invoice = m.Invoice(
            order_id=order.id, invoice_number="2026-001", status="emitida",
            issue_date=date(2026, 11, 1), due_date=date.today() - timedelta(days=1),
        )
        session.add(invoice)
        session.flush()
        session.add(m.InvoiceItem(
            invoice_id=invoice.id, description="Boletus", quantity=Decimal("3"), unit="kg",
            unit_price=Decimal("30"), tax_rate=Decimal("0.10"),
        ))
        session.commit()
        row = session.execute(text("SELECT * FROM invoice_balance")).mappings().one()
        assert float(row["total_amount"]) == pytest.approx(99)
        assert row["status"] == "vencida"

        session.add(m.Payment(invoice_id=invoice.id, paid_at=NOW, amount=Decimal("40"), method="bizum"))
        session.commit()
        row = session.execute(text("SELECT * FROM invoice_balance")).mappings().one()
        assert float(row["outstanding_amount"]) == pytest.approx(59)

        session.add(m.Payment(invoice_id=invoice.id, paid_at=NOW, amount=Decimal("59")))
        session.commit()
        row = session.execute(text("SELECT * FROM invoice_balance")).mappings().one()
        assert row["status"] == "pagada"


class TestConstraints:
    """Tests for the integrity constraints of the tables."""

    def test_0_duplicate_interaction_is_rejected(self, session):
        """Two interactions with the same source and external_id violate the unique constraint."""
        _, _, order, _ = seed_order_with_lot(session)
        values = dict(
            company_id=order.company_id, occurred_at=NOW, type="WhatsApp", summary="x",
            source="whatsapp", external_id="wamid.1",
        )
        session.add(m.Interaction(**values))
        session.commit()
        session.add(m.Interaction(**values))
        with pytest.raises(IntegrityError):
            session.commit()

    def test_1_value_outside_enum_is_rejected(self, session):
        """A customer_status that is not in the enum is refused."""
        session.add(m.Company(
            name="X", roles=["Cliente"], type=["restaurante"], customer_status="Inventado"
        ))
        with pytest.raises(Exception):
            session.commit()

    def test_2_foreign_keys_are_enforced(self, session):
        """A contact pointing to a non-existent company is refused."""
        session.add(m.Contact(company_id=uuid.uuid4(), first_name="Ana"))
        with pytest.raises(IntegrityError):
            session.commit()
