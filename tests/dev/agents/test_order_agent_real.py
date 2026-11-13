"""The order agent against the real language model: different transcripts, checked field by field.

Run with:  poetry run pytest tests/dev -m llm
They call Groq (tokens, network) and the answers of a model can vary: a failure prints the full trace
of tool calls so you can tell a model slip from a real regression. Each test empties the test database.
"""

from decimal import Decimal

import pytest
from sqlalchemy import select

from crm import models as m

from tests.utils.agent_cases import NoOrderCase, OrderCase, explain, orders_of, run_agent
from tests.utils.factories import make_company, make_contact

pytestmark = pytest.mark.llm

D = Decimal
REBOZUELOS, BOLETUS = "Rebozuelos frescos", "Boletus edulis fresco"

ORDER_CASES = [
    OrderCase("alias", "Alberto me ha pedido 5 kilos de chantarelas",
              company="Restaurante X", contact="Alberto", items={REBOZUELOS: D(5)}),
    OrderCase("company_and_spelled_number", "Restaurante X quiere diez kilos de boletus",
              company="Restaurante X", items={BOLETUS: D(10)}),
    OrderCase("two_products_and_weekday",
              "Acabo de hablar con Marta del Bar Y: quiere tres kilos de boletus y dos de rebozuelos para el viernes",
              company="Bar Y", contact="Marta", items={BOLETUS: D(3), REBOZUELOS: D(2)}, delivery_weekday=4),
    OrderCase("decimal_quantity", "Alberto necesita kilo y medio de boletus",
              company="Restaurante X", contact="Alberto", items={BOLETUS: D("1.5")}),
    OrderCase("transcription_typo", "Alberto quiere cuatro kilos de rebosuelos",
              company="Restaurante X", contact="Alberto", items={REBOZUELOS: D(4)}),
    OrderCase("grams_to_kilos", "Marta me pide quinientos gramos de boletus",
              company="Bar Y", contact="Marta", items={BOLETUS: D("0.5")}),
    OrderCase("explicit_date", "Alberto pide 2 kilos de girolles para el 20 de noviembre",
              company="Restaurante X", contact="Alberto", items={REBOZUELOS: D(2)}, delivery_month_day=(11, 20)),
    OrderCase("rambling_note",
              "Vale, pues mira, he estado con Alberto, el del restaurante, y me ha dicho que, bueno, "
              "que le hacen falta seis kilos de boletus, a ver si puede ser pronto",
              company="Restaurante X", contact="Alberto", items={BOLETUS: D(6)}),
]

NO_ORDER_CASES = [
    NoOrderCase("ambiguous_contact", "Alberto me ha pedido 5 kilos de boletus",
                extra_contacts=[("Bar Y", "Alberto", "Pérez")]),
    NoOrderCase("unknown_product", "Alberto me ha pedido 5 kilos de trufa negra"),
    NoOrderCase("unknown_customer", "Julián del Mesón del Puerto quiere 3 kilos de boletus"),
    NoOrderCase("doubtful_quantity", "Marta quiere unas cuantas cajas de boletus"),
    NoOrderCase("missing_quantity", "Alberto quiere rebozuelos"),
]


class TestOrderExtraction:
    """The agent turns a clear order into the right Order."""

    @pytest.mark.parametrize("case", ORDER_CASES, ids=lambda c: c.id)
    def test_0_order_has_the_expected_data(self, session, real_llm, catalog, case):
        """Customer, contact, products, quantities and delivery date match what the note says."""
        note, execution = run_agent(session, real_llm, case.transcript)
        trace = explain(case.transcript, execution)

        [order] = orders_of(session) or pytest.fail(f"No order was created{trace}")
        assert execution.status == "correcta", trace
        assert order.created_by_agent is True and order.source_interaction_id == note.id, trace
        assert order.company.name == case.company, trace
        if case.contact:
            assert order.contact is not None and order.contact.first_name == case.contact, trace
        got = {item.product.name: item.quantity for item in order.items}
        assert got == case.items, trace
        if case.delivery_weekday is not None:
            assert order.requested_delivery_date is not None, trace
            assert order.requested_delivery_date.weekday() == case.delivery_weekday, trace
        if case.delivery_month_day is not None:
            assert order.requested_delivery_date is not None, trace
            date = order.requested_delivery_date
            assert (date.month, date.day) == case.delivery_month_day, trace
        assert note.processing_status == "procesada" and note.company_id == order.company_id, trace
        # No date in the note: the order is kept and the user is asked to fill it in
        alerts = session.scalars(select(m.Alert).where(m.Alert.type == "pedido_sin_fecha_entrega")).all()
        has_date = case.delivery_weekday is not None or case.delivery_month_day is not None
        assert (alerts == []) == has_date, trace
        assert has_date == (order.requested_delivery_date is not None), trace

    def test_1_one_order_per_note(self, session, real_llm, catalog):
        """A single note produces exactly one order, made with exactly one create_order call."""
        transcript = "Marta me ha pedido tres kilos de boletus para mañana"
        _, execution = run_agent(session, real_llm, transcript)
        assert len(orders_of(session)) == 1, explain(transcript, execution)
        assert sum(c["tool"] == "create_order" and "order_id" in c["result"] for c in execution.tool_calls) == 1


class TestNoOrder:
    """When the note is ambiguous or incomplete the agent must not invent an order."""

    @pytest.mark.parametrize("case", NO_ORDER_CASES, ids=lambda c: c.id)
    def test_0_no_order_and_an_alert_for_review(self, session, real_llm, catalog, case):
        """No order is created; the note is flagged with an alert and the run needs review."""
        for company_name, first, last in case.extra_contacts:
            company = catalog.get(company_name) or make_company(session, company_name)
            make_contact(session, company, first, last_name=last)
        note, execution = run_agent(session, real_llm, case.transcript)
        trace = explain(case.transcript, execution)

        assert orders_of(session) == [], f"An order was invented{trace}"
        assert execution.status == "requiere_revisión", trace
        [alert] = session.scalars(select(m.Alert)).all()
        assert alert.type == "nota_en_revision" and alert.interaction_id == note.id, trace
        assert alert.message.strip(), trace

    def test_1_note_that_is_not_an_order_is_only_linked(self, session, real_llm, catalog):
        """A follow-up note creates no order and is assigned to the customer it talks about."""
        transcript = "He estado con Marta, dice que se lo piensa y que me llama ella la semana que viene"
        note, execution = run_agent(session, real_llm, transcript)
        trace = explain(transcript, execution)
        assert orders_of(session) == [], trace
        assert note.processing_status == "procesada", trace
        assert note.company_id == catalog["Bar Y"].id, trace
