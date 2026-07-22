from __future__ import annotations

import os
import sys
from typing import Any

# Ensure sibling licos-core is importable when running the app from the repo root.
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LICOS_ROOT = os.path.abspath(os.path.join(ROOT_DIR, "..", "..", "200_LICOS", "licos-core"))
if os.path.isdir(LICOS_ROOT) and LICOS_ROOT not in sys.path:
    sys.path.insert(0, LICOS_ROOT)

from pathlib import Path
from infrastructure.config.settings import settings
from infrastructure.events.in_process_dispatcher import InProcessEventDispatcher
from infrastructure.events.outbox_worker import OutboxWorker
from domain.events.metrics import EventMetrics
from domain.events.registry import EventRegistry
from infrastructure.media.pillow_validator import PillowImageValidator
from infrastructure.repositories.memory import (
    MemoryListingRepository,
    MemoryListingImageRepository,
    MemoryOutboxRepository,
    MemoryReservationRepository,
    MemoryUserRepository,
)
from infrastructure.sqlite.database import Database
from infrastructure.sqlite.listing_image_repository import SQLiteListingImageRepository
from infrastructure.sqlite.listing_repository import SQLiteListingRepository
from infrastructure.sqlite.outbox_repository import SQLiteOutboxRepository
from infrastructure.sqlite.reservation_repository import SQLiteReservationRepository
from infrastructure.sqlite.search_repository import SQLiteSearchRepository
from infrastructure.sqlite.user_repository import SQLiteUserRepository
from infrastructure.sqlite.trust_repository import SQLiteTrustRepository
from infrastructure.security.credentials import MemoryCredentialRepository
from infrastructure.media.pillow_processor import PillowImageProcessor
from infrastructure.storage.local import LocalStorageProvider
from kernel.events.store import EventStore
from kernel.integration.recorder import EventRecorder
from application.marketplace.service import MarketplaceService
from application.media.service import MediaService
from application.media.thumbnail_service import ThumbnailService
from application.media.image_uploaded_handler import ImageUploadedHandler
from domain.media.events import ImageUploaded
from infrastructure.repositories.memory import MemoryTrustRepository
from application.trust.handlers import TrustEventHandlers


class _EventPipelineController:
    def __init__(self, dispatcher: InProcessEventDispatcher, worker: OutboxWorker) -> None:
        self._dispatcher = dispatcher
        self._worker = worker

    def register(self, event_type: type[object], handler) -> None:
        self._dispatcher.register(event_type, handler)

    def publish(self, event: object) -> None:
        self._dispatcher.publish(event)

    def dispatch(self, event: object) -> None:
        self._dispatcher.dispatch(event)

    def start(self) -> None:
        self._dispatcher.start()
        self._worker.start()

    def stop(self) -> None:
        self._worker.stop()
        self._dispatcher.stop()

    def wait_until_idle(self, timeout: float | None = None) -> bool:
        if not self._worker.wait_until_idle(timeout=timeout):
            return False
        return self._dispatcher.wait_until_idle(timeout=timeout)


def _register_event_handlers(
    registry: EventRegistry, image_handler: ImageUploadedHandler,
    trust_handlers: TrustEventHandlers,
) -> None:
    registry.register(ImageUploaded, image_handler.handle)
    for event_type in ("TransactionCompleted", "ReservationCompleted", "PaymentReleased"):
        registry.register(event_type, trust_handlers.transaction_completed)
    registry.register("ReviewSubmitted", trust_handlers.review_submitted)
    registry.register("DisputeResolved", trust_handlers.dispute_resolved)


def _build_repositories() -> tuple[Any, Any, Any, Any, Any, Any]:
    """Construct and return repositories based on settings."""
    backend = settings.repository_backend
    if backend == "memory":
        return (
            MemoryUserRepository(),
            MemoryListingRepository(),
            MemoryReservationRepository(),
            MemoryListingImageRepository(),
            MemoryOutboxRepository(event_metrics),
            MemoryTrustRepository(),
        )
    if backend == "sqlite":
        db_path = settings.database_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db = Database(str(db_path))
        return (
            SQLiteUserRepository(db),
            SQLiteListingRepository(db),
            SQLiteReservationRepository(db),
            SQLiteListingImageRepository(db),
            SQLiteOutboxRepository(db, event_metrics),
            SQLiteTrustRepository(db),
        )
    raise ValueError(
        f"Unknown repository backend '{backend}'. Supported: 'memory', 'sqlite'."
    )


event_metrics = EventMetrics()
user_repository, listing_repository, reservation_repository, image_repository, outbox_repository, trust_repository = _build_repositories()
credential_repository = MemoryCredentialRepository()
event_store = EventStore()
event_recorder = EventRecorder(event_store)
storage_provider = LocalStorageProvider(Path(settings.storage_path))
thumbnail_service = ThumbnailService(PillowImageProcessor(), storage_provider)
image_validator = PillowImageValidator()
event_registry = EventRegistry()
event_dispatcher = InProcessEventDispatcher(event_registry, event_metrics)
outbox_worker = OutboxWorker(
    outbox=outbox_repository,
    dispatcher=event_dispatcher,
    poll_interval_seconds=settings.outbox_poll_interval_seconds,
    max_retry_count=settings.outbox_max_retry_count,
    metrics=event_metrics,
)
if hasattr(outbox_repository, "set_notifier"):
    outbox_repository.set_notifier(outbox_worker.wake)
