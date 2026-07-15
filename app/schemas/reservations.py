from __future__ import annotations

from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel
from pydantic import ConfigDict


class ReservationCreate(BaseModel):
    buyer_id: UUID
    listing_id: UUID


class ReservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    listing_id: UUID
    buyer_id: UUID
    seller_id: UUID
    status: str
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
