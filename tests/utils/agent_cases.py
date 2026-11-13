"""Cases and helpers for the tests that run the order agent against the real language model."""

import json
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from crm import models as m
from crm.services.agents import order_agent

from tests.utils.factories import make_voice_note


@dataclass(frozen=True)
class OrderCase:
    """A transcript and the order the agent must extract from it."""

    id: str
    transcript: str
    company: str
    items: dict[str, Decimal]  # product name -> quantity in the product's unit (kg)
    contact: str | None = None  # first name of the expected contact, when the note names one
    delivery_weekday: int | None = None  # 0 = Monday ... 6 = Sunday
    delivery_month_day: tuple[int, int] | None = None  # (month, day) when the note gives a date


@dataclass(frozen=True)
class NoOrderCase:
    """A transcript from which the agent must NOT create an order, and why."""

    id: str
    transcript: str
    needs_review: bool = True  # True: a human must look at it (alert); False: it is simply not an order
    extra_contacts: list[tuple[str, str, str]] = field(default_factory=list)  # (company, first, last) to add first
    linked_company: str | None = None  # company the note should still be assigned to


def run_agent(session: Session, llm, transcript: str) -> tuple[m.Interaction, m.AgentExecution]:
    """Save `transcript` as a pending voice note, run the agent on it and return (note, execution)."""
    note = make_voice_note(session, transcript=transcript)
    execution = order_agent.process_interaction(session, note.id, llm)
    session.refresh(note)
    return note, execution


def explain(transcript: str, execution: m.AgentExecution) -> str:
    """Return a readable trace of the run, to show when an assertion fails."""
    calls = "\n".join(
        f"  {c['tool']}({json.dumps(c['arguments'], ensure_ascii=False)}) -> "
        f"{json.dumps(c['result'], ensure_ascii=False)}"
        for c in execution.tool_calls or []
    )
    return f"\nTranscript: {transcript}\nStatus: {execution.status}\nTool calls:\n{calls}\nOutput: {execution.output}"


def orders_of(session: Session) -> list[m.Order]:
    """Return every order in the database."""
    return list(session.scalars(select(m.Order)).unique())
