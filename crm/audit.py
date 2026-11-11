"""Who is doing the current operation, for the audit columns (created_by) of every table.

The API sets the actor to the logged-in user's email for each request; scripts, agents, the seed
and the tests that set nothing are recorded as the default actor (settings audit.default_actor).
"""

from contextvars import ContextVar, Token

from .config import settings

_actor: ContextVar[str | None] = ContextVar("actor", default=None)


def set_actor(name: str | None) -> Token:
    """Make `name` the author of what is written from now on (in this context); return the reset token."""
    return _actor.set(name or None)


def reset_actor(token: Token) -> None:
    """Undo a previous `set_actor`."""
    _actor.reset(token)


def current_actor() -> str:
    """Return the current author, or the default actor when nobody has been set."""
    return _actor.get() or settings.audit.default_actor
