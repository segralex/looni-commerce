from __future__ import annotations

from dataclasses import replace
from collections.abc import Mapping
from datetime import UTC, datetime
import threading
from typing import Any
from uuid import UUID

from domain.events.outbox import OutboxEntry, OutboxState
from domain.events.metrics import EventMetrics
from domain.events.serialization import deserialize_event, serialize_event
from domain.repositories import (
    DuplicateEntityError,
    EntityNotFoundError,
    ListingRepository,
    ReservationRepository,
    UserRepository,
)
from domain.listings.images import ListingImage
from domain.listings.repositories import ListingImageRepository
from domain.media.processing import ImageProcessingStatus, infer_processing_status
from domain.trust.aggregate import TrustAggregate


class _MemoryRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, Any] = {}
        self._order: list[UUID] = []

    def _add(self, entity: Any) -> None:
        entity_id = getattr(entity, "id")
        if entity_id in self._store:
            raise DuplicateEntityError("Duplicate entity id")
        self._store[entity_id] = entity
        self._order.append(entity_id)

    def _get(self, entity_id: UUID) -> Any:
        try:
            return self._store[entity_id]
        except KeyError as exc:
            raise EntityNotFoundError("Entity not found") from exc

    def _save(self, entity: Any) -> None:
        entity_id = getattr(entity, "id")
        if entity_id not in self._store:
            raise EntityNotFoundError("Unknown entity id")
        self._store[entity_id] = entity

    def _all(self) -> tuple[Any, ...]:
        return tuple(self._store[entity_id] for entity_id in self._order)


class MemoryUserRepository(_MemoryRepository, UserRepository):
    def add(self, entity: Any) -> None:
        self._add(entity)

    def get(self, entity_id: UUID) -> Any:
        return self._get(entity_id)

    def save(self, entity: Any) -> None:
        self._save(entity)

    def all(self) -> tuple[Any, ...]:
        return self._all()


class MemoryListingRepository(_MemoryRepository, ListingRepository):
    def add(self, entity: Any) -> None:
        self._add(entity)

    def get(self, entity_id: UUID) -> Any:
        return self._get(entity_id)

    def save(self, entity: Any) -> None:
        self._save(entity)

    def all(self) -> tuple[Any, ...]:
        return self._all()


class MemoryReservationRepository(_MemoryRepository, ReservationRepository):
    def add(self, entity: Any) -> None:
        self._add(entity)

    def get(self, entity_id: UUID) -> Any:
        return self._get(entity_id)

    def save(self, entity: Any) -> None:
        self._save(entity)

    def all(self) -> tuple[Any, ...]:
        return self._all()


class MemoryTrustRepository:
    def __init__(self) -> None:
        self._profiles: dict[str, TrustAggregate] = {}
        self._lock = threading.RLock()

    def get(self, user_id: str) -> TrustAggregate | None:
        with self._lock:
            profile = self._profiles.get(str(user_id))
            return replace(profile) if profile is not None else None

    def save(self, aggregate: TrustAggregate) -> None:
        with self._lock:
            self._profiles[str(aggregate.user_id)] = replace(aggregate)

    def all(self) -> tuple[TrustAggregate, ...]:
        with self._lock:
            return tuple(replace(profile) for profile in self._profiles.values())


