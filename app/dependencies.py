from __future__ import annotations

import os
import sys
from typing import Any

# Ensure sibling licos-core is importable when running the app from the repo root.
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LICOS_ROOT = os.path.abspath(os.path.join(ROOT_DIR, "..", "..", "200_LICOS", "licos-core"))
if os.path.isdir(LICOS_ROOT) and LICOS_ROOT not in sys.path:
    sys.path.insert(0, LICOS_ROOT)

from infrastructure.repositories.memory import (
    MemoryListingRepository,
    MemoryReservationRepository,
    MemoryUserRepository,
)
from kernel.events.store import EventStore
from kernel.integration.recorder import EventRecorder
from application.marketplace.service import MarketplaceService

user_repository = MemoryUserRepository()
listing_repository = MemoryListingRepository()
reservation_repository = MemoryReservationRepository()
event_store = EventStore()
event_recorder = EventRecorder(event_store)
marketplace_service = MarketplaceService(
    user_repository=user_repository,
    listing_repository=listing_repository,
    reservation_repository=reservation_repository,
    event_recorder=event_recorder,
)


def get_user_repository() -> MemoryUserRepository:
    return user_repository


def get_listing_repository() -> MemoryListingRepository:
    return listing_repository


def get_reservation_repository() -> MemoryReservationRepository:
    return reservation_repository


def get_event_store() -> EventStore:
    return event_store


def get_event_recorder() -> EventRecorder:
    return event_recorder


def get_marketplace_service() -> MarketplaceService:
    return marketplace_service
