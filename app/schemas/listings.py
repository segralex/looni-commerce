from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, constr, ConfigDict


class ListingCreate(BaseModel):
    seller_id: UUID
    title: constr(strip_whitespace=True, min_length=1)
    description: constr(strip_whitespace=True, min_length=1)
    price: Decimal
    currency: constr(strip_whitespace=True, min_length=1)
    category: constr(strip_whitespace=True, min_length=1)
    condition: constr(strip_whitespace=True, min_length=1)
    location: constr(strip_whitespace=True, min_length=1)


class ListingPublish(BaseModel):
    seller_id: UUID


class ListingResponse(BaseModel):
    id: UUID
    seller_id: UUID
    title: str
    description: str
    category: str
    price: str
    currency: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
