from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Dict, Optional
from uuid import UUID, uuid4

from domain.reservations.exceptions import InvalidReservationStateError, ReservationValidationError
from domain.reservations.models import Reservation, ReservationStatus


class ReservationService:
    def __init__(self) -> None:
        self._store: Dict[UUID, Reservation] = {}

    def create_reservation(
        self,
        listing_id: UUID,
        buyer_id: UUID,
        seller_id: UUID,
        expires_at: Optional[datetime] = None,
    ) -> Reservation:
        r = Reservation(
            id=uuid4(),
            listing_id=listing_id,
            buyer_id=buyer_id,
            seller_id=seller_id,
            expires_at=expires_at,
        )
        self._store[r.id] = r
        return deepcopy(r)

    def get_reservation(self, reservation_id: UUID) -> Reservation:
        return deepcopy(self._store[reservation_id])

    def _ensure_not_terminal(self, r: Reservation) -> None:
        if r.status in {
            ReservationStatus.DECLINED,
            ReservationStatus.CANCELLED,
            ReservationStatus.EXPIRED,
            ReservationStatus.COMPLETED,
        }:
            raise InvalidReservationStateError("Terminal reservations cannot be modified")

    def accept(self, reservation_id: UUID) -> Reservation:
        r = self._store.get(reservation_id)
        if r is None:
            raise KeyError(reservation_id)
        if r.status != ReservationStatus.PENDING:
            raise InvalidReservationStateError("Can only accept PENDING reservations")
        r.status = ReservationStatus.ACCEPTED
        r.updated_at = datetime.now(UTC)
        self._store[r.id] = r
        return deepcopy(r)

    def decline(self, reservation_id: UUID) -> Reservation:
        r = self._store.get(reservation_id)
        if r is None:
            raise KeyError(reservation_id)
        if r.status != ReservationStatus.PENDING:
            raise InvalidReservationStateError("Can only decline PENDING reservations")
        r.status = ReservationStatus.DECLINED
        r.updated_at = datetime.now(UTC)
        self._store[r.id] = r
        return deepcopy(r)

    def cancel(self, reservation_id: UUID) -> Reservation:
        r = self._store.get(reservation_id)
        if r is None:
            raise KeyError(reservation_id)
        if r.status not in {ReservationStatus.PENDING, ReservationStatus.ACCEPTED}:
            raise InvalidReservationStateError("Can only cancel PENDING or ACCEPTED reservations")
        r.status = ReservationStatus.CANCELLED
        r.updated_at = datetime.now(UTC)
        self._store[r.id] = r
        return deepcopy(r)

    def expire(self, reservation_id: UUID) -> Reservation:
        r = self._store.get(reservation_id)
        if r is None:
            raise KeyError(reservation_id)
        if r.status not in {ReservationStatus.PENDING, ReservationStatus.ACCEPTED}:
            raise InvalidReservationStateError("Can only expire PENDING or ACCEPTED reservations")
        r.status = ReservationStatus.EXPIRED
        r.updated_at = datetime.now(UTC)
        self._store[r.id] = r
        return deepcopy(r)

    def complete(self, reservation_id: UUID) -> Reservation:
        r = self._store.get(reservation_id)
        if r is None:
            raise KeyError(reservation_id)
        if r.status != ReservationStatus.ACCEPTED:
            raise InvalidReservationStateError("Can only complete ACCEPTED reservations")
        r.status = ReservationStatus.COMPLETED
        r.updated_at = datetime.now(UTC)
        self._store[r.id] = r
        return deepcopy(r)