event_pipeline = _EventPipelineController(event_dispatcher, outbox_worker)
image_uploaded_handler = ImageUploadedHandler(
    image_repo=image_repository,
    storage=storage_provider,
    thumbnail_service=thumbnail_service,
)
trust_event_handlers = TrustEventHandlers(trust_repository, outbox_repository)
_register_event_handlers(event_registry, image_uploaded_handler, trust_event_handlers)
event_pipeline.start()
media_service = MediaService(
    image_repo=image_repository,
    storage=storage_provider,
    listing_lookup=listing_repository.get,
    thumbnail_service=thumbnail_service,
    outbox=outbox_repository,
    image_validator=image_validator,
)
marketplace_service = MarketplaceService(
    user_repository=user_repository,
    listing_repository=listing_repository,
    reservation_repository=reservation_repository,
    event_recorder=event_recorder,
    media_service=media_service,
)
search_repository = None
if settings.repository_backend == "sqlite":
    # Listing repository was created with a shared Database instance in sqlite mode.
    search_repository = SQLiteSearchRepository(listing_repository.db)


def reset_singletons() -> None:
    """Reset all singleton dependencies, re-reading current settings/environment.

    Intended for tests only. Rebuilds repositories according to the active backend
    so that environment-variable overrides take effect between tests.
    """
    global user_repository, listing_repository, reservation_repository, image_repository
    global outbox_repository
    global trust_repository, trust_event_handlers
    global credential_repository, event_store, event_recorder, marketplace_service, search_repository
    global storage_provider, media_service
    global thumbnail_service, image_validator, event_registry, event_dispatcher, outbox_worker, event_pipeline, image_uploaded_handler, event_metrics

    try:
        event_pipeline.stop()
    except Exception:
        pass

    event_metrics = EventMetrics()
    user_repository, listing_repository, reservation_repository, image_repository, outbox_repository, trust_repository = _build_repositories()
    credential_repository = MemoryCredentialRepository()
    event_store = EventStore()
    event_recorder = EventRecorder(event_store)
    storage_provider = LocalStorageProvider(Path(settings.storage_path))
    thumbnail_service = ThumbnailService(PillowImageProcessor(), storage_provider)
    image_validator = PillowImageValidator()
    event_registry = EventRegistry()
    event_dispatcher = InProcessEventDispatcher(event_registry, event_metrics)
    outbox_worker = OutboxWorker(
        outbox=outbox_repository,
        dispatcher=event_dispatcher,
        poll_interval_seconds=settings.outbox_poll_interval_seconds,
        max_retry_count=settings.outbox_max_retry_count,
        metrics=event_metrics,
    )
    if hasattr(outbox_repository, "set_notifier"):
        outbox_repository.set_notifier(outbox_worker.wake)
    event_pipeline = _EventPipelineController(event_dispatcher, outbox_worker)
    image_uploaded_handler = ImageUploadedHandler(
        image_repo=image_repository,
        storage=storage_provider,
        thumbnail_service=thumbnail_service,
    )
    trust_event_handlers = TrustEventHandlers(trust_repository, outbox_repository)
    _register_event_handlers(event_registry, image_uploaded_handler, trust_event_handlers)
    event_pipeline.start()
    media_service = MediaService(
        image_repo=image_repository,
        storage=storage_provider,
        listing_lookup=listing_repository.get,
        thumbnail_service=thumbnail_service,
        outbox=outbox_repository,
        image_validator=image_validator,
    )
    marketplace_service = MarketplaceService(
        user_repository=user_repository,
        listing_repository=listing_repository,
        reservation_repository=reservation_repository,
        event_recorder=event_recorder,
        media_service=media_service,
    )
    search_repository = None
    if settings.repository_backend == "sqlite":
        search_repository = SQLiteSearchRepository(listing_repository.db)


def get_user_repository() -> Any:
    return user_repository


def get_listing_repository() -> Any:
    return listing_repository


def get_reservation_repository() -> Any:
    return reservation_repository


def get_credential_repository() -> MemoryCredentialRepository:
    return credential_repository


def get_event_store() -> EventStore:
    return event_store


def get_event_recorder() -> EventRecorder:
    return event_recorder


def get_marketplace_service() -> MarketplaceService:
    return marketplace_service


def get_image_repository() -> Any:
    return image_repository


def get_storage_provider() -> LocalStorageProvider:
    return storage_provider


def get_media_service() -> MediaService:
    return media_service


def get_event_dispatcher() -> _EventPipelineController:
    return event_pipeline


def get_outbox_worker() -> OutboxWorker:
    return outbox_worker


def get_outbox_repository() -> Any:
    return outbox_repository


def get_event_metrics() -> EventMetrics:
    return event_metrics


def get_trust_repository() -> Any:
    return trust_repository


def get_search_repository() -> Any:
    return search_repository
