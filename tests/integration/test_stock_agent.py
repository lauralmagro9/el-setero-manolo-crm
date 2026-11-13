"""Tests for the stock agent and the alerts API (rules only; the model, when used, is scripted)."""

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select

from crm import models as m
from crm.services.agents import stock_agent

from tests.utils.factories import make_company, make_lot, make_order
from tests.utils.llm import say


@pytest.fixture(autouse=True)
def no_llm_wording(monkeypatch):
    """Use the fixed alert templates unless a test passes a scripted model on purpose."""
    monkeypatch.setitem(stock_agent.settings.agents.stock.as_dict(), "use_llm_for_text", False)


def alerts_of(session, alert_type: str) -> list[m.Alert]:
    """Return the alerts of one type."""
    return list(session.scalars(select(m.Alert).where(m.Alert.type == alert_type)))


class TestInsufficientStock:
    """Open orders against the available stock."""

    def test_0_order_larger_than_stock_raises_an_alert(self, session):
        """15 kg requested with 10 kg in stock: a critical alert says 5 kg are missing."""
        lot = make_lot(session, quantity="10")
        make_order(session, make_company(session), lot.product, quantity="15")
        result = stock_agent.run_stock_agent(session)
        [alert] = alerts_of(session, "stock_insuficiente")
        assert result.alerts_created == 1
        assert alert.severity == "critico" and alert.product_id == lot.product_id
        assert alert.data["missing"].startswith("5")
        assert "Boletus" in alert.message

    def test_1_enough_stock_raises_nothing(self, session):
        """5 kg requested with 10 kg in stock is fine."""
        lot = make_lot(session, quantity="10")
        make_order(session, make_company(session), lot.product, quantity="5")
        stock_agent.run_stock_agent(session)
        assert alerts_of(session, "stock_insuficiente") == []

    def test_2_delivered_and_cancelled_orders_do_not_count(self, session):
        """Only open orders are demand."""
        lot = make_lot(session, quantity="10")
        company = make_company(session)
        make_order(session, company, lot.product, quantity="50", status="Cancelado")
        make_order(session, company, lot.product, quantity="50", status="Entregado")
        stock_agent.run_stock_agent(session)
        assert alerts_of(session, "stock_insuficiente") == []

    def test_3_demand_of_several_orders_is_added_up(self, session):
        """Two 6 kg orders against 10 kg of stock are insufficient together."""
        lot = make_lot(session, quantity="10")
        company = make_company(session)
        make_order(session, company, lot.product, quantity="6")
        make_order(session, company, lot.product, quantity="6", status="Confirmado")
        stock_agent.run_stock_agent(session)
        assert len(alerts_of(session, "stock_insuficiente")) == 1


class TestExpiringLots:
    """Lots about to expire and who to offer them to."""

    def test_0_alert_suggests_buyers_then_interested_customers(self, session):
        """The past buyer comes first, then the interested customer; a merely contacted one is left out."""
        lot = make_lot(session, quantity="10", expires_in_days=5)
        buyer = make_company(session, "Comprador", customer_status="Cliente")
        interested = make_company(session, "Interesado", customer_status="Muy interesado")
        make_company(session, "Frío", customer_status="Contactado")
        make_order(session, buyer, lot.product, quantity="2", status="Entregado")
        stock_agent.run_stock_agent(session)
        [alert] = alerts_of(session, "lote_por_caducar")
        names = [x["name"] for x in alert.data["suggested_companies"]]
        assert names == ["Comprador", "Interesado"]
        assert alert.company_id == buyer.id and alert.lot_id == lot.id
        assert "Comprador" in alert.message and lot.lot_code in alert.message

    def test_1_lot_far_from_expiry_or_without_date_is_ignored(self, session):
        """Only lots expiring within the configured window raise the alert."""
        far = stock_agent.settings.dashboard.expiry_alert_days + 5
        make_lot(session, product_name="Lejano", quantity="10", expires_in_days=far)
        make_lot(session, product_name="Sin fecha", quantity="10")
        stock_agent.run_stock_agent(session)
        assert alerts_of(session, "lote_por_caducar") == []

    def test_2_cancelled_orders_are_not_a_purchase_history(self, session):
        """A company whose only order was cancelled is not suggested."""
        lot = make_lot(session, quantity="10", expires_in_days=3)
        make_order(session, make_company(session, "Canceló"), lot.product, status="Cancelado")
        stock_agent.run_stock_agent(session)
        [alert] = alerts_of(session, "lote_por_caducar")
        assert alert.data["suggested_companies"] == []


