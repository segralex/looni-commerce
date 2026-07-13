from datetime import UTC, datetime
from uuid import uuid4

import pytest

from domain.reservations.exceptions import ReservationValidationError
from domain.reservations.models import Reservation, ReservationStatus


def test_create_valid_reservation_without_expires() -> None:
    r = Reservation(
        id=uuid4(),
        listing_id=uuid4(),
        buyer_id=uuid4(),
        seller_id=uuid4(),
    )
    assert r.status == ReservationStatus.PENDING
    assert r.created_at.tzinfo == UTC


def test_buyer_cannot_equal_seller() -> None:
    uid = uuid4()
    with pytest.raises(ReservationValidationError):
        Reservation(id=uuid4(), listing_id=uuid4(), buyer_id=uid, seller_id=uid)


def test_expires_at_timezone_required() -> None:
    naive = datetime(2025, 1, 1)
    with pytest.raises(ReservationValidationError):
        Reservation(id=uuid4(), listing_id=uuid4(), buyer_id=uuid4(), seller_id=uuid4(), expires_at=naive)
