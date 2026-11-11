"""Endpoints of contacts."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ... import schemas as s
from ...services import companies as svc
from ..deps import PageParams, get_db

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("", response_model=s.Page[s.ContactOut])
def list_contacts(
    company_id: uuid.UUID | None = None,
    search: str | None = None,
    paging: PageParams = Depends(),
    db: Session = Depends(get_db),
):
    """List contacts, optionally of one company."""
    items, total = svc.list_contacts(
        db, company_id=company_id, search=search, page=paging.page, page_size=paging.page_size
    )
    return s.Page(items=items, total=total, page=paging.page, page_size=paging.page_size)


@router.post("", response_model=s.ContactOut, status_code=status.HTTP_201_CREATED)
def create_contact(data: s.ContactIn, db: Session = Depends(get_db)):
    """Create a contact."""
    return svc.create_contact(db, data)


@router.get("/{contact_id}", response_model=s.ContactOut)
def get_contact(contact_id: uuid.UUID, db: Session = Depends(get_db)):
    """Return one contact."""
    return svc.get_contact(db, contact_id)


@router.patch("/{contact_id}", response_model=s.ContactOut)
def update_contact(contact_id: uuid.UUID, data: s.ContactUpdate, db: Session = Depends(get_db)):
    """Edit a contact."""
    return svc.update_contact(db, contact_id, data)


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(contact_id: uuid.UUID, db: Session = Depends(get_db)):
    """Delete a contact."""
    svc.delete_contact(db, contact_id)
