from __future__ import annotations

from datetime import UTC, datetime

from domain.media.events import ImageUploaded


def test_image_uploaded_event_is_immutable_and_serializable():
    occurred_at = datetime.now(UTC)
    event = ImageUploaded.create(
        image_id="image-1",
        listing_id="listing-1",
        original_storage_key="abc123.jpg",
        occurred_at=occurred_at,
    )

    assert event.image_id == "image-1"
    assert event.listing_id == "listing-1"
    assert event.original_storage_key == "abc123.jpg"
    assert event.occurred_at == occurred_at
    assert event.event_id
    assert "C:\\" not in event.original_storage_key

    try:
        event.image_id = "mutated"  # type: ignore[misc]
        raised = False
    except Exception:
        raised = True
    assert raised
