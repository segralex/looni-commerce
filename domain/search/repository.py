from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from domain.listings.models import ItemCondition


@dataclass(frozen=True)
class SearchFilters:
    keyword: str | None = None
    category: str | None = None
    seller_id: UUID | None = None
    condition: ItemCondition | None = None
    location: str | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    published_only: bool = True


class SearchRepository(Protocol):
    def search_listing_ids(
        self,
        filters: SearchFilters,
        *,
        limit: int,
        offset: int,
    ) -> tuple[UUID, ...]:
        ...
