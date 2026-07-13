from uuid import uuid4
from datetime import UTC
from decimal import Decimal

import pytest

from application.marketplace.service import MarketplaceService, MarketplaceWorkflowError
from domain.users.service import UserService
from domain.listings.service import ListingService
from domain.reservations.service import ReservationService
from domain.listings.models import ItemCondition, ListingStatus


def setup_services():
    us = UserService()
    ls = ListingService()
    rs = ReservationService()
    mp = MarketplaceService(user_service=us, listing_service=ls, reservation_service=rs)
    return us, ls, rs, mp


def test_active_seller_creates_listing():
    us, ls, rs, mp = setup_services()
    seller = us.create_user("Seller", "s@example.com")
    us.activate(seller.id)
    listing = mp.create_listing_for_user(seller.id, "T", "D", "C", ItemCondition.GOOD, Decimal("1.00"), "USD", "L")
    assert listing.seller_id == seller.id
    assert listing.status == ListingStatus.DRAFT


def test_inactive_seller_rejected():
    us, ls, rs, mp = setup_services()
    seller = us.create_user("Seller", "s@example.com")
    with pytest.raises(MarketplaceWorkflowError):
        mp.create_listing_for_user(seller.id, "T", "D", "C", ItemCondition.GOOD, Decimal("1.00"), "USD", "L")


def test_publish_ownership_check():
    us, ls, rs, mp = setup_services()
    seller = us.create_user("Seller", "s@example.com")
    us.activate(seller.id)
    listing = ls.create_listing(seller.id, "T", "D", "C", ItemCondition.GOOD, Decimal("1.00"), "USD", "L")
    # another seller tries to publish
    other = us.create_user("Other", "o@example.com")
    us.activate(other.id)
    with pytest.raises(MarketplaceWorkflowError):
        mp.publish_listing(other.id, listing.id)


def test_active_buyer_reserves_and_seller_cannot_reserve_own():
    us, ls, rs, mp = setup_services()
    seller = us.create_user("Seller", "s@example.com")
    buyer = us.create_user("Buyer", "b@example.com")
    us.activate(seller.id); us.activate(buyer.id)
    listing = ls.create_listing(seller.id, "T", "D", "C", ItemCondition.GOOD, Decimal("1.00"), "USD", "L")
    ls.publish(listing.id)
    res = mp.create_reservation(buyer.id, listing.id)
    assert res.buyer_id == buyer.id

    with pytest.raises(MarketplaceWorkflowError):
        mp.create_reservation(seller.id, listing.id)


def test_accept_reservation_updates_both_and_rejects_second_accept():
    us, ls, rs, mp = setup_services()
    seller = us.create_user("Seller", "s@example.com")
    b1 = us.create_user("B1", "b1@example.com")
    b2 = us.create_user("B2", "b2@example.com")
    us.activate(seller.id); us.activate(b1.id); us.activate(b2.id)
    listing = ls.create_listing(seller.id, "T", "D", "C", ItemCondition.GOOD, Decimal("1.00"), "USD", "L")
    ls.publish(listing.id)
    r1 = mp.create_reservation(b1.id, listing.id)
    r2 = mp.create_reservation(b2.id, listing.id)

    mp.accept_reservation(r1.id, seller.id)
    assert rs.get_reservation(r1.id).status.name == "ACCEPTED"
    assert ls.get_listing(listing.id).status.name == "RESERVED"

    with pytest.raises(MarketplaceWorkflowError):
        mp.accept_reservation(r2.id, seller.id)

    assert rs.get_reservation(r2.id).status.name == "PENDING"


def test_failed_workflow_rolls_back_reservation():
    us, ls, rs, mp = setup_services()
    seller = us.create_user("Seller", "s@example.com")
    buyer = us.create_user("Buyer", "b@example.com")
    us.activate(seller.id); us.activate(buyer.id)
    listing = ls.create_listing(seller.id, "T", "D", "C", ItemCondition.GOOD, Decimal("1.00"), "USD", "L")
    ls.publish(listing.id)
    r = mp.create_reservation(buyer.id, listing.id)

    # simulate listing reserve failure
    original_reserve = ls.reserve

    def fail_reserve(_):
        raise Exception("boom")

    ls.reserve = fail_reserve
    try:
        with pytest.raises(MarketplaceWorkflowError):
            mp.accept_reservation(r.id, seller.id)
    finally:
        ls.reserve = original_reserve

    # reservation should be rolled back to PENDING
    assert rs.get_reservation(r.id).status.name == "PENDING"
    # listing should remain PUBLISHED
    assert ls.get_listing(listing.id).status.name == "PUBLISHED"
