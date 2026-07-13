from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from domain.reservations.exceptions import InvalidReservationStateError
from domain.reservations.models import ReservationStatus
from domain.reservations.service import ReservationService


def test_reservation_lifecycle_and_terminal_states() -> None:
    svc = ReservationService()
    listing = uuid4()
    buyer = uuid4()
    seller = uuid4()

    r = svc.create_reservation(listing, buyer, seller)
    assert r.status == ReservationStatus.PENDING

    before = svc.get_reservation(r.id).updated_at
    svc.accept(r.id)
    assert svc.get_reservation(r.id).status == ReservationStatus.ACCEPTED
    assert svc.get_reservation(r.id).updated_at >= before

    svc.complete(r.id)
    assert svc.get_reservation(r.id).status == ReservationStatus.COMPLETED

    with pytest.raises(InvalidReservationStateError):
        svc.cancel(r.id)


def test_decline_and_cancel_and_expire() -> None:
    svc = ReservationService()
    listing = uuid4(); buyer = uuid4(); seller = uuid4()
    r1 = svc.create_reservation(listing, buyer, seller)
    svc.decline(r1.id)
    with pytest.raises(InvalidReservationStateError):
        svc.accept(r1.id)

    r2 = svc.create_reservation(listing, buyer, seller)
    svc.cancel(r2.id)
    with pytest.raises(InvalidReservationStateError):
        svc.accept(r2.id)

    r3 = svc.create_reservation(listing, buyer, seller)
    svc.expire(r3.id)
    with pytest.raises(InvalidReservationStateError):
        svc.accept(r3.id)


def test_cancel_from_accepted_allowed_and_updated_at_changes() -> None:
    svc = ReservationService()
    listing = uuid4(); buyer = uuid4(); seller = uuid4()
    r = svc.create_reservation(listing, buyer, seller)
    svc.accept(r.id)
    before = svc.get_reservation(r.id).updated_at
    svc.cancel(r.id)
    after = svc.get_reservation(r.id).updated_at
    assert after >= before
    assert svc.get_reservation(r.id).status == ReservationStatus.CANCELLED


def test_expires_at_validation_on_create() -> None:
    svc = ReservationService()
    listing = uuid4(); buyer = uuid4(); seller = uuid4()
    expires = datetime.now(UTC) + timedelta(days=1)
    r = svc.create_reservation(listing, buyer, seller, expires_at=expires)
    assert svc.get_reservation(r.id).expires_at == expires
