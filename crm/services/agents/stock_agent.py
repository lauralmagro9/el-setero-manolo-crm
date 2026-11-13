"""Stock agent: watches orders and lots and raises alerts. The rules are plain queries, no model.

The model (optional) only writes the text of an alert from facts the rules already found.
Each alert has a dedupe key (type + entity + day), so running the agent many times a day is safe.
"""

import logging
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ... import enums as e
from ... import models as m
from ... import schemas as s
from ... import view_models as v
from ...config import settings
from ...utils import format_quantity
from .. import alerts as alerts_svc
from .llm import LLM, get_llm, is_configured
from .utils import system_actor

logger = logging.getLogger(__name__)

AGENT_NAME = "stock_agent"


def _key(alert_type: e.AlertType, entity: str, entity_id, today: date) -> str:
    """Return the dedupe key: one alert per type, entity and day."""
    return f"{alert_type}:{entity}:{entity_id}:{today.isoformat()}"


def _write_text(llm: LLM | None, facts: str, fallback: str) -> str:
    """Let the model word the alert from `facts`; use `fallback` when it is off or fails."""
    if llm is None:
        return fallback
    try:
        reply = llm.complete([
            {"role": "system", "content": settings.agents.stock.text_system_prompt},
            {"role": "user", "content": facts},
        ])
        return (reply.content or "").strip() or fallback
    except Exception as exc:  # noqa: BLE001 - the template is always good enough
        logger.warning("Stock agent could not word an alert with the model: %s", exc)
        return fallback


def _open_demand(session: Session) -> dict:
    """Return {product_id: (product name, kg requested and not reserved yet)} for the open orders."""
    cfg = settings.agents.stock
    reserved = (
        select(m.LotAllocation.order_item_id, func.sum(m.LotAllocation.quantity).label("reserved"))
        .where(m.LotAllocation.status != e.AllocationStatus.RELEASED, m.LotAllocation.deleted_at.is_(None))
        .group_by(m.LotAllocation.order_item_id).subquery()
    )
    rows = session.execute(
        select(m.OrderItem.product_id, m.Product.name, m.OrderItem.quantity,
               func.coalesce(reserved.c.reserved, 0))
        .join(m.Order, m.Order.id == m.OrderItem.order_id)
        .join(m.Product, m.Product.id == m.OrderItem.product_id)
        .outerjoin(reserved, reserved.c.order_item_id == m.OrderItem.id)
        .where(m.Order.status.in_([e.OrderStatus(x) for x in cfg.open_order_statuses]))
    ).all()
    demand: dict = defaultdict(lambda: ["", Decimal(0)])
    for product_id, name, quantity, already in rows:
        demand[product_id][0] = name
        demand[product_id][1] += max(Decimal(quantity) - Decimal(already), Decimal(0))
    return demand


def _check_insufficient_stock(session: Session, today: date, llm: LLM | None) -> int:
    """Alert for each product whose open orders ask for more than the stock available."""
    created = 0
    available = dict(session.execute(
        select(v.LotStock.product_id, func.sum(v.LotStock.available_quantity))
        .where(v.LotStock.status == "disponible").group_by(v.LotStock.product_id)
    ).all())
    for product_id, (name, needed) in _open_demand(session).items():
        have = Decimal(available.get(product_id) or 0)
        if needed <= have:
            continue
        missing = needed - have
        fallback = (f"Stock insuficiente de {name}: los pedidos abiertos necesitan {format_quantity(needed)} kg "
                    f"y hay {format_quantity(have)} kg disponibles (faltan {format_quantity(missing)} kg).")
        alert = alerts_svc.create_alert(
            session, type=e.AlertType.INSUFFICIENT_STOCK,
            severity=e.AlertSeverity(settings.agents.stock.insufficient_severity),
            message=_write_text(llm, fallback, fallback), product_id=product_id,
            data={"needed": str(needed), "available": str(have), "missing": str(missing)},
            dedupe_key=_key(e.AlertType.INSUFFICIENT_STOCK, "product", product_id, today),
        )
        created += alert is not None
    return created


