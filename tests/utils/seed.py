"""Helpers that build sample data for the tests."""


from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from crm import models as m

NOW = datetime(2026, 11, 10, 12, 0)


def seed_demo(session: Session) -> bool:
    """Insert a small realistic data set; return False if the database already had data."""
    if session.scalar(select(func.count()).select_from(m.Company)):
        return False
    now = datetime.now().replace(microsecond=0)

    boletus = m.Product(name="Boletus edulis fresco", species="Boletus edulis", format="Fresco",
                        tax_rate=Decimal("0.10"), target_net_margin=Decimal("0.30"))
    chanterelle = m.Product(name="Cantarelo congelado", species="Cantharellus cibarius",
                            format="Congelado", tax_rate=Decimal("0.10"),
                            target_net_margin=Decimal("0.25"))
    morel = m.Product(name="Colmenilla deshidratada", species="Morchella esculenta",
                      format="Deshidratado", tax_rate=Decimal("0.10"),
                      target_net_margin=Decimal("0.35"), base_unit="kg")
    restaurant = m.Company(name="Restaurante El Faro", roles=["Cliente"], type=["restaurante"],
                           customer_status="Interesado", city="Algeciras", region="Cádiz",
                           country="España", phone="+34956000001")
    shop = m.Company(name="Frutería La Huerta", roles=["Cliente"], type=["frutería", "tienda"],
                     customer_status="Contactado", city="La Línea", phone="+34956000002")
    collector = m.Company(name="Recolector Antonio", roles=["Proveedor"], type=["distribuidor"],
                          supplier_status="Activo", city="Los Barrios")
    session.add_all([boletus, chanterelle, morel, restaurant, shop, collector])
    session.flush()

    contact = m.Contact(company_id=restaurant.id, first_name="Marta", last_name="Ruiz",
                        position="Jefa de cocina", phone="+34600000001", is_primary=True)
    session.add(contact)
    session.flush()
    interaction = m.Interaction(
        company_id=restaurant.id, contact_id=contact.id, occurred_at=now, type="WhatsApp",
        direction="Entrante", source="whatsapp", external_id="demo-1",
        summary="Pide 3 kg de boletus frescos para mañana", processing_status="procesada")
    lot_boletus = m.Lot(product_id=boletus.id, supplier_company_id=collector.id, lot_code="BOL-001",
                        received_at=now - timedelta(days=1), quantity_received=Decimal("5"),
                        purchase_cost_per_unit=Decimal("20"), additional_costs=Decimal("5"),
                        expiry_date=date.today() + timedelta(days=4))
    lot_chanterelle = m.Lot(product_id=chanterelle.id, supplier_company_id=collector.id,
                            lot_code="CAN-001", received_at=now - timedelta(days=10),
                            quantity_received=Decimal("8"), purchase_cost_per_unit=Decimal("12"),
                            expiry_date=date.today() + timedelta(days=120))
    session.add_all([interaction, lot_boletus, lot_chanterelle])
    session.flush()

    order = m.Order(company_id=restaurant.id, contact_id=contact.id, requested_at=now,
                    requested_delivery_date=date.today() + timedelta(days=1),
                    status="Acordando precio", source_interaction_id=interaction.id)
    session.add(order)
    session.flush()
    item = m.OrderItem(order_id=order.id, product_id=boletus.id, quantity=Decimal("3"))
    session.add(item)
    session.flush()
    session.add(m.LotAllocation(lot_id=lot_boletus.id, order_item_id=item.id,
                                quantity=Decimal("3"), allocated_at=now))
    session.commit()
    return True


def seed_order_with_lot(session):
    """Insert a product, a customer, a 5 kg lot costing 21 EUR/kg and an order line of 3 kg.

    Return the tuple (product, lot, order, item).
    """
    product = m.Product(
        name="Boletus edulis fresco", format="Fresco", tax_rate=Decimal("0.10"),
        target_net_margin=Decimal("0.30"),
    )
    customer = m.Company(
        name="Restaurante X", roles=["Cliente"], type=["restaurante"], customer_status="Interesado"
    )
    session.add_all([product, customer])
    session.flush()
    # 5 kg at 20 EUR/kg plus 5 EUR of transport in total -> 21 EUR/kg
    lot = m.Lot(
        product_id=product.id, lot_code="L1", received_at=NOW, quantity_received=Decimal("5"),
        purchase_cost_per_unit=Decimal("20"), additional_costs=Decimal("5"),
    )
    order = m.Order(
        company_id=customer.id, requested_at=NOW, requested_delivery_date=date(2026, 11, 11)
    )
    session.add_all([lot, order])
    session.flush()
    item = m.OrderItem(order_id=order.id, product_id=product.id, quantity=Decimal("3"))
    session.add(item)
    session.flush()
    return product, lot, order, item


def write_env(directory, text):
    """Write `text` to a .env file inside `directory` and return its path."""
    path = directory / ".env"
    path.write_text(text, encoding="utf8")
    return path
