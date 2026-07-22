from __future__ import annotations

from collections.abc import Callable
from typing import Any


class EventRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[[object], None]]] = {}

    def register(self, event_type: str | type[object], handler: Callable[[object], None]) -> None:
        key = self._normalize_event_type(event_type)
        handlers = self._handlers.setdefault(key, [])
        if handler in handlers:
            raise ValueError(f"duplicate handler registration for event type '{key}'")
        handlers.append(handler)

    def handlers_for(self, event_type: str | type[object]) -> tuple[Callable[[object], None], ...]:
        key = self._normalize_event_type(event_type)
        return tuple(self._handlers.get(key, []))

    def _normalize_event_type(self, event_type: str | type[object]) -> str:
        if isinstance(event_type, str):
            return event_type
        if hasattr(event_type, "EVENT_TYPE"):
            return str(getattr(event_type, "EVENT_TYPE"))
        return event_type.__name__
