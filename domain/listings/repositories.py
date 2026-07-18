"""Listing image repository interface."""
from typing import Protocol
from uuid import UUID
from domain.listings.images import ListingImage


class ListingImageRepository(Protocol):
    """Repository for listing images."""
    
    def store(self, image: ListingImage) -> None:
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
    
    def delete_by_id(self, image_id: UUID) -> bool:
        """Delete image by ID.
        
        Args:
            image_id: Image ID to delete
            
        Returns:
            True if deleted, False if not found
        """
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
    
    def store(self, image: ListingImage) -> None:
        """Store a listing image."""
        self._images[image.id] = image
    
    def get_by_id(self, image_id: UUID) -> ListingImage | None:
        """Get image by ID."""
        return self._images.get(image_id)
    
    def get_by_listing(self, listing_id: UUID) -> list[ListingImage]:
        """Get all images for a listing, ordered by position."""
        images = [img for img in self._images.values() if img.listing_id == listing_id]
        return sorted(images, key=lambda x: x.position)
    
    def delete_by_id(self, image_id: UUID) -> bool:
        """Delete image by ID."""
        if image_id in self._images:
            del self._images[image_id]
            return True
        return False
    
    def count_by_listing(self, listing_id: UUID) -> int:
        """Count images in a listing."""
        return sum(1 for img in self._images.values() if img.listing_id == listing_id)
