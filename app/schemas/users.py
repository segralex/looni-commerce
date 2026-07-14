from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, constr


class UserCreate(BaseModel):
    display_name: constr(strip_whitespace=True, min_length=1)
    email: constr(strip_whitespace=True, min_length=1)
    phone: str | None = None


class UserResponse(BaseModel):
    id: UUID
    display_name: str
    email: str
    phone: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
