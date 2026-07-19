import os
import sys
from decimal import Decimal
from uuid import uuid4
from datetime import UTC, datetime
from pathlib import Path

# Ensure licos-core is importable when running tests from looni-commerce
LICOS_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "200_LICOS", "licos-core"))
if os.path.isdir(LICOS_ROOT) and LICOS_ROOT not in sys.path:
    sys.path.insert(0, LICOS_ROOT)

import pytest
from domain.listings.models import ItemCondition, ListingStatus
from domain.repositories import EntityNotFoundError
from domain.reservations.models import ReservationStatus
from domain.users.models import UserStatus
from domain.listings.images import ListingImage
from domain.media.processing import ImageProcessingStatus
from infrastructure.repositories.memory import (
    MemoryListingRepository,
    MemoryReservationRepository,
    MemoryUserRepository,
    MemoryListingImageRepository,
)
from infrastructure.storage.local import LocalStorageProvider
from kernel.events.store import EventStore
from kernel.integration.recorder import EventRecorder
from application.marketplace.service import MarketplaceService, MarketplaceWorkflowError
from application.media.service import MediaService


def make_marketplace():
    user_repo = MemoryUserRepository()
    listing_repo = MemoryListingRepository()
    reservation_repo = MemoryReservationRepository()
    image_repo = MemoryListingImageRepository()
    storage = LocalStorageProvider(Path("data/test_storage"))
    media_service = MediaService(image_repo=image_repo, storage=storage)
    store = EventStore()
    recorder = EventRecorder(store)
    service = MarketplaceService(
        user_repository=user_repo,
        listing_repository=listing_repo,
        reservation_repository=reservation_repo,
        event_recorder=recorder,
        media_service=media_service,
    )
    return user_repo, listing_repo, reservation_repo, image_repo, store, recorder, service, media_service


def _make_ready_image(listing_id, position: int) -> ListingImage:
    return ListingImage(
        id=uuid4(),
        listing_id=listing_id,
        filename=f"test{position}.jpg",
        content_type="image/jpeg",
        size_bytes=1000,
        position=position,
        created_at=UTC.localize(datetime.utcnow()) if hasattr(UTC, 'localize') else datetime.now(UTC),
        thumbnail_small=f"small-{position}.jpg",
        thumbnail_medium=f"medium-{position}.jpg",
        thumbnail_large=f"large-{position}.jpg",
        processing_status=ImageProcessingStatus.READY,
        processing_error=None,
        processing_attempts=1,
    )


def test_create_and_retrieve_user():
    user_repo, _, _, _, _, _, mp, _ = make_marketplace()
    user = mp.create_user("Alice", "alice@example.com")

    saved = user_repo.get(user.id)
    assert saved.id == user.id
    assert saved.status == UserStatus.PENDING
    assert saved.email == "alice@example.com"


def test_activate_persisted_user():
    user_repo, _, _, _, _, _, mp, _ = make_marketplace()
    user = mp.create_user("Alice", "alice@example.com")
    activated = mp.activate_user(user.id)

    assert activated.status == UserStatus.ACTIVE
    assert user_repo.get(user.id).status == UserStatus.ACTIVE


def test_create_and_retrieve_listing():
    user_repo, listing_repo, _, _, _, _, mp, _ = make_marketplace()
    seller = mp.create_user("Seller", "seller@example.com")
    mp.activate_user(seller.id)

    listing = mp.create_listing_for_user(
        seller.id,
        "Book",
        "A book",
        "Books",
        ItemCondition.GOOD,
        Decimal("12.50"),
        "USD",
        "Online",
    )

    stored = listing_repo.get(listing.id)
    assert listing.id == stored.id
    assert stored.seller_id == seller.id
    assert stored.status == ListingStatus.DRAFT


def test_publish_persisted_listing():
    _, listing_repo, _, image_repo, _, _, mp, _ = make_marketplace()
    seller = mp.create_user("Seller", "seller@example.com")
    mp.activate_user(seller.id)
    listing = mp.create_listing_for_user(
        seller.id,
        "Book",
        "A book",
        "Books",
        ItemCondition.GOOD,
        Decimal("12.50"),
        "USD",
        "Online",
    )

    # Add 2 images to allow publishing
    for i in range(2):
        image_repo.store(_make_ready_image(listing.id, i + 1))

    published = mp.publish_listing(seller.id, listing.id)

    assert published.status == ListingStatus.PUBLISHED
    assert listing_repo.get(listing.id).status == ListingStatus.PUBLISHED


