from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from domain.repositories import (
    DuplicateEntityError,
    EntityNotFoundError,
    ListingRepository,
    ReservationRepository,
    UserRepository,
)


class _MemoryRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, Any] = {}
        self._order: list[UUID] = []

    def _add(self, entity: Any) -> None:
        entity_id = getattr(entity, "id")
        if entity_id in self._store:
            raise DuplicateEntityError("Duplicate entity id")
        self._store[entity_id] = entity
        self._order.append(entity_id)

    def _get(self, entity_id: UUID) -> Any:
        try:
            return self._store[entity_id]
        except KeyError as exc:
            raise EntityNotFoundError("Entity not found") from exc

    def _save(self, entity: Any) -> None:
        entity_id = getattr(entity, "id")
        if entity_id not in self._store:
            raise EntityNotFoundError("Unknown entity id")
        self._store[entity_id] = entity

    def _all(self) -> tuple[Any, ...]:
        return tuple(self._store[entity_id] for entity_id in self._order)


class MemoryUserRepository(_MemoryRepository, UserRepository):
    def add(self, entity: Any) -> None:
        self._add(entity)

    def get(self, entity_id: UUID) -> Any:
        return self._get(entity_id)

    def save(self, entity: Any) -> None:
        self._save(entity)

    def all(self) -> tuple[Any, ...]:
        return self._all()


class MemoryListingRepository(_MemoryRepository, ListingRepository):
    def add(self, entity: Any) -> None:
        self._add(entity)

    def get(self, entity_id: UUID) -> Any:
        return self._get(entity_id)

    def save(self, entity: Any) -> None:
        self._save(entity)

    def all(self) -> tuple[Any, ...]:
        return self._all()


class MemoryReservationRepository(_MemoryRepository, ReservationRepository):
    def add(self, entity: Any) -> None:
        self._add(entity)

    def get(self, entity_id: UUID) -> Any:
        return self._get(entity_id)

    def save(self, entity: Any) -> None:
        self._save(entity)

    def all(self) -> tuple[Any, ...]:
        return self._all()
