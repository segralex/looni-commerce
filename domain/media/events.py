"""Media integration events."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class ImageUploaded:
    event_id: str
    image_id: str
    listing_id: str
    original_storage_key: str
    occurred_at: datetime

    @classmethod
    def create(
        cls,
        image_id: str,
        listing_id: str,
        original_storage_key: str,
        occurred_at: datetime,
    ) -> "ImageUploaded":
        return cls(
            event_id=str(uuid4()),
            image_id=image_id,
            listing_id=listing_id,
            original_storage_key=original_storage_key,
            occurred_at=occurred_at,
        )
