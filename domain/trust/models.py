from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class VerificationLevel(StrEnum):
    NONE = "NONE"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    IDENTITY = "IDENTITY"
    BUSINESS = "BUSINESS"

    @property
    def rank(self) -> int:
        return list(type(self)).index(self)


class TransactionRole(StrEnum):
    SALE = "SALE"
    PURCHASE = "PURCHASE"
    TRADE = "TRADE"


class DisputeOutcome(StrEnum):
    OPENED = "OPENED"
    WON = "WON"
    LOST = "LOST"


@dataclass(frozen=True, slots=True)
class PublicTrustProfile:
    user_id: str
    trust_score: int
    verification_badge: str
    completed_deals: int
    recommendations: int
    response_rate: float | None
    response_time: float | None
    member_since: datetime

