"""In-memory credential repository."""
from __future__ import annotations

from uuid import UUID

from infrastructure.security.passwords import hash_password


class DuplicateCredentialsError(Exception):
    """Raised when attempting to store credentials with a duplicate email or user_id."""


class Credential:
    """A credential record: user_id + email (normalized) + password_hash."""

    def __init__(self, user_id: UUID, email: str, password_hash: str):
        self.user_id = user_id
        self.email = email  # Normalized: strip().lower()
        self.password_hash = password_hash


class MemoryCredentialRepository:
    """In-memory storage of user credentials (password hashes only).
    
    Enforces:
    - Exactly one credential per user_id
    - Exactly one credential per normalized email
    - Email normalization: strip().lower()
    """

    def __init__(self):
        self._by_user_id: dict[UUID, Credential] = {}
        self._by_email: dict[str, Credential] = {}

    @staticmethod
    def _normalize_email(email: str) -> str:
        """Normalize email: strip() and lower()."""
        return email.strip().lower()

    def store(self, user_id: UUID, email: str, password_hash: str) -> None:
        """Store a credential for a user with normalized email.

        Raises DuplicateCredentialsError if:
        - Credentials already exist for this user_id
        - Credentials already exist for this normalized email
        """
        normalized_email = self._normalize_email(email)
        
        if user_id in self._by_user_id:
            raise DuplicateCredentialsError(f"Credentials already exist for user {user_id}")
        
        if normalized_email in self._by_email:
            raise DuplicateCredentialsError(f"Email already registered: {normalized_email}")
        
        cred = Credential(user_id, normalized_email, password_hash)
        self._by_user_id[user_id] = cred
        self._by_email[normalized_email] = cred

    def get(self, user_id: UUID) -> Credential | None:
        """Retrieve credential by user ID. Returns None if not found."""
        return self._by_user_id.get(user_id)

    def get_by_email(self, email: str) -> Credential | None:
        """Retrieve credential by normalized email. Returns None if not found."""
        normalized_email = self._normalize_email(email)
        return self._by_email.get(normalized_email)
