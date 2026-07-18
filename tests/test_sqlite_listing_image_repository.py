from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from uuid import uuid4

from application.media.service import MediaService
from domain.listings.images import ListingImage
from infrastructure.sqlite.database import Database
from infrastructure.sqlite.listing_image_repository import SQLiteListingImageRepository
from infrastructure.storage.local import LocalStorageProvider


def _make_image(listing_id, position: int = 1) -> ListingImage:
    return ListingImage(
        id=uuid4(),
        listing_id=listing_id,
        filename=f"photo{position}.jpg",
        content_type="image/jpeg",
        size_bytes=1000 + position,
        position=position,
        created_at=datetime.now(UTC),
    )


def test_sqlite_listing_image_repository_crud(tmp_path):
    repo = SQLiteListingImageRepository(Database(str(tmp_path / "images.db")))
    listing_id = uuid4()
    image_one = _make_image(listing_id, 2)
    image_two = _make_image(listing_id, 1)

    repo.store(image_one)
    repo.store(image_two)

    fetched = repo.get_by_id(image_one.id)
    assert fetched is not None
    assert fetched.filename == image_one.filename

    ordered = repo.get_by_listing(listing_id)
    assert [image.position for image in ordered] == [1, 2]
    assert repo.count_by_listing(listing_id) == 2

    assert repo.delete_by_id(image_one.id) is True
    assert repo.get_by_id(image_one.id) is None
    assert repo.count_by_listing(listing_id) == 1
    assert repo.delete_by_id(image_one.id) is False


def test_sqlite_listing_image_repository_persists_across_recreation(tmp_path):
    db_path = tmp_path / "persist-images.db"
    listing_id = uuid4()

    first_repo = SQLiteListingImageRepository(Database(str(db_path)))
    first_repo.store(_make_image(listing_id, 1))
    first_repo.store(_make_image(listing_id, 2))

    second_repo = SQLiteListingImageRepository(Database(str(db_path)))
    images = second_repo.get_by_listing(listing_id)

    assert len(images) == 2
    assert [image.position for image in images] == [1, 2]


def test_image_metadata_persists_across_media_service_recreation(tmp_path):
    db_path = tmp_path / "service-images.db"
    storage_path = tmp_path / "storage"
    listing_id = uuid4()

    first_repo = SQLiteListingImageRepository(Database(str(db_path)))
    storage = LocalStorageProvider(storage_path)
    first_service = MediaService(image_repo=first_repo, storage=storage)

    uploaded = first_service.upload_image(
        listing_id=listing_id,
        file_data=BytesIO(b"first-image"),
        content_type="image/jpeg",
        filename="first.jpg",
    )

    second_repo = SQLiteListingImageRepository(Database(str(db_path)))
    second_service = MediaService(image_repo=second_repo, storage=storage)
    images = second_service.get_listing_images(listing_id)

    assert len(images) == 1
    assert images[0].id == uploaded.id
    assert images[0].filename == "first.jpg"


def test_repo_delete_removes_metadata_only(tmp_path):
    db_path = tmp_path / "delete-metadata.db"
    storage = LocalStorageProvider(tmp_path / "storage")
    repo = SQLiteListingImageRepository(Database(str(db_path)))
    media_service = MediaService(image_repo=repo, storage=storage)
    listing_id = uuid4()

    uploaded = media_service.upload_image(
        listing_id=listing_id,
        file_data=BytesIO(b"keep-binary"),
        content_type="image/jpeg",
        filename="photo.jpg",
    )

    stored_files = list((tmp_path / "storage").iterdir())
    assert len(stored_files) == 1

    assert repo.delete_by_id(uploaded.id) is True
    assert repo.get_by_id(uploaded.id) is None
    assert repo.count_by_listing(listing_id) == 0
    assert stored_files[0].exists()


def test_media_service_delete_keeps_storage_delegated(tmp_path):
    db_path = tmp_path / "service-delete.db"
    storage = LocalStorageProvider(tmp_path / "storage")
    repo = SQLiteListingImageRepository(Database(str(db_path)))
    media_service = MediaService(image_repo=repo, storage=storage)
    listing_id = uuid4()

    uploaded = media_service.upload_image(
        listing_id=listing_id,
        file_data=BytesIO(b"delete-me"),
        content_type="image/jpeg",
        filename="photo.jpg",
    )

    stored_files = list((tmp_path / "storage").iterdir())
    assert len(stored_files) == 1

    assert media_service.delete_image(uploaded.id) is True
    assert repo.get_by_id(uploaded.id) is None
    assert stored_files[0].exists()