import os
import sys
from decimal import Decimal
from uuid import uuid4

# Ensure licos-core is importable when running tests from looni-commerce
LICOS_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "200_LICOS", "licos-core"))
if os.path.isdir(LICOS_ROOT) and LICOS_ROOT not in sys.path:
    sys.path.insert(0, LICOS_ROOT)

import pytest
from datetime import UTC
from domain.listings.models import ItemCondition, ListingStatus
from domain.repositories import EntityNotFoundError
from domain.reservations.models import ReservationStatus
from domain.users.models import UserStatus
from infrastructure.repositories.memory import (
    MemoryListingRepository,
    MemoryReservationRepository,
    MemoryUserRepository,
)
from kernel.events.store import EventStore
from kernel.integration.recorder import EventRecorder
from application.marketplace.service import MarketplaceService, MarketplaceWorkflowError


def make_marketplace():
    user_repo = MemoryUserRepository()
    listing_repo = MemoryListingRepository()
    reservation_repo = MemoryReservationRepository()
    store = EventStore()
    recorder = EventRecorder(store)
    service = MarketplaceService(
        user_repository=user_repo,
        listing_repository=listing_repo,
        reservation_repository=reservation_repo,
        event_recorder=recorder,
    )
    return user_repo, listing_repo, reservation_repo, store, recorder, service


def test_create_and_retrieve_user():
    user_repo, _, _, _, _, mp = make_marketplace()
    user = mp.create_user("Alice", "alice@example.com")

    saved = user_repo.get(user.id)
    assert saved.id == user.id
    assert saved.status == UserStatus.PENDING
    assert saved.email == "alice@example.com"


def test_activate_persisted_user():
    user_repo, _, _, _, _, mp = make_marketplace()
    user = mp.create_user("Alice", "alice@example.com")
    activated = mp.activate_user(user.id)

    assert activated.status == UserStatus.ACTIVE
    assert user_repo.get(user.id).status == UserStatus.ACTIVE


def test_create_and_retrieve_listing():
    user_repo, listing_repo, _, _, _, mp = make_marketplace()
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
    _, listing_repo, _, _, _, mp = make_marketplace()
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

    published = mp.publish_listing(seller.id, listing.id)

    assert published.status == ListingStatus.PUBLISHED
    assert listing_repo.get(listing.id).status == ListingStatus.PUBLISHED


def test_create_and_retrieve_reservation():
    _, listing_repo, reservation_repo, _, _, mp = make_marketplace()
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
    mp.publish_listing(seller.id, listing.id)

    reservation = mp.create_reservation(buyer.id, listing.id)
    stored = reservation_repo.get(reservation.id)

    assert stored.id == reservation.id
    assert stored.buyer_id == buyer.id
    assert stored.listing_id == listing.id
    assert stored.status == ReservationStatus.PENDING


def test_accept_updates_both_stored_reservation_and_listing():
    _, listing_repo, reservation_repo, _, _, mp = make_marketplace()
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
    mp.publish_listing(seller.id, listing.id)
    reservation = mp.create_reservation(buyer.id, listing.id)

    mp.accept_reservation(reservation.id, seller.id)

    assert reservation_repo.get(reservation.id).status == ReservationStatus.ACCEPTED
    assert listing_repo.get(listing.id).status == ListingStatus.RESERVED


def test_cancel_reservation_restores_listing_via_service():
    _, listing_repo, reservation_repo, _, _, mp = make_marketplace()
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
    mp.publish_listing(seller.id, listing.id)
    reservation = mp.create_reservation(buyer.id, listing.id)

    mp.accept_reservation(reservation.id, seller.id)
    assert reservation_repo.get(reservation.id).status == ReservationStatus.ACCEPTED
    assert listing_repo.get(listing.id).status == ListingStatus.RESERVED

    mp.cancel_reservation(reservation.id)
    assert reservation_repo.get(reservation.id).status == ReservationStatus.CANCELLED
    assert listing_repo.get(listing.id).status == ListingStatus.PUBLISHED


def test_unknown_ids_rejected():
    user_repo, listing_repo, reservation_repo, _, _, mp = make_marketplace()
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
    _, listing_repo, reservation_repo, _, _, mp = make_marketplace()
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
    store = EventStore()
    recorder = EventRecorder(store)
    mp = MarketplaceService(
        user_repository=user_repo,
        listing_repository=listing_repo,
        reservation_repository=reservation_repo,
        event_recorder=recorder,
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
    mp.publish_listing(seller.id, listing.id)
    reservation = mp.create_reservation(buyer.id, listing.id)
    mp.accept_reservation(reservation.id, seller.id)

    types = [event.event_type for event in store.all_events()]
    assert "commerce.reservation.accepted" in types
    assert "commerce.listing.reserved" in types
    assert types.index("commerce.reservation.accepted") < types.index("commerce.listing.reserved")
