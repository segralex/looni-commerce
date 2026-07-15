"""Tests for JWT token generation and validation (EO-LC-000021)."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import uuid4

# Ensure the external LICOS kernel package is importable.
LICOS_ROOT = Path(__file__).resolve().parents[3] / "200_LICOS" / "licos-core"
if LICOS_ROOT.is_dir() and str(LICOS_ROOT) not in sys.path:
    sys.path.insert(0, str(LICOS_ROOT))

import pytest
import jwt
from datetime import datetime, timedelta, timezone

from infrastructure.security.tokens import (
    create_access_token,
    decode_access_token,
    InvalidTokenError,
    TokenExpiredError,
)


@pytest.fixture
def jwt_secret(monkeypatch):
    """Provide a JWT secret for testing."""
    monkeypatch.setenv("LOONI_JWT_SECRET", "looni-test-secret-key-32-bytes-minimum-2026")
    # Re-import settings to pick up the env var.
    import importlib
    import infrastructure.config.settings
    importlib.reload(infrastructure.config.settings)


def test_token_round_trip(jwt_secret):
    """Create and decode a valid token."""
    user_id = uuid4()
    token = create_access_token(user_id)
    decoded_user_id = decode_access_token(token)
    assert decoded_user_id == user_id


def test_expired_token_rejected(jwt_secret, monkeypatch):
    """Reject a token with exp in the past."""
    from infrastructure.config.settings import settings

    user_id = uuid4()
    # Manually create an expired token.
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now - timedelta(seconds=60),  # Past
        "iss": "looni-commerce",
        "type": "access",
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    with pytest.raises(TokenExpiredError):
        decode_access_token(token)


def test_tampered_token_rejected(jwt_secret):
    """Reject a token with an invalid signature."""
    user_id = uuid4()
    token = create_access_token(user_id)
    tampered = token[:-5] + "xxxxx"  # Corrupt the signature.

    with pytest.raises(InvalidTokenError):
        decode_access_token(tampered)


def test_wrong_issuer_rejected(jwt_secret):
    """Reject a token with wrong issuer."""
    from infrastructure.config.settings import settings

    user_id = uuid4()
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=30)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": exp,
        "iss": "wrong-issuer",
        "type": "access",
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_missing_secret_raises(monkeypatch):
    """Raise ValueError if JWT secret is not configured."""
    monkeypatch.delenv("LOONI_JWT_SECRET", raising=False)
    import importlib
    import infrastructure.config.settings
    importlib.reload(infrastructure.config.settings)

    user_id = uuid4()
    with pytest.raises(ValueError, match="secret is not configured"):
        create_access_token(user_id)
