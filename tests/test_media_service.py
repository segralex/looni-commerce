from __future__ import annotations

from io import BytesIO
from uuid import uuid4

import pytest

from application.media.service import MediaService
from infrastructure.media.pillow_validator import PillowImageValidator
from infrastructure.repositories.memory import MemoryListingImageRepository
from infrastructure.storage.local import LocalStorageProvider
from tests.conftest import make_jpeg_bytes


class NoTouchStorageProvider(LocalStorageProvider):
    def __init__(self, root_path):
        super().__init__(root_path)
        self.delete_calls: list[str | None] = []

    def save(self, source_path: str, content_type: str):
        raise AssertionError("reorder should not save files")

    def open(self, storage_key: str):
        raise AssertionError("reorder should not open files")

    def delete(self, storage_key: str) -> None:
        self.delete_calls.append(storage_key)


class RecordingPublisher:
    def __init__(self):
        self.published: list[object] = []

    def publish(self, event: object) -> None:
        self.published.append(event)


class FailingPublisher:
    def publish(self, event: object) -> None:
        raise RuntimeError("dispatcher unavailable")


def test_media_service_validates_exact_image_set_for_reorder(tmp_path):
    repo = MemoryListingImageRepository()
    listing_id = uuid4()
    storage = LocalStorageProvider(tmp_path / "storage")
    service = MediaService(image_repo=repo, storage=storage)

    first = service.upload_image(listing_id, BytesIO(b"one"), "image/jpeg", "one.jpg")
    second = service.upload_image(listing_id, BytesIO(b"two"), "image/jpeg", "two.jpg")

    with pytest.raises(ValueError):
        service.reorder_listing_images(listing_id, [first.id, first.id])

    with pytest.raises(ValueError):
        service.reorder_listing_images(listing_id, [first.id])

    with pytest.raises(ValueError):
        service.reorder_listing_images(listing_id, [first.id, second.id, uuid4()])


def test_media_service_reorder_delegates_without_touching_binary_storage(tmp_path):
    repo = MemoryListingImageRepository()
    listing_id = uuid4()
    upload_storage = LocalStorageProvider(tmp_path / "upload-storage")
    service = MediaService(image_repo=repo, storage=upload_storage, listing_lookup=lambda _: {"id": str(listing_id)})

    first = service.upload_image(listing_id, BytesIO(b"one"), "image/jpeg", "one.jpg")
    second = service.upload_image(listing_id, BytesIO(b"two"), "image/jpeg", "two.jpg")

    no_touch_storage = NoTouchStorageProvider(tmp_path / "reorder-storage")
    reorder_service = MediaService(image_repo=repo, storage=no_touch_storage, listing_lookup=lambda _: {"id": str(listing_id)})
    reordered = reorder_service.reorder_listing_images(listing_id, [second.id, first.id])

    assert [image.id for image in reordered] == [second.id, first.id]
    assert no_touch_storage.delete_calls == []


def test_media_service_delete_delegates_binary_removal(tmp_path):
    repo = MemoryListingImageRepository()
    upload_storage = LocalStorageProvider(tmp_path / "upload-storage")
    service = MediaService(image_repo=repo, storage=upload_storage)
    listing_id = uuid4()
    image = service.upload_image(listing_id, BytesIO(b"one"), "image/jpeg", "one.jpg")
    storage_key = repo.get_storage_key(image.id)
    assert storage_key is not None

    tracking_storage = NoTouchStorageProvider(tmp_path / "tracking-storage")
    delete_service = MediaService(image_repo=repo, storage=tracking_storage)
    assert delete_service.delete_image(image.id) is True
    assert tracking_storage.delete_calls == [storage_key]


def test_media_service_upload_persists_pending_and_publishes_event(tmp_path):
    repo = MemoryListingImageRepository()
    storage = LocalStorageProvider(tmp_path / "storage")
    publisher = RecordingPublisher()
    service = MediaService(
        image_repo=repo,
        storage=storage,
        event_publisher=publisher,
        image_validator=PillowImageValidator(),
    )

    listing_id = uuid4()
    image = service.upload_image(listing_id, BytesIO(make_jpeg_bytes()), "image/jpeg", "one.jpg")

    original_key = repo.get_storage_key(image.id)

    assert original_key is not None and storage.exists(original_key)
    assert image.processing_status.value == "PENDING"
    assert image.processing_error is None
    assert image.processing_attempts == 0
    assert image.thumbnails == {"small": None, "medium": None, "large": None}
    assert len(publisher.published) == 1

    assert service.delete_image(image.id) is True
    assert storage.exists(original_key) is False


def test_media_service_upload_marks_failed_when_event_publication_fails(tmp_path):
    repo = MemoryListingImageRepository()
    storage = LocalStorageProvider(tmp_path / "storage")
    service = MediaService(
        image_repo=repo,
        storage=storage,
        event_publisher=FailingPublisher(),
        image_validator=PillowImageValidator(),
    )

    listing_id = uuid4()
    with pytest.raises(RuntimeError, match="could not be scheduled"):
        service.upload_image(listing_id, BytesIO(make_jpeg_bytes()), "image/jpeg", "broken.jpg")

    images = repo.get_by_listing(listing_id)
    assert len(images) == 1
    assert images[0].processing_status.value == "FAILED"
    assert images[0].processing_error is not None


def test_media_service_rejects_invalid_image_before_publication(tmp_path):
    repo = MemoryListingImageRepository()
    storage = LocalStorageProvider(tmp_path / "storage")
    publisher = RecordingPublisher()
    service = MediaService(
        image_repo=repo,
        storage=storage,
        event_publisher=publisher,
        image_validator=PillowImageValidator(),
    )

    listing_id = uuid4()
    with pytest.raises(ValueError, match="Unable to decode image"):
        service.upload_image(listing_id, BytesIO(b"not-an-image"), "image/jpeg", "broken.jpg")

    assert repo.count_by_listing(listing_id) == 0
    assert publisher.published == []