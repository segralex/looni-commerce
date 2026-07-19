from __future__ import annotations

from dataclasses import replace
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from domain.repositories import (
    DuplicateEntityError,
    EntityNotFoundError,
    ListingRepository,
    ReservationRepository,
    UserRepository,
)
from domain.listings.images import ListingImage
from domain.listings.repositories import ListingImageRepository


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


class MemoryListingImageRepository(ListingImageRepository):
    """In-memory implementation of ListingImageRepository."""
    
    def __init__(self) -> None:
        self._store: dict[UUID, ListingImage] = {}
        self._storage_keys: dict[UUID, str | None] = {}
        self._thumbnail_small_keys: dict[UUID, str | None] = {}
        self._thumbnail_medium_keys: dict[UUID, str | None] = {}
        self._thumbnail_large_keys: dict[UUID, str | None] = {}

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
