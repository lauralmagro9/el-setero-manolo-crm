"""Endpoints of interactions."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ... import enums as e
from ... import schemas as s
from ... import models as m
from ...services import deletion
from ...services import interactions as svc
from ..auth import AuthUser, current_user
from ..deps import PageParams, get_db

router = APIRouter(prefix="/interactions", tags=["interactions"])


@router.get("", response_model=s.Page[s.InteractionOut])
def list_interactions(
    company_id: uuid.UUID | None = None,
    contact_id: uuid.UUID | None = None,
    type: e.InteractionType | None = None,
    processing_status: e.ProcessingStatus | None = None,
    source: e.InteractionSource | None = None,
    unassigned: bool = False,
    search: str | None = None,
    paging: PageParams = Depends(),
    db: Session = Depends(get_db),
):
    """List interactions, newest first."""
    items, total = svc.list_interactions(
        db, company_id=company_id, contact_id=contact_id, type=type,
        processing_status=processing_status, source=source, unassigned=unassigned,
        search=search, page=paging.page, page_size=paging.page_size,
    )
    return s.Page(items=items, total=total, page=paging.page, page_size=paging.page_size)


@router.post("", response_model=s.InteractionOut, status_code=status.HTTP_201_CREATED)
def create_interaction(
    data: s.InteractionIn, db: Session = Depends(get_db), user: AuthUser = Depends(current_user)
):
    """Register an interaction by hand; it is attributed to the logged-in user."""
    return svc.create_interaction(db, data, created_by=user.email)


@router.get("/{interaction_id}", response_model=s.InteractionOut)
def get_interaction(interaction_id: uuid.UUID, db: Session = Depends(get_db)):
    """Return one interaction."""
    return svc.get_interaction(db, interaction_id)


@router.patch("/{interaction_id}", response_model=s.InteractionOut)
def update_interaction(
    interaction_id: uuid.UUID, data: s.InteractionUpdate, db: Session = Depends(get_db)
):
    """Edit an interaction (e.g. assign a company to an unassigned voice note)."""
    return svc.update_interaction(db, interaction_id, data)


@router.delete("/{interaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_interaction(interaction_id: uuid.UUID, db: Session = Depends(get_db)):
    """Delete an interaction (soft delete: it disappears from the app but stays in the database)."""
    deletion.delete_record(db, m.Interaction, interaction_id)
