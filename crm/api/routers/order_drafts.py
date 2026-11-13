"""Endpoints of the order drafts the user has to complete."""

import uuid

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from ... import enums as e
from ... import schemas as s
from ...services import order_drafts as svc
from ..deps import get_db

router = APIRouter(prefix="/order-drafts", tags=["order-drafts"])


@router.get("", response_model=list[s.OrderDraftOut])
def list_drafts(status: e.OrderDraftStatus | None = e.OrderDraftStatus.PENDING, db: Session = Depends(get_db)):
    """List the drafts waiting for the user (?status=... for the others)."""
    return [svc.to_out(d) for d in svc.list_drafts(db, status)]


@router.get("/{draft_id}", response_model=s.OrderDraftOut)
def get_draft(draft_id: uuid.UUID, db: Session = Depends(get_db)):
    """Return one draft with what is still missing."""
    return svc.to_out(svc.get_draft(db, draft_id))


@router.patch("/{draft_id}", response_model=s.OrderDraftOut)
def update_draft(draft_id: uuid.UUID, data: s.OrderDraftUpdate, db: Session = Depends(get_db)):
    """Save what the user filled in; the draft may still be incomplete."""
    return svc.to_out(svc.update_draft(db, draft_id, data))


@router.post("/{draft_id}/complete", response_model=s.OrderOut)
def complete_draft(
    draft_id: uuid.UUID, data: s.OrderDraftUpdate | None = Body(None), db: Session = Depends(get_db)
):
    """Mark the draft as complete (saving the changes sent) and create the order; 422 lists what is missing."""
    return svc.complete_draft(db, draft_id, data)


@router.post("/{draft_id}/discard", response_model=s.OrderDraftOut)
def discard_draft(draft_id: uuid.UUID, db: Session = Depends(get_db)):
    """Discard the draft: the note was not an order."""
    return svc.to_out(svc.discard_draft(db, draft_id))