class TestLowStock:
    """Lots at or below the threshold."""

    def test_0_low_lot_raises_an_info_alert(self, session):
        """A lot with 1 kg left (threshold 2) raises a low-stock alert; one with 10 kg does not."""
        make_lot(session, product_name="Poco", quantity="1")
        make_lot(session, product_name="Mucho", quantity="10")
        stock_agent.run_stock_agent(session)
        [alert] = alerts_of(session, "stock_bajo")
        assert alert.severity == "info" and "Poco" in alert.message


class TestRunBehaviour:
    """Deduplication, wording and audit trail."""

    def test_0_same_day_run_does_not_repeat_alerts(self, session):
        """Running twice on the same day creates the alerts once; the next day they come back."""
        make_lot(session, quantity="1")
        today = date.today()
        assert stock_agent.run_stock_agent(session, today).alerts_created == 1
        assert stock_agent.run_stock_agent(session, today).alerts_created == 0
        assert stock_agent.run_stock_agent(session, today + timedelta(days=1)).alerts_created == 1

    def test_1_model_words_the_alert(self, session, scripted_llm):
        """With a model, its text replaces the template; the facts and the suggestions stay in `data`."""
        make_lot(session, quantity="1")
        stock_agent.run_stock_agent(session, llm=scripted_llm(say("Queda poco Boletus: repón.")))
        assert alerts_of(session, "stock_bajo")[0].message == "Queda poco Boletus: repón."

    def test_2_model_failure_falls_back_to_the_template(self, session, scripted_llm):
        """If the model fails the alert is still created with the fixed text."""
        make_lot(session, quantity="1")
        stock_agent.run_stock_agent(session, llm=scripted_llm(RuntimeError("Groq caído")))
        assert "Poco stock" in alerts_of(session, "stock_bajo")[0].message

    def test_3_run_is_logged_and_attributed_to_the_system(self, session):
        """Each run leaves an AgentExecution and the alerts are created by the default actor."""
        make_lot(session, quantity="1")
        stock_agent.run_stock_agent(session)
        execution = session.scalars(select(m.AgentExecution)).one()
        assert execution.agent_name == "stock_agent" and execution.status == "correcta"
        assert execution.output["low_stock"] == 1
        assert alerts_of(session, "stock_bajo")[0].created_by == "system"


class TestAlertsApi:
    """Tests for /api/alerts."""

    def make_alerts(self, session):
        """Create one unread and one read alert; return them."""
        unread = m.Alert(type="stock_bajo", severity="info", message="Poco stock")
        read = m.Alert(type="lote_por_caducar", severity="aviso", message="Caduca", read_at=datetime.now())
        session.add_all([unread, read])
        session.commit()
        return unread, read

    def test_0_list_and_filter_unread(self, client, session):
        """The list returns every alert; ?unread=true only the unread ones."""
        unread, _ = self.make_alerts(session)
        assert client.get("/api/alerts").json()["total"] == 2
        body = client.get("/api/alerts?unread=true").json()
        assert [a["id"] for a in body["items"]] == [str(unread.id)]

    def test_1_unread_count(self, client, session):
        """The counter used by the menu badge."""
        self.make_alerts(session)
        assert client.get("/api/alerts/unread-count").json() == {"unread": 1}

    def test_2_mark_one_read(self, client, session):
        """Marking an alert read sets its read time and lowers the counter."""
        unread, _ = self.make_alerts(session)
        response = client.post(f"/api/alerts/{unread.id}/read")
        assert response.status_code == 200 and response.json()["read_at"] is not None
        assert client.get("/api/alerts/unread-count").json() == {"unread": 0}

    def test_3_mark_unknown_alert_is_404(self, client):
        """An unknown id is a 404."""
        assert client.post("/api/alerts/00000000-0000-0000-0000-000000000001/read").status_code == 404

    def test_4_mark_all_read(self, client, session):
        """read-all clears the counter."""
        self.make_alerts(session)
        assert client.post("/api/alerts/read-all").json() == {"unread": 0}
        assert client.get("/api/alerts?unread=true").json()["total"] == 0

    def test_5_requires_login(self, anonymous_client):
        """Anonymous requests are rejected."""
        assert anonymous_client.get("/api/alerts").status_code == 401
