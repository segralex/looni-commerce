from __future__ import annotations

from datetime import UTC, datetime

from domain.media.events import ImageUploaded
from infrastructure.repositories.memory import MemoryOutboxRepository
from infrastructure.sqlite.database import Database
from infrastructure.sqlite.outbox_repository import SQLiteOutboxRepository


def _event() -> ImageUploaded:
    return ImageUploaded.create(
        image_id="image-1",
        listing_id="listing-1",
        original_storage_key="media/original.jpg",
        occurred_at=datetime.now(UTC),
    )


def test_memory_outbox_repository_roundtrip_and_publish_marking() -> None:
    repo = MemoryOutboxRepository()
    entry = repo.save(_event())

    unpublished = repo.list_unpublished()
    assert len(unpublished) == 1
    assert unpublished[0].event == entry.event

    retried = repo.increment_retry(entry.id)
    assert retried is not None
    assert retried.retry_count == 1

    published = repo.mark_published(entry.id, datetime.now(UTC))
    assert published is not None
    assert published.published is True
    assert repo.list_unpublished() == []


def test_sqlite_outbox_repository_roundtrip_and_retry_filtering(tmp_path) -> None:
    db = Database(str(tmp_path / "outbox.db"))
    repo = SQLiteOutboxRepository(db)
    entry = repo.save(_event())

    assert repo.get(entry.id) is not None
    assert len(repo.list_unpublished(max_retry_count=3)) == 1

    repo.increment_retry(entry.id)
    assert len(repo.list_unpublished(max_retry_count=1)) == 0

    published = repo.mark_published(entry.id, datetime.now(UTC))
    assert published is not None
    assert published.published is True