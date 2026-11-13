"""Business logic for the alerts raised by the agents."""

import logging
import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import enums as e
from .. import models as m
from ..utils import paginate
from .errors import NotFoundError

logger = logging.getLogger(__name__)


def list_alerts(
    session: Session,
    *,
    unread_only: bool = False,
    type: e.AlertType | None = None,
    page: int = 1,
    page_size: int = 25,
):
    """Return (alerts, total) matching the filters, newest first."""
    query = select(m.Alert).order_by(m.Alert.created_at.desc(), m.Alert.id)
    if unread_only:
        query = query.where(m.Alert.read_at.is_(None))
    if type:
        query = query.where(m.Alert.type == type)
    return paginate(session, query, page, page_size)


def count_unread(session: Session) -> int:
    """Return how many alerts have not been read yet."""
    return session.scalar(select(func.count()).select_from(m.Alert).where(m.Alert.read_at.is_(None))) or 0


def get_alert(session: Session, alert_id: uuid.UUID) -> m.Alert:
    """Return an alert or raise NotFoundError."""
    alert = session.get(m.Alert, alert_id)
    if alert is None:
        raise NotFoundError("Alerta no encontrada")
    return alert


def mark_read(session: Session, alert_id: uuid.UUID) -> m.Alert:
    """Mark an alert as read (it keeps the first read time if it was already read)."""
    alert = get_alert(session, alert_id)
    if alert.read_at is None:
        alert.read_at = datetime.now()
        session.commit()
    return alert


def mark_all_read(session: Session) -> int:
    """Mark every unread alert as read and return how many there were."""
    result = session.execute(
        update(m.Alert).where(m.Alert.read_at.is_(None), m.Alert.deleted_at.is_(None))
        .values(read_at=datetime.now())
    )
    session.commit()
    return result.rowcount


def create_alert(
    session: Session,
    *,
    type: e.AlertType,
    severity: e.AlertSeverity,
    message: str,
    dedupe_key: str | None = None,
    **links,
) -> m.Alert | None:
    """Create and commit an alert; return None when one with the same `dedupe_key` already exists.

    `links` are the optional references of the alert (product_id, lot_id, company_id, order_id,
    interaction_id) and `data`.
    """
    if dedupe_key and session.scalar(select(m.Alert.id).where(m.Alert.dedupe_key == dedupe_key)):
        return None
    alert = m.Alert(type=type, severity=severity, message=message, dedupe_key=dedupe_key, **links)
    session.add(alert)
    try:
        session.commit()
    except IntegrityError:  # another run created the same alert at the same time
        session.rollback()
        return None
    logger.info("Alert created: %s (%s)", alert.type, alert.dedupe_key)
    return alert


def mark_read_by_key(session: Session, dedupe_key: str) -> None:
    """Mark as read the alert with this dedupe key (nothing happens when there is none)."""
    alert = session.scalar(select(m.Alert).where(m.Alert.dedupe_key == dedupe_key))
    if alert is not None and alert.read_at is None:
        alert.read_at = datetime.now()
        session.commit()
