from __future__ import annotations

from datetime import UTC, datetime

from domain.media.events import ImageUploaded
from infrastructure.events.in_process_dispatcher import InProcessEventDispatcher
from infrastructure.events.outbox_worker import OutboxWorker
from infrastructure.repositories.memory import MemoryOutboxRepository


def test_outbox_worker_publishes_unpublished_event_and_marks_published() -> None:
    outbox = MemoryOutboxRepository()
    dispatcher = InProcessEventDispatcher()
    received: list[str] = []

    def handler(event: ImageUploaded) -> None:
        received.append(event.image_id)

    dispatcher.register(ImageUploaded, handler)
    outbox.save(
        ImageUploaded.create(
            image_id="image-1",
            listing_id="listing-1",
            original_storage_key="media/original.jpg",
            occurred_at=datetime.now(UTC),
        )
    )

    worker = OutboxWorker(outbox=outbox, dispatcher=dispatcher, poll_interval_seconds=0.0)
    processed = worker.run_once()

    assert processed == 1
    assert received == ["image-1"]
    assert outbox.list_unpublished() == []


def test_outbox_worker_background_loop_drains_queue() -> None:
    outbox = MemoryOutboxRepository()
    dispatcher = InProcessEventDispatcher()
    received: list[str] = []

    def handler(event: ImageUploaded) -> None:
        received.append(event.image_id)

    dispatcher.register(ImageUploaded, handler)
    outbox.save(
        ImageUploaded.create(
            image_id="image-2",
            listing_id="listing-2",
            original_storage_key="media/original-2.jpg",
            occurred_at=datetime.now(UTC),
        )
    )

    worker = OutboxWorker(outbox=outbox, dispatcher=dispatcher, poll_interval_seconds=0.001)
    worker.start()
    try:
        assert worker.wait_until_idle(timeout=2.0)
    finally:
        worker.stop()

    assert received == ["image-2"]
    assert outbox.list_unpublished() == []