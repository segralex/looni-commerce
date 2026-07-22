from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from domain.trust.models import VerificationLevel
from domain.trust.policies import DEFAULT_TRUST_SCORE_POLICY, TrustScorePolicy


class TrustEvidence(Protocol):
    verification_level: VerificationLevel
    completed_transactions: int
    reviews_received: int
    disputes_opened: int
    disputes_won: int
    disputes_lost: int
    created_at: datetime


class TrustScoreCalculator:
    def __init__(self, policy: TrustScorePolicy = DEFAULT_TRUST_SCORE_POLICY) -> None:
        self.policy = policy

    def calculate(
        self, evidence: TrustEvidence, *, now: datetime | None = None,
        cancelled_transactions: int = 0, confirmed_fraud: int = 0,
    ) -> int:
        now = now or datetime.now(UTC)
        age_months = max(0, (now - evidence.created_at).days // 30)
        score = self.policy.base_score
        score += min(
            evidence.completed_transactions * self.policy.completed_transaction_points,
            self.policy.completed_transaction_cap,
        )
        score += self.policy.verification_points[evidence.verification_level]
        score += min(age_months * self.policy.account_age_points_per_month, self.policy.account_age_cap)
        score += min(evidence.reviews_received * self.policy.review_points, self.policy.review_cap)
        score += evidence.disputes_won * self.policy.dispute_won_points
        score -= evidence.disputes_lost * self.policy.dispute_lost_penalty
        score -= evidence.disputes_opened * self.policy.open_dispute_penalty
        score -= cancelled_transactions * self.policy.cancelled_transaction_penalty
        score -= confirmed_fraud * self.policy.confirmed_fraud_penalty
        return max(self.policy.minimum_score, min(self.policy.maximum_score, score))

