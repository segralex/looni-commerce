from __future__ import annotations

from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from app.dependencies import get_marketplace_service
from app.schemas.search import SearchResponse
from app.schemas.listings import ListingResponse
from domain.search.service import SearchService
from domain.search.models import SearchQuery
from application.marketplace.service import MarketplaceService, MarketplaceWorkflowError

router = APIRouter(prefix="/search", tags=["search"])


def _to_listing_response(listing) -> ListingResponse:
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


@router.get("/", response_model=SearchResponse)
def search_listings(
    q: Optional[str] = Query(None, alias="q"),
    category: Optional[str] = None,
    seller_id: Optional[UUID] = None,
    published_only: bool = True,
    marketplace_service: MarketplaceService = Depends(get_marketplace_service),
) -> SearchResponse:
    # Acquire listings from repository via marketplace wiring
    listings = marketplace_service.listing_repository.all() if marketplace_service.listing_repository else ()

    # Build SearchQuery (domain) — only uses fields it understands
    query = SearchQuery(keyword=q, category=category)

    searcher = SearchService()
    try:
        results = searcher.search(listings, query)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Apply seller filter if present (post-search to avoid changing SearchService behavior)
    if seller_id is not None:
        results = tuple(r for r in results if r.seller_id == seller_id)

    items = [_to_listing_response(r) for r in results]
    return SearchResponse(count=len(items), items=items)
