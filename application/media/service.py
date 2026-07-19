"""Media application service."""
from uuid import UUID, uuid4
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO, Callable
import tempfile

from application.media.thumbnail_service import ThumbnailService
from domain.listings.images import ListingImage
from domain.listings.repositories import ListingImageRepository
from domain.listings.exceptions import MaxImagesExceededError
from domain.storage import StorageProvider


class MediaService:
    """Application service for media management."""
    
    MAX_IMAGES_PER_LISTING = 10
    
    def __init__(
        self,
        image_repo: ListingImageRepository,
        storage: StorageProvider,
        listing_lookup: Callable[[UUID], Any] | None = None,
        thumbnail_service: ThumbnailService | None = None,
    ):
        """Initialize media service.
        
        Args:
            image_repo: Repository for storing image metadata
            storage: Storage provider for file storage
        """
        self.image_repo = image_repo
        self.storage = storage
        self.listing_lookup = listing_lookup
        self.thumbnail_service = thumbnail_service
    
    def upload_image(
        self,
        listing_id: UUID,
        file_data: BinaryIO,
        content_type: str,
        filename: str,
    ) -> ListingImage:
        """Upload an image for a listing.
        
        Args:
            listing_id: ID of listing to upload to
            file_data: Binary file data
            content_type: MIME type (e.g. "image/jpeg")
            filename: Original filename (for reference only)
            
        Returns:
            Created ListingImage entity
            
        Raises:
            MaxImagesExceededError: If listing already has 10 images
            ValueError: If content type not supported
        """
        # Check image limit
        count = self.image_repo.count_by_listing(listing_id)
        if count >= self.MAX_IMAGES_PER_LISTING:
            raise MaxImagesExceededError(
                f"Listing already has maximum {self.MAX_IMAGES_PER_LISTING} images"
            )
        
        # Save file to temporary location first.
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(file_data.read())
            tmp_path = tmp.name

        image_id = uuid4()
        created_storage_keys: list[str] = []

        try:
            stored_file = self.storage.save(tmp_path, content_type)
            created_storage_keys.append(stored_file.storage_key)

            thumbnail_keys = {
                "small": None,
                "medium": None,
                "large": None,
            }
            if self.thumbnail_service is not None:
                created_thumbnails = self.thumbnail_service.generate_and_store(tmp_path, content_type)
                thumbnail_keys = {
                    "small": created_thumbnails["small"].storage_key,
                    "medium": created_thumbnails["medium"].storage_key,
                    "large": created_thumbnails["large"].storage_key,
                }
                created_storage_keys.extend(
                    [
                        thumbnail_keys["small"],
                        thumbnail_keys["medium"],
                        thumbnail_keys["large"],
                    ]
                )

            existing_images = self.image_repo.get_by_listing(listing_id)
            next_position = len(existing_images) + 1

            image = ListingImage(
                id=image_id,
                listing_id=listing_id,
                filename=filename,
                content_type=content_type,
                size_bytes=stored_file.size_bytes,
                position=next_position,
                created_at=datetime.now(),
                thumbnail_small=thumbnail_keys["small"],
                thumbnail_medium=thumbnail_keys["medium"],
                thumbnail_large=thumbnail_keys["large"],
            )

            self.image_repo.store(
                image,
                storage_key=stored_file.storage_key,
                thumbnail_small_key=thumbnail_keys["small"],
                thumbnail_medium_key=thumbnail_keys["medium"],
                thumbnail_large_key=thumbnail_keys["large"],
            )

            return image
        except Exception:
            for storage_key in reversed(created_storage_keys):
                if storage_key is not None:
                    self.storage.delete(storage_key)
            self.image_repo.delete_by_id(image_id)
            raise
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    
    def get_listing_images(self, listing_id: UUID) -> list[ListingImage]:
        """Get all images for a listing.
        
        Args:
            listing_id: Listing ID
            
        Returns:
            List of ListingImage entities ordered by position
        """
        return self.image_repo.get_by_listing(listing_id)

    def reorder_listing_images(
        self,
        listing_id: UUID,
        ordered_image_ids: list[UUID],
    ) -> list[ListingImage]:
        """Reorder images for a listing without touching binary storage."""
        if self.listing_lookup is not None:
            self.listing_lookup(listing_id)

        current_images = self.image_repo.get_by_listing(listing_id)
        current_ids = [image.id for image in current_images]

        if len(ordered_image_ids) != len(set(ordered_image_ids)):
            raise ValueError("image_ids must not contain duplicates")

        if current_ids and not ordered_image_ids:
            raise ValueError("image_ids must contain every current image exactly once")

        if len(current_ids) != len(ordered_image_ids) or set(current_ids) != set(ordered_image_ids):
            raise ValueError("image_ids must contain every current image exactly once")

        return self.image_repo.reorder_for_listing(listing_id, ordered_image_ids)
    
    def delete_image(self, image_id: UUID) -> bool:
        """Delete an image.
        
        Args:
            image_id: Image ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        image = self.image_repo.get_by_id(image_id)
        if not image:
            return False

        storage_keys = [
            self.image_repo.get_storage_key(image_id),
            self.image_repo.get_thumbnail_key(image_id, "small"),
            self.image_repo.get_thumbnail_key(image_id, "medium"),
            self.image_repo.get_thumbnail_key(image_id, "large"),
        ]

        for storage_key in storage_keys:
            if storage_key:
                self.storage.delete(storage_key)

        return self.image_repo.delete_by_id(image_id)
