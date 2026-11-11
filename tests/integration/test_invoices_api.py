"""Tests for the invoices endpoints."""

import uuid
from datetime import date

from sqlalchemy import func, select

from crm import models as m
from crm.services import invoices as invoices_service
from crm.services.errors import EmailError

from tests.utils.factories import make_company, make_product

NEW_COMPANY = {
    "name": "Frutería La Era", "type": ["frutería"], "address": "Calle Mayor 1, Algeciras",
    "billing_name": "Pedro Pérez García", "tax_id": "12345678Z",
    "billing_address": "Calle Mayor 1, Algeciras",
}


def line(product, **overrides):
    """Return an invoice line for `product` (10 kg at 20 EUR/kg unless overridden)."""
    data = {"product_id": str(product.id), "description": "Boletus frescos", "unit": "kg",
            "quantity": "10", "unit_price": "20"}
    data.update(overrides)
    return data


def billed_company(session, name="Frutería La Era", **overrides):
    """Insert a company that has complete billing data."""
    data = {"billing_name": "Juan Autónomo", "tax_id": "X1234567L", "billing_address": "Calle Sol 5, Cádiz"}
    data.update(overrides)
    return make_company(session, name, **data)


def payload(product, **overrides):
    """Return a valid invoice request that creates a new company."""
    data = {"invoice_type": "VDA", "new_company": NEW_COMPANY, "lines": [line(product)]}
    data.update(overrides)
    return data


