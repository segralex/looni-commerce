from __future__ import annotations

import pytest

from infrastructure.events.in_process_dispatcher import InProcessEventDispatcher


class DemoEvent:
    def __init__(self, value: str):
        self.value = value


def test_dispatcher_dispatch_runs_registered_handler_synchronously() -> None:
    dispatcher = InProcessEventDispatcher()
    received: list[str] = []

    def handler(event: DemoEvent) -> None:
        received.append(event.value)

    dispatcher.register(DemoEvent, handler)
    dispatcher.dispatch(DemoEvent("ok"))

    assert received == ["ok"]


def test_dispatcher_dispatch_propagates_handler_failure() -> None:
    dispatcher = InProcessEventDispatcher()

    def handler(_event: DemoEvent) -> None:
        raise RuntimeError("boom")

    dispatcher.register(DemoEvent, handler)

    with pytest.raises(RuntimeError, match="boom"):
        dispatcher.dispatch(DemoEvent("x"))