from __future__ import annotations

import threading

from infrastructure.events.in_process_dispatcher import InProcessEventDispatcher


class DemoEvent:
    def __init__(self, value: str):
        self.value = value


class OtherEvent:
    pass


def test_dispatcher_publishes_to_registered_handler_and_runs_async():
    dispatcher = InProcessEventDispatcher()
    dispatcher.start()
    received: list[str] = []
    barrier = threading.Event()

    def handler(event: DemoEvent) -> None:
        received.append(event.value)
        barrier.set()

    dispatcher.register(DemoEvent, handler)
    dispatcher.publish(DemoEvent("ok"))

    assert received == []
    assert barrier.wait(2.0)
    assert dispatcher.wait_until_idle(timeout=2.0)
    dispatcher.stop()
    assert received == ["ok"]


def test_dispatcher_handles_unknown_event_and_stops_cleanly():
    dispatcher = InProcessEventDispatcher()
    dispatcher.start()
    dispatcher.publish(OtherEvent())
    assert dispatcher.wait_until_idle(timeout=2.0)
    dispatcher.stop()
    assert dispatcher.wait_until_idle(timeout=0.1)