def test_create_and_retrieve_reservation():
    _, listing_repo, reservation_repo, image_repo, _, _, mp, _ = make_marketplace()
    seller = mp.create_user("Seller", "seller@example.com")
    buyer = mp.create_user("Buyer", "buyer@example.com")
    mp.activate_user(seller.id)
    mp.activate_user(buyer.id)

    listing = mp.create_listing_for_user(
        seller.id,
        "Book",
        "A book",
        "Books",
        ItemCondition.GOOD,
        Decimal("12.50"),
        "USD",
        "Online",
    )
    
    # Add 2 images to allow publishing
    for i in range(2):
        image_repo.store(_make_ready_image(listing.id, i + 1))
    
    mp.publish_listing(seller.id, listing.id)

    reservation = mp.create_reservation(buyer.id, listing.id)
    stored = reservation_repo.get(reservation.id)

    assert stored.id == reservation.id
    assert stored.buyer_id == buyer.id
    assert stored.listing_id == listing.id
    assert stored.status == ReservationStatus.PENDING


def test_accept_updates_both_stored_reservation_and_listing():
    _, listing_repo, reservation_repo, image_repo, _, _, mp, _ = make_marketplace()
    seller = mp.create_user("Seller", "seller@example.com")
    buyer = mp.create_user("Buyer", "buyer@example.com")
    mp.activate_user(seller.id)
    mp.activate_user(buyer.id)

    listing = mp.create_listing_for_user(
        seller.id,
        "Book",
        "A book",
        "Books",
        ItemCondition.GOOD,
        Decimal("12.50"),
        "USD",
        "Online",
    )
    
    # Add 2 images to allow publishing
    for i in range(2):
        image_repo.store(_make_ready_image(listing.id, i + 1))
    
    mp.publish_listing(seller.id, listing.id)
    reservation = mp.create_reservation(buyer.id, listing.id)

    mp.accept_reservation(reservation.id, seller.id)

    assert reservation_repo.get(reservation.id).status == ReservationStatus.ACCEPTED
    assert listing_repo.get(listing.id).status == ListingStatus.RESERVED


def test_cancel_reservation_restores_listing_via_service():
    _, listing_repo, reservation_repo, image_repo, _, _, mp, _ = make_marketplace()
    seller = mp.create_user("Seller", "seller@example.com")
    buyer = mp.create_user("Buyer", "buyer@example.com")
    mp.activate_user(seller.id)
    mp.activate_user(buyer.id)

    listing = mp.create_listing_for_user(
        seller.id,
        "Book",
        "A book",
        "Books",
        ItemCondition.GOOD,
        Decimal("12.50"),
        "USD",
        "Online",
    )
    
    # Add 2 images to allow publishing
    for i in range(2):
            image_repo.store(_make_ready_image(listing.id, i + 1))
    
    mp.publish_listing(seller.id, listing.id)
    reservation = mp.create_reservation(buyer.id, listing.id)

    mp.accept_reservation(reservation.id, seller.id)
    assert reservation_repo.get(reservation.id).status == ReservationStatus.ACCEPTED
    assert listing_repo.get(listing.id).status == ListingStatus.RESERVED

    mp.cancel_reservation(reservation.id)
    assert reservation_repo.get(reservation.id).status == ReservationStatus.CANCELLED
    assert listing_repo.get(listing.id).status == ListingStatus.PUBLISHED


def test_unknown_ids_rejected():
    user_repo, listing_repo, reservation_repo, _, _, _, mp, _ = make_marketplace()
    seller = mp.create_user("Seller", "seller@example.com")
    mp.activate_user(seller.id)

    with pytest.raises(MarketplaceWorkflowError):
        mp.activate_user(uuid4())

    with pytest.raises(MarketplaceWorkflowError):
        mp.create_listing_for_user(uuid4(), "Book", "A book", "Books", ItemCondition.GOOD, Decimal("12.50"), "USD", "Online")

    with pytest.raises(MarketplaceWorkflowError):
        mp.publish_listing(seller.id, uuid4())

    buyer = mp.create_user("Buyer", "buyer@example.com")
    mp.activate_user(buyer.id)
    with pytest.raises(MarketplaceWorkflowError):
        mp.create_reservation(buyer.id, uuid4())

    with pytest.raises(MarketplaceWorkflowError):
        mp.accept_reservation(uuid4(), seller.id)

    # ensure repository state has not been altered by failed workflows
    assert [user.id for user in user_repo.all()] == [seller.id, buyer.id]
    assert listing_repo.all() == ()
    assert reservation_repo.all() == ()