class MemoryListingImageRepository(ListingImageRepository):
    """In-memory implementation of ListingImageRepository."""
    
    def __init__(self) -> None:
        self._store: dict[UUID, ListingImage] = {}
        self._storage_keys: dict[UUID, str | None] = {}
        self._thumbnail_small_keys: dict[UUID, str | None] = {}
        self._thumbnail_medium_keys: dict[UUID, str | None] = {}
        self._thumbnail_large_keys: dict[UUID, str | None] = {}
        self._lock = threading.Lock()

    def _ordered_images(self, listing_id: UUID) -> list[ListingImage]:
        images = [image for image in self._store.values() if image.listing_id == listing_id]
        return sorted(images, key=lambda image: (image.position, image.created_at, str(image.id)))

    def _compact_listing(self, listing_id: UUID) -> list[ListingImage]:
        ordered = self._ordered_images(listing_id)
        compacted: list[ListingImage] = []
        for index, image in enumerate(ordered, start=1):
            normalized = replace(image, position=index)
            self._store[image.id] = normalized
            compacted.append(normalized)
        return compacted
    
    def store(
        self,
        image: ListingImage,
        storage_key: str | None = None,
        thumbnail_small_key: str | None = None,
        thumbnail_medium_key: str | None = None,
        thumbnail_large_key: str | None = None,
    ) -> None:
        """Store a listing image.
        
        Args:
            image: ListingImage entity to store
        """
        self._store[image.id] = image
        if storage_key is not None or image.id not in self._storage_keys:
            self._storage_keys[image.id] = storage_key
        if thumbnail_small_key is not None or image.id not in self._thumbnail_small_keys:
            self._thumbnail_small_keys[image.id] = thumbnail_small_key
        if thumbnail_medium_key is not None or image.id not in self._thumbnail_medium_keys:
            self._thumbnail_medium_keys[image.id] = thumbnail_medium_key
        if thumbnail_large_key is not None or image.id not in self._thumbnail_large_keys:
            self._thumbnail_large_keys[image.id] = thumbnail_large_key
        self._compact_listing(image.listing_id)
    
    def get_by_id(self, image_id: UUID) -> ListingImage | None:
        """Get image by ID.
        
        Args:
            image_id: Image ID
            
        Returns:
            ListingImage or None if not found
        """
        return self._store.get(image_id)

    def get(self, image_id: UUID) -> ListingImage | None:
        return self.get_by_id(image_id)
    
    def get_by_listing(self, listing_id: UUID) -> list[ListingImage]:
        """Get all images for a listing.
        
        Args:
            listing_id: Listing ID
            
        Returns:
            List of ListingImage entities (ordered by position)
        """
        return self._ordered_images(listing_id)

    def get_storage_key(self, image_id: UUID) -> str | None:
        """Get stored storage key for an image."""
        return self._storage_keys.get(image_id)

    def get_thumbnail_key(self, image_id: UUID, size: str) -> str | None:
        if size == "small":
            return self._thumbnail_small_keys.get(image_id)
        if size == "medium":
            return self._thumbnail_medium_keys.get(image_id)
        if size == "large":
            return self._thumbnail_large_keys.get(image_id)
        raise ValueError("thumbnail size must be one of: small, medium, large")

    def claim_for_processing(self, image_id: UUID, max_attempts: int) -> ListingImage | None:
        with self._lock:
            image = self._store.get(image_id)
            if image is None:
                return None
            if image.processing_status == ImageProcessingStatus.READY:
                return None
            if image.processing_status == ImageProcessingStatus.PROCESSING:
                return None
            if image.processing_attempts >= max_attempts:
                return None

            claimed = replace(
                image,
                processing_status=ImageProcessingStatus.PROCESSING,
                processing_attempts=image.processing_attempts + 1,
            )
            self._store[image_id] = claimed
            return claimed

    def mark_ready(self, image_id: UUID, thumbnails: dict[str, str]) -> ListingImage | None:
        with self._lock:
            image = self._store.get(image_id)
            if image is None:
                return None

            ready = replace(
                image,
                thumbnail_small=thumbnails.get("small"),
                thumbnail_medium=thumbnails.get("medium"),
                thumbnail_large=thumbnails.get("large"),
                processing_status=ImageProcessingStatus.READY,
                processing_error=None,
            )
            self._store[image_id] = ready
            self._thumbnail_small_keys[image_id] = thumbnails.get("small")
            self._thumbnail_medium_keys[image_id] = thumbnails.get("medium")
            self._thumbnail_large_keys[image_id] = thumbnails.get("large")
            return ready

    def mark_failed(self, image_id: UUID, error: str) -> ListingImage | None:
        with self._lock:
            image = self._store.get(image_id)
            if image is None:
                return None

            failed = replace(
                image,
                processing_status=ImageProcessingStatus.FAILED,
                processing_error=error,
            )
            self._store[image_id] = failed
            return failed
    
    def delete_by_id(self, image_id: UUID) -> bool:
        """Delete image by ID.
        
        Args:
            image_id: Image ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        if image_id not in self._store:
            return False

        image = self._store.pop(image_id)
        self._storage_keys.pop(image_id, None)
        self._thumbnail_small_keys.pop(image_id, None)
        self._thumbnail_medium_keys.pop(image_id, None)
        self._thumbnail_large_keys.pop(image_id, None)
        self._compact_listing(image.listing_id)

        return True

    def count_ready_by_listing(self, listing_id: UUID) -> int:
        return len([image for image in self._ordered_images(listing_id) if image.processing_status == ImageProcessingStatus.READY])

    def reorder_for_listing(
        self,
        listing_id: UUID,
        ordered_image_ids: list[UUID],
    ) -> list[ListingImage]:
        if len(ordered_image_ids) != len(set(ordered_image_ids)):
            raise ValueError("image_ids must not contain duplicates")

        current = self._ordered_images(listing_id)
        current_ids = [image.id for image in current]
        if current_ids or ordered_image_ids:
            if len(current_ids) != len(ordered_image_ids) or set(current_ids) != set(ordered_image_ids):
                raise ValueError("image_ids must contain every current image exactly once")

        updated: list[ListingImage] = []
        for index, image_id in enumerate(ordered_image_ids, start=1):
            image = self._store[image_id]
            updated.append(replace(image, position=index))

        for image in updated:
            self._store[image.id] = image

        return self._ordered_images(listing_id)
    
    def count_by_listing(self, listing_id: UUID) -> int:
        """Count images in a listing.
        
        Args:
            listing_id: Listing ID
            
        Returns:
            Number of images
        """
        return len(self._ordered_images(listing_id))


class MemoryOutboxRepository:
    def __init__(self, metrics: EventMetrics | None = None) -> None:
        self._entries: dict[str, dict[str, Any]] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()
        self._notifier = None
        self._metrics = metrics

    def set_notifier(self, notifier) -> None:
        self._notifier = notifier

    def save(self, event) -> OutboxEntry:
        payload = serialize_event(event)
        entry_id = event.event_id
        with self._lock:
            self._entries[entry_id] = {
                "id": entry_id,
                "event": payload,
                "published": False,
                "published_at": None,
                "retry_count": 0,
                "permanently_failed": False,
                "failed_at": None,
                "failure_reason": None,
            }
            if entry_id not in self._order:
                self._order.append(entry_id)
            entry = self._hydrate(self._entries[entry_id])
        if self._notifier is not None:
            self._notifier()
        self._sync_metrics()
        return entry

    def get(self, entry_id: str) -> OutboxEntry | None:
        with self._lock:
            row = self._entries.get(entry_id)
            if row is None:
                return None
            return self._hydrate(row)

    def list_unpublished(
        self,
        limit: int | None = None,
        max_retry_count: int | None = None,
    ) -> list[OutboxEntry]:
        with self._lock:
            rows = [
                self._entries[entry_id]
                for entry_id in self._order
                if not self._entries[entry_id]["published"]
                and not self._entries[entry_id]["permanently_failed"]
                and (max_retry_count is None or self._entries[entry_id]["retry_count"] < max_retry_count)
            ]
            if limit is not None:
                rows = rows[:limit]
            return [self._hydrate(row) for row in rows]

    def get_unpublished(
        self,
        limit: int | None = None,
        max_retry_count: int | None = None,
    ) -> list[OutboxEntry]:
        return self.list_unpublished(limit=limit, max_retry_count=max_retry_count)

    def get_failed(self, limit: int | None = None) -> list[OutboxEntry]:
        with self._lock:
            rows = [
                self._entries[entry_id]
                for entry_id in self._order
                if self._entries[entry_id]["permanently_failed"]
            ]
            if limit is not None:
                rows = rows[:limit]
            return [self._hydrate(row) for row in rows]

    def get_by_aggregate(self, aggregate_type: str, aggregate_id: str) -> list[OutboxEntry]:
        with self._lock:
            rows = [
                self._entries[entry_id]
                for entry_id in self._order
                if self._entries[entry_id]["event"]["aggregate_type"] == aggregate_type
                and self._entries[entry_id]["event"]["aggregate_id"] == aggregate_id
            ]
            return [self._hydrate(row) for row in rows]

    def query(
        self, *, state: OutboxState | str | None = None,
        status: OutboxState | str | None = None, event_type: str | None = None,
        aggregate_id: str | None = None, correlation_id: str | None = None,
        occurred_from: datetime | None = None, occurred_to: datetime | None = None,
        limit: int | None = None,
    ) -> list[OutboxEntry]:
        requested_state = OutboxState(state or status) if (state or status) else None
        with self._lock:
            entries = [self._hydrate(self._entries[entry_id]) for entry_id in self._order]
        result = [
            entry for entry in entries
            if (requested_state is None or entry.state == requested_state or
                requested_state == OutboxState.FAILED and entry.permanently_failed)
            and (event_type is None or entry.event.event_type == event_type)
            and (aggregate_id is None or entry.event.aggregate_id == aggregate_id)
            and (correlation_id is None or entry.event.correlation_id == correlation_id)
            and (occurred_from is None or entry.event.occurred_at >= occurred_from)
            and (occurred_to is None or entry.event.occurred_at <= occurred_to)
        ]
        return result[:limit] if limit is not None else result

    def requeue(self, entry_ids: list[str]) -> list[OutboxEntry]:
        result: list[OutboxEntry] = []
        with self._lock:
            for entry_id in entry_ids:
                row = self._entries.get(entry_id)
                if row is None or not row["permanently_failed"]:
                    continue
                row.update({
                    "published": False, "published_at": None, "retry_count": 0,
                    "permanently_failed": False, "failed_at": None,
                    "failure_reason": None,
                })
                result.append(self._hydrate(row))
        self._sync_metrics()
        if result and self._notifier is not None:
            self._notifier()
        return result

    def mark_published(self, entry_id: str, published_at: datetime) -> OutboxEntry | None:
        with self._lock:
            row = self._entries.get(entry_id)
            if row is None:
                return None
            row["published"] = True
            row["published_at"] = published_at.astimezone(UTC)
            entry = self._hydrate(row)
        self._sync_metrics()
        return entry

    def increment_retry(self, entry_id: str) -> OutboxEntry | None:
        with self._lock:
            row = self._entries.get(entry_id)
            if row is None:
                return None
            row["retry_count"] += 1
            entry = self._hydrate(row)
        self._sync_metrics()
        return entry

    def mark_failed(self, entry_id: str, failed_at: datetime, failure_reason: str | None = None) -> OutboxEntry | None:
        with self._lock:
            row = self._entries.get(entry_id)
            if row is None:
                return None
            row["permanently_failed"] = True
            row["failed_at"] = failed_at.astimezone(UTC)
            row["failure_reason"] = failure_reason
            entry = self._hydrate(row)
        self._sync_metrics()
        return entry

    def _hydrate(self, row: dict[str, Any]) -> OutboxEntry:
        published_at = row["published_at"]
        failed_at = row.get("failed_at")
        if isinstance(published_at, str):
            published_at = datetime.fromisoformat(published_at)
        if isinstance(failed_at, str):
            failed_at = datetime.fromisoformat(failed_at)
        return OutboxEntry(
            id=str(row["id"]),
            event=deserialize_event(row["event"]),
            published=bool(row["published"]),
            published_at=published_at,
            retry_count=int(row["retry_count"]),
            permanently_failed=bool(row.get("permanently_failed", False)),
            failed_at=failed_at,
            failure_reason=row.get("failure_reason"),
        )

    def _sync_metrics(self) -> None:
        if self._metrics is None:
            return
        with self._lock:
            queue_depth = len(
                [
                    entry_id
                    for entry_id in self._order
                    if not self._entries[entry_id]["published"]
                    and not self._entries[entry_id]["permanently_failed"]
                ]
            )
        self._metrics.record_queue_depth(queue_depth)