class TestCreateInvoice:
    """Tests for POST /api/invoices."""

    def test_0_new_company_is_created_with_the_invoice(self, client, session, issuer):
        """A new company is stored with all its fields and billing data, and the invoice copies the billing data."""
        product = make_product(session)
        response = client.post("/api/invoices", json=payload(product))
        assert response.status_code == 201
        body = response.json()
        assert body["invoice_number"].startswith("VDA-") and body["invoice_number"].endswith("-0001")
        assert body["status"] == "emitida"
        assert body["customer_name"] == "Pedro Pérez García"
        assert body["customer_tax_id"] == "12345678Z"
        assert body["customer_address"] == "Calle Mayor 1, Algeciras"
        assert body["created_by"] == "laura@example.com"
        totals = body["totals"]
        assert (totals["taxable_base"], totals["vat_amount"], totals["total"]) == ("200.00", "20.00", "220.00")
        company = session.scalar(select(m.Company).where(m.Company.id == uuid.UUID(body["company_id"])))
        assert company.name == "Frutería La Era" and company.type == ["frutería"]
        assert company.billing_name == "Pedro Pérez García"
        assert session.scalar(select(func.count()).select_from(m.Contact)) == 0  # no contact is involved

    def test_1_existing_company_uses_its_billing_data_not_its_name(self, client, session, issuer):
        """A fruit shop run by a self-employed person is invoiced under the owner's name."""
        company = billed_company(session, "Frutería La Era")
        product = make_product(session)
        body = client.post("/api/invoices", json={
            "company_id": str(company.id), "lines": [line(product)]}).json()
        assert body["customer_name"] == "Juan Autónomo"
        assert body["customer_tax_id"] == "X1234567L"
        assert body["customer_address"] == "Calle Sol 5, Cádiz"
        assert session.scalar(select(func.count()).select_from(m.Company)) == 1

    def test_2_snapshot_survives_company_edits(self, client, session, issuer):
        """Editing the company afterwards does not change an issued invoice."""
        company = billed_company(session)
        product = make_product(session)
        created = client.post("/api/invoices", json={"company_id": str(company.id), "lines": [line(product)]}).json()
        client.patch(f"/api/companies/{company.id}", json={"billing_name": "Otro Dueño", "billing_address": "Otra calle"})
        invoice = client.get(f"/api/invoices/{created['id']}").json()
        assert invoice["customer_name"] == "Juan Autónomo"
        assert invoice["customer_address"] == "Calle Sol 5, Cádiz"

    def test_3_existing_company_without_billing_data_is_rejected(self, client, session, issuer):
        """The error names every missing billing field."""
        company = make_company(session, billing_name="Solo nombre")
        product = make_product(session)
        response = client.post("/api/invoices", json={"company_id": str(company.id), "lines": [line(product)]})
        assert response.status_code == 422
        assert "dirección fiscal" in response.json()["detail"] and "NIF/CIF" in response.json()["detail"]

    def test_4_new_company_requires_company_and_billing_fields(self, client, session, issuer):
        """Without type, name, address or any fiscal field a new company is rejected."""
        product = make_product(session)
        for missing in ("type", "billing_name", "address", "tax_id", "name"):
            company = {k: v for k, v in NEW_COMPANY.items() if k != missing}
            if missing == "address":
                company.pop("billing_address", None)  # the billing address would fall back to the address
            response = client.post("/api/invoices", json=payload(product, new_company=company))
            assert response.status_code == 422, missing
        assert session.scalar(select(func.count()).select_from(m.Company)) == 0

    def test_5_exactly_one_of_company_or_new_company(self, client, session, issuer):
        """Sending both or neither is rejected."""
        company = billed_company(session)
        product = make_product(session)
        both = payload(product, company_id=str(company.id))
        neither = {"lines": [line(product)]}
        assert client.post("/api/invoices", json=both).status_code == 422
        assert client.post("/api/invoices", json=neither).status_code == 422

    def test_6_numbers_are_correlative(self, client, session, issuer):
        """Consecutive invoices of the same series and year get 0001, 0002, 0003."""
        company = billed_company(session)
        product = make_product(session)
        numbers = [
            client.post("/api/invoices", json={"company_id": str(company.id), "lines": [line(product)]}).json()["invoice_number"]
            for _ in range(3)
        ]
        assert [n[-4:] for n in numbers] == ["0001", "0002", "0003"]

    def test_7_sequence_restarts_each_year(self, client, session, issuer):
        """A new year starts again at 0001 inside the same series."""
        company = billed_company(session)
        product = make_product(session)
        send = lambda day: client.post("/api/invoices", json={
            "company_id": str(company.id), "issue_date": day, "lines": [line(product)]}).json()
        assert send("2026-12-31")["invoice_number"] == "VDA-2026-0001"
        assert send("2027-01-01")["invoice_number"] == "VDA-2027-0001"

    def test_8_dates_default_to_today_and_can_be_set(self, client, session, issuer):
        """Issue and operation dates are today unless given."""
        company = billed_company(session)
        product = make_product(session)
        default = client.post("/api/invoices", json={"company_id": str(company.id), "lines": [line(product)]}).json()
        assert default["issue_date"] == default["operation_date"] == date.today().isoformat()
        explicit = client.post("/api/invoices", json={
            "company_id": str(company.id), "issue_date": "2026-11-10", "operation_date": "2026-11-05",
            "lines": [line(product)]}).json()
        assert explicit["issue_date"] == "2026-11-10" and explicit["operation_date"] == "2026-11-05"

    def test_9_product_is_mandatory_and_must_exist(self, client, session, issuer):
        """Lines without product (or with an unknown one) are rejected; the product name is copied."""
        company = billed_company(session)
        product = make_product(session, "Boletus edulis")
        no_product = {k: v for k, v in line(product).items() if k != "product_id"}
        assert client.post("/api/invoices", json={"company_id": str(company.id), "lines": [no_product]}).status_code == 422
        unknown = line(product, product_id=str(uuid.uuid4()))
        assert client.post("/api/invoices", json={"company_id": str(company.id), "lines": [unknown]}).status_code == 422
        ok = client.post("/api/invoices", json={"company_id": str(company.id), "lines": [line(product)]}).json()
        assert ok["items"][0]["product_name"] == "Boletus edulis"

    def test_10_disabled_type_is_rejected(self, client, session, issuer):
        """Agrario and Empresa exist in the model but cannot be issued yet."""
        product = make_product(session)
        assert client.post("/api/invoices", json=payload(product, invoice_type="Agrario")).status_code == 422
        config = client.get("/api/invoices/config").json()
        assert config["enabled_types"] == ["VDA"] and float(config["vat_rate"]) == 0.10

    def test_11_line_validation(self, client, session, issuer):
        """No lines or a zero quantity are rejected."""
        product = make_product(session)
        assert client.post("/api/invoices", json=payload(product, lines=[])).status_code == 422
        assert client.post("/api/invoices", json=payload(product, lines=[line(product, quantity="0")])).status_code == 422

    def test_12_duplicate_tax_id_for_new_company_is_409(self, client, session, issuer):
        """A new company whose NIF/CIF already exists must be selected instead."""
        make_company(session, "Ya existe", tax_id="B999")
        product = make_product(session)
        response = client.post("/api/invoices", json=payload(product, new_company={**NEW_COMPANY, "tax_id": "B999"}))
        assert response.status_code == 409

    def test_13_failed_invoice_creates_nothing_and_leaves_no_gap(self, client, session, issuer):
        """A failure after creating the company rolls everything back, numbering included."""
        product = make_product(session)
        bad = payload(product, new_company={**NEW_COMPANY, "tax_id": "B1"}, lines=[line(product, product_id=str(uuid.uuid4()))])
        assert client.post("/api/invoices", json=bad).status_code == 422
        assert session.scalar(select(func.count()).select_from(m.Company)) == 0
        ok = client.post("/api/invoices", json=payload(product)).json()
        assert ok["invoice_number"].endswith("-0001")

    def test_14_missing_issuer_data_is_503(self, client, session, monkeypatch):
        """Without the seller's data no invoice can be issued (whatever .env contains)."""
        from crm.config import settings
        monkeypatch.setitem(settings.issuer.as_dict(), "name", "")
        product = make_product(session)
        assert client.post("/api/invoices", json=payload(product)).status_code == 503

    def test_15_requires_authentication(self, anonymous_client):
        """No token, no invoice."""
        assert anonymous_client.post("/api/invoices", json={}).status_code == 401

    def test_16_preview_matches_the_saved_totals(self, client, session, issuer):
        """The preview endpoint (quantity and price only) returns the amounts that will be saved."""
        product = make_product(session)
        preview = client.post("/api/invoices/preview", json={"lines": [{"quantity": "10", "unit_price": "20"}]}).json()
        saved = client.post("/api/invoices", json=payload(product)).json()["totals"]
        assert preview == saved
        assert preview["line_amounts"] == ["200.00"]

    def test_17_new_company_is_a_customer_by_default(self, client, session, issuer):
        """Role and customer status are not sent from the invoice form: the company is created as a customer."""
        product = make_product(session)
        body = client.post("/api/invoices", json=payload(product)).json()
        company = session.get(m.Company, uuid.UUID(body["company_id"]))
        assert company.roles == ["Cliente"]
        assert company.customer_status == "Cliente"

    def test_18_billing_address_defaults_to_the_address(self, client, session, issuer):
        """Without a billing address the normal address is printed; a different one is kept as given."""
        product = make_product(session)
        company = {k: v for k, v in NEW_COMPANY.items() if k != "billing_address"}
        same = client.post("/api/invoices", json=payload(product, new_company={**company, "address": "Plaza 3, Jerez"}))
        assert same.json()["customer_address"] == "Plaza 3, Jerez"
        other = {**company, "tax_id": "B2", "address": "Plaza 3, Jerez", "billing_address": "Calle Fiscal 9"}
        different = client.post("/api/invoices", json=payload(product, new_company=other))
        assert different.json()["customer_address"] == "Calle Fiscal 9"


