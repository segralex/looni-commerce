from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class DomainEvent:
    event_id: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    occurred_at: datetime
    correlation_id: str | None = None
    causation_id: str | None = None
    schema_version: int = 1

    def __post_init__(self) -> None:
        # Resolve lineage at construction time so every event subtype benefits,
        # including events created directly inside a handler.
        from domain.events.context import get_causation_id, get_correlation_id

        if self.correlation_id is None:
            object.__setattr__(self, "correlation_id", get_correlation_id())
        if self.causation_id is None:
            object.__setattr__(self, "causation_id", get_causation_id())
        if not self.event_id:
            raise ValueError("event_id is required")
        if not self.event_type:
            raise ValueError("event_type is required")
        if not self.aggregate_type:
            raise ValueError("aggregate_type is required")
        if not self.aggregate_id:
            raise ValueError("aggregate_id is required")
        if self.schema_version < 1:
            raise ValueError("schema_version must be >= 1")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        if self.occurred_at.tzinfo != UTC:
            object.__setattr__(self, "occurred_at", self.occurred_at.astimezone(UTC))
