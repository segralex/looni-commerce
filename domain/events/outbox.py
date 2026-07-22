from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from domain.events.base import DomainEvent


class OutboxState(StrEnum):
    PENDING = "PENDING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    DEAD_LETTER = "DEAD_LETTER"


@dataclass(frozen=True, slots=True)
class OutboxEntry:
    id: str
    event: DomainEvent
    published: bool = False
    published_at: datetime | None = None
    retry_count: int = 0
    permanently_failed: bool = False
    failed_at: datetime | None = None
    failure_reason: str | None = None

    @property
    def state(self) -> OutboxState:
        if self.permanently_failed:
            return OutboxState.DEAD_LETTER
        if self.published:
            return OutboxState.PUBLISHED
        return OutboxState.PENDING

    @property
    def status(self) -> OutboxState:
        return self.state


class OutboxRepository(Protocol):
    def save(self, event: DomainEvent) -> OutboxEntry:
        ...

    def get(self, entry_id: str) -> OutboxEntry | None:
        ...

    def list_unpublished(
        self,
        limit: int | None = None,
        max_retry_count: int | None = None,
    ) -> list[OutboxEntry]:
        ...

    def get_unpublished(
        self,
        limit: int | None = None,
        max_retry_count: int | None = None,
    ) -> list[OutboxEntry]:
        ...

    def get_failed(self, limit: int | None = None) -> list[OutboxEntry]:
        ...

    def get_by_aggregate(self, aggregate_type: str, aggregate_id: str) -> list[OutboxEntry]:
        ...

    def query(
        self, *, state: OutboxState | str | None = None,
        status: OutboxState | str | None = None, event_type: str | None = None,
        aggregate_id: str | None = None, correlation_id: str | None = None,
        occurred_from: datetime | None = None, occurred_to: datetime | None = None,
        limit: int | None = None,
    ) -> list[OutboxEntry]:
        ...

    def requeue(self, entry_ids: list[str]) -> list[OutboxEntry]:
        ...

    def mark_published(self, entry_id: str, published_at: datetime) -> OutboxEntry | None:
        ...

    def increment_retry(self, entry_id: str) -> OutboxEntry | None:
        ...

    def mark_failed(
        self,
        entry_id: str,
        failed_at: datetime,
        failure_reason: str | None = None,
    ) -> OutboxEntry | None:
        ...