def test_failed_workflow_preserves_repository_state():
    _, listing_repo, reservation_repo, image_repo, _, _, mp, _ = make_marketplace()
    seller = mp.create_user("Seller", "seller@example.com")
    buyer = mp.create_user("Buyer", "buyer@example.com")
    mp.activate_user(seller.id)
    mp.activate_user(buyer.id)

    listing = mp.create_listing_for_user(
        seller.id,
        "Book",
        "A book",
        "Books",
        ItemCondition.GOOD,
        Decimal("12.50"),
        "USD",
        "Online",
    )
    
    # Add 2 images to allow publishing
    for i in range(2):
            image_repo.store(_make_ready_image(listing.id, i + 1))
    
    mp.publish_listing(seller.id, listing.id)
    reservation = mp.create_reservation(buyer.id, listing.id)

    original_save = listing_repo.save

    def fail_save(_):
        raise Exception("boom")

    listing_repo.save = fail_save
    try:
        with pytest.raises(MarketplaceWorkflowError):
            mp.accept_reservation(reservation.id, seller.id)
    finally:
        listing_repo.save = original_save

    assert reservation_repo.get(reservation.id).status == ReservationStatus.PENDING
    assert listing_repo.get(listing.id).status == ListingStatus.PUBLISHED


def test_licos_events_still_emitted_in_correct_order():
    user_repo = MemoryUserRepository()
    listing_repo = MemoryListingRepository()
    reservation_repo = MemoryReservationRepository()
    image_repo = MemoryListingImageRepository()
    storage = LocalStorageProvider(Path("data/test_storage"))
    media_service = MediaService(image_repo=image_repo, storage=storage)
    store = EventStore()
    recorder = EventRecorder(store)
    mp = MarketplaceService(
        user_repository=user_repo,
        listing_repository=listing_repo,
        reservation_repository=reservation_repo,
        event_recorder=recorder,
        media_service=media_service,
    )

    seller = mp.create_user("Seller", "seller@example.com")
    buyer = mp.create_user("Buyer", "buyer@example.com")
    mp.activate_user(seller.id)
    mp.activate_user(buyer.id)

    listing = mp.create_listing_for_user(
        seller.id,
        "Book",
        "A book",
        "Books",
        ItemCondition.GOOD,
        Decimal("12.50"),
        "USD",
        "Online",
    )
    
    # Add 2 images to allow publishing
    for i in range(2):
        image_repo.store(_make_ready_image(listing.id, i + 1))
    
    mp.publish_listing(seller.id, listing.id)
    reservation = mp.create_reservation(buyer.id, listing.id)
    mp.accept_reservation(reservation.id, seller.id)

    types = [event.event_type for event in store.all_events()]
    assert "commerce.reservation.accepted" in types
    assert "commerce.listing.reserved" in types
    assert types.index("commerce.reservation.accepted") < types.index("commerce.listing.reserved")


def test_publish_listing_fails_with_zero_images():
    """Verify that publishing fails when listing has no images."""
    _, listing_repo, _, _, _, _, mp, _ = make_marketplace()
    seller = mp.create_user("Seller", "seller@example.com")
    mp.activate_user(seller.id)
    
    listing = mp.create_listing_for_user(
        seller.id,
        "Book",
        "A book",
        "Books",
        ItemCondition.GOOD,
        Decimal("12.50"),
        "USD",
        "Online",
    )
    
    # Attempt to publish without adding any images
    with pytest.raises(MarketplaceWorkflowError) as exc_info:
        mp.publish_listing(seller.id, listing.id)
    
    assert "successfully processed images" in str(exc_info.value)
    
    # Verify listing state unchanged
    assert listing_repo.get(listing.id).status == ListingStatus.DRAFT


