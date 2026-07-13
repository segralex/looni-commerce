from __future__ import annotations


class ListingError(Exception):
    """Base listing error."""


class ListingValidationError(ListingError):
    """Raised when a listing fails validation."""


class InvalidListingStateError(ListingError):
    """Raised when attempting an invalid state transition."""
