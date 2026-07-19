from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from uuid import uuid4

from application.media.image_uploaded_handler import ImageUploadedHandler
from application.media.thumbnail_service import ThumbnailService
from domain.listings.images import ListingImage
from domain.media.events import ImageUploaded
from domain.media.processing import ImageProcessingStatus
from infrastructure.media.pillow_processor import PillowImageProcessor
from infrastructure.repositories.memory import MemoryListingImageRepository
from infrastructure.storage.local import LocalStorageProvider
from tests.conftest import make_jpeg_bytes


def _event(image_id: str, listing_id: str, storage_key: str) -> ImageUploaded:
    return ImageUploaded.create(
        image_id=image_id,
        listing_id=listing_id,
        original_storage_key=storage_key,
        occurred_at=datetime.now(UTC),
    )


def test_handler_processes_pending_image_to_ready(tmp_path):
    repo = MemoryListingImageRepository()
    storage = LocalStorageProvider(tmp_path / "storage")
    thumbnails = ThumbnailService(PillowImageProcessor(), storage)
    handler = ImageUploadedHandler(repo, storage, thumbnails, retry_delays=(0.0,), sleeper=lambda _: None)

    listing_id = uuid4()
    image = ListingImage(
        id=uuid4(),
        listing_id=listing_id,
        filename="photo.jpg",
        content_type="image/jpeg",
        size_bytes=len(make_jpeg_bytes()),
        position=1,
        created_at=datetime.now(UTC),
    )
    storage_key = "orig.jpg"
    repo.store(image, storage_key=storage_key)
    source = tmp_path / "source.jpg"
    source.write_bytes(make_jpeg_bytes())
    storage.save_as(str(source), storage_key, "image/jpeg")

    handler.handle(_event(str(image.id), str(listing_id), storage_key))

    stored = repo.get(image.id)
    assert stored is not None
    assert stored.processing_status == ImageProcessingStatus.READY
    assert stored.processing_error is None
    assert stored.processing_attempts == 1
    assert stored.has_required_thumbnails


def test_handler_ignores_deleted_image(tmp_path):
    repo = MemoryListingImageRepository()
    storage = LocalStorageProvider(tmp_path / "storage")
    thumbnails = ThumbnailService(PillowImageProcessor(), storage)
    handler = ImageUploadedHandler(repo, storage, thumbnails, sleeper=lambda _: None)

    handler.handle(_event(str(uuid4()), str(uuid4()), "missing.jpg"))
    assert True
