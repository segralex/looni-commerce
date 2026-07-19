"""Event publishing abstractions."""
from __future__ import annotations

from typing import Protocol


class EventPublisher(Protocol):
    def publish(self, event: object) -> None:
        ...


class EventDispatcher(EventPublisher, Protocol):
    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...

    def wait_until_idle(self, timeout: float | None = None) -> bool:
        ...