class TestInvoiceEmail:
    """Tests for the emailing of invoices."""

    def issue(self, client, session):
        """Issue an invoice for a company with billing data and return the response body."""
        company = billed_company(session)
        product = make_product(session)
        return client.post("/api/invoices", json={"company_id": str(company.id), "lines": [line(product)]}).json()

    def test_0_email_disabled_leaves_pending(self, client, session, issuer, sent_emails):
        """With email.enabled = false the invoice is saved as pending and nothing is sent."""
        body = self.issue(client, session)
        assert body["email_status"] == "pending"
        assert sent_emails == []

    def test_1_sent_to_configured_address_with_pdf(self, client, session, issuer, email_enabled, sent_emails):
        """The PDF goes to the configured address and the result is recorded."""
        body = self.issue(client, session)
        assert body["email_status"] == "sent"
        assert body["email_recipient"] == "facturas@example.com"
        assert body["email_sent_at"] and body["email_error"] is None
        (mail,) = sent_emails
        assert mail["recipient"] == "facturas@example.com"
        assert body["invoice_number"] in mail["subject"]
        filename, content, mime = mail["attachments"][0]
        assert filename == f"{body['invoice_number']}.pdf" and content.startswith(b"%PDF") and mime == "application/pdf"

    def test_2_failure_keeps_the_invoice_and_can_be_retried(self, client, session, issuer, email_enabled, monkeypatch):
        """If the mail fails the invoice exists with status failed; resending later succeeds."""
        def boom(**kwargs):
            raise EmailError("servidor caído")

        monkeypatch.setattr(invoices_service, "send_email", boom)
        body = self.issue(client, session)
        assert body["email_status"] == "failed" and "servidor caído" in body["email_error"]
        assert client.get(f"/api/invoices/{body['id']}").status_code == 200

        sent = []
        monkeypatch.setattr(invoices_service, "send_email", lambda **kwargs: sent.append(kwargs))
        retry = client.post(f"/api/invoices/{body['id']}/send").json()
        assert retry["email_status"] == "sent" and retry["email_error"] is None and len(sent) == 1

    def test_3_cannot_send_twice(self, client, session, issuer, email_enabled, sent_emails):
        """Resending an invoice that was already sent is a conflict."""
        body = self.issue(client, session)
        assert client.post(f"/api/invoices/{body['id']}/send").status_code == 409
        assert len(sent_emails) == 1

    def test_4_missing_recipient_marks_failed(self, client, session, issuer, monkeypatch, sent_emails):
        """Enabled email without a configured destination fails clearly instead of sending."""
        from crm.config import settings
        monkeypatch.setitem(settings.email.as_dict(), "enabled", True)
        monkeypatch.setitem(settings.email.as_dict(), "invoice_recipient", "")
        body = self.issue(client, session)
        assert body["email_status"] == "failed" and "EMAIL_INVOICE_RECIPIENT" in body["email_error"]


