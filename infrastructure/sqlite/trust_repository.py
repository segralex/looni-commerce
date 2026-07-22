from __future__ import annotations

from datetime import datetime

from domain.trust.aggregate import TrustAggregate
from domain.trust.models import VerificationLevel
from infrastructure.sqlite.database import Database


class SQLiteTrustRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def get(self, user_id: str) -> TrustAggregate | None:
        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM trust_profiles WHERE user_id = ?", (str(user_id),))
        row = cur.fetchone()
        return self._hydrate(row) if row is not None else None

    def save(self, aggregate: TrustAggregate) -> None:
        conn = self.db.connect()
        conn.execute(
            """
            INSERT INTO trust_profiles (
                user_id, trust_score, verification_level, completed_transactions,
                successful_sales, successful_purchases, successful_trades,
                reviews_received, reviews_given, disputes_opened, disputes_won,
                disputes_lost, last_activity, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                trust_score=excluded.trust_score,
                verification_level=excluded.verification_level,
                completed_transactions=excluded.completed_transactions,
                successful_sales=excluded.successful_sales,
                successful_purchases=excluded.successful_purchases,
                successful_trades=excluded.successful_trades,
                reviews_received=excluded.reviews_received,
                reviews_given=excluded.reviews_given,
                disputes_opened=excluded.disputes_opened,
                disputes_won=excluded.disputes_won,
                disputes_lost=excluded.disputes_lost,
                last_activity=excluded.last_activity,
                updated_at=excluded.updated_at
            """,
            (
                aggregate.user_id, aggregate.trust_score, aggregate.verification_level.value,
                aggregate.completed_transactions, aggregate.successful_sales,
                aggregate.successful_purchases, aggregate.successful_trades,
                aggregate.reviews_received, aggregate.reviews_given,
                aggregate.disputes_opened, aggregate.disputes_won, aggregate.disputes_lost,
                aggregate.last_activity.isoformat() if aggregate.last_activity else None,
                aggregate.created_at.isoformat(), aggregate.updated_at.isoformat(),
            ),
        )
        conn.commit()

    def all(self) -> tuple[TrustAggregate, ...]:
        rows = self.db.connect().execute(
            "SELECT * FROM trust_profiles ORDER BY created_at ASC, user_id ASC"
        ).fetchall()
        return tuple(self._hydrate(row) for row in rows)

    @staticmethod
    def _hydrate(row) -> TrustAggregate:
        return TrustAggregate(
            user_id=row["user_id"], trust_score=int(row["trust_score"]),
            verification_level=VerificationLevel(row["verification_level"]),
            completed_transactions=int(row["completed_transactions"]),
            successful_sales=int(row["successful_sales"]),
            successful_purchases=int(row["successful_purchases"]),
            successful_trades=int(row["successful_trades"]),
            reviews_received=int(row["reviews_received"]), reviews_given=int(row["reviews_given"]),
            disputes_opened=int(row["disputes_opened"]), disputes_won=int(row["disputes_won"]),
            disputes_lost=int(row["disputes_lost"]),
            last_activity=datetime.fromisoformat(row["last_activity"]) if row["last_activity"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
