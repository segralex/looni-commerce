from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from domain.listings.images import ListingImage
from infrastructure.repositories.memory import MemoryListingImageRepository


def _make_image(listing_id, position: int, image_id=None) -> ListingImage:
    return ListingImage(
        id=image_id or uuid4(),
        listing_id=listing_id,
        filename=f"photo{position}.jpg",
        content_type="image/jpeg",
        size_bytes=1000,
        position=position,
        created_at=datetime.now(UTC),
    )


def test_memory_repository_returns_images_sorted_by_position():
    repo = MemoryListingImageRepository()
    listing_id = uuid4()
    repo.store(_make_image(listing_id, 2), storage_key="two.jpg")
    repo.store(_make_image(listing_id, 1), storage_key="one.jpg")

    images = repo.get_by_listing(listing_id)
    assert [image.position for image in images] == [1, 2]


def test_memory_repository_reorder_persists_for_repository_lifetime():
    repo = MemoryListingImageRepository()
    listing_id = uuid4()
    image_one = _make_image(listing_id, 1)
    image_two = _make_image(listing_id, 2)
    image_three = _make_image(listing_id, 3)
    repo.store(image_one, storage_key="one.jpg")
    repo.store(image_two, storage_key="two.jpg")
    repo.store(image_three, storage_key="three.jpg")

    reordered = repo.reorder_for_listing(listing_id, [image_three.id, image_one.id, image_two.id])

    assert [image.id for image in reordered] == [image_three.id, image_one.id, image_two.id]
    assert [image.position for image in reordered] == [1, 2, 3]
    assert [repo.get_storage_key(image.id) for image in reordered] == ["three.jpg", "one.jpg", "two.jpg"]


def test_memory_repository_persists_thumbnail_keys():
    repo = MemoryListingImageRepository()
    listing_id = uuid4()
    image = _make_image(listing_id, 1)

    repo.store(
        image,
        storage_key="original.jpg",
        thumbnail_small_key="small.jpg",
        thumbnail_medium_key="medium.jpg",
        thumbnail_large_key="large.jpg",
    )

    assert repo.get_storage_key(image.id) == "original.jpg"
    assert repo.get_thumbnail_key(image.id, "small") == "small.jpg"
    assert repo.get_thumbnail_key(image.id, "medium") == "medium.jpg"
    assert repo.get_thumbnail_key(image.id, "large") == "large.jpg"


def test_memory_repository_delete_compacts_positions():
    repo = MemoryListingImageRepository()
    listing_id = uuid4()
    image_one = _make_image(listing_id, 1)
    image_two = _make_image(listing_id, 2)
    image_three = _make_image(listing_id, 3)
    repo.store(image_one, storage_key="one.jpg")
    repo.store(image_two, storage_key="two.jpg")
    repo.store(image_three, storage_key="three.jpg")

    assert repo.delete_by_id(image_two.id) is True
    images = repo.get_by_listing(listing_id)
    assert [image.id for image in images] == [image_one.id, image_three.id]
    assert [image.position for image in images] == [1, 2]


def test_memory_repository_delete_primary_promotes_next_image():
    repo = MemoryListingImageRepository()
    listing_id = uuid4()
    image_one = _make_image(listing_id, 1)
    image_two = _make_image(listing_id, 2)
    repo.store(image_one, storage_key="one.jpg")
    repo.store(image_two, storage_key="two.jpg")

    repo.delete_by_id(image_one.id)
    images = repo.get_by_listing(listing_id)
    assert len(images) == 1
    assert images[0].id == image_two.id
    assert images[0].position == 1


def test_memory_repository_rejects_duplicate_missing_extra_or_unknown_ids():
    repo = MemoryListingImageRepository()
    listing_id = uuid4()
    image_one = _make_image(listing_id, 1)
    image_two = _make_image(listing_id, 2)
    repo.store(image_one, storage_key="one.jpg")
    repo.store(image_two, storage_key="two.jpg")

    with pytest.raises(ValueError):
        repo.reorder_for_listing(listing_id, [image_one.id, image_one.id])

    with pytest.raises(ValueError):
        repo.reorder_for_listing(listing_id, [image_one.id])

    with pytest.raises(ValueError):
        repo.reorder_for_listing(listing_id, [image_one.id, image_two.id, uuid4()])

    other_listing_image = _make_image(uuid4(), 1)
    repo.store(other_listing_image, storage_key="other.jpg")
    with pytest.raises(ValueError):
        repo.reorder_for_listing(listing_id, [image_one.id, other_listing_image.id])