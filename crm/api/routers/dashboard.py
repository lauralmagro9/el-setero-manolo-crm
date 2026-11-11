"""Endpoint of the dashboard."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ... import schemas as s
from ...services import dashboard as svc
from ..deps import get_db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=s.DashboardOut)
def get_dashboard(db: Session = Depends(get_db)):
    """Return the figures of the home screen."""
    return svc.get_dashboard(db)
