"""Key figures for the home screen."""

from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import enums as e
from .. import models as m
from .. import schemas as s
from .. import view_models as v
from ..config import settings
from .interactions import count_pending


def _count_since(session: Session, since: datetime) -> int:
    """Return how many interactions happened since `since`."""
    return session.scalar(
        select(func.count()).select_from(m.Interaction).where(m.Interaction.occurred_at >= since)
    ) or 0


def get_dashboard(session: Session, today: date | None = None) -> s.DashboardOut:
    """Compute every figure of the dashboard."""
    cfg = settings.dashboard
    today = today or date.today()
    now = datetime.combine(today, datetime.max.time())

    rows = session.execute(
        select(m.Company.customer_status, func.count())
        .where(m.Company.customer_status.is_not(None))
        .group_by(m.Company.customer_status)
    ).all()
    counts = {status: count for status, count in rows}
    customers_by_status = [
        s.StatusCount(customer_status=status, count=counts.get(status, 0)) for status in e.CustomerStatus
    ]

    limit = today + timedelta(days=cfg.expiry_alert_days)
    expiring = session.scalars(
        select(v.LotStock)
        .where(
            v.LotStock.status.in_(["disponible", "reservado"]),
            v.LotStock.expiry_date.is_not(None),
            v.LotStock.expiry_date >= today,
            v.LotStock.expiry_date <= limit,
        )
        .order_by(v.LotStock.expiry_date)
    ).all()
    low_stock = session.scalars(
        select(v.LotStock)
        .where(v.LotStock.status == "disponible", v.LotStock.available_quantity <= cfg.low_stock_threshold)
        .order_by(v.LotStock.available_quantity)
    ).all()
    recent = session.scalars(
        select(m.Interaction).order_by(m.Interaction.occurred_at.desc()).limit(cfg.recent_activity_limit)
    ).unique().all()
    unassigned = session.scalar(
        select(func.count()).select_from(m.Interaction).where(
            m.Interaction.company_id.is_(None),
            m.Interaction.source == e.InteractionSource.VOICE_NOTE,
        )
    ) or 0

    return s.DashboardOut(
        customers_by_status=customers_by_status,
        interactions_short_window=_count_since(session, now - timedelta(days=cfg.short_window_days)),
        interactions_long_window=_count_since(session, now - timedelta(days=cfg.long_window_days)),
        short_window_days=cfg.short_window_days,
        long_window_days=cfg.long_window_days,
        pending_interactions=count_pending(session),
        unassigned_voice_notes=unassigned,
        expiring_lots=[s.LotAlert.model_validate(r) for r in expiring],
        low_stock_lots=[s.LotAlert.model_validate(r) for r in low_stock],
        recent_interactions=[s.InteractionOut.model_validate(r) for r in recent],
    )
