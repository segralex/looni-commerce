from __future__ import annotations

from copy import deepcopy
from datetime import datetime, UTC
from decimal import Decimal
from typing import Dict, Optional
from uuid import UUID, uuid4

from .exceptions import InvalidListingStateError, ListingValidationError
from .models import ItemCondition, Listing, ListingStatus


class ListingService:
    def __init__(self) -> None:
        self._store: Dict[UUID, Listing] = {}

    def create_listing(
        self,
        seller_id: UUID,
        title: str,
        description: str,
        category: str,
        condition: ItemCondition,
        price: Decimal,
        currency: str,
        location: str,
    ) -> Listing:
        # Ensure Decimal
        if not isinstance(price, Decimal):
            try:
                price = Decimal(price)
            except Exception:
                raise ListingValidationError("price must be a Decimal")

        listing = Listing(
            id=uuid4(),
            seller_id=seller_id,
            title=title,
            description=description or "",
            category=category,
            condition=condition,
            price=price,
            currency=currency,
            location=location,
        )
        self._store[listing.id] = listing
        return deepcopy(listing)

    def get_listing(self, listing_id: UUID) -> Listing:
        return deepcopy(self._store[listing_id])

    def update_listing(self, listing_id: UUID, **fields) -> Listing:
        listing = self._store.get(listing_id)
        if listing is None:
            raise KeyError(listing_id)
        if listing.status == ListingStatus.ARCHIVED:
            raise InvalidListingStateError("ARCHIVED listings cannot be modified")

        # Allowed updates
        allowed = {"title", "description", "category", "condition", "price", "currency", "location"}
        for k, v in fields.items():
            if k not in allowed:
                continue
            if k == "price":
                if not isinstance(v, Decimal):
                    try:
                        v = Decimal(v)
                    except Exception:
                        raise ListingValidationError("price must be a Decimal")
                if v < Decimal("0"):
                    raise ListingValidationError("price cannot be negative")
            setattr(listing, k, v)

        listing.updated_at = datetime.now(UTC)
        self._store[listing.id] = listing
        return deepcopy(listing)

    def publish(self, listing_id: UUID) -> Listing:
        listing = self._store.get(listing_id)
        if listing is None:
            raise KeyError(listing_id)
        if listing.status != ListingStatus.DRAFT:
            raise InvalidListingStateError("Can only publish listings in DRAFT")
        listing.status = ListingStatus.PUBLISHED
        listing.updated_at = datetime.now(UTC)
        self._store[listing.id] = listing
        return deepcopy(listing)

    def reserve(self, listing_id: UUID) -> Listing:
        listing = self._store.get(listing_id)
        if listing is None:
            raise KeyError(listing_id)
        if listing.status != ListingStatus.PUBLISHED:
            raise InvalidListingStateError("Can only reserve listings in PUBLISHED")
        listing.status = ListingStatus.RESERVED
        listing.updated_at = datetime.now(UTC)
        self._store[listing.id] = listing
        return deepcopy(listing)

    def mark_sold(self, listing_id: UUID) -> Listing:
        listing = self._store.get(listing_id)
        if listing is None:
            raise KeyError(listing_id)
        if listing.status != ListingStatus.RESERVED:
            raise InvalidListingStateError("Can only mark SOLD listings in RESERVED")
        listing.status = ListingStatus.SOLD
        listing.updated_at = datetime.now(UTC)
        self._store[listing.id] = listing
        return deepcopy(listing)

    def archive(self, listing_id: UUID) -> Listing:
        listing = self._store.get(listing_id)
        if listing is None:
            raise KeyError(listing_id)
        if listing.status == ListingStatus.ARCHIVED:
            raise InvalidListingStateError("Listing is already ARCHIVED")
        listing.status = ListingStatus.ARCHIVED
        listing.updated_at = datetime.now(UTC)
        self._store[listing.id] = listing
        return deepcopy(listing)