def test_publish_listing_fails_with_one_image():
    """Verify that publishing fails when listing has only 1 image."""
    _, listing_repo, _, image_repo, _, _, mp, _ = make_marketplace()
    seller = mp.create_user("Seller", "seller@example.com")
    mp.activate_user(seller.id)
    
    listing = mp.create_listing_for_user(
        seller.id,
        "Book",
        "A book",
        "Books",
        ItemCondition.GOOD,
        Decimal("12.50"),
        "USD",
        "Online",
    )
    
    # Add only 1 image
    image_repo.store(_make_ready_image(listing.id, 1))
    
    # Attempt to publish with only 1 image
    with pytest.raises(MarketplaceWorkflowError) as exc_info:
        mp.publish_listing(seller.id, listing.id)
    
    assert "successfully processed images" in str(exc_info.value)
    
    # Verify listing state unchanged
    assert listing_repo.get(listing.id).status == ListingStatus.DRAFT


def test_publish_listing_succeeds_with_exactly_two_images():
    """Verify that publishing succeeds when listing has exactly 2 images."""
    _, listing_repo, _, image_repo, _, _, mp, _ = make_marketplace()
    seller = mp.create_user("Seller", "seller@example.com")
    mp.activate_user(seller.id)
    
    listing = mp.create_listing_for_user(
        seller.id,
        "Book",
        "A book",
        "Books",
        ItemCondition.GOOD,
        Decimal("12.50"),
        "USD",
        "Online",
    )
    
    # Add exactly 2 images
    for i in range(2):
        image_repo.store(_make_ready_image(listing.id, i + 1))
    
    # Publish should succeed
    published = mp.publish_listing(seller.id, listing.id)
    
    assert published.status == ListingStatus.PUBLISHED
    assert listing_repo.get(listing.id).status == ListingStatus.PUBLISHED


def test_publish_listing_succeeds_with_ten_images():
    """Verify that publishing succeeds when listing has 10 images."""
    _, listing_repo, _, image_repo, _, _, mp, _ = make_marketplace()
    seller = mp.create_user("Seller", "seller@example.com")
    mp.activate_user(seller.id)
    
    listing = mp.create_listing_for_user(
        seller.id,
        "Book",
        "A book",
        "Books",
        ItemCondition.GOOD,
        Decimal("12.50"),
        "USD",
        "Online",
    )
    
    # Add 10 images
    for i in range(10):
        image_repo.store(_make_ready_image(listing.id, i + 1))
    
    # Publish should succeed
    published = mp.publish_listing(seller.id, listing.id)
    
    assert published.status == ListingStatus.PUBLISHED
    assert listing_repo.get(listing.id).status == ListingStatus.PUBLISHED


def test_failed_publish_does_not_emit_event():
    """Verify that failed publication due to insufficient images does not emit events."""
    user_repo = MemoryUserRepository()
    listing_repo = MemoryListingRepository()
    reservation_repo = MemoryReservationRepository()
    image_repo = MemoryListingImageRepository()
    storage = LocalStorageProvider(Path("data/test_storage"))
    media_service = MediaService(image_repo=image_repo, storage=storage)
    store = EventStore()
    recorder = EventRecorder(store)
    mp = MarketplaceService(
        user_repository=user_repo,
        listing_repository=listing_repo,
        reservation_repository=reservation_repo,
        event_recorder=recorder,
        media_service=media_service,
    )
    
    seller = mp.create_user("Seller", "seller@example.com")
    mp.activate_user(seller.id)
    
    listing = mp.create_listing_for_user(
        seller.id,
        "Book",
        "A book",
        "Books",
        ItemCondition.GOOD,
        Decimal("12.50"),
        "USD",
        "Online",
    )
    
    # Get event count before failed publish attempt
    initial_events = len(store.all_events())
    
    # Try to publish without images
    with pytest.raises(MarketplaceWorkflowError):
        mp.publish_listing(seller.id, listing.id)
    
    # Verify no publish event was emitted
    final_events = len(store.all_events())
    assert final_events == initial_events
    
    # Verify no commerce.listing.published event exists
    all_types = [event.event_type for event in store.all_events()]
    assert "commerce.listing.published" not in all_types
