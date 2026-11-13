"""Builders of sample records for the API tests."""

from datetime import date, datetime, timedelta
from decimal import Decimal

from crm import models as m


def make_company(session, name="Restaurante X", **overrides):
    """Insert and return a customer company."""
    data = {"name": name, "roles": ["Cliente"], "type": ["restaurante"], "customer_status": "Contactado"}
    data.update(overrides)
    company = m.Company(**data)
    session.add(company)
    session.commit()
    return company


def make_contact(session, company, first_name="Marta", **overrides):
    """Insert and return a contact of `company`."""
    contact = m.Contact(company_id=company.id, first_name=first_name, **overrides)
    session.add(contact)
    session.commit()
    return contact


def make_interaction(session, company=None, **overrides):
    """Insert and return an interaction (a manual call today unless overridden)."""
    data = {
        "company_id": company.id if company else None,
        "occurred_at": datetime.now(),
        "type": "Llamada",
        "source": "manual",
        "summary": "Resumen",
        "processing_status": "procesada",
    }
    data.update(overrides)
    interaction = m.Interaction(**data)
    session.add(interaction)
    session.commit()
    return interaction


def make_lot(session, product_name="Boletus", quantity="10", expires_in_days=None, **overrides):
    """Insert a product with one lot; return the lot."""
    product = m.Product(name=product_name, format="Fresco", tax_rate=Decimal("0.10"),
                        target_net_margin=Decimal("0.30"))
    session.add(product)
    session.flush()
    lot = m.Lot(
        product_id=product.id, lot_code=f"L-{product_name}", received_at=datetime.now(),
        quantity_received=Decimal(quantity), purchase_cost_per_unit=Decimal("10"),
        expiry_date=date.today() + timedelta(days=expires_in_days) if expires_in_days is not None else None,
        **overrides,
    )
    session.add(lot)
    session.commit()
    return lot


def make_product(session, name="Boletus edulis fresco", **overrides):
    """Insert and return a product (10 % VAT, 30 % target margin unless overridden)."""
    data = {"name": name, "format": "Fresco", "tax_rate": Decimal("0.10"), "target_net_margin": Decimal("0.30")}
    data.update(overrides)
    product = m.Product(**data)
    session.add(product)
    session.commit()
    return product


def make_order(session, company, product, quantity="5", status="Nuevo", **overrides):
    """Insert and return an order of `company` with one line of `quantity` kg of `product`."""
    order = m.Order(company_id=company.id, requested_at=datetime.now(), status=status, **overrides)
    order.items.append(m.OrderItem(product_id=product.id, quantity=Decimal(quantity), unit="kg"))
    session.add(order)
    session.commit()
    return order


def make_voice_note(session, transcript="Alberto me ha pedido 5 kg de chantarelas", **overrides):
    """Insert and return a pending voice note."""
    data = {"source": "nota_de_voz", "transcript": transcript, "summary": None,
            "processing_status": "pendiente", "type": "Otro"}
    data.update(overrides)
    return make_interaction(session, **data)
