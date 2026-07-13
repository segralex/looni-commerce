from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Tuple

from datetime import UTC

from domain.listings.models import Listing, ListingStatus
from .models import SearchQuery


class SearchService:
    def search(self, listings: Iterable[Listing], query: SearchQuery) -> Tuple[Listing, ...]:
        # Validate price range
        if query.min_price is not None and query.max_price is not None:
            if query.min_price > query.max_price:
                raise ValueError("min_price cannot be greater than max_price")

        results = []
        for l in listings:
            # Only published
            if l.status != ListingStatus.PUBLISHED:
                continue

            # Keyword
            if query.keyword:
                kw = query.keyword.lower()
                if kw not in (l.title or "").lower() and kw not in (l.description or "").lower():
                    continue

            # Category exact
            if query.category is not None and l.category != query.category:
                continue

            # Condition exact
            if query.condition is not None and l.condition != query.condition:
                continue

            # Location case-insensitive exact
            if query.location is not None and (l.location or "").lower() != query.location.lower():
                continue

            # Price range inclusive
            if query.min_price is not None and l.price < query.min_price:
                continue
            if query.max_price is not None and l.price > query.max_price:
                continue

            results.append(l)

        # Sort newest first by created_at
        results_sorted = sorted(results, key=lambda x: x.created_at, reverse=True)

        return tuple(results_sorted)
