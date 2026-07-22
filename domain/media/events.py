"""Media integration events."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar
from uuid import uuid4

from domain.events.context import get_causation_id, get_correlation_id
from domain.events.base import DomainEvent
from domain.events.serialization import register_event_class


@dataclass(frozen=True, slots=True)
class ImageUploaded(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "ImageUploaded"

    image_id: str
    listing_id: str
    original_storage_key: str

    @classmethod
    def create(
        cls,
        image_id: str,
        listing_id: str,
        original_storage_key: str,
        occurred_at: datetime,
        correlation_id: str | None = None,
        causation_id: str | None = None,
    ) -> "ImageUploaded":
        return cls(
            event_id=str(uuid4()),
            event_type=cls.EVENT_TYPE,
            aggregate_type="ListingImage",
            aggregate_id=image_id,
            correlation_id=correlation_id if correlation_id is not None else get_correlation_id(),
            causation_id=causation_id if causation_id is not None else get_causation_id(),
            schema_version=1,
            occurred_at=occurred_at,
            image_id=image_id,
            listing_id=listing_id,
            original_storage_key=original_storage_key,
        )


register_event_class(ImageUploaded.EVENT_TYPE, ImageUploaded)
