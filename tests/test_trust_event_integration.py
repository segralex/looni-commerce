from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from application.trust.handlers import TrustEventHandlers
from domain.events.base import DomainEvent
from domain.events.registry import EventRegistry
from domain.events.serialization import register_event_class
from domain.trust.events import TransactionRecorded, TrustScoreChanged
from infrastructure.events.in_process_dispatcher import InProcessEventDispatcher
from infrastructure.events.outbox_worker import OutboxWorker
from infrastructure.repositories.memory import MemoryOutboxRepository, MemoryTrustRepository


@dataclass(frozen=True, slots=True, kw_only=True)
class TransactionCompleted(DomainEvent):
    buyer_id: str
    seller_id: str
    transaction_id: str


register_event_class("TransactionCompleted", TransactionCompleted)
register_event_class("ReservationCompleted", TransactionCompleted)


def test_transaction_event_updates_both_participants_and_emits_causal_outbox_events() -> None:
    trust_repository = MemoryTrustRepository()
    outbox = MemoryOutboxRepository()
    handlers = TrustEventHandlers(trust_repository, outbox)
    registry = EventRegistry()
    registry.register("TransactionCompleted", handlers.transaction_completed)
    dispatcher = InProcessEventDispatcher(registry)
    source = TransactionCompleted(
        event_id="source-event", event_type="TransactionCompleted",
        aggregate_type="Transaction", aggregate_id="transaction-1",
        occurred_at=datetime(2026, 7, 22, tzinfo=UTC), correlation_id="correlation-1",
        buyer_id="buyer-1", seller_id="seller-1", transaction_id="transaction-1",
    )

    dispatcher.dispatch(source)

    buyer = trust_repository.get("buyer-1")
    seller = trust_repository.get("seller-1")
    assert buyer is not None and buyer.successful_purchases == 1
    assert seller is not None and seller.successful_sales == 1
    emitted = outbox.query(correlation_id="correlation-1")
    assert len(emitted) == 4
    assert all(entry.event.causation_id == source.event_id for entry in emitted)
    assert sum(isinstance(entry.event, TransactionRecorded) for entry in emitted) == 2
    assert sum(isinstance(entry.event, TrustScoreChanged) for entry in emitted) == 2


def test_existing_outbox_pipeline_delivers_marketplace_event_to_trust_engine() -> None:
    trust_repository = MemoryTrustRepository()
    outbox = MemoryOutboxRepository()
    handlers = TrustEventHandlers(trust_repository, outbox)
    dispatcher = InProcessEventDispatcher()
    dispatcher.register("ReservationCompleted", handlers.transaction_completed)
    source = TransactionCompleted(
        event_id="reservation-event", event_type="ReservationCompleted",
        aggregate_type="Reservation", aggregate_id="reservation-1",
        occurred_at=datetime(2026, 7, 22, tzinfo=UTC),
        buyer_id="buyer-2", seller_id="seller-2", transaction_id="reservation-1",
    )
    entry = outbox.save(source)

    processed = OutboxWorker(outbox, dispatcher).run_once(limit=1)

    assert processed == 1
    assert outbox.get(entry.id).published is True  # type: ignore[union-attr]
    assert trust_repository.get("buyer-2").completed_transactions == 1  # type: ignore[union-attr]
    assert trust_repository.get("seller-2").completed_transactions == 1  # type: ignore[union-attr]
