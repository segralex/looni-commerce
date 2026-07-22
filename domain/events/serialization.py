from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import datetime
from typing import Any

from domain.events.base import DomainEvent

_BASE_FIELD_NAMES = {
    "event_id",
    "event_type",
    "aggregate_type",
    "aggregate_id",
    "occurred_at",
    "correlation_id",
    "causation_id",
    "schema_version",
}

_EVENT_TYPE_REGISTRY: dict[str, type[DomainEvent]] = {}


def register_event_class(event_type: str, event_class: type[DomainEvent]) -> None:
    _EVENT_TYPE_REGISTRY[event_type] = event_class


def serialize_event(event: DomainEvent) -> dict[str, Any]:
    if not is_dataclass(event):
        raise TypeError("event must be a dataclass instance")

    payload: dict[str, Any] = {}
    for f in fields(event):
        if f.name in _BASE_FIELD_NAMES:
            continue
        payload[f.name] = getattr(event, f.name)

    return {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "aggregate_type": event.aggregate_type,
        "aggregate_id": event.aggregate_id,
        "occurred_at": event.occurred_at.isoformat(),
        "correlation_id": event.correlation_id,
        "causation_id": event.causation_id,
        "schema_version": event.schema_version,
        "payload": payload,
    }


def deserialize_event(data: dict[str, Any]) -> DomainEvent:
    event_type = str(data["event_type"])
    event_class = _EVENT_TYPE_REGISTRY.get(event_type, DomainEvent)

    event_kwargs: dict[str, Any] = {
        "event_id": str(data["event_id"]),
        "event_type": event_type,
        "aggregate_type": str(data["aggregate_type"]),
        "aggregate_id": str(data["aggregate_id"]),
        "occurred_at": datetime.fromisoformat(str(data["occurred_at"])),
        "correlation_id": data.get("correlation_id"),
        "causation_id": data.get("causation_id"),
        "schema_version": int(data.get("schema_version", 1)),
    }

    payload = data.get("payload") or {}
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    event_kwargs.update(payload)

    return event_class(**event_kwargs)
