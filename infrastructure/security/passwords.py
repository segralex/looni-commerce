"""Password hashing using pwdlib with Argon2."""
from __future__ import annotations

from pwdlib import PasswordHash

# Use recommended Argon2 configuration.
_pwd_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash a plaintext password. Raises ValueError if password is too short."""
    if len(password) < 10:
        raise ValueError("Password must be at least 10 characters")
    return _pwd_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a hash. Returns False on mismatch."""
    try:
        return _pwd_hash.verify(password, password_hash)
    except Exception:
        return False
