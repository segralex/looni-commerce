from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from starlette.status import HTTP_201_CREATED

from app.dependencies import get_marketplace_service
from app.schemas.listings import ListingCreate, ListingPublish, ListingResponse
from application.marketplace.service import MarketplaceService, MarketplaceWorkflowError

router = APIRouter(prefix="/listings", tags=["listings"])


def _to_response(listing) -> ListingResponse:
    return ListingResponse(
        id=listing.id,
        seller_id=listing.seller_id,
        title=listing.title,
        description=listing.description,
        category=listing.category,
        price=str(listing.price),
        currency=listing.currency,
        status=listing.status.value if hasattr(listing.status, "value") else str(listing.status),
        created_at=listing.created_at,
        updated_at=listing.updated_at,
    )


@router.post("/", response_model=ListingResponse, status_code=HTTP_201_CREATED)
def create_listing(
    payload: ListingCreate,
    marketplace_service: MarketplaceService = Depends(get_marketplace_service),
) -> ListingResponse:
    try:
        listing = marketplace_service.create_listing_for_user(
            payload.seller_id,
            payload.title,
            payload.description,
            payload.category,
            payload.condition,
            payload.price,
            payload.currency,
            payload.location,
        )
    except MarketplaceWorkflowError as exc:
        message = str(exc)
        if "not found" in message:
            raise HTTPException(status_code=404, detail=message)
        raise HTTPException(status_code=409, detail=message)
    return _to_response(listing)


@router.get("/{listing_id}", response_model=ListingResponse)
def get_listing(
    listing_id: UUID,
    marketplace_service: MarketplaceService = Depends(get_marketplace_service),
) -> ListingResponse:
    try:
        listing = marketplace_service.get_listing(listing_id)
    except MarketplaceWorkflowError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _to_response(listing)


@router.post("/{listing_id}/publish", response_model=ListingResponse)
def publish_listing(
    listing_id: UUID,
    marketplace_service: MarketplaceService = Depends(get_marketplace_service),
) -> ListingResponse:
    try:
        listing = marketplace_service.get_listing(listing_id)
        published = marketplace_service.publish_listing(listing.seller_id, listing_id)
    except MarketplaceWorkflowError as exc:
        message = str(exc)
        if "not found" in message:
            raise HTTPException(status_code=404, detail=message)
        raise HTTPException(status_code=409, detail=message)
    return _to_response(published)
