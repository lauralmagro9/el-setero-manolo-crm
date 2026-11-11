"""Tests for the audit columns of every table and for the soft delete of records."""

import time
import uuid
from decimal import Decimal

from sqlalchemy import select, text

from crm import models as m
from crm.audit import reset_actor, set_actor
from crm.services import deletion
from crm.services.errors import NotFoundError

from tests.utils.factories import make_company, make_contact, make_interaction, make_lot, make_product
from tests.utils.seed import NOW, seed_order_with_lot

AUDIT = ("created_at", "modified_at", "created_by")


def everything(session, model):
    """Return every row of `model`, deleted ones included."""
    return session.scalars(select(model).execution_options(include_deleted=True)).unique().all()


def issue_invoice(client, session, tax_id="X1"):
    """Issue an invoice for a new company with billing data; return the invoice body."""
    company = make_company(session, "Cliente", tax_id=tax_id, billing_name="Juan", billing_address="Calle 1, Cádiz")
    product = make_product(session, f"Producto {tax_id}")
    line = {"product_id": str(product.id), "description": "x", "unit": "kg", "quantity": "1", "unit_price": "10"}
    return client.post("/api/invoices", json={"company_id": str(company.id), "lines": [line]}).json(), company


class TestAuditColumns:
    """Every table records who created a row, when, and when it last changed."""

    def test_0_every_table_has_the_mandatory_audit_columns(self, engine):
        """created_at, modified_at and created_by exist and are NOT NULL in every table (future ones too)."""
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT table_name, column_name, is_nullable FROM information_schema.columns "
                "WHERE table_schema = 'public' AND column_name = ANY(:names)"),
                {"names": list(AUDIT) + ["deleted_at", "deleted_by"]},
            ).all()
        by_table = {}
        for table, column, nullable in rows:
            by_table.setdefault(table, {})[column] = nullable
        for table in m.Base.metadata.tables:
            assert set(by_table[table]) == set(AUDIT) | {"deleted_at", "deleted_by"}, table
            assert all(by_table[table][c] == "NO" for c in AUDIT), table
            assert all(by_table[table][c] == "YES" for c in ("deleted_at", "deleted_by")), table

    def test_1_rows_without_a_logged_user_are_recorded_as_system(self, session):
        """Scripts and agents leave the default actor, and the timestamps are filled in."""
        company = make_company(session)
        assert company.created_by == "system"
        assert company.created_at is not None and company.modified_at is not None

    def test_2_the_logged_in_user_is_the_author_of_what_the_api_writes(self, client, session):
        """A company created through the API carries the email of the user who did it."""
        body = client.post("/api/companies", json={
            "name": "Bar Sol", "roles": ["Cliente"], "type": ["restaurante"], "address": "Calle Sol 1, Cádiz"}).json()
        company = session.get(m.Company, uuid.UUID(body["id"]))
        assert company.created_by == "laura@example.com"

    def test_3_modified_at_changes_on_update_but_created_at_does_not(self, session):
        """Editing a row moves modified_at forward and leaves created_at alone."""
        company = make_company(session)
        created, modified = company.created_at, company.modified_at
        time.sleep(0.01)
        company.city = "Cádiz"
        session.commit()
        session.refresh(company)
        assert company.created_at == created and company.modified_at > modified

    def test_4_set_actor_overrides_the_default(self, session):
        """Code that sets an actor (an agent, a script) is recorded under that name."""
        token = set_actor("agente-pedidos")
        try:
            company = make_company(session, "Con actor")
        finally:
            reset_actor(token)
        assert company.created_by == "agente-pedidos"

    def test_5_an_explicit_author_is_kept(self, session):
        """A created_by given by the service is not overwritten."""
        interaction = make_interaction(session, None, created_by="manolo@example.com")
        assert interaction.created_by == "manolo@example.com"


