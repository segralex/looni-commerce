"""JWT access token generation and validation."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt

from infrastructure.config.settings import settings


class InvalidTokenError(Exception):
    """Raised when a token is invalid."""


class TokenExpiredError(InvalidTokenError):
    """Raised when a token has expired."""


def create_access_token(user_id: UUID) -> str:
    """Create a signed JWT access token for the given user.

    Returns the token string. Raises ValueError if jwt_secret is not configured.
    """
    if not settings.jwt_secret:
        raise ValueError("JWT secret is not configured")

    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.access_token_minutes)

    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": exp,
        "iss": "looni-commerce",
        "type": "access",
    }

    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token


def decode_access_token(token: str) -> UUID:
    """Decode and validate a JWT access token.

    Returns the user UUID from the 'sub' claim.
    Raises InvalidTokenError for any validation failure.
    """
    if not settings.jwt_secret:
        raise InvalidTokenError("JWT secret is not configured")

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            issuer="looni-commerce",
        )
    except jwt.ExpiredSignatureError as e:
        raise TokenExpiredError("Token has expired") from e
    except jwt.InvalidSignatureError as e:
        raise InvalidTokenError("Invalid token signature") from e
    except jwt.InvalidIssuerError as e:
        raise InvalidTokenError("Invalid issuer") from e
    except jwt.DecodeError as e:
        raise InvalidTokenError("Failed to decode token") from e
    except Exception as e:
        raise InvalidTokenError(f"Token validation failed: {e}") from e

    # Validate token type.
    if payload.get("type") != "access":
        raise InvalidTokenError("Invalid token type")

    # Validate subject.
    sub = payload.get("sub")
    if not sub:
        raise InvalidTokenError("Missing subject claim")

    try:
        return UUID(sub)
    except (ValueError, TypeError) as e:
        raise InvalidTokenError("Invalid subject claim") from e
