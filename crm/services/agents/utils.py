"""Helpers shared by the agents."""

import difflib
import re
import unicodedata
from datetime import date, timedelta
from collections.abc import Iterator
from contextlib import contextmanager

from ...audit import reset_actor, set_actor


CONTAINED_MANY_WORDS = 0.97  # candidate of several words found whole inside the query
CONTAINED_ONE_WORD = 0.9  # single-word candidate found inside the query
WORD_MATCH_FACTOR = 0.95  # a match on one word of a longer name counts a little less than a full match
MIN_WORD_LENGTH = 4  # shorter queries are too ambiguous to be matched word by word
WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def normalize_text(value: str | None) -> str:
    """Lower-case `value`, drop accents and punctuation, and collapse spaces ("Frutería  Ñu" -> "fruteria nu")."""
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def match_score(query: str, candidate: str | None) -> float:
    """Return how well `candidate` matches `query` (0-1), ignoring case and accents.

    1.0 is an exact match, 0.95 means every word of the query appears in the candidate
    ("alberto" in "alberto garcia"), anything else is the fuzzy similarity of the two texts.
    """
    a, b = normalize_text(query), normalize_text(candidate)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if set(a.split()) <= set(b.split()):
        return 0.95
    # The candidate is named inside a longer query ("marta del bar y" contains "bar y"): a name made of
    # several words is stronger evidence than a single first name
    if set(b.split()) <= set(a.split()):
        return CONTAINED_MANY_WORDS if len(b.split()) > 1 else CONTAINED_ONE_WORD
    whole = difflib.SequenceMatcher(None, a, b).ratio()
    # A misspelt word of the query against each word of the candidate ("rebosuelos" ~ "rebozuelos frescos")
    words = max((difflib.SequenceMatcher(None, a, word).ratio() for word in b.split()), default=0.0)
    return max(whole, words * WORD_MATCH_FACTOR if len(a) >= MIN_WORD_LENGTH else 0.0)


@contextmanager
def system_actor() -> Iterator[None]:
    """Record everything written inside the block as done by the default actor (not by a user)."""
    token = set_actor(None)
    try:
        yield
    finally:
        reset_actor(token)


def calendar_hint(today: date, days: int) -> str:
    """Return one line per day from today on ("viernes 2026-11-13"), so a model need not do date arithmetic."""
    return "\n".join(
        f"- {WEEKDAYS[d.weekday()]} {d.isoformat()}" for d in (today + timedelta(n) for n in range(days))
    )

