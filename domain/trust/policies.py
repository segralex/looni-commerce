from __future__ import annotations

from dataclasses import dataclass, field

from domain.trust.models import VerificationLevel


@dataclass(frozen=True, slots=True)
class TrustScorePolicy:
    minimum_score: int = 0
    maximum_score: int = 1000
    base_score: int = 100
    completed_transaction_points: int = 20
    completed_transaction_cap: int = 400
    account_age_points_per_month: int = 2
    account_age_cap: int = 120
    review_points: int = 4
    review_cap: int = 160
    dispute_won_points: int = 5
    dispute_lost_penalty: int = 75
    open_dispute_penalty: int = 10
    cancelled_transaction_penalty: int = 20
    confirmed_fraud_penalty: int = 700
    verification_points: dict[VerificationLevel, int] = field(default_factory=lambda: {
        VerificationLevel.NONE: 0,
        VerificationLevel.EMAIL: 40,
        VerificationLevel.PHONE: 80,
        VerificationLevel.IDENTITY: 160,
        VerificationLevel.BUSINESS: 220,
    })


DEFAULT_TRUST_SCORE_POLICY = TrustScorePolicy()

