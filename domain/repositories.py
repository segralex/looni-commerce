from __future__ import annotations

from typing import Protocol, runtime_checkable, Any
from uuid import UUID


class EntityNotFoundError(Exception):
    """Raised when a requested entity does not exist."""


class DuplicateEntityError(Exception):
    """Raised when attempting to add an entity with an existing id."""


class UserRepository(Protocol):
    def add(self, entity: Any) -> None:  # pragma: no cover - protocol
        ...

    def get(self, entity_id: UUID) -> Any:  # pragma: no cover - protocol
        ...

    def save(self, entity: Any) -> None:  # pragma: no cover - protocol
        ...

    def all(self) -> tuple:  # pragma: no cover - protocol
        ...


class ListingRepository(Protocol):
    def add(self, entity: Any) -> None:  # pragma: no cover - protocol
        ...

    def get(self, entity_id: UUID) -> Any:  # pragma: no cover - protocol
        ...

    def save(self, entity: Any) -> None:  # pragma: no cover - protocol
        ...

    def all(self) -> tuple:  # pragma: no cover - protocol
        ...


class ReservationRepository(Protocol):
    def add(self, entity: Any) -> None:  # pragma: no cover - protocol
        ...

    def get(self, entity_id: UUID) -> Any:  # pragma: no cover - protocol
        ...

    def save(self, entity: Any) -> None:  # pragma: no cover - protocol
        ...

    def all(self) -> tuple:  # pragma: no cover - protocol
        ...
