"""Listing image domain model."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from domain.listings.exceptions import InvalidImagePositionError
from domain.media.processing import ImageProcessingStatus, infer_processing_status



@dataclass
class ListingImage:
    """Domain model for a listing image.
    
    Rules:
    - Images belong to one listing
    - Positions are unique per listing
    - Positions start at 1 (not 0)
    - Maximum 10 images per listing
    - Minimum 2 images before publishing (enforced at service level)
    - Filenames are immutable
    - Metadata only—no binary image data
    """
    
    id: UUID
    listing_id: UUID
    filename: str
    content_type: str
    size_bytes: int
    position: int
    created_at: datetime
    thumbnail_small: str | None = None
    thumbnail_medium: str | None = None
    thumbnail_large: str | None = None
    processing_status: ImageProcessingStatus = ImageProcessingStatus.PENDING
    processing_error: str | None = None
    processing_attempts: int = 0
    
    def __post_init__(self):
        """Validate constraints after initialization."""
        if self.position < 1:
            raise InvalidImagePositionError(f"Position must be >= 1, got {self.position}")
        if self.position > 10:
            raise InvalidImagePositionError(f"Position must be <= 10, got {self.position}")
        if not self.filename:
            raise ValueError("Filename cannot be empty")
        if not self.content_type:
            raise ValueError("Content type cannot be empty")
        if self.size_bytes < 0:
            raise ValueError("Size bytes cannot be negative")
        if self.processing_attempts < 0:
            raise ValueError("Processing attempts cannot be negative")
        if self.processing_status == ImageProcessingStatus.PENDING and self.has_required_thumbnails:
            self.processing_status = infer_processing_status(True)
        if self.processing_status == ImageProcessingStatus.READY and not self.has_required_thumbnails:
            self.processing_status = infer_processing_status(False)
        if self.processing_status == ImageProcessingStatus.READY and self.processing_error:
            self.processing_error = None
    
    @property
    def is_image(self) -> bool:
        """Check if content type is an image."""
        return self.content_type.startswith("image/")
    
    @property
    def is_supported_format(self) -> bool:
        """Check if image format is supported."""
        supported_types = {
            "image/jpeg",
            "image/png",
            "image/webp",
            "image/gif",
        }
        return self.content_type in supported_types

    @property
    def thumbnails(self) -> dict[str, str | None]:
        """Return thumbnail identifiers grouped by size."""
        return {
            "small": self.thumbnail_small,
            "medium": self.thumbnail_medium,
            "large": self.thumbnail_large,
        }

    @property
    def has_required_thumbnails(self) -> bool:
        return all([self.thumbnail_small, self.thumbnail_medium, self.thumbnail_large])