class TestSoftDeleteCompanies:
    """Deleting companies and what depends on them."""

    def test_0_deleted_company_disappears_but_stays_in_the_database(self, client, session):
        """It is gone from the API and lists, and kept in the table with who and when."""
        company = make_company(session, "A borrar")
        assert client.delete(f"/api/companies/{company.id}").status_code == 204
        assert client.get(f"/api/companies/{company.id}").status_code == 404
        assert client.get("/api/companies").json()["total"] == 0
        (row,) = everything(session, m.Company)
        assert row.deleted_at is not None and row.deleted_by == "laura@example.com"

    def test_1_contacts_and_interactions_of_the_company_go_with_it(self, client, session):
        """Cascade: its contacts and interactions are hidden too (and kept in the table)."""
        company = make_company(session)
        make_contact(session, company)
        make_interaction(session, company)
        make_interaction(session, None, source="nota_de_voz", summary=None, transcript="suelta")
        client.delete(f"/api/companies/{company.id}")
        assert client.get("/api/contacts").json()["total"] == 0
        assert client.get("/api/interactions").json()["total"] == 1  # only the unassigned note remains
        assert all(c.deleted_at for c in everything(session, m.Contact))

    def test_2_a_company_with_invoices_cannot_be_deleted(self, client, session, issuer):
        """Fiscal documents block the deletion; nothing is changed."""
        _, company = issue_invoice(client, session)
        response = client.delete(f"/api/companies/{company.id}")
        assert response.status_code == 409 and "facturas" in response.json()["detail"]
        assert client.get(f"/api/companies/{company.id}").status_code == 200

    def test_3_deleting_twice_or_an_unknown_id_is_404(self, client, session):
        """Already deleted records behave as if they did not exist."""
        company = make_company(session)
        assert client.delete(f"/api/companies/{company.id}").status_code == 204
        assert client.delete(f"/api/companies/{company.id}").status_code == 404
        assert client.delete(f"/api/companies/{uuid.uuid4()}").status_code == 404

    def test_4_the_tax_id_of_a_deleted_company_can_be_reused(self, client, session):
        """Uniqueness only applies to live rows, but a live duplicate is still refused."""
        company = make_company(session, tax_id="B123")
        body = {"name": "Nueva", "roles": ["Cliente"], "type": ["tienda"], "address": "Calle 1, Cádiz", "tax_id": "B123"}
        assert client.post("/api/companies", json=body).status_code == 409
        client.delete(f"/api/companies/{company.id}")
        assert client.post("/api/companies", json=body).status_code == 201

    def test_5_requires_authentication(self, anonymous_client):
        """Nobody deletes anything without logging in."""
        assert anonymous_client.delete(f"/api/companies/{uuid.uuid4()}").status_code == 401


