from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar, TypeVar
from uuid import uuid4

from domain.events.base import DomainEvent
from domain.events.serialization import register_event_class
from domain.trust.models import DisputeOutcome, TransactionRole, VerificationLevel

E = TypeVar("E", bound=DomainEvent)


def _metadata(event_type: str, user_id: str, occurred_at: datetime | None) -> dict[str, object]:
    return {
        "event_id": str(uuid4()), "event_type": event_type,
        "aggregate_type": "Trust", "aggregate_id": str(user_id),
        "occurred_at": occurred_at or datetime.now(UTC),
    }


@dataclass(frozen=True, slots=True, kw_only=True)
class TrustScoreChanged(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "TrustScoreChanged"
    user_id: str
    previous_score: int
    new_score: int
    reason: str

    @classmethod
    def create(cls, user_id: str, previous_score: int, new_score: int, reason: str,
               occurred_at: datetime | None = None) -> "TrustScoreChanged":
        return cls(**_metadata(cls.EVENT_TYPE, user_id, occurred_at), user_id=str(user_id),
                   previous_score=previous_score, new_score=new_score, reason=reason)


@dataclass(frozen=True, slots=True, kw_only=True)
class VerificationGranted(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "VerificationGranted"
    user_id: str
    verification_level: str

    @classmethod
    def create(cls, user_id: str, level: VerificationLevel,
               occurred_at: datetime | None = None) -> "VerificationGranted":
        return cls(**_metadata(cls.EVENT_TYPE, user_id, occurred_at), user_id=str(user_id),
                   verification_level=level.value)


@dataclass(frozen=True, slots=True, kw_only=True)
class VerificationRevoked(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "VerificationRevoked"
    user_id: str
    previous_level: str
    verification_level: str = VerificationLevel.NONE.value

    @classmethod
    def create(cls, user_id: str, previous_level: VerificationLevel,
               occurred_at: datetime | None = None) -> "VerificationRevoked":
        return cls(**_metadata(cls.EVENT_TYPE, user_id, occurred_at), user_id=str(user_id),
                   previous_level=previous_level.value)


@dataclass(frozen=True, slots=True, kw_only=True)
class TransactionRecorded(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "TransactionRecorded"
    user_id: str
    transaction_id: str
    role: str

    @classmethod
    def create(cls, user_id: str, transaction_id: str, role: TransactionRole,
               occurred_at: datetime | None = None) -> "TransactionRecorded":
        return cls(**_metadata(cls.EVENT_TYPE, user_id, occurred_at), user_id=str(user_id),
                   transaction_id=str(transaction_id), role=role.value)


@dataclass(frozen=True, slots=True, kw_only=True)
class DisputeRecorded(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "DisputeRecorded"
    user_id: str
    dispute_id: str
    outcome: str

    @classmethod
    def create(cls, user_id: str, dispute_id: str, outcome: DisputeOutcome,
               occurred_at: datetime | None = None) -> "DisputeRecorded":
        return cls(**_metadata(cls.EVENT_TYPE, user_id, occurred_at), user_id=str(user_id),
                   dispute_id=str(dispute_id), outcome=outcome.value)


@dataclass(frozen=True, slots=True, kw_only=True)
class ReviewRecorded(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "ReviewRecorded"
    user_id: str
    review_id: str
    received: bool
    recommended: bool

    @classmethod
    def create(cls, user_id: str, review_id: str, *, received: bool,
               recommended: bool = True, occurred_at: datetime | None = None) -> "ReviewRecorded":
        return cls(**_metadata(cls.EVENT_TYPE, user_id, occurred_at), user_id=str(user_id),
                   review_id=str(review_id), received=received, recommended=recommended)


for _event_class in (
    TrustScoreChanged, VerificationGranted, VerificationRevoked,
    TransactionRecorded, DisputeRecorded, ReviewRecorded,
):
    register_event_class(_event_class.EVENT_TYPE, _event_class)

