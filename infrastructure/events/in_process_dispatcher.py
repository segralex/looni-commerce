"""Thread-backed in-process event dispatcher."""
from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable
from typing import Any

from application.events.publisher import EventDispatcher

logger = logging.getLogger(__name__)


class InProcessEventDispatcher(EventDispatcher):
    def __init__(self) -> None:
        self._handlers: dict[type[object], list[Callable[[object], None]]] = {}
        self._queue: queue.Queue[object] = queue.Queue()
        self._condition = threading.Condition()
        self._pending = 0
        self._running = False
        self._stop_requested = False
        self._thread: threading.Thread | None = None
        self._sentinel = object()

    def register(self, event_type: type[object], handler: Callable[[object], None]) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def start(self) -> None:
        if self._running:
            return
        self._stop_requested = False
        self._running = True
        self._thread = threading.Thread(target=self._run, name="image-event-dispatcher", daemon=False)
        self._thread.start()

    def stop(self) -> None:
        if not self._running:
            return
        self._stop_requested = True
        self._queue.put(self._sentinel)
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._running = False
        self._thread = None

    def publish(self, event: object) -> None:
        if not self._running:
            raise RuntimeError("Event dispatcher is not running")
        with self._condition:
            self._pending += 1
        self._queue.put(event)

    def wait_until_idle(self, timeout: float | None = None) -> bool:
        with self._condition:
            if self._pending == 0:
                return True
            if timeout is None:
                while self._pending > 0:
                    self._condition.wait()
                return True

            return self._condition.wait_for(lambda: self._pending == 0, timeout=timeout)

    def _run(self) -> None:
        while True:
            event = self._queue.get()
            try:
                if event is self._sentinel:
                    return
                self._dispatch(event)
            finally:
                with self._condition:
                    if self._pending > 0:
                        self._pending -= 1
                    self._condition.notify_all()
                self._queue.task_done()

    def _dispatch(self, event: object) -> None:
        handlers = self._handlers.get(type(event), [])
        if not handlers:
            logger.warning("unknown event skipped", extra={"event_type": type(event).__name__})
            return

        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception("event handler failed", extra={"event_type": type(event).__name__})