class TestSoftDeleteOtherRecords:
    """Contacts, interactions, products and invoices."""

    def test_0_deleting_a_contact_keeps_its_interactions(self, client, session):
        """Detach: the interactions stay, without contact."""
        company = make_company(session)
        contact = make_contact(session, company)
        interaction = make_interaction(session, company, contact_id=contact.id)
        assert client.delete(f"/api/contacts/{contact.id}").status_code == 204
        assert client.get(f"/api/interactions/{interaction.id}").json()["contact"] is None
        assert client.get(f"/api/contacts/{contact.id}").status_code == 404

    def test_1_deleted_interaction_leaves_lists_and_counters(self, client, session):
        """It no longer counts as pending on the dashboard."""
        note = make_interaction(session, None, source="nota_de_voz", summary=None, transcript="x", processing_status="pendiente")
        assert client.get("/api/dashboard").json()["pending_interactions"] == 1
        assert client.delete(f"/api/interactions/{note.id}").status_code == 204
        assert client.get("/api/dashboard").json()["pending_interactions"] == 0
        assert client.get("/api/interactions").json()["total"] == 0

    def test_2_product_name_can_be_reused_after_deleting_it(self, client, session):
        """Deleting frees the name; a second live product with the same name is still refused."""
        product = make_product(session, "Boletus")
        new = {"name": "Boletus", "format": "Fresco", "target_net_margin": "0.3"}
        assert client.post("/api/products", json=new).status_code == 409
        assert client.delete(f"/api/products/{product.id}").status_code == 204
        assert client.post("/api/products", json=new).status_code == 201

    def test_3_a_product_in_use_cannot_be_deleted(self, client, session):
        """Block: lots that use it must be dealt with first."""
        lot = make_lot(session, "Usado")
        response = client.delete(f"/api/products/{lot.product_id}")
        assert response.status_code == 409 and "lotes" in response.json()["detail"]
        assert len(client.get("/api/products").json()) == 1

    def test_4_deleted_invoice_is_hidden_and_its_number_is_not_reused(self, client, session, issuer):
        """The invoice and its lines disappear; the next invoice gets the next number."""
        invoice, _ = issue_invoice(client, session, "A1")
        assert client.delete(f"/api/invoices/{invoice['id']}").status_code == 204
        assert client.get(f"/api/invoices/{invoice['id']}").status_code == 404
        assert client.get(f"/api/invoices/{invoice['id']}/pdf").status_code == 404
        assert client.get("/api/invoices").json()["total"] == 0
        assert session.execute(text("SELECT count(*) FROM invoice_balance")).scalar() == 0
        assert all(i.deleted_at for i in everything(session, m.InvoiceItem))
        second, _ = issue_invoice(client, session, "A2")
        assert second["invoice_number"].endswith("-0002")


class TestSoftDeleteAnyTable:
    """The generic service works on every table and the stock views ignore deleted rows."""

    def test_0_deleted_allocation_releases_the_stock(self, session):
        """A reservation that is deleted stops counting in lot_stock."""
        _, lot, _, item = seed_order_with_lot(session)
        allocation = m.LotAllocation(lot_id=lot.id, order_item_id=item.id, quantity=Decimal("3"), allocated_at=NOW)
        session.add(allocation)
        session.commit()
        stock = lambda: session.execute(text("SELECT available_quantity FROM lot_stock")).scalar()
        assert stock() == 2
        deletion.delete_record(session, m.LotAllocation, allocation.id)
        assert stock() == 5

    def test_1_deleted_lot_leaves_the_stock_view(self, session):
        """The view lists only live lots; the lot's adjustments go with it."""
        lot = make_lot(session, "Caduco")
        session.add(m.LotAdjustment(lot_id=lot.id, quantity=Decimal("1"), reason="merma", adjusted_at=NOW))
        session.commit()
        assert session.execute(text("SELECT count(*) FROM lot_stock")).scalar() == 1
        deletion.delete_record(session, m.Lot, lot.id)
        assert session.execute(text("SELECT count(*) FROM lot_stock")).scalar() == 0
        assert all(a.deleted_at for a in everything(session, m.LotAdjustment))

    def test_2_works_on_a_table_with_no_rules(self, session):
        """A leaf table (payments) is deleted too, recorded under the default actor."""
        _, _, order, _ = seed_order_with_lot(session)
        invoice = m.Invoice(order_id=order.id, invoice_number="X-1")
        session.add(invoice)
        session.flush()
        payment = m.Payment(invoice_id=invoice.id, paid_at=NOW, amount=Decimal("5"))
        session.add(payment)
        session.commit()
        deletion.delete_record(session, m.Payment, payment.id)
        (row,) = everything(session, m.Payment)
        assert row.deleted_by == "system"
        with_filter = session.scalars(select(m.Payment)).all()
        assert with_filter == []

    def test_3_unknown_record_raises(self, session):
        """The service reports a missing record instead of silently doing nothing."""
        try:
            deletion.delete_record(session, m.Company, uuid.uuid4())
        except NotFoundError:
            return
        raise AssertionError("NotFoundError not raised")