def suggest_companies(session: Session, product_id) -> list[dict]:
    """Return who could be offered `product_id`: past buyers first (most orders first), then interested customers."""
    cfg = settings.agents.stock
    buyers = session.execute(
        select(m.Company.id, m.Company.name, func.count(func.distinct(m.Order.id)), func.max(m.Order.requested_at))
        .join(m.Order, m.Order.company_id == m.Company.id)
        .join(m.OrderItem, m.OrderItem.order_id == m.Order.id)
        .where(m.OrderItem.product_id == product_id,
               m.Order.status.not_in([e.OrderStatus(x) for x in cfg.excluded_history_statuses]))
        .group_by(m.Company.id, m.Company.name)
        .order_by(func.count(func.distinct(m.Order.id)).desc(), func.max(m.Order.requested_at).desc())
    ).all()
    suggestions = [
        {"company_id": str(cid), "name": name, "reason": f"ha comprado este producto {count} vez/veces"}
        for cid, name, count, _ in buyers
    ]
    seen = {x["company_id"] for x in suggestions}
    interested = session.execute(
        select(m.Company.id, m.Company.name, m.Company.customer_status)
        .where(m.Company.customer_status.in_([e.CustomerStatus(x) for x in cfg.interested_statuses]))
        .order_by(m.Company.name)
    ).all()
    for cid, name, status in interested:
        if str(cid) not in seen:
            suggestions.append({"company_id": str(cid), "name": name, "reason": f"está {status.lower()}"})
    return suggestions[: cfg.max_suggestions]


def _check_expiring_lots(session: Session, today: date, llm: LLM | None) -> int:
    """Alert for each lot expiring within dashboard.expiry_alert_days, with customers to offer it to."""
    created = 0
    limit = today + timedelta(days=settings.dashboard.expiry_alert_days)
    lots = session.scalars(
        select(v.LotStock).where(
            v.LotStock.status.in_(["disponible", "reservado"]), v.LotStock.available_quantity > 0,
            v.LotStock.expiry_date.is_not(None), v.LotStock.expiry_date >= today, v.LotStock.expiry_date <= limit,
        ).order_by(v.LotStock.expiry_date)
    ).all()
    for lot in lots:
        suggestions = suggest_companies(session, lot.product_id)
        who = "; ".join(f"{x['name']} ({x['reason']})" for x in suggestions)
        facts = (f"El lote {lot.lot_code} de {lot.product_name} caduca el {lot.expiry_date:%d/%m/%Y} y quedan "
                 f"{format_quantity(lot.available_quantity)} kg." + (f" Clientes a quienes ofrecerlo: {who}." if who else ""))
        alert = alerts_svc.create_alert(
            session, type=e.AlertType.EXPIRING_LOT,
            severity=e.AlertSeverity(settings.agents.stock.expiring_severity),
            message=_write_text(llm, facts, facts), product_id=lot.product_id, lot_id=lot.lot_id,
            company_id=uuid.UUID(suggestions[0]["company_id"]) if suggestions else None,
            data={"expiry_date": lot.expiry_date.isoformat(), "available": str(lot.available_quantity),
                  "suggested_companies": suggestions},
            dedupe_key=_key(e.AlertType.EXPIRING_LOT, "lot", lot.lot_id, today),
        )
        created += alert is not None
    return created


def _check_low_stock(session: Session, today: date, llm: LLM | None) -> int:
    """Alert for each lot at or below dashboard.low_stock_threshold."""
    created = 0
    lots = session.scalars(
        select(v.LotStock).where(
            v.LotStock.status == "disponible", v.LotStock.available_quantity <= settings.dashboard.low_stock_threshold
        ).order_by(v.LotStock.available_quantity)
    ).all()
    for lot in lots:
        fallback = (f"Poco stock del lote {lot.lot_code} de {lot.product_name}: "
                    f"quedan {format_quantity(lot.available_quantity)} kg.")
        alert = alerts_svc.create_alert(
            session, type=e.AlertType.LOW_STOCK,
            severity=e.AlertSeverity(settings.agents.stock.low_stock_severity),
            message=_write_text(llm, fallback, fallback), product_id=lot.product_id, lot_id=lot.lot_id,
            data={"available": str(lot.available_quantity)},
            dedupe_key=_key(e.AlertType.LOW_STOCK, "lot", lot.lot_id, today),
        )
        created += alert is not None
    return created


def run_stock_agent(session: Session, today: date | None = None, llm: LLM | None = None) -> s.StockAgentRunOut:
    """Evaluate every stock rule once and log the run in AgentExecution.

    `llm` words the alerts; when it is None the model is used only if agents.stock.use_llm_for_text is on
    and a Groq key exists, otherwise fixed templates are used.
    """
    today = today or date.today()
    if llm is None and settings.agents.stock.use_llm_for_text and is_configured():
        llm = get_llm()
    started = datetime.now()
    with system_actor():
        counts = {
            "insufficient_stock": _check_insufficient_stock(session, today, llm),
            "expiring_lots": _check_expiring_lots(session, today, llm),
            "low_stock": _check_low_stock(session, today, llm),
        }
        session.add(m.AgentExecution(
            agent_name=AGENT_NAME, started_at=started, finished_at=datetime.now(), input={"today": today.isoformat()},
            output=counts, status=e.AgentStatus.SUCCESS, model=llm.model if llm else None,
        ))
        session.commit()
    logger.info("Stock agent finished: %s", counts)
    return s.StockAgentRunOut(alerts_created=sum(counts.values()))
