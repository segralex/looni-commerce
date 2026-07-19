"""Image upload API routes."""
from uuid import UUID
from fastapi import APIRouter, Depends, File, UploadFile, status, HTTPException
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from application.media.service import MediaService
from application.marketplace.service import MarketplaceWorkflowError
from app.routes.auth import _get_current_user_id
from app.dependencies import (
    get_marketplace_service,
    get_media_service,
)
from app.schemas.images import ListingImageResponse, ListingImagesListResponse, ListingImageOrderRequest
from domain.media.processing import ImageProcessingStatus
from domain.listings.images import ListingImage
from domain.listings.exceptions import MaxImagesExceededError

router = APIRouter(tags=["images"])


def _build_image_response(image: ListingImage) -> dict[str, object]:
    base_url = f"/api/v1/images/{image.id}"
    thumbnails: dict[str, str] = {}
    if image.processing_status == ImageProcessingStatus.READY:
        thumbnails = {
            "small": f"{base_url}/thumbnails/small",
            "medium": f"{base_url}/thumbnails/medium",
            "large": f"{base_url}/thumbnails/large",
        }

    return {
        "id": image.id,
        "listing_id": image.listing_id,
        "original_url": f"{base_url}/original",
        "position": image.position,
        "content_type": image.content_type,
        "size_bytes": image.size_bytes,
        "processing_status": image.processing_status,
        "processing_error": image.processing_error,
        "thumbnails": thumbnails,
    }


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
        return _build_image_response(image)
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
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
        "items": [_build_image_response(image) for image in images],
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
        "items": [_build_image_response(image) for image in images],
    }


@router.get("/images/{image_id}/original")
def get_original_image(
    image_id: UUID,
    media_service: MediaService = Depends(get_media_service),
):
    image = media_service.get_image(image_id)
    if image is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    storage_key = media_service.image_repo.get_storage_key(image_id)
    if storage_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    handle = media_service.storage.open(storage_key)
    return StreamingResponse(
        handle,
        media_type=image.content_type,
        background=BackgroundTask(handle.close),
    )


@router.get("/images/{image_id}/thumbnails/{size}")
def get_thumbnail_image(
    image_id: UUID,
    size: str,
    media_service: MediaService = Depends(get_media_service),
):
    if size not in {"small", "medium", "large"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid thumbnail size")

    image = media_service.get_image(image_id)
    if image is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    if image.processing_status == ImageProcessingStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "IMAGE_PROCESSING_NOT_READY",
                "message": "The requested thumbnail is not ready.",
                "processing_status": image.processing_status,
            },
        )
    if image.processing_status == ImageProcessingStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "IMAGE_PROCESSING_FAILED",
                "message": "Thumbnail processing failed.",
                "processing_status": image.processing_status,
            },
        )

    storage_key = media_service.image_repo.get_thumbnail_key(image_id, size)
    if storage_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thumbnail not found")

    handle = media_service.storage.open(storage_key)
    return StreamingResponse(
        handle,
        media_type=image.content_type,
        background=BackgroundTask(handle.close),
    )
