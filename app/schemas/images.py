"""Schemas for image upload and response."""
from uuid import UUID
from pydantic import BaseModel, Field

from domain.media.processing import ImageProcessingStatus


class ListingImageResponse(BaseModel):
    """Response model for listing image metadata."""
    
    id: UUID = Field(..., description="Image ID")
    listing_id: UUID = Field(..., description="Listing ID")
    original_url: str = Field(..., description="Original image URL")
    position: int = Field(..., description="Position in listing (1-10)")
    content_type: str = Field(..., description="MIME type (e.g. 'image/jpeg')")
    size_bytes: int = Field(..., description="File size in bytes")
    processing_status: ImageProcessingStatus = Field(..., description="Thumbnail pipeline status")
    processing_error: str | None = Field(default=None, description="Safe processing error summary")
    thumbnails: dict[str, str] = Field(default_factory=dict, description="Thumbnail URLs by size")
    
    model_config = {"from_attributes": True}


class ListingImagesListResponse(BaseModel):
    """Response for listing all images."""
    
    count: int = Field(..., description="Total number of images")
    items: list[ListingImageResponse] = Field(
        ..., description="List of image metadata"
    )


class ListingImageOrderRequest(BaseModel):
    """Request payload for image reordering."""

    image_ids: list[UUID] = Field(..., description="Complete ordered set of image IDs")
