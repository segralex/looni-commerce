from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from uuid import UUID

from .exceptions import UserValidationError


class UserStatus(Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DELETED = "DELETED"


@dataclass
class User:
    id: UUID
    display_name: str
    email: str
    phone: str | None = None
    status: UserStatus = UserStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.display_name:
            raise UserValidationError("display_name is required")
        if not self.email:
            raise UserValidationError("email is required")
        self.email = self.email.strip().lower()

        for attr in ("created_at", "updated_at"):
            dt = getattr(self, attr)
            if dt.tzinfo is None:
                raise UserValidationError(f"{attr} must be timezone-aware UTC datetime")
            if dt.tzinfo != UTC:
                raise UserValidationError(f"{attr} must be UTC timezone")
