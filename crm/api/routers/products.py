"""Endpoints of products."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ... import schemas as s
from ... import models as m
from ...services import deletion
from ...services import products as svc
from ..deps import get_db

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[s.ProductOut])
def list_products(active_only: bool = True, search: str | None = None, db: Session = Depends(get_db)):
    """List products (active ones by default), optionally searching by name or species."""
    return svc.list_products(db, active_only, search)


@router.post("", response_model=s.ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(data: s.ProductIn, db: Session = Depends(get_db)):
    """Create a product."""
    return svc.create_product(db, data)


@router.get("/{product_id}", response_model=s.ProductOut)
def get_product(product_id: uuid.UUID, db: Session = Depends(get_db)):
    """Return one product."""
    return svc.get_product(db, product_id)


@router.patch("/{product_id}", response_model=s.ProductOut)
def update_product(product_id: uuid.UUID, data: s.ProductUpdate, db: Session = Depends(get_db)):
    """Edit a product (use is_active = false to retire it)."""
    return svc.update_product(db, product_id, data)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: uuid.UUID, db: Session = Depends(get_db)):
    """Delete a product (refused while orders or lots use it) (soft delete: it disappears from the app but stays in the database)."""
    deletion.delete_record(db, m.Product, product_id)
