from __future__ import annotations

from typing import List
from pydantic import BaseModel
from pydantic import ConfigDict
from app.schemas.listings import ListingResponse


class SearchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    count: int
    items: List[ListingResponse]
