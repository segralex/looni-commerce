from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from domain.events.base import DomainEvent
from domain.events.context import event_context, reset_correlation_id, set_correlation_id
from domain.events.metrics import EventMetrics
from domain.events.outbox import OutboxState
from domain.media.events import ImageUploaded
from infrastructure.events.in_process_dispatcher import InProcessEventDispatcher
from infrastructure.events.outbox_worker import OutboxWorker
from infrastructure.repositories.memory import MemoryOutboxRepository
from infrastructure.sqlite.database import Database
from infrastructure.sqlite.outbox_repository import SQLiteOutboxRepository


def make_event(image_id: str, *, correlation_id: str = "corr-1", offset: int = 0) -> ImageUploaded:
    return ImageUploaded.create(
        image_id=image_id,
        listing_id="listing-1",
        original_storage_key=f"media/{image_id}.jpg",
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=offset),
        correlation_id=correlation_id,
    )


def test_request_and_handler_context_propagate_event_lineage() -> None:
    token = set_correlation_id("request-correlation")
    try:
        root = make_event("root", correlation_id=None)  # type: ignore[arg-type]
    finally:
        reset_correlation_id(token)

    with event_context(root.correlation_id, root.event_id):
        follow_up = DomainEvent(
            event_id="follow-up", event_type="FollowUp", aggregate_type="Demo",
            aggregate_id="demo-1", occurred_at=datetime.now(UTC),
        )

    assert root.correlation_id == "request-correlation"
    assert follow_up.correlation_id == root.correlation_id
    assert follow_up.causation_id == root.event_id


@pytest.mark.parametrize("backend", ["memory", "sqlite"])
def test_outbox_query_and_dead_letter_requeue(backend: str, tmp_path) -> None:
    repo = (MemoryOutboxRepository() if backend == "memory" else
            SQLiteOutboxRepository(Database(str(tmp_path / "events.db"))))
    first = repo.save(make_event("image-1", offset=1))
    repo.save(make_event("image-2", correlation_id="other", offset=2))
    repo.increment_retry(first.id)
    repo.mark_failed(first.id, datetime.now(UTC), "permanent test failure")

    matches = repo.query(
        state=OutboxState.DEAD_LETTER, event_type="ImageUploaded",
        aggregate_id="image-1", correlation_id="corr-1",
        occurred_from=datetime(2026, 1, 1, tzinfo=UTC),
        occurred_to=datetime(2026, 1, 2, tzinfo=UTC),
    )
    assert [entry.id for entry in matches] == [first.id]
    assert matches[0].failure_reason == "permanent test failure"

    replayed = repo.requeue([first.id, "missing"])
    assert [entry.id for entry in replayed] == [first.id]
    assert replayed[0].state == OutboxState.PENDING
    assert replayed[0].retry_count == 0


def test_metrics_snapshot_is_immutable_and_tracks_all_phase_c_values() -> None:
    metrics = EventMetrics()
    metrics.record_publish_success()
    metrics.record_handler_failure()
    metrics.record_retry()
    metrics.record_permanent_failure()
    metrics.record_queue_depth(4)
    metrics.record_handler_duration(12.5)
    snapshot = metrics.snapshot()

    assert (snapshot.published_count, snapshot.handler_failure_count,
            snapshot.retry_count, snapshot.dead_letter_count) == (1, 1, 1, 1)
    assert snapshot.queue_depth == 4
    assert snapshot.handler_duration_average_ms == 12.5
    with pytest.raises(FrozenInstanceError):
        snapshot.queue_depth = 0  # type: ignore[misc]


def test_exhausted_event_is_retained_with_payload_failure_metadata_and_metrics() -> None:
    metrics = EventMetrics()
    repo = MemoryOutboxRepository(metrics)
    dispatcher = InProcessEventDispatcher(metrics=metrics)
    dispatcher.register(ImageUploaded, lambda _event: (_ for _ in ()).throw(RuntimeError("boom")))
    entry = repo.save(make_event("failed-image"))

    OutboxWorker(repo, dispatcher, max_retry_count=1, metrics=metrics).run_once()

    exhausted = repo.get(entry.id)
    assert exhausted is not None
    assert exhausted.state == OutboxState.DEAD_LETTER
    assert exhausted.event == entry.event
    assert exhausted.failure_reason == "boom"
    assert exhausted.failed_at is not None
    assert metrics.snapshot().dead_letter_count == 1
    assert metrics.snapshot().handler_failure_count == 1
