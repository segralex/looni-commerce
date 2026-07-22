from __future__ import annotations

from datetime import UTC, datetime
import logging
import threading
import time

from application.events.publisher import EventDispatcher
from domain.events.outbox import OutboxRepository
from domain.events.metrics import EventMetrics

logger = logging.getLogger(__name__)


class OutboxWorker:
    def __init__(
        self,
        outbox: OutboxRepository,
        dispatcher: EventDispatcher,
        poll_interval_seconds: float = 0.05,
        max_retry_count: int = 3,
        metrics: EventMetrics | None = None,
        sleeper=time.sleep,
    ) -> None:
        self.outbox = outbox
        self.dispatcher = dispatcher
        self.poll_interval_seconds = poll_interval_seconds
        self.max_retry_count = max_retry_count
        self.metrics = metrics
        self.sleeper = sleeper
        self._condition = threading.Condition()
        self._pending = 0
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, name="event-outbox-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self._running:
            return
        with self._condition:
            self._running = False
            self._condition.notify_all()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._thread = None

    def wake(self) -> None:
        with self._condition:
            self._condition.notify_all()

    def wait_until_idle(self, timeout: float | None = None) -> bool:
        with self._condition:
            if self._is_idle():
                return True
            if timeout is None:
                while not self._is_idle():
                    self._condition.wait()
                return True
            return self._condition.wait_for(self._is_idle, timeout=timeout)

    def run_once(self, limit: int | None = None) -> int:
        entries = self.outbox.get_unpublished(limit=limit, max_retry_count=self.max_retry_count)
        if not entries:
            if self.metrics is not None:
                self.metrics.record_queue_depth(len(self.outbox.get_unpublished(max_retry_count=self.max_retry_count)))
            return 0

        with self._condition:
            self._pending += len(entries)

        try:
            for entry in entries:
                fields = {
                    "event_id": entry.event.event_id,
                    "event_type": entry.event.event_type,
                    "aggregate_id": entry.event.aggregate_id,
                    "correlation_id": entry.event.correlation_id,
                    "causation_id": entry.event.causation_id,
                    "retry_count": entry.retry_count,
                }
                logger.info("event dequeued from outbox", extra={**fields, "duration_ms": 0.0})
                dispatch_started = time.monotonic()
                logger.info("event dispatch started", extra={**fields, "duration_ms": 0.0})
                try:
                    self.dispatcher.dispatch(entry.event)
                    duration_ms = round((time.monotonic() - dispatch_started) * 1000, 2)
                    published_at = datetime.now(UTC)
                    published = self.outbox.mark_published(entry.id, published_at)
                    if self.metrics is not None:
                        self.metrics.record_publish_success()
                        self.metrics.record_queue_depth(len(self.outbox.get_unpublished(max_retry_count=self.max_retry_count)))
                    logger.info(
                        "event dispatch succeeded",
                        extra={**fields, "duration_ms": duration_ms},
                    )
                    if published is None:
                        raise RuntimeError("failed to mark published")
                except Exception as exc:
                    duration_ms = round((time.monotonic() - dispatch_started) * 1000, 2)
                    retried = self.outbox.increment_retry(entry.id)
                    if self.metrics is not None:
                        self.metrics.record_retry()
                    logger.warning(
                        "event retry scheduled",
                        extra={**fields,
                               "retry_count": retried.retry_count if retried is not None else entry.retry_count + 1,
                               "duration_ms": duration_ms},
                    )
                    if retried is not None and retried.retry_count >= self.max_retry_count:
                        failed_at = datetime.now(UTC)
                        failed = self.outbox.mark_failed(entry.id, failed_at, str(exc))
                        if self.metrics is not None:
                            self.metrics.record_permanent_failure()
                            self.metrics.record_queue_depth(len(self.outbox.get_unpublished(max_retry_count=self.max_retry_count)))
                        logger.error(
                            "event transitioned to dead letter",
                            extra={**fields, "retry_count": retried.retry_count,
                                   "duration_ms": duration_ms, "failure_reason": str(exc)},
                        )
                        if failed is None:
                            raise RuntimeError("failed to mark permanent failure") from exc
                    elif retried is None:
                        raise RuntimeError("failed to increment retry") from exc
            return len(entries)
        finally:
            with self._condition:
                self._pending = max(0, self._pending - len(entries))
                self._condition.notify_all()

    def _run(self) -> None:
        while True:
            processed = self.run_once()
            with self._condition:
                if not self._running:
                    return
                if processed == 0:
                    self._condition.wait(timeout=self.poll_interval_seconds)

    def _is_idle(self) -> bool:
        if self._pending > 0:
            return False
        return len(self.outbox.list_unpublished(limit=1, max_retry_count=self.max_retry_count)) == 0
