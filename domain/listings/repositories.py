"""Listing image repository interface."""
from dataclasses import replace
from typing import Protocol
from uuid import UUID
from domain.listings.images import ListingImage


class ListingImageRepository(Protocol):
    """Repository for listing images."""
    
    def store(self, image: ListingImage, storage_key: str | None = None) -> None:
        """Store a listing image.
        
        Args:
            image: ListingImage entity to store
        """
        ...
    
    def get_by_id(self, image_id: UUID) -> ListingImage | None:
        """Get image by ID.
        
        Args:
            image_id: Image ID
            
        Returns:
            ListingImage or None if not found
        """
        ...
    
    def get_by_listing(self, listing_id: UUID) -> list[ListingImage]:
        """Get all images for a listing.
        
        Args:
            listing_id: Listing ID
            
        Returns:
            List of ListingImage entities (ordered by position)
        """
        ...

    def get_storage_key(self, image_id: UUID) -> str | None:
        """Get the storage key for an image if known."""
        ...
    
    def delete_by_id(self, image_id: UUID) -> bool:
        """Delete image by ID.
        
        Args:
            image_id: Image ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        ...

    def reorder_for_listing(
        self,
        listing_id: UUID,
        ordered_image_ids: list[UUID],
    ) -> list[ListingImage]:
        """Persist a new contiguous ordering for a listing's images."""
        ...
    
    def count_by_listing(self, listing_id: UUID) -> int:
        """Count images in a listing.
        
        Args:
            listing_id: Listing ID
            
        Returns:
            Number of images
        """
        ...


class MemoryListingImageRepository:
    """In-memory implementation of listing image repository."""
    
    def __init__(self):
        """Initialize repository."""
        self._images: dict[UUID, ListingImage] = {}
        self._storage_keys: dict[UUID, str | None] = {}

    def _ordered_images(self, listing_id: UUID) -> list[ListingImage]:
        images = [img for img in self._images.values() if img.listing_id == listing_id]
        return sorted(images, key=lambda x: (x.position, x.created_at, str(x.id)))

    def _compact_listing(self, listing_id: UUID) -> list[ListingImage]:
        ordered = self._ordered_images(listing_id)
        updated: list[ListingImage] = []
        for index, image in enumerate(ordered, start=1):
            normalized = replace(image, position=index)
            self._images[image.id] = normalized
            updated.append(normalized)
        return updated
    
    def store(self, image: ListingImage, storage_key: str | None = None) -> None:
        """Store a listing image."""
        self._images[image.id] = image
        if storage_key is not None or image.id not in self._storage_keys:
            self._storage_keys[image.id] = storage_key
        self._compact_listing(image.listing_id)
    
    def get_by_id(self, image_id: UUID) -> ListingImage | None:
        """Get image by ID."""
        return self._images.get(image_id)
    
    def get_by_listing(self, listing_id: UUID) -> list[ListingImage]:
        """Get all images for a listing, ordered by position."""
        return self._ordered_images(listing_id)

    def get_storage_key(self, image_id: UUID) -> str | None:
        """Get storage key by image ID."""
        return self._storage_keys.get(image_id)
    
    def delete_by_id(self, image_id: UUID) -> bool:
        """Delete image by ID."""
        image = self._images.pop(image_id, None)
        if image is None:
            return False
        self._storage_keys.pop(image_id, None)
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
            image = self._images[image_id]
            updated.append(replace(image, position=index))

        for image in updated:
            self._images[image.id] = image

        return self._ordered_images(listing_id)
    
    def count_by_listing(self, listing_id: UUID) -> int:
        """Count images in a listing."""
        return len(self._ordered_images(listing_id))
