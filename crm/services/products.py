"""Business logic for products."""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models as m
from .. import schemas as s
from .errors import ConflictError, NotFoundError


def list_products(session: Session, active_only: bool = True, search: str | None = None) -> list[m.Product]:
    """Return the products ordered by name, by default only the active ones."""
    query = select(m.Product).order_by(func.lower(m.Product.name))
    if active_only:
        query = query.where(m.Product.is_active)
    if search:
        like = f"%{search.strip()}%"
        query = query.where(or_(m.Product.name.ilike(like), m.Product.species.ilike(like)))
    return list(session.scalars(query))


def get_product(session: Session, product_id: uuid.UUID) -> m.Product:
    """Return a product or raise NotFoundError."""
    product = session.get(m.Product, product_id)
    if product is None:
        raise NotFoundError("Producto no encontrado")
    return product


def _save(session: Session) -> None:
    """Commit, turning a duplicated name into ConflictError."""
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError("Ya existe un producto con ese nombre") from exc


def create_product(session: Session, data: s.ProductIn) -> m.Product:
    """Create a product."""
    product = m.Product(**data.model_dump())
    session.add(product)
    _save(session)
    return product


def update_product(session: Session, product_id: uuid.UUID, data: s.ProductUpdate) -> m.Product:
    """Apply the fields sent in `data` to a product (products are deactivated, never deleted)."""
    product = get_product(session, product_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(product, key, value)
    _save(session)
    return product
