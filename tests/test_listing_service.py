from datetime import UTC
from decimal import Decimal
from uuid import uuid4

import pytest

from domain.listings.exceptions import InvalidListingStateError
from domain.listings.models import ItemCondition, ListingStatus
from domain.listings.service import ListingService


def test_service_create_and_transitions() -> None:
    svc = ListingService()
    seller = uuid4()
    listing = svc.create_listing(
        seller,
        "Title",
        "Desc",
        "Cat",
        ItemCondition.NEW,
        Decimal("5.00"),
        "USD",
        "Loc",
    )

    assert listing.status == ListingStatus.DRAFT

    svc.publish(listing.id)
    assert svc.get_listing(listing.id).status == ListingStatus.PUBLISHED

    svc.reserve(listing.id)
    assert svc.get_listing(listing.id).status == ListingStatus.RESERVED

    svc.mark_sold(listing.id)
    assert svc.get_listing(listing.id).status == ListingStatus.SOLD

    svc.archive(listing.id)
    assert svc.get_listing(listing.id).status == ListingStatus.ARCHIVED

    with pytest.raises(InvalidListingStateError):
        svc.publish(listing.id)


def test_invalid_transitions_raise() -> None:
    svc = ListingService()
    seller = uuid4()
    l = svc.create_listing(seller, "T", "", "C", ItemCondition.GOOD, Decimal("1.00"), "USD", "L")

    with pytest.raises(InvalidListingStateError):
        svc.reserve(l.id)

    with pytest.raises(InvalidListingStateError):
        svc.mark_sold(l.id)

    svc.publish(l.id)
    with pytest.raises(InvalidListingStateError):
        svc.mark_sold(l.id)


def test_update_listing_changes_updated_at_and_forbids_archived_changes() -> None:
    svc = ListingService()
    seller = uuid4()
    l = svc.create_listing(seller, "T", "D", "C", ItemCondition.GOOD, Decimal("1.00"), "USD", "L")
    before = svc.get_listing(l.id).updated_at
    updated = svc.update_listing(l.id, title="New")
    assert updated.title == "New"
    assert updated.updated_at.tzinfo == UTC
    assert updated.updated_at >= before

    svc.archive(l.id)
    with pytest.raises(InvalidListingStateError):
        svc.update_listing(l.id, title="Another")
