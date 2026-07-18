from __future__ import annotations

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
        self._by_listing: dict[UUID, list[ListingImage]] = {}
    
    def store(self, image: ListingImage) -> None:
        """Store a listing image.
        
        Args:
            image: ListingImage entity to store
        """
        self._store[image.id] = image
        
        if image.listing_id not in self._by_listing:
            self._by_listing[image.listing_id] = []
        
        # Add to listing and keep sorted by position
        self._by_listing[image.listing_id].append(image)
        self._by_listing[image.listing_id].sort(key=lambda x: x.position)
    
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
        return self._by_listing.get(listing_id, [])
    
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
        
        if image.listing_id in self._by_listing:
            self._by_listing[image.listing_id] = [
                img for img in self._by_listing[image.listing_id]
                if img.id != image_id
            ]
            if not self._by_listing[image.listing_id]:
                del self._by_listing[image.listing_id]
        
        return True
    
    def count_by_listing(self, listing_id: UUID) -> int:
        """Count images in a listing.
        
        Args:
            listing_id: Listing ID
            
        Returns:
            Number of images
        """
        return len(self._by_listing.get(listing_id, []))
