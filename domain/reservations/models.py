from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from domain.reservations.exceptions import ReservationValidationError


class ReservationStatus(Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    COMPLETED = "COMPLETED"


@dataclass
class Reservation:
    id: UUID
    listing_id: UUID
    buyer_id: UUID
    seller_id: UUID
    status: ReservationStatus = ReservationStatus.PENDING
    expires_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.listing_id:
            raise ReservationValidationError("listing_id is required")
        if not self.buyer_id:
            raise ReservationValidationError("buyer_id is required")
        if not self.seller_id:
            raise ReservationValidationError("seller_id is required")
        if self.buyer_id == self.seller_id:
            raise ReservationValidationError("buyer_id cannot equal seller_id")

        if self.expires_at is not None:
            if self.expires_at.tzinfo is None:
                raise ReservationValidationError("expires_at must be timezone-aware UTC datetime")
            # optionally check tz is UTC
            if self.expires_at.tzinfo != UTC:
                raise ReservationValidationError("expires_at must be UTC timezone")

        for attr in ("created_at", "updated_at"):
            dt = getattr(self, attr)
            if dt.tzinfo is None:
                raise ReservationValidationError(f"{attr} must be timezone-aware UTC datetime")
            if dt.tzinfo != UTC:
                raise ReservationValidationError(f"{attr} must be UTC timezone")
