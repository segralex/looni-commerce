from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from domain.events.base import DomainEvent
from domain.events.registry import EventRegistry
from domain.events.serialization import deserialize_event, serialize_event
from domain.media.events import ImageUploaded


def test_domain_event_is_immutable() -> None:
    event = DomainEvent(
        event_id="evt-1",
        event_type="DemoEvent",
        aggregate_type="Demo",
        aggregate_id="agg-1",
        occurred_at=datetime.now(UTC),
    )

    with pytest.raises(FrozenInstanceError):
        event.event_type = "OtherEvent"  # type: ignore[misc]


def test_image_uploaded_inherits_domain_event() -> None:
    event = ImageUploaded.create(
        image_id="image-1",
        listing_id="listing-1",
        original_storage_key="media/original.jpg",
        occurred_at=datetime.now(UTC),
    )

    assert isinstance(event, DomainEvent)
    assert event.event_type == "ImageUploaded"
    assert event.aggregate_type == "ListingImage"
    assert event.aggregate_id == "image-1"


def test_event_serialization_roundtrip_preserves_payload_and_metadata() -> None:
    occurred_at = datetime.now(UTC)
    event = ImageUploaded.create(
        image_id="image-2",
        listing_id="listing-2",
        original_storage_key="media/source.jpg",
        occurred_at=occurred_at,
    )

    serialized = serialize_event(event)
    deserialized = deserialize_event(serialized)

    assert serialized["event_id"] == event.event_id
    assert serialized["occurred_at"] == occurred_at.isoformat()
    assert serialized["payload"]["image_id"] == "image-2"

    assert isinstance(deserialized, ImageUploaded)
    assert deserialized == event


def test_event_registry_supports_multiple_handlers_and_rejects_duplicates() -> None:
    registry = EventRegistry()

    def handler_one(_event: object) -> None:
        return

    def handler_two(_event: object) -> None:
        return

    registry.register("ImageUploaded", handler_one)
    registry.register("ImageUploaded", handler_two)

    handlers = registry.handlers_for("ImageUploaded")
    assert handlers == (handler_one, handler_two)

    with pytest.raises(ValueError):
        registry.register("ImageUploaded", handler_one)
