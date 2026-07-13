from __future__ import annotations


class UserError(Exception):
    """Base user error."""


class UserValidationError(UserError):
    """Raised when a user fails validation."""


class InvalidUserStateError(UserError):
    """Raised when attempting an invalid user state transition."""
