from __future__ import annotations


class ListingError(Exception):
    """Base listing error."""


class ListingValidationError(ListingError):
    """Raised when a listing fails validation."""


class InvalidListingStateError(ListingError):
    """Raised when attempting an invalid state transition."""


class InvalidImagePositionError(ListingError):
    """Raised when image position is invalid."""


class DuplicateImagePositionError(ListingError):
    """Raised when image position already exists for listing."""


class MaxImagesExceededError(ListingError):
    """Raised when listing exceeds maximum image count."""


class MinImagesRequiredError(ListingError):
    """Raised when listing has fewer than minimum required images."""


class ImageNotFoundError(ListingError):
    """Raised when image is not found."""
