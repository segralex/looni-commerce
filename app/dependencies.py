from __future__ import annotations

import os
import sys
from typing import Any

# Ensure sibling licos-core is importable when running the app from the repo root.
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LICOS_ROOT = os.path.abspath(os.path.join(ROOT_DIR, "..", "..", "200_LICOS", "licos-core"))
if os.path.isdir(LICOS_ROOT) and LICOS_ROOT not in sys.path:
    sys.path.insert(0, LICOS_ROOT)

from infrastructure.config.settings import settings
from infrastructure.repositories.memory import (
    MemoryListingRepository,
    MemoryReservationRepository,
    MemoryUserRepository,
)
from infrastructure.sqlite.database import Database
from infrastructure.sqlite.listing_repository import SQLiteListingRepository
from infrastructure.sqlite.reservation_repository import SQLiteReservationRepository
from infrastructure.sqlite.user_repository import SQLiteUserRepository
from kernel.events.store import EventStore
from kernel.integration.recorder import EventRecorder
from application.marketplace.service import MarketplaceService


def _build_repositories() -> tuple[Any, Any, Any]:
    """Construct and return (user_repo, listing_repo, reservation_repo) based on settings."""
    backend = settings.repository_backend
    if backend == "memory":
        return (
            MemoryUserRepository(),
            MemoryListingRepository(),
            MemoryReservationRepository(),
        )
    if backend == "sqlite":
        db_path = settings.database_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db = Database(str(db_path))
        return (
            SQLiteUserRepository(db),
            SQLiteListingRepository(db),
            SQLiteReservationRepository(db),
        )
    raise ValueError(
        f"Unknown repository backend '{backend}'. Supported: 'memory', 'sqlite'."
    )


user_repository, listing_repository, reservation_repository = _build_repositories()
event_store = EventStore()
event_recorder = EventRecorder(event_store)
marketplace_service = MarketplaceService(
    user_repository=user_repository,
    listing_repository=listing_repository,
    reservation_repository=reservation_repository,
    event_recorder=event_recorder,
)


def reset_singletons() -> None:
    """Reset all singleton dependencies, re-reading current settings/environment.

    Intended for tests only. Rebuilds repositories according to the active backend
    so that environment-variable overrides take effect between tests.
    """
    global user_repository, listing_repository, reservation_repository
    global event_store, event_recorder, marketplace_service

    user_repository, listing_repository, reservation_repository = _build_repositories()
    event_store = EventStore()
    event_recorder = EventRecorder(event_store)
    marketplace_service = MarketplaceService(
        user_repository=user_repository,
        listing_repository=listing_repository,
        reservation_repository=reservation_repository,
        event_recorder=event_recorder,
    )


def get_user_repository() -> Any:
    return user_repository


def get_listing_repository() -> Any:
    return listing_repository


def get_reservation_repository() -> Any:
    return reservation_repository


def get_event_store() -> EventStore:
    return event_store


def get_event_recorder() -> EventRecorder:
    return event_recorder


def get_marketplace_service() -> MarketplaceService:
    return marketplace_service
