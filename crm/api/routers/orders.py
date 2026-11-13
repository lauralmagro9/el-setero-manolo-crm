"""Endpoints of customer orders."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ... import enums as e
from ... import schemas as s
from ...services import orders as svc
from ..deps import PageParams, get_db

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=s.Page[s.OrderOut])
def list_orders(
    status: e.OrderStatus | None = None,
    company_id: uuid.UUID | None = None,
    created_by_agent: bool | None = None,
    paging: PageParams = Depends(),
    db: Session = Depends(get_db),
):
    """List orders, newest first."""
    items, total = svc.list_orders(
        db, status=status, company_id=company_id, created_by_agent=created_by_agent,
        page=paging.page, page_size=paging.page_size,
    )
    return s.Page(items=items, total=total, page=paging.page, page_size=paging.page_size)


@router.get("/{order_id}", response_model=s.OrderOut)
def get_order(order_id: uuid.UUID, db: Session = Depends(get_db)):
    """Return one order."""
    return svc.get_order(db, order_id)


@router.patch("/{order_id}", response_model=s.OrderOut)
def update_order(order_id: uuid.UUID, data: s.OrderUpdate, db: Session = Depends(get_db)):
    """Edit an order: customer and contact, delivery date, status or notes."""
    return svc.update_order(db, order_id, data)
