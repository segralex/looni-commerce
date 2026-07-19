from __future__ import annotations

from uuid import UUID
from typing import Optional
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from app.dependencies import get_marketplace_service, get_search_repository
from app.schemas.search import SearchResponse
from app.schemas.listings import ListingResponse
from domain.search.service import SearchService
from domain.search.models import SearchQuery
from domain.search.repository import SearchFilters
from domain.listings.models import ItemCondition
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
    condition: Optional[ItemCondition] = None,
    location: Optional[str] = None,
    min_price: Optional[Decimal] = None,
    max_price: Optional[Decimal] = None,
    published_only: bool = True,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    marketplace_service: MarketplaceService = Depends(get_marketplace_service),
    search_repository=Depends(get_search_repository),
) -> SearchResponse:
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(status_code=422, detail="min_price cannot be greater than max_price")

    # SQLite backend: FTS5 read-model with ranked text search.
    if search_repository is not None and marketplace_service.listing_repository is not None:
        filters = SearchFilters(
            keyword=q,
            category=category,
            seller_id=seller_id,
            condition=condition,
            location=location,
            min_price=min_price,
            max_price=max_price,
            published_only=published_only,
        )
        listing_ids = search_repository.search_listing_ids(filters, limit=limit, offset=offset)
        results = []
        for listing_id in listing_ids:
            try:
                listing = marketplace_service.listing_repository.get(listing_id)
                results.append(listing)
            except Exception:
                # Index is a read model; source of truth is listing repository.
                continue

        items = [_to_listing_response(r) for r in results]
        return SearchResponse(count=len(items), items=items)

    # Memory backend compatibility: existing linear scan path.
    listings = marketplace_service.listing_repository.all() if marketplace_service.listing_repository else ()

    query = SearchQuery(
        keyword=q,
        category=category,
        condition=condition,
        location=location,
        min_price=min_price,
        max_price=max_price,
    )
    searcher = SearchService()
    try:
        results = searcher.search(listings, query)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    if seller_id is not None:
        results = tuple(r for r in results if r.seller_id == seller_id)

    if not published_only:
        # The in-memory domain service is intentionally publication-focused.
        # Keep compatibility and avoid changing domain semantics.
        pass

    results = results[offset: offset + limit]

    items = [_to_listing_response(r) for r in results]
    return SearchResponse(count=len(items), items=items)
