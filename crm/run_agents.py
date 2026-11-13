"""Run an agent from the command line (e.g. a daily cron job for the stock agent).

    python -m crm.run_agents stock      # watch stock, expiring lots and open orders
    python -m crm.run_agents orders     # process the pending voice notes
"""

import argparse
import logging

from .db import get_session
from .logging_config import setup_logging
from .services.agents import order_agent, stock_agent

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> None:
    """Parse the agent name and run it against the configured database."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("agent", choices=["stock", "orders"])
    args = parser.parse_args(argv)
    setup_logging()
    with get_session() as session:
        result = stock_agent.run_stock_agent(session) if args.agent == "stock" else order_agent.process_pending(session)
    logger.info("Result: %s", result.model_dump())


if __name__ == "__main__":
    main()
