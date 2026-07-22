from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from domain.events.base import DomainEvent
from domain.events.serialization import deserialize_event, serialize_event
from domain.trust.aggregate import TrustAggregate
from domain.trust.events import (
    DisputeRecorded, ReviewRecorded, TransactionRecorded, TrustScoreChanged,
    VerificationGranted, VerificationRevoked,
)
from domain.trust.models import DisputeOutcome, TransactionRole, VerificationLevel
from domain.trust.score import TrustScoreCalculator


NOW = datetime(2026, 7, 22, tzinfo=UTC)


def test_trust_aggregate_records_each_transaction_role_and_recalculates_score() -> None:
    trust = TrustAggregate(user_id="user-1", created_at=NOW, updated_at=NOW)
    emitted = (
        *trust.record_transaction("sale-1", TransactionRole.SALE, at=NOW),
        *trust.record_transaction("purchase-1", TransactionRole.PURCHASE, at=NOW),
        *trust.record_transaction("trade-1", TransactionRole.TRADE, at=NOW),
    )

    assert trust.completed_transactions == 3
    assert (trust.successful_sales, trust.successful_purchases, trust.successful_trades) == (1, 1, 1)
    assert trust.trust_score == 160
    assert sum(isinstance(event, TransactionRecorded) for event in emitted) == 3
    assert any(isinstance(event, TrustScoreChanged) for event in emitted)


def test_verification_is_ordered_future_proof_and_revocable() -> None:
    trust = TrustAggregate(user_id="business-1", created_at=NOW, updated_at=NOW)
    granted = trust.grant_verification(VerificationLevel.BUSINESS, at=NOW)
    assert trust.verification_level == VerificationLevel.BUSINESS
    assert trust.trust_score == 320
    assert isinstance(granted[0], VerificationGranted)
    with pytest.raises(ValueError, match="higher level"):
        trust.grant_verification(VerificationLevel.EMAIL, at=NOW)

    revoked = trust.revoke_verification(at=NOW)
    assert trust.verification_level == VerificationLevel.NONE
    assert isinstance(revoked[0], VerificationRevoked)


def test_dispute_review_and_public_profile_hide_internal_evidence() -> None:
    trust = TrustAggregate(user_id="user-2", created_at=NOW, updated_at=NOW)
    trust.record_dispute("d-1", DisputeOutcome.OPENED, at=NOW)
    trust.record_dispute("d-1", DisputeOutcome.LOST, at=NOW)
    trust.record_review("r-1", received=True, recommended=True, at=NOW)
    trust.record_review("r-2", received=False, at=NOW)

    profile = trust.to_public_profile()
    assert trust.disputes_opened == 0
    assert trust.disputes_lost == 1
    assert (trust.reviews_received, trust.reviews_given) == (1, 1)
    assert profile.recommendations == 1
    assert not hasattr(profile, "disputes_lost")
    assert not hasattr(profile, "confirmed_fraud")


def test_weighted_score_accounts_for_age_evidence_penalties_and_bounds() -> None:
    trust = TrustAggregate(
        user_id="user-3", verification_level=VerificationLevel.IDENTITY,
        completed_transactions=100, reviews_received=100, disputes_won=2,
        created_at=NOW - timedelta(days=365 * 5), updated_at=NOW,
    )
    calculator = TrustScoreCalculator()
    assert calculator.calculate(trust, now=NOW) == 950
    assert calculator.calculate(trust, now=NOW, confirmed_fraud=2) == 0


@pytest.mark.parametrize("event_type", [
    TrustScoreChanged, VerificationGranted, VerificationRevoked,
    TransactionRecorded, DisputeRecorded, ReviewRecorded,
])
def test_trust_events_inherit_domain_event(event_type) -> None:
    factories = {
        TrustScoreChanged: lambda: TrustScoreChanged.create("u", 100, 120, "test", NOW),
        VerificationGranted: lambda: VerificationGranted.create("u", VerificationLevel.EMAIL, NOW),
        VerificationRevoked: lambda: VerificationRevoked.create("u", VerificationLevel.EMAIL, NOW),
        TransactionRecorded: lambda: TransactionRecorded.create("u", "t", TransactionRole.SALE, NOW),
        DisputeRecorded: lambda: DisputeRecorded.create("u", "d", DisputeOutcome.WON, NOW),
        ReviewRecorded: lambda: ReviewRecorded.create("u", "r", received=True, occurred_at=NOW),
    }
    event = factories[event_type]()
    assert isinstance(event, DomainEvent)
    assert deserialize_event(serialize_event(event)) == event
    with pytest.raises(FrozenInstanceError):
        event.aggregate_id = "changed"  # type: ignore[misc]

