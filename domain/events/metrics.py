from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EventMetricsSnapshot:
    published_count: int
    handler_failure_count: int
    retry_count: int
    dead_letter_count: int
    queue_depth: int
    handler_duration_count: int
    handler_duration_total_ms: float
    handler_duration_average_ms: float


class EventMetrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._published_events = 0
        self._handler_failures = 0
        self._retries = 0
        self._permanent_failures = 0
        self._queue_depth = 0
        self._handler_duration_total_ms = 0.0
        self._handler_duration_count = 0

    def record_publish_success(self) -> None:
        with self._lock:
            self._published_events += 1

    def record_retry(self) -> None:
        with self._lock:
            self._retries += 1

    def record_handler_failure(self) -> None:
        with self._lock:
            self._handler_failures += 1

    def record_permanent_failure(self) -> None:
        with self._lock:
            self._permanent_failures += 1

    def record_queue_depth(self, queue_depth: int) -> None:
        with self._lock:
            self._queue_depth = queue_depth

    def record_handler_duration(self, duration_ms: float) -> None:
        with self._lock:
            self._handler_duration_total_ms += duration_ms
            self._handler_duration_count += 1

    @property
    def published_events(self) -> int:
        with self._lock:
            return self._published_events

    @property
    def retries(self) -> int:
        with self._lock:
            return self._retries

    @property
    def permanent_failures(self) -> int:
        with self._lock:
            return self._permanent_failures

    @property
    def queue_depth(self) -> int:
        with self._lock:
            return self._queue_depth

    @property
    def average_handler_duration_ms(self) -> float:
        with self._lock:
            if self._handler_duration_count == 0:
                return 0.0
            return self._handler_duration_total_ms / self._handler_duration_count

    @property
    def handler_failures(self) -> int:
        with self._lock:
            return self._handler_failures

    published_count = property(lambda self: self.published_events)
    handler_failure_count = property(lambda self: self.handler_failures)
    retry_count = property(lambda self: self.retries)
    dead_letter_count = property(lambda self: self.permanent_failures)
    handler_duration_ms = property(lambda self: self.average_handler_duration_ms)

    def snapshot(self) -> EventMetricsSnapshot:
        with self._lock:
            average = (
                self._handler_duration_total_ms / self._handler_duration_count
                if self._handler_duration_count else 0.0
            )
            return EventMetricsSnapshot(
                published_count=self._published_events,
                handler_failure_count=self._handler_failures,
                retry_count=self._retries,
                dead_letter_count=self._permanent_failures,
                queue_depth=self._queue_depth,
                handler_duration_count=self._handler_duration_count,
                handler_duration_total_ms=self._handler_duration_total_ms,
                handler_duration_average_ms=average,
            )
