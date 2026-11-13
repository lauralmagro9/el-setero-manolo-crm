"""Entry points to run the agents outside a request: background tasks and the command line."""

import logging
import uuid

from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from ...config import settings
from . import order_agent
from .llm import is_configured
from .utils import system_actor

logger = logging.getLogger(__name__)


def process_voice_note_in_background(engine: Engine, interaction_id: uuid.UUID) -> None:
    """Run the order agent on one voice note with its own session; never raises.

    It does nothing (the note stays pending, for POST /api/agents/process-pending) when
    agents.auto_process is off or the llm key is missing.
    """
    if not settings.agents.auto_process:
        return
    if not is_configured():
        logger.warning("Voice note %s left pending: the Groq key is not configured", interaction_id)
        return
    try:
        with sessionmaker(engine, expire_on_commit=False)() as session, system_actor():
            order_agent.process_interaction(session, interaction_id)
    except Exception:  # noqa: BLE001 - a background task has nobody to report to
        logger.exception("Background processing of voice note %s failed", interaction_id)
