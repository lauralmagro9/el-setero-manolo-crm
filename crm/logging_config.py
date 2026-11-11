"""Logging setup: level and format come from settings.toml ([logging])."""

import logging

from .config import settings


def setup_logging() -> None:
    """Make the application's own loggers visible at the configured level.

    uvicorn only configures its own loggers, so without this the messages of our modules would be
    lost. The handler is added only when the root logger has none, so running under uvicorn gets
    one console handler and running under pytest keeps pytest's own (live logs, caplog).
    """
    cfg = settings.logging
    root = logging.getLogger()
    root.setLevel(cfg.level.upper())
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(cfg.format))
        root.addHandler(handler)
