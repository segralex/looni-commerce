"""Image upload API routes."""
from uuid import UUID
from fastapi import APIRouter, Depends, File, UploadFile, status, HTTPException
from application.media.service import MediaService
from application.marketplace.service import MarketplaceWorkflowError
from app.routes.auth import _get_current_user_id
from app.dependencies import (
    get_marketplace_service,
    get_media_service,
)
from app.schemas.images import ListingImageResponse, ListingImagesListResponse, ListingImageOrderRequest
from domain.listings.exceptions import MaxImagesExceededError

router = APIRouter(tags=["images"])


@router.post(
    "/listings/{listing_id}/images",
    response_model=ListingImageResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_image(
    listing_id: UUID,
    file: UploadFile = File(..., description="Image file (JPEG, PNG, WebP, or GIF)"),
    marketplace_service=Depends(get_marketplace_service),
    media_service: MediaService = Depends(get_media_service),
):
    """Upload an image to a listing.
    
    Supported types: JPEG, PNG, WebP, GIF
    Maximum: 10 images per listing
    """
    # Verify listing exists
    try:
        listing = marketplace_service.get_listing(listing_id)
    except MarketplaceWorkflowError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    
    # Validate content type
    if file.content_type not in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported content type: {file.content_type}. Supported: JPEG, PNG, WebP, GIF",
        )
    
    try:
        # Upload image using service
        image = media_service.upload_image(
            listing_id=listing_id,
            file_data=file.file,
            content_type=file.content_type,
            filename=file.filename or "upload",
        )
        return image
    except MaxImagesExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )


@router.get("/listings/{listing_id}/images", response_model=ListingImagesListResponse)
def list_images(
    listing_id: UUID,
    marketplace_service=Depends(get_marketplace_service),
    media_service: MediaService = Depends(get_media_service),
):
    """Get all images for a listing.
    
    Returns metadata only (no binary data).
    """
    # Verify listing exists
    try:
        listing = marketplace_service.get_listing(listing_id)
    except MarketplaceWorkflowError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    
    images = media_service.get_listing_images(listing_id)
    return {
        "count": len(images),
        "items": images,
    }


@router.delete("/listings/{listing_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_image(
    listing_id: UUID,
    image_id: UUID,
    marketplace_service=Depends(get_marketplace_service),
    media_service: MediaService = Depends(get_media_service),
):
    """Delete an image from a listing."""
    # Verify listing exists
    try:
        listing = marketplace_service.get_listing(listing_id)
    except MarketplaceWorkflowError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

    listing_images = media_service.get_listing_images(listing_id)
    if not any(image.id == image_id for image in listing_images):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    
    # Delete image
    deleted = media_service.delete_image(image_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    
    return None


@router.patch(
    "/listings/{listing_id}/images/order",
    response_model=ListingImagesListResponse,
)
def reorder_images(
    listing_id: UUID,
    payload: ListingImageOrderRequest,
    current_user_id: UUID = Depends(_get_current_user_id),
    marketplace_service=Depends(get_marketplace_service),
    media_service: MediaService = Depends(get_media_service),
):
    """Reorder image metadata for a listing."""
    try:
        listing = marketplace_service.get_listing(listing_id)
    except MarketplaceWorkflowError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

    if listing.seller_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    try:
        images = media_service.reorder_listing_images(listing_id, payload.image_ids)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    return {
        "count": len(images),
        "items": images,
    }
