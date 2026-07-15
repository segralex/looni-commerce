"""In-memory credential repository."""
from __future__ import annotations

from uuid import UUID

from infrastructure.security.passwords import hash_password


class DuplicateCredentialsError(Exception):
    """Raised when attempting to store credentials for a user that already has them."""


class Credential:
    """A credential record: user_id + password_hash."""

    def __init__(self, user_id: UUID, password_hash: str):
        self.user_id = user_id
        self.password_hash = password_hash


class MemoryCredentialRepository:
    """In-memory storage of user credentials (password hashes only)."""

    def __init__(self):
        self._credentials: dict[UUID, Credential] = {}

    def store(self, user_id: UUID, password_hash: str) -> None:
        """Store a credential for a user.

        Raises DuplicateCredentialsError if credentials already exist for this user.
        """
        if user_id in self._credentials:
            raise DuplicateCredentialsError(f"Credentials already exist for user {user_id}")
        self._credentials[user_id] = Credential(user_id, password_hash)

    def get(self, user_id: UUID) -> Credential | None:
        """Retrieve credential by user ID. Returns None if not found."""
        return self._credentials.get(user_id)
