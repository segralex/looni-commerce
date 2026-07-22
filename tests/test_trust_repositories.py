from __future__ import annotations

from datetime import UTC, datetime

import pytest

from domain.trust.aggregate import TrustAggregate
from domain.trust.models import TransactionRole, VerificationLevel
from infrastructure.repositories.memory import MemoryTrustRepository
from infrastructure.sqlite.database import Database
from infrastructure.sqlite.trust_repository import SQLiteTrustRepository


@pytest.mark.parametrize("backend", ["memory", "sqlite"])
def test_trust_repository_create_update_and_roundtrip(backend: str, tmp_path) -> None:
    repository = (MemoryTrustRepository() if backend == "memory" else
                  SQLiteTrustRepository(Database(str(tmp_path / "trust.db"))))
    now = datetime(2026, 7, 22, tzinfo=UTC)
    trust = TrustAggregate(user_id="user-1", created_at=now, updated_at=now)
    trust.grant_verification(VerificationLevel.IDENTITY, at=now)
    trust.record_transaction("transaction-1", TransactionRole.SALE, at=now)
    repository.save(trust)

    loaded = repository.get("user-1")
    assert loaded is not None
    assert loaded == trust
    assert repository.get("missing") is None
    assert repository.all() == (trust,)

    loaded.record_transaction("transaction-2", TransactionRole.PURCHASE, at=now)
    repository.save(loaded)
    assert repository.get("user-1").completed_transactions == 2  # type: ignore[union-attr]


def test_sqlite_trust_schema_has_requested_indexes(tmp_path) -> None:
    database = Database(str(tmp_path / "indexes.db"))
    rows = database.connect().execute("PRAGMA index_list(trust_profiles)").fetchall()
    names = {row["name"] for row in rows}
    assert "idx_trust_profiles_user_id" in names
    assert "idx_trust_profiles_trust_score" in names

