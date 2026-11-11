"""Tests for the dashboard endpoint."""

from datetime import datetime, timedelta

from tests.utils.factories import make_company, make_interaction, make_lot


class TestDashboard:
    """Tests for /api/dashboard."""

    def test_0_empty_database(self, client):
        """With no data every counter is zero and every status is listed."""
        body = client.get("/api/dashboard").json()
        assert body["pending_interactions"] == 0
        assert body["recent_interactions"] == []
        assert len(body["customers_by_status"]) == 7
        assert all(row["count"] == 0 for row in body["customers_by_status"])

    def test_1_customers_by_status(self, client, session):
        """Companies are counted by customer status."""
        make_company(session, "A", customer_status="Interesado")
        make_company(session, "B", customer_status="Interesado")
        make_company(session, "C", customer_status="Cliente")
        counts = {r["customer_status"]: r["count"] for r in client.get("/api/dashboard").json()["customers_by_status"]}
        assert counts["Interesado"] == 2
        assert counts["Cliente"] == 1
        assert counts["Perdido"] == 0

    def test_2_interaction_windows_and_pending(self, client, session):
        """Interactions are counted per window; pending and unassigned notes are reported."""
        company = make_company(session)
        make_interaction(session, company, occurred_at=datetime.now() - timedelta(days=2))
        make_interaction(session, company, occurred_at=datetime.now() - timedelta(days=20))
        make_interaction(session, company, occurred_at=datetime.now() - timedelta(days=60))
        make_interaction(session, None, source="nota_de_voz", summary=None, transcript="x",
                         processing_status="pendiente")
        body = client.get("/api/dashboard").json()
        assert body["interactions_short_window"] == 2  # 2 days ago + the voice note (now)
        assert body["interactions_long_window"] == 3
        assert body["pending_interactions"] == 1
        assert body["unassigned_voice_notes"] == 1
        assert len(body["recent_interactions"]) == 4

    def test_3_lot_alerts(self, client, session):
        """Lots about to expire and lots running out appear in their own lists."""
        make_lot(session, "Caduca pronto", quantity="10", expires_in_days=3)
        make_lot(session, "Casi agotado", quantity="1")
        make_lot(session, "Sobrado", quantity="50", expires_in_days=200)
        body = client.get("/api/dashboard").json()
        assert [x["product_name"] for x in body["expiring_lots"]] == ["Caduca pronto"]
        assert [x["product_name"] for x in body["low_stock_lots"]] == ["Casi agotado"]
