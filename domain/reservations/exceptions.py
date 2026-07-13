from __future__ import annotations


class ReservationError(Exception):
    """Base reservation error."""


class ReservationValidationError(ReservationError):
    """Raised when reservation data is invalid."""


class InvalidReservationStateError(ReservationError):
    """Raised when attempting an invalid state transition."""
