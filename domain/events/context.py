from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator


_current_correlation_id: ContextVar[str | None] = ContextVar("current_correlation_id", default=None)
_current_causation_id: ContextVar[str | None] = ContextVar("current_causation_id", default=None)


def set_correlation_id(correlation_id: str | None):
    return _current_correlation_id.set(correlation_id)


def reset_correlation_id(token) -> None:
    _current_correlation_id.reset(token)


def get_correlation_id() -> str | None:
    return _current_correlation_id.get()


def set_causation_id(causation_id: str | None):
    return _current_causation_id.set(causation_id)


def reset_causation_id(token) -> None:
    _current_causation_id.reset(token)


def get_causation_id() -> str | None:
    return _current_causation_id.get()


@contextmanager
def event_context(correlation_id: str | None, causation_id: str | None) -> Iterator[None]:
    """Make event lineage available while a handler creates follow-up events."""
    correlation_token = set_correlation_id(correlation_id)
    causation_token = set_causation_id(causation_id)
    try:
        yield
    finally:
        reset_causation_id(causation_token)
        reset_correlation_id(correlation_token)
