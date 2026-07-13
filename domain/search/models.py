from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from domain.listings.models import ItemCondition


@dataclass(frozen=True)
class SearchQuery:
    keyword: Optional[str] = None
    category: Optional[str] = None
    condition: Optional[ItemCondition] = None
    location: Optional[str] = None
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
