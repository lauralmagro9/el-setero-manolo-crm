"""Tests for the orders endpoints."""

import uuid

from tests.utils.factories import make_company, make_contact, make_order, make_product


class TestListOrders:
    """Tests for GET /api/orders."""

    def test_0_lists_orders_with_their_lines(self, client, session):
        """Each order comes with its customer and its lines (product name, quantity, unit)."""
        company = make_company(session)
        make_order(session, company, make_product(session, "Boletus edulis fresco"), quantity="5")
        [order] = client.get("/api/orders").json()["items"]
        assert order["company"]["name"] == "Restaurante X"
        assert order["status"] == "Nuevo"
        assert [(i["product_name"], float(i["quantity"]), i["unit"]) for i in order["items"]] == [
            ("Boletus edulis fresco", 5.0, "kg")
        ]

    def test_1_filters_by_status_and_company(self, client, session):
        """The status and company filters narrow the list."""
        product = make_product(session)
        x, y = make_company(session, "Restaurante X"), make_company(session, "Bar Y")
        make_order(session, x, product)
        make_order(session, y, product, status="Entregado")
        assert len(client.get("/api/orders").json()["items"]) == 2
        [only] = client.get("/api/orders", params={"status": "Entregado"}).json()["items"]
        assert only["company"]["name"] == "Bar Y"
        [only] = client.get("/api/orders", params={"company_id": str(x.id)}).json()["items"]
        assert only["company"]["name"] == "Restaurante X"

    def test_2_requires_login(self, anonymous_client):
        """Anonymous requests are rejected."""
        assert anonymous_client.get("/api/orders").status_code == 401


class TestUpdateOrder:
    """Tests for GET and PATCH /api/orders/{id}."""

    def test_0_edits_date_status_and_notes(self, client, session):
        """The delivery date, the status and the notes can be changed."""
        order = make_order(session, make_company(session), make_product(session))
        response = client.patch(f"/api/orders/{order.id}", json={
            "requested_delivery_date": "2026-11-20", "status": "Confirmado", "notes": "Llamar antes",
        })
        assert response.status_code == 200
        body = client.get(f"/api/orders/{order.id}").json()
        assert (body["requested_delivery_date"], body["status"], body["notes"]) == (
            "2026-11-20", "Confirmado", "Llamar antes"
        )

    def test_1_changes_company_and_contact_together(self, client, session):
        """Re-linking an order to another customer and one of its contacts works."""
        order = make_order(session, make_company(session), make_product(session))
        other = make_company(session, "Bar Y")
        contact = make_contact(session, other, "Marta")
        body = client.patch(
            f"/api/orders/{order.id}", json={"company_id": str(other.id), "contact_id": str(contact.id)}
        ).json()
        assert body["company"]["name"] == "Bar Y" and body["contact"]["first_name"] == "Marta"

    def test_2_contact_of_another_company_is_rejected(self, client, session):
        """The contact must belong to the order's company."""
        order = make_order(session, make_company(session), make_product(session))
        stranger = make_contact(session, make_company(session, "Bar Y"), "Marta")
        response = client.patch(f"/api/orders/{order.id}", json={"contact_id": str(stranger.id)})
        assert response.status_code == 422

    def test_3_changing_company_requires_a_matching_contact(self, client, session):
        """Moving the order to another company while its old contact stays is refused."""
        company = make_company(session)
        order = make_order(session, company, make_product(session), contact_id=make_contact(session, company, "Ana").id)
        other = make_company(session, "Bar Y")
        assert client.patch(f"/api/orders/{order.id}", json={"company_id": str(other.id)}).status_code == 422
        moved = client.patch(f"/api/orders/{order.id}", json={"company_id": str(other.id), "contact_id": None})
        assert moved.status_code == 200

    def test_5_edits_products_and_quantities(self, client, session):
        """Lines can be changed (product and quantity), added and removed in one save."""
        company = make_company(session)
        boletus, rebozuelos, morillas = (make_product(session, n) for n in ("Boletus", "Rebozuelos", "Morillas"))
        order = make_order(session, company, boletus, quantity="5")
        line = client.get(f"/api/orders/{order.id}").json()["items"][0]
        body = client.patch(f"/api/orders/{order.id}", json={"items": [
            {"id": line["id"], "product_id": str(rebozuelos.id), "quantity": "8"},
            {"product_id": str(morillas.id), "quantity": "2", "unit": "kg"},
        ]}).json()
        assert sorted((i["product_name"], float(i["quantity"])) for i in body["items"]) == [
            ("Morillas", 2.0), ("Rebozuelos", 8.0)]
        assert [i["id"] for i in body["items"] if i["product_name"] == "Rebozuelos"] == [line["id"]]  # same line
        kept = [i for i in body["items"] if i["product_name"] == "Morillas"]
        body = client.patch(f"/api/orders/{order.id}", json={"items": [
            {"id": kept[0]["id"], "product_id": str(morillas.id), "quantity": "2"}]}).json()
        assert [i["product_name"] for i in body["items"]] == ["Morillas"]  # the others were removed

    def test_6_invalid_lines_change_nothing(self, client, session):
        """No lines, a zero quantity, an unknown product or a foreign line are refused without saving."""
        order = make_order(session, make_company(session), make_product(session, "Boletus"), quantity="5")
        other = make_order(session, make_company(session, "Bar Y"), make_product(session, "Morillas"))
        product = order.items[0].product_id
        foreign = str(other.items[0].id)
        for items in (
            [],
            [{"product_id": str(product), "quantity": "0"}],
            [{"product_id": "00000000-0000-0000-0000-000000000001", "quantity": "1"}],
            [{"id": foreign, "product_id": str(product), "quantity": "1"}],
        ):
            assert client.patch(f"/api/orders/{order.id}", json={"items": items}).status_code in (422, 400), items
        [line] = client.get(f"/api/orders/{order.id}").json()["items"]
        assert (line["product_name"], float(line["quantity"])) == ("Boletus", 5.0)

    def test_7_invalid_status_and_unknown_order(self, client, session):
        """An unknown status is a validation error and an unknown order is 404."""
        order = make_order(session, make_company(session), make_product(session))
        assert client.patch(f"/api/orders/{order.id}", json={"status": "Inventado"}).status_code == 422
        assert client.get(f"/api/orders/{uuid.uuid4()}").status_code == 404
