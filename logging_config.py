from __future__ import annotations

import contextvars
import logging
import sys
import threading
from typing import Any

_correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id",
    default=None,
)


def set_correlation_id(thread_id: str) -> None:
    """Set correlation id for log lines (e.g. LangGraph thread_id or issue URL)."""
    _correlation_id.set(thread_id)


def get_correlation_id() -> str | None:
    """Return the current correlation id, if any."""
    return _correlation_id.get()


class _CorrelationIdFilter(logging.Filter):
    """Inject ``thread_id`` from ContextVar into every ``LogRecord``."""

    def filter(self, record: logging.LogRecord) -> bool:
        cid = _correlation_id.get()
        record.thread_id = cid if cid is not None else "-"
        return True


class _NodeOutputFormatter(logging.Formatter):
    """Append ``output_payload`` extra field when present (node completion summaries)."""

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        payload: Any = getattr(record, "output_payload", None)
        if payload is not None:
            return f"{base} | {payload!r}"
        return base


_FORMAT = "%(asctime)s [%(name)s] [%(thread_id)s] %(levelname)s: %(message)s"
_logging_configured = False
_logging_lock = threading.Lock()


def get_logger(name: str) -> logging.Logger:
    """Return a stdlib logger; configures root handler once with correlation id + format."""
    global _logging_configured
    logger = logging.getLogger(name)
    with _logging_lock:
        if not _logging_configured:
            _logging_configured = True
            root = logging.getLogger()
            if not root.handlers:
                handler = logging.StreamHandler(sys.stderr)
                handler.setFormatter(_NodeOutputFormatter(_FORMAT))
                handler.addFilter(_CorrelationIdFilter())
                root.addHandler(handler)
                root.setLevel(logging.INFO)
    logger.setLevel(logging.INFO)
    logger.propagate = True
    return logger
