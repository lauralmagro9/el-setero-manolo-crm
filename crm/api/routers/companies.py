"""Endpoints of companies."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ... import enums as e
from ... import schemas as s
from ... import models as m
from ...services import deletion
from ...services import companies as svc
from ..deps import PageParams, get_db

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=s.Page[s.CompanyOut])
def list_companies(
    search: str | None = None,
    role: e.Role | None = None,
    type: e.CompanyType | None = None,
    customer_status: e.CustomerStatus | None = None,
    city: str | None = None,
    paging: PageParams = Depends(),
    db: Session = Depends(get_db),
):
    """List companies with search, filters and pagination."""
    items, total = svc.list_companies(
        db, search=search, role=role, company_type=type, customer_status=customer_status,
        city=city, page=paging.page, page_size=paging.page_size,
    )
    return s.Page(items=items, total=total, page=paging.page, page_size=paging.page_size)


@router.post("", response_model=s.CompanyDetail, status_code=status.HTTP_201_CREATED)
def create_company(data: s.CompanyIn, db: Session = Depends(get_db)):
    """Create a company."""
    return svc.create_company(db, data)


@router.get("/{company_id}", response_model=s.CompanyDetail)
def get_company(company_id: uuid.UUID, db: Session = Depends(get_db)):
    """Return a company with its contacts."""
    return svc.get_company(db, company_id)


@router.patch("/{company_id}", response_model=s.CompanyDetail)
def update_company(company_id: uuid.UUID, data: s.CompanyUpdate, db: Session = Depends(get_db)):
    """Edit a company."""
    return svc.update_company(db, company_id, data)


@router.put("/{company_id}/customer-status", response_model=s.CompanyOut)
def set_customer_status(
    company_id: uuid.UUID, data: s.CustomerStatusUpdate, db: Session = Depends(get_db)
):
    """Move a company to another step of the customer pipeline."""
    return svc.set_customer_status(db, company_id, data.customer_status)


@router.get("/{company_id}/contacts", response_model=list[s.ContactOut])
def list_company_contacts(company_id: uuid.UUID, db: Session = Depends(get_db)):
    """List every contact of a company."""
    svc.get_company(db, company_id)
    items, _ = svc.list_contacts(db, company_id=company_id, page=1, page_size=1000)
    return items


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(company_id: uuid.UUID, db: Session = Depends(get_db)):
    """Delete a company and what depends on it (soft delete: it disappears from the app but stays in the database)."""
    deletion.delete_record(db, m.Company, company_id)
