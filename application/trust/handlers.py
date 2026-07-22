from __future__ import annotations

from datetime import UTC, datetime
import threading
from typing import Any

from domain.events.outbox import OutboxRepository
from domain.trust.aggregate import TrustAggregate
from domain.trust.models import DisputeOutcome, TransactionRole
from domain.trust.repository import TrustRepository


class TrustEventHandlers:
    """Adapters from marketplace integration events into trust evidence."""

    def __init__(self, repository: TrustRepository, outbox: OutboxRepository) -> None:
        self.repository = repository
        self.outbox = outbox
        self._lock = threading.RLock()

    def transaction_completed(self, event: object) -> None:
        event_id = self._identity(event, "transaction_id", "reservation_id", "payment_id")
        at = self._occurred_at(event)
        participants = (
            (self._value(event, "seller_id", "payee_id", "provider_id"), TransactionRole.SALE),
            (self._value(event, "buyer_id", "payer_id", "customer_id"), TransactionRole.PURCHASE),
        )
        seen: set[str] = set()
        for user_id, role in participants:
            if user_id is not None and str(user_id) not in seen:
                seen.add(str(user_id))
                self._update(str(user_id), lambda trust, role=role: trust.record_transaction(event_id, role, at=at), at)
        if not seen:
            user_id = self._value(event, "user_id", "participant_id")
            if user_id is not None:
                self._update(str(user_id), lambda trust: trust.record_transaction(event_id, TransactionRole.TRADE, at=at), at)

    def review_submitted(self, event: object) -> None:
        review_id = self._identity(event, "review_id")
        at = self._occurred_at(event)
        recommended = bool(getattr(event, "recommended", True))
        author = self._value(event, "reviewer_id", "author_id", "from_user_id")
        recipient = self._value(event, "reviewee_id", "subject_id", "to_user_id", "user_id")
        if author is not None:
            self._update(str(author), lambda trust: trust.record_review(
                review_id, received=False, recommended=recommended, at=at), at)
        if recipient is not None and str(recipient) != str(author):
            self._update(str(recipient), lambda trust: trust.record_review(
                review_id, received=True, recommended=recommended, at=at), at)

    def dispute_resolved(self, event: object) -> None:
        dispute_id = self._identity(event, "dispute_id")
        at = self._occurred_at(event)
        winner = self._value(event, "winner_id", "resolved_for_user_id")
        loser = self._value(event, "loser_id", "resolved_against_user_id")
        if winner is not None:
            self._update(str(winner), lambda trust: trust.record_dispute(dispute_id, DisputeOutcome.WON, at=at), at)
        if loser is not None and str(loser) != str(winner):
            self._update(str(loser), lambda trust: trust.record_dispute(dispute_id, DisputeOutcome.LOST, at=at), at)
        if winner is None and loser is None:
            user_id = self._value(event, "user_id")
            raw_outcome = str(getattr(event, "outcome", "LOST")).upper()
            outcome = DisputeOutcome.WON if raw_outcome == "WON" else DisputeOutcome.LOST
            if user_id is not None:
                self._update(str(user_id), lambda trust: trust.record_dispute(dispute_id, outcome, at=at), at)

    def _update(self, user_id: str, operation, at: datetime) -> None:
        with self._lock:
            aggregate = self.repository.get(user_id) or TrustAggregate(
                user_id=user_id, created_at=at, updated_at=at,
            )
            events = operation(aggregate)
            self.repository.save(aggregate)
            for event in events:
                self.outbox.save(event)

    @staticmethod
    def _value(event: object, *names: str) -> Any | None:
        for name in names:
            value = getattr(event, name, None)
            if value is not None:
                return value
        return None

    @classmethod
    def _identity(cls, event: object, *names: str) -> str:
        value = cls._value(event, *names, "aggregate_id", "event_id")
        if value is None:
            raise ValueError("marketplace event requires an identifier")
        return str(value)

    @staticmethod
    def _occurred_at(event: object) -> datetime:
        value = getattr(event, "occurred_at", None) or datetime.now(UTC)
        if value.tzinfo is None:
            raise ValueError("marketplace event occurred_at must be timezone-aware")
        return value.astimezone(UTC)
