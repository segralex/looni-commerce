"""Thread-backed in-process event dispatcher."""
from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable
from typing import Any

from application.events.publisher import EventDispatcher
from domain.events.metrics import EventMetrics
from domain.events.registry import EventRegistry
from domain.events.context import event_context

logger = logging.getLogger(__name__)


class InProcessEventDispatcher(EventDispatcher):
    def __init__(self, registry: EventRegistry | None = None, metrics: EventMetrics | None = None) -> None:
        self._registry = registry or EventRegistry()
        self._metrics = metrics
        self._queue: queue.Queue[object] = queue.Queue()
        self._condition = threading.Condition()
        self._pending = 0
        self._running = False
        self._stop_requested = False
        self._thread: threading.Thread | None = None
        self._sentinel = object()

    def register(self, event_type: type[object], handler: Callable[[object], None]) -> None:
        self._registry.register(event_type, handler)

    def start(self) -> None:
        if self._running:
            return
        self._stop_requested = False
        self._running = True
        self._thread = threading.Thread(target=self._run, name="image-event-dispatcher", daemon=True)
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

    def dispatch(self, event: object) -> None:
        event_type = getattr(event, "event_type", type(event))
        handlers = self._registry.handlers_for(event_type)
        if not handlers:
            logger.warning("unknown event skipped", extra={"event_type": type(event).__name__})
            return

        for handler in handlers:
            handler_name = getattr(handler, "__qualname__", getattr(handler, "__name__", repr(handler)))
            start = time.monotonic()
            fields = {
                "event_id": getattr(event, "event_id", None),
                "event_type": getattr(event, "event_type", type(event).__name__),
                "aggregate_id": getattr(event, "aggregate_id", None),
                "correlation_id": getattr(event, "correlation_id", None),
                "causation_id": getattr(event, "causation_id", None),
                "retry_count": getattr(event, "retry_count", 0),
                "handler": handler_name,
            }
            logger.info("event dispatch started", extra={**fields, "duration_ms": 0.0})
            try:
                with event_context(fields["correlation_id"], fields["event_id"]):
                    handler(event)
            except Exception:
                duration_ms = round((time.monotonic() - start) * 1000, 2)
                if self._metrics is not None:
                    self._metrics.record_handler_failure()
                    self._metrics.record_handler_duration(duration_ms)
                logger.exception(
                    "event handler failed",
                    extra={**fields, "duration_ms": duration_ms},
                )
                raise
            else:
                duration_ms = round((time.monotonic() - start) * 1000, 2)
                if self._metrics is not None:
                    self._metrics.record_handler_duration(duration_ms)
                logger.info(
                    "event handler succeeded",
                    extra={**fields, "duration_ms": duration_ms},
                )

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
                self.dispatch(event)
            except Exception:
                logger.exception("event handler failed", extra={"event_type": type(event).__name__})
            finally:
                with self._condition:
                    if self._pending > 0:
                        self._pending -= 1
                    self._condition.notify_all()
                self._queue.task_done()
