from datetime import UTC
from decimal import Decimal
from uuid import uuid4

import pytest

from domain.listings.models import Listing, ListingStatus, ItemCondition
from domain.listings.exceptions import ListingValidationError


def test_create_valid_listing() -> None:
    l = Listing(
        id=uuid4(),
        seller_id=uuid4(),
        title="My Item",
        description="Nice item",
        category="stuff",
        condition=ItemCondition.GOOD,
        price=Decimal("10.00"),
        currency="USD",
        location="LocalTown",
    )
    assert l.status == ListingStatus.DRAFT
    assert l.created_at.tzinfo is not None
    assert l.created_at.tzinfo == UTC


def test_negative_price_raises() -> None:
    with pytest.raises(ListingValidationError):
        Listing(
            id=uuid4(),
            seller_id=uuid4(),
            title="My Item",
            description="",
            category="stuff",
            condition=ItemCondition.GOOD,
            price=Decimal("-1.00"),
            currency="USD",
            location="LocalTown",
        )
