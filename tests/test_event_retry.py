from __future__ import annotations

from datetime import UTC, datetime

from domain.media.events import ImageUploaded
from infrastructure.events.in_process_dispatcher import InProcessEventDispatcher
from infrastructure.events.outbox_worker import OutboxWorker
from infrastructure.repositories.memory import MemoryOutboxRepository


def test_outbox_worker_increments_retry_and_leaves_event_unpublished_on_failure() -> None:
    outbox = MemoryOutboxRepository()
    dispatcher = InProcessEventDispatcher()

    def handler(_event: ImageUploaded) -> None:
        raise RuntimeError("boom")

    dispatcher.register(ImageUploaded, handler)
    entry = outbox.save(
        ImageUploaded.create(
            image_id="image-1",
            listing_id="listing-1",
            original_storage_key="media/original.jpg",
            occurred_at=datetime.now(UTC),
        )
    )

    worker = OutboxWorker(outbox=outbox, dispatcher=dispatcher, poll_interval_seconds=0.0, max_retry_count=3)
    processed = worker.run_once()

    assert processed == 1
    current = outbox.get(entry.id)
    assert current is not None
    assert current.retry_count == 1
    assert current.published is False


def test_outbox_worker_stops_retrying_after_configured_max() -> None:
    outbox = MemoryOutboxRepository()
    dispatcher = InProcessEventDispatcher()
    attempts: list[str] = []

    def handler(_event: ImageUploaded) -> None:
        attempts.append("attempt")
        raise RuntimeError("boom")

    dispatcher.register(ImageUploaded, handler)
    entry = outbox.save(
        ImageUploaded.create(
            image_id="image-9",
            listing_id="listing-9",
            original_storage_key="media/original-9.jpg",
            occurred_at=datetime.now(UTC),
        )
    )

    worker = OutboxWorker(outbox=outbox, dispatcher=dispatcher, poll_interval_seconds=0.0, max_retry_count=1)
    worker.run_once()
    worker.run_once()

    current = outbox.get(entry.id)
    assert current is not None
    assert current.retry_count == 1
    assert current.published is False
    assert attempts == ["attempt"]