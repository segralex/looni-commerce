from __future__ import annotations

from io import BytesIO
from uuid import uuid4

import pytest
from PIL import Image

from application.media.service import MediaService
from application.media.thumbnail_service import ThumbnailService
from infrastructure.repositories.memory import MemoryListingImageRepository
from infrastructure.media.pillow_processor import PillowImageProcessor
from infrastructure.storage.local import LocalStorageProvider


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


def _image_bytes(image_format: str = "JPEG") -> bytes:
    image = Image.new("RGB", (32, 24), (32, 64, 180))
    buf = BytesIO()
    image.save(buf, format=image_format)
    return buf.getvalue()


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


def test_media_service_upload_generates_thumbnails_and_delete_removes_all_assets(tmp_path):
    repo = MemoryListingImageRepository()
    storage = LocalStorageProvider(tmp_path / "storage")
    thumbnails = ThumbnailService(processor=PillowImageProcessor(), storage=storage)
    service = MediaService(image_repo=repo, storage=storage, thumbnail_service=thumbnails)

    listing_id = uuid4()
    image = service.upload_image(listing_id, BytesIO(_image_bytes("JPEG")), "image/jpeg", "one.jpg")

    original_key = repo.get_storage_key(image.id)
    small_key = repo.get_thumbnail_key(image.id, "small")
    medium_key = repo.get_thumbnail_key(image.id, "medium")
    large_key = repo.get_thumbnail_key(image.id, "large")

    assert original_key is not None and storage.exists(original_key)
    assert small_key is not None and storage.exists(small_key)
    assert medium_key is not None and storage.exists(medium_key)
    assert large_key is not None and storage.exists(large_key)
    assert image.thumbnails == {
        "small": small_key,
        "medium": medium_key,
        "large": large_key,
    }

    assert service.delete_image(image.id) is True
    assert storage.exists(original_key) is False
    assert storage.exists(small_key) is False
    assert storage.exists(medium_key) is False
    assert storage.exists(large_key) is False


def test_media_service_upload_rolls_back_original_on_thumbnail_failure(tmp_path):
    repo = MemoryListingImageRepository()
    storage = LocalStorageProvider(tmp_path / "storage")
    thumbnails = ThumbnailService(processor=PillowImageProcessor(), storage=storage)
    service = MediaService(image_repo=repo, storage=storage, thumbnail_service=thumbnails)

    listing_id = uuid4()
    with pytest.raises(ValueError, match="invalid image data"):
        service.upload_image(listing_id, BytesIO(b"not-an-image"), "image/jpeg", "broken.jpg")

    assert repo.count_by_listing(listing_id) == 0
    assert list((tmp_path / "storage").iterdir()) == []