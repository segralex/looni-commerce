from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from uuid import UUID, uuid4

import pytest

from application.media.service import MediaService
from domain.listings.images import ListingImage
from infrastructure.sqlite.database import Database
from infrastructure.sqlite.listing_image_repository import SQLiteListingImageRepository
from infrastructure.storage.local import LocalStorageProvider


def _make_image(listing_id, position: int = 1, image_id=None) -> ListingImage:
    return ListingImage(
        id=image_id or uuid4(),
        listing_id=listing_id,
        filename=f"photo{position}.jpg",
        content_type="image/jpeg",
        size_bytes=1000 + position,
        position=position,
        created_at=datetime.now(UTC),
    )


def test_sqlite_listing_image_repository_returns_sorted_images(tmp_path):
    repo = SQLiteListingImageRepository(Database(str(tmp_path / "images.db")))
    listing_id = uuid4()

    repo.store(_make_image(listing_id, 2), storage_key="b.jpg")
    repo.store(_make_image(listing_id, 1), storage_key="a.jpg")

    ordered = repo.get_by_listing(listing_id)
    assert [image.position for image in ordered] == [1, 2]
    assert [repo.get_storage_key(image.id) for image in ordered] == ["a.jpg", "b.jpg"]


def test_sqlite_listing_image_repository_persists_thumbnail_keys(tmp_path):
    repo = SQLiteListingImageRepository(Database(str(tmp_path / "thumbs.db")))
    listing_id = uuid4()
    image = _make_image(listing_id, 1)

    repo.store(
        image,
        storage_key="original.jpg",
        thumbnail_small_key="small.jpg",
        thumbnail_medium_key="medium.jpg",
        thumbnail_large_key="large.jpg",
    )

    hydrated = repo.get_by_id(image.id)
    assert hydrated is not None
    assert hydrated.thumbnail_small == "small.jpg"
    assert hydrated.thumbnail_medium == "medium.jpg"
    assert hydrated.thumbnail_large == "large.jpg"
    assert repo.get_thumbnail_key(image.id, "small") == "small.jpg"
    assert repo.get_thumbnail_key(image.id, "medium") == "medium.jpg"
    assert repo.get_thumbnail_key(image.id, "large") == "large.jpg"


def test_sqlite_listing_image_repository_reorder_persists_after_recreation(tmp_path):
    db_path = tmp_path / "persist-images.db"
    listing_id = uuid4()

    first_repo = SQLiteListingImageRepository(Database(str(db_path)))
    image_one = _make_image(listing_id, 1)
    image_two = _make_image(listing_id, 2)
    image_three = _make_image(listing_id, 3)
    first_repo.store(image_one, storage_key="one.jpg")
    first_repo.store(image_two, storage_key="two.jpg")
    first_repo.store(image_three, storage_key="three.jpg")

    reordered = first_repo.reorder_for_listing(listing_id, [image_three.id, image_one.id, image_two.id])
    assert [image.id for image in reordered] == [image_three.id, image_one.id, image_two.id]

    second_repo = SQLiteListingImageRepository(Database(str(db_path)))
    images = second_repo.get_by_listing(listing_id)
    assert [image.id for image in images] == [image_three.id, image_one.id, image_two.id]
    assert [image.position for image in images] == [1, 2, 3]
    assert [second_repo.get_storage_key(image.id) for image in images] == ["three.jpg", "one.jpg", "two.jpg"]


def test_sqlite_listing_image_repository_delete_compacts_positions(tmp_path):
    repo = SQLiteListingImageRepository(Database(str(tmp_path / "compact.db")))
    listing_id = uuid4()
    image_one = _make_image(listing_id, 1)
    image_two = _make_image(listing_id, 2)
    image_three = _make_image(listing_id, 3)
    repo.store(image_one, storage_key="one.jpg")
    repo.store(image_two, storage_key="two.jpg")
    repo.store(image_three, storage_key="three.jpg")

    assert repo.delete_by_id(image_two.id) is True
    ordered = repo.get_by_listing(listing_id)
    assert [image.id for image in ordered] == [image_one.id, image_three.id]
    assert [image.position for image in ordered] == [1, 2]


def test_sqlite_listing_image_repository_rows_stay_with_correct_listing(tmp_path):
    repo = SQLiteListingImageRepository(Database(str(tmp_path / "multi.db")))
    listing_a = uuid4()
    listing_b = uuid4()
    image_a1 = _make_image(listing_a, 1)
    image_a2 = _make_image(listing_a, 2)
    image_b1 = _make_image(listing_b, 1)
    repo.store(image_a1, storage_key="a1.jpg")
    repo.store(image_a2, storage_key="a2.jpg")
    repo.store(image_b1, storage_key="b1.jpg")

    repo.reorder_for_listing(listing_a, [image_a2.id, image_a1.id])

    ordered_a = repo.get_by_listing(listing_a)
    ordered_b = repo.get_by_listing(listing_b)
    assert [image.id for image in ordered_a] == [image_a2.id, image_a1.id]
    assert [image.id for image in ordered_b] == [image_b1.id]
    assert ordered_b[0].position == 1


def test_sqlite_listing_image_repository_rolls_back_failed_reorder(tmp_path, monkeypatch):
    repo = SQLiteListingImageRepository(Database(str(tmp_path / "rollback.db")))
    listing_id = uuid4()
    image_one = _make_image(listing_id, 1)
    image_two = _make_image(listing_id, 2)
    repo.store(image_one, storage_key="one.jpg")
    repo.store(image_two, storage_key="two.jpg")

    real_conn = repo.db.connect()
    call_count = {"value": 0}

    class FailingConnection:
        def __init__(self, connection):
            self._connection = connection

        def execute(self, sql, params=()):
            if "UPDATE listing_images SET position = ? WHERE id = ? AND listing_id = ?" in sql:
                call_count["value"] += 1
                if call_count["value"] == 3:
                    raise RuntimeError("boom")
            return self._connection.execute(sql, params)

        def __getattr__(self, name):
            return getattr(self._connection, name)

    monkeypatch.setattr(repo.db, "connect", lambda: FailingConnection(real_conn))

    with pytest.raises(RuntimeError):
        repo.reorder_for_listing(listing_id, [image_two.id, image_one.id])

    restored = repo.get_by_listing(listing_id)
    assert [image.id for image in restored] == [image_one.id, image_two.id]
    assert [image.position for image in restored] == [1, 2]


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
    assert second_repo.get_storage_key(uploaded.id) is not None


def test_repo_delete_removes_metadata_only_when_called_directly(tmp_path):
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

    storage_key = repo.get_storage_key(uploaded.id)
    assert storage_key is not None
    assert storage.exists(storage_key)

    assert repo.delete_by_id(uploaded.id) is True
    assert repo.get_by_id(uploaded.id) is None
    assert repo.count_by_listing(listing_id) == 0
    assert storage.exists(storage_key)


def test_media_service_delete_delegates_binary_removal_to_storage_provider(tmp_path):
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

    storage_key = repo.get_storage_key(uploaded.id)
    assert storage_key is not None
    assert storage.exists(storage_key)

    assert media_service.delete_image(uploaded.id) is True
    assert repo.get_by_id(uploaded.id) is None
    assert storage.exists(storage_key) is False


def test_sqlite_listing_image_schema_migrates_missing_position_column(tmp_path):
    db_path = tmp_path / "legacy.db"
    conn = Database(str(db_path)).connect()
    conn.execute("DROP TABLE IF EXISTS listing_images")
    conn.execute(
        """
        CREATE TABLE listing_images (
            id TEXT PRIMARY KEY,
            listing_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            content_type TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    listing_id = str(uuid4())
    created_at = datetime.now(UTC).isoformat()
    conn.execute(
        "INSERT INTO listing_images (id, listing_id, filename, content_type, size_bytes, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (str(uuid4()), listing_id, "one.jpg", "image/jpeg", 1, created_at),
    )
    conn.execute(
        "INSERT INTO listing_images (id, listing_id, filename, content_type, size_bytes, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (str(uuid4()), listing_id, "two.jpg", "image/jpeg", 2, created_at),
    )
    conn.commit()
    conn.close()

    repo = SQLiteListingImageRepository(Database(str(db_path)))
    images = repo.get_by_listing(UUID(listing_id))
    assert [image.position for image in images] == [1, 2]


def test_sqlite_listing_image_schema_migrates_thumbnail_columns(tmp_path):
    db_path = tmp_path / "legacy-thumbs.db"
    conn = Database(str(db_path)).connect()
    conn.execute("DROP TABLE IF EXISTS listing_images")
    conn.execute(
        """
        CREATE TABLE listing_images (
            id TEXT PRIMARY KEY,
            listing_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            content_type TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            position INTEGER,
            storage_key TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()

    repo = SQLiteListingImageRepository(Database(str(db_path)))
    listing_id = uuid4()
    image = _make_image(listing_id, 1)
    repo.store(
        image,
        storage_key="original.jpg",
        thumbnail_small_key="small.jpg",
        thumbnail_medium_key="medium.jpg",
        thumbnail_large_key="large.jpg",
    )

    assert repo.get_thumbnail_key(image.id, "small") == "small.jpg"
    assert repo.get_thumbnail_key(image.id, "medium") == "medium.jpg"
    assert repo.get_thumbnail_key(image.id, "large") == "large.jpg"