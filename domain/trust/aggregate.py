from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from domain.events.base import DomainEvent
from domain.trust.events import (
    DisputeRecorded, ReviewRecorded, TransactionRecorded, TrustScoreChanged,
    VerificationGranted, VerificationRevoked,
)
from domain.trust.models import (
    DisputeOutcome, PublicTrustProfile, TransactionRole, VerificationLevel,
)
from domain.trust.score import TrustScoreCalculator


@dataclass(slots=True)
class TrustAggregate:
    user_id: str
    trust_score: int = 100
    verification_level: VerificationLevel = VerificationLevel.NONE
    completed_transactions: int = 0
    successful_sales: int = 0
    successful_purchases: int = 0
    successful_trades: int = 0
    disputes_opened: int = 0
    disputes_lost: int = 0
    disputes_won: int = 0
    reviews_received: int = 0
    reviews_given: int = 0
    last_activity: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    _calculator: TrustScoreCalculator = field(default_factory=TrustScoreCalculator, repr=False, compare=False)

    def __post_init__(self) -> None:
        self.user_id = str(self.user_id)
        for name in ("created_at", "updated_at"):
            value = getattr(self, name)
            if value.tzinfo is None:
                raise ValueError(f"{name} must be timezone-aware")
            setattr(self, name, value.astimezone(UTC))
        if self.last_activity is not None:
            if self.last_activity.tzinfo is None:
                raise ValueError("last_activity must be timezone-aware")
            self.last_activity = self.last_activity.astimezone(UTC)
        if not 0 <= self.trust_score <= 1000:
            raise ValueError("trust_score must be between 0 and 1000")

    def grant_verification(self, level: VerificationLevel, *, at: datetime | None = None) -> tuple[DomainEvent, ...]:
        if level.rank <= self.verification_level.rank:
            raise ValueError("verification can only be granted at a higher level")
        at = at or datetime.now(UTC)
        self.verification_level = level
        return (VerificationGranted.create(self.user_id, level, at), *self._refresh_score("verification_granted", at))

    def revoke_verification(self, *, at: datetime | None = None) -> tuple[DomainEvent, ...]:
        if self.verification_level == VerificationLevel.NONE:
            raise ValueError("verification is not currently granted")
        at = at or datetime.now(UTC)
        previous = self.verification_level
        self.verification_level = VerificationLevel.NONE
        return (VerificationRevoked.create(self.user_id, previous, at), *self._refresh_score("verification_revoked", at))

    def record_transaction(self, transaction_id: str, role: TransactionRole,
                           *, at: datetime | None = None) -> tuple[DomainEvent, ...]:
        at = at or datetime.now(UTC)
        self.completed_transactions += 1
        if role == TransactionRole.SALE:
            self.successful_sales += 1
        elif role == TransactionRole.PURCHASE:
            self.successful_purchases += 1
        else:
            self.successful_trades += 1
        return (TransactionRecorded.create(self.user_id, transaction_id, role, at),
                *self._refresh_score("transaction_recorded", at))

    def record_dispute(self, dispute_id: str, outcome: DisputeOutcome,
                       *, at: datetime | None = None) -> tuple[DomainEvent, ...]:
        at = at or datetime.now(UTC)
        if outcome == DisputeOutcome.OPENED:
            self.disputes_opened += 1
        elif outcome == DisputeOutcome.WON:
            self.disputes_won += 1
            self.disputes_opened = max(0, self.disputes_opened - 1)
        else:
            self.disputes_lost += 1
            self.disputes_opened = max(0, self.disputes_opened - 1)
        return (DisputeRecorded.create(self.user_id, dispute_id, outcome, at),
                *self._refresh_score("dispute_recorded", at))

    def record_review(self, review_id: str, *, received: bool, recommended: bool = True,
                      at: datetime | None = None) -> tuple[DomainEvent, ...]:
        at = at or datetime.now(UTC)
        if received:
            self.reviews_received += 1
        else:
            self.reviews_given += 1
        return (ReviewRecorded.create(self.user_id, review_id, received=received,
                                      recommended=recommended, occurred_at=at),
                *self._refresh_score("review_recorded", at))

    def to_public_profile(self) -> PublicTrustProfile:
        return PublicTrustProfile(
            user_id=self.user_id, trust_score=self.trust_score,
            verification_badge=self.verification_level.value,
            completed_deals=self.completed_transactions,
            recommendations=self.reviews_received,
            response_rate=None, response_time=None, member_since=self.created_at,
        )

    def _refresh_score(self, reason: str, at: datetime) -> tuple[DomainEvent, ...]:
        previous = self.trust_score
        self.trust_score = self._calculator.calculate(self, now=at)
        self.last_activity = at.astimezone(UTC)
        self.updated_at = at.astimezone(UTC)
        if previous == self.trust_score:
            return ()
        return (TrustScoreChanged.create(self.user_id, previous, self.trust_score, reason, at),)

