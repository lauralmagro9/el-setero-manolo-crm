"""Endpoints of the alerts raised by the agents."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ... import enums as e
from ... import schemas as s
from ...services import alerts as svc
from ..deps import PageParams, get_db

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=s.Page[s.AlertOut])
def list_alerts(
    unread: bool = False,
    type: e.AlertType | None = None,
    paging: PageParams = Depends(),
    db: Session = Depends(get_db),
):
    """List alerts, newest first (?unread=true for the ones not read yet)."""
    items, total = svc.list_alerts(
        db, unread_only=unread, type=type, page=paging.page, page_size=paging.page_size
    )
    return s.Page(items=items, total=total, page=paging.page, page_size=paging.page_size)


@router.get("/unread-count", response_model=s.UnreadCount)
def unread_count(db: Session = Depends(get_db)):
    """Return how many alerts are unread (for the badge in the menu)."""
    return s.UnreadCount(unread=svc.count_unread(db))


@router.post("/read-all", response_model=s.UnreadCount)
def mark_all_read(db: Session = Depends(get_db)):
    """Mark every alert as read."""
    svc.mark_all_read(db)
    return s.UnreadCount(unread=0)


@router.post("/{alert_id}/read", response_model=s.AlertOut)
def mark_read(alert_id: uuid.UUID, db: Session = Depends(get_db)):
    """Mark one alert as read."""
    return svc.mark_read(db, alert_id)
