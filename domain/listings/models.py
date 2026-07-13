from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID

from .exceptions import ListingValidationError


class ListingStatus(Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    RESERVED = "RESERVED"
    SOLD = "SOLD"
    ARCHIVED = "ARCHIVED"


class ItemCondition(Enum):
    NEW = "NEW"
    LIKE_NEW = "LIKE_NEW"
    GOOD = "GOOD"
    FAIR = "FAIR"
    POOR = "POOR"


@dataclass
class Listing:
    id: UUID
    seller_id: UUID
    title: str
    description: str
    category: str
    condition: ItemCondition
    price: Decimal
    currency: str
    location: str
    status: ListingStatus = ListingStatus.DRAFT
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        # Required fields
        if not self.title:
            raise ListingValidationError("title is required")
        if not self.seller_id:
            raise ListingValidationError("seller_id is required")
        if not self.category:
            raise ListingValidationError("category is required")
        if not self.currency:
            raise ListingValidationError("currency is required")
        if not self.location:
            raise ListingValidationError("location is required")

        # Price must be a Decimal and non-negative
        if not isinstance(self.price, Decimal):
            try:
                self.price = Decimal(self.price)
            except Exception:
                raise ListingValidationError("price must be a Decimal")
        if self.price < Decimal("0"):
            raise ListingValidationError("price cannot be negative")

        # Timestamps must be timezone-aware UTC
        for attr in ("created_at", "updated_at"):
            dt = getattr(self, attr)
            if dt.tzinfo is None:
                raise ListingValidationError(f"{attr} must be timezone-aware UTC datetime")
            if dt.tzinfo != UTC:
                raise ListingValidationError(f"{attr} must be UTC timezone")
