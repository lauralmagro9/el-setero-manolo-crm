"""Manual triggers of the agents (retry of the order agent, run of the stock agent)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ... import schemas as s
from ...services.agents import order_agent, stock_agent
from ..deps import get_db

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/process-pending", response_model=s.OrderAgentRunOut)
def process_pending(db: Session = Depends(get_db)):
    """Process the voice notes still pending (retry after a failure or a missing key)."""
    return order_agent.process_pending(db)


@router.post("/run-stock", response_model=s.StockAgentRunOut)
def run_stock(db: Session = Depends(get_db)):
    """Run the stock agent now (it also runs on a schedule, see crm/run_agents.py)."""
    return stock_agent.run_stock_agent(db)