class TestReadInvoices:
    """Tests for listing, reading and downloading invoices."""

    def test_0_list_filters_and_search(self, client, session, issuer):
        """Invoices can be searched by number or customer and filtered by email status."""
        product = make_product(session)
        a = billed_company(session, "A", billing_name="Pedro Pérez")
        b = billed_company(session, "B", billing_name="María López", tax_id="Y7654321M")
        for company in (a, b):
            client.post("/api/invoices", json={"company_id": str(company.id), "lines": [line(product)]})
        assert client.get("/api/invoices").json()["total"] == 2
        assert client.get("/api/invoices", params={"search": "lópez"}).json()["total"] == 1
        assert client.get("/api/invoices", params={"email_status": "failed"}).json()["total"] == 0

    def test_1_pdf_download(self, client, session, issuer):
        """The PDF endpoint returns the file named after the invoice number."""
        company = billed_company(session)
        product = make_product(session)
        body = client.post("/api/invoices", json={"company_id": str(company.id), "lines": [line(product)]}).json()
        response = client.get(f"/api/invoices/{body['id']}/pdf")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert body["invoice_number"] in response.headers["content-disposition"]
        assert response.content.startswith(b"%PDF")

    def test_2_unknown_invoice_is_404(self, client):
        """Unknown ids answer 404."""
        assert client.get(f"/api/invoices/{uuid.uuid4()}").status_code == 404

    def test_3_products_endpoint(self, client, session):
        """The products list feeds the invoice form (active products only by default)."""
        make_product(session, "Activo")
        make_product(session, "Inactivo", is_active=False)
        assert [p["name"] for p in client.get("/api/products").json()] == ["Activo"]
        assert len(client.get("/api/products", params={"active_only": False}).json()) == 2
