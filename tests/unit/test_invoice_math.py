"""Tests for the invoice amount helpers."""

from decimal import Decimal

from crm.utils import calculate_totals, format_money, format_quantity, round_money


class TestCalculateTotals:
    """Tests for calculate_totals."""

    def test_0_example_of_the_spec(self):
        """10 kg at 20 EUR/kg with 10 % VAT: base 200, VAT 20, total 220."""
        amounts, base, vat, total = calculate_totals([(Decimal("10"), Decimal("20"))], Decimal("0.10"))
        assert amounts == [Decimal("200.00")]
        assert (base, vat, total) == (Decimal("200.00"), Decimal("20.00"), Decimal("220.00"))

    def test_1_lines_are_rounded_to_cents_then_summed(self):
        """Each line is rounded to cents (half up) before adding them."""
        amounts, base, vat, total = calculate_totals(
            [(Decimal("0.333"), Decimal("1.5")), (Decimal("2"), Decimal("0.005"))], Decimal("0.10")
        )
        assert amounts == [Decimal("0.50"), Decimal("0.01")]
        assert base == Decimal("0.51")
        assert vat == Decimal("0.05")
        assert total == Decimal("0.56")

    def test_2_vat_is_computed_once_on_the_base(self):
        """VAT is rounded on the base, not per line."""
        lines = [(Decimal("1"), Decimal("0.15"))] * 3
        _, base, vat, _ = calculate_totals(lines, Decimal("0.10"))
        assert base == Decimal("0.45")
        assert vat == Decimal("0.05")  # 0.045 rounds up; per line it would be 3 x 0.02 = 0.06

    def test_3_round_money_half_up(self):
        """2.675 becomes 2.68 (plain half-up, no bankers rounding)."""
        assert round_money(Decimal("2.675")) == Decimal("2.68")


class TestFormatting:
    """Tests for the Spanish number formats."""

    def test_0_money(self):
        """Thousands with dots, decimals with a comma, euro sign at the end."""
        assert format_money(Decimal("1234.5")) == "1.234,50 €"

    def test_1_quantity(self):
        """Trailing zeros are dropped and the decimal separator is a comma."""
        assert format_quantity(Decimal("10.000")) == "10"
        assert format_quantity(Decimal("2.500")) == "2,5"
