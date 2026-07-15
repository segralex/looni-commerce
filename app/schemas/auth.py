"""Authentication request/response schemas."""
from __future__ import annotations

from pydantic import BaseModel, constr, Field

from app.schemas.users import UserResponse


class RegisterRequest(BaseModel):
    display_name: constr(strip_whitespace=True, min_length=1)
    email: constr(strip_whitespace=True, min_length=1)
    phone: str | None = None
    password: str = Field(..., min_length=10, description="At least 10 characters")


class LoginRequest(BaseModel):
    email: constr(strip_whitespace=True, min_length=1)
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class AuthMeResponse(UserResponse):
    """Authenticated user info; same as UserResponse."""
    pass
