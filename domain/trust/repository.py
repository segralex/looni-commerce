from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from domain.trust.aggregate import TrustAggregate


class TrustRepository(Protocol):
    def get(self, user_id: str) -> "TrustAggregate | None": ...

    def save(self, aggregate: "TrustAggregate") -> None: ...

    def all(self) -> tuple["TrustAggregate", ...]: ...
