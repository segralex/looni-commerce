"""Tests for authentication API endpoints (EO-LC-000021)."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import UUID

# Ensure the external LICOS kernel package is importable.
LICOS_ROOT = Path(__file__).resolve().parents[3] / "200_LICOS" / "licos-core"
if LICOS_ROOT.is_dir() and str(LICOS_ROOT) not in sys.path:
    sys.path.insert(0, str(LICOS_ROOT))

import pytest
from fastapi.testclient import TestClient

import app.dependencies as deps
from app.main import app
from infrastructure.config.settings import settings

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_singletons(monkeypatch):
    """Reset singletons before each test and set JWT secret."""
    monkeypatch.setenv("LOONI_JWT_SECRET", "looni-test-secret-key-32-bytes-minimum-2026")
    import importlib
    import infrastructure.config.settings
    importlib.reload(infrastructure.config.settings)
    deps.reset_singletons()
    yield
    deps.reset_singletons()
    # Restore default env for subsequent tests
    monkeypatch.delenv("LOONI_JWT_SECRET", raising=False)
    importlib.reload(infrastructure.config.settings)


@pytest.fixture
def jwt_secret(monkeypatch):
    """Explicitly set JWT secret (redundant with autouse, but allowed by test)."""
    monkeypatch.setenv("LOONI_JWT_SECRET", "looni-test-secret-key-32-bytes-minimum-2026")
    import importlib
    import infrastructure.config.settings
    importlib.reload(infrastructure.config.settings)


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------


def test_register_creates_user_and_credentials(jwt_secret):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "display_name": "Alice",
            "email": "alice@example.com",
            "phone": "555-1234",
            "password": "SecurePassword123!",
        },
    )
    assert response.status_code == 201
    user = response.json()
    assert user["display_name"] == "Alice"
    assert user["email"] == "alice@example.com"
    assert user["status"] == "PENDING"
    assert UUID(user["id"])


def test_password_absent_from_response(jwt_secret):
    """Verify password is never in any response."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "display_name": "Bob",
            "email": "bob@example.com",
            "password": "SecurePassword123!",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "password" not in data


def test_duplicate_registration_rejected(jwt_secret):
    """Exact duplicate email rejected on registration."""
    reg1 = client.post(
        "/api/v1/auth/register",
        json={
            "display_name": "Carol",
            "email": "carol1@example.com",
            "password": "SecurePassword123!",
        },
    )
    assert reg1.status_code == 201
    
    # Try to register same email again
    reg2 = client.post(
        "/api/v1/auth/register",
        json={
            "display_name": "Carol2",
            "email": "carol1@example.com",
            "password": "AnotherPassword123!",
        },
    )
    assert reg2.status_code == 409


def test_case_insensitive_duplicate_rejected(jwt_secret):
    """Different capitalization of same email rejected."""
    reg1 = client.post(
        "/api/v1/auth/register",
        json={
            "display_name": "David",
            "email": "David@Example.COM",
            "password": "SecurePassword123!",
        },
    )
    assert reg1.status_code == 201
    
    # Try to register same email with different case
    reg2 = client.post(
        "/api/v1/auth/register",
        json={
            "display_name": "David2",
            "email": "david@example.com",
            "password": "AnotherPassword123!",
        },
    )
    assert reg2.status_code == 409


def test_whitespace_normalized_duplicate_rejected(jwt_secret):
    """Email with surrounding whitespace treated as duplicate."""
    reg1 = client.post(
        "/api/v1/auth/register",
        json={
            "display_name": "Eve",
            "email": "eve@example.com",
            "password": "SecurePassword123!",
        },
    )
    assert reg1.status_code == 201
    
    # Try with leading/trailing whitespace
    reg2 = client.post(
        "/api/v1/auth/register",
        json={
            "display_name": "Eve2",
            "email": "  eve@example.com  ",
            "password": "AnotherPassword123!",
        },
    )
    assert reg2.status_code == 409


def test_different_emails_succeed(jwt_secret):
    """Different emails can be registered."""
    reg1 = client.post(
        "/api/v1/auth/register",
        json={
            "display_name": "Frank",
            "email": "frank@example.com",
            "password": "SecurePassword123!",
        },
    )
    assert reg1.status_code == 201
    
    reg2 = client.post(
        "/api/v1/auth/register",
        json={
            "display_name": "Grace",
            "email": "grace@example.com",
            "password": "AnotherPassword123!",
        },
    )
    assert reg2.status_code == 201


def test_short_password_rejected(jwt_secret):
    """Password < 10 chars rejected at registration."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "display_name": "Dave",
            "email": "dave@example.com",
            "password": "short",
        },
    )
    assert response.status_code in (422, 400)


# ---------------------------------------------------------------------------
# Login tests
# ---------------------------------------------------------------------------


def test_active_user_can_log_in(jwt_secret):
    """Register, activate, then log in."""
    reg_response = client.post(
        "/api/v1/auth/register",
        json={
            "display_name": "Eve",
            "email": "eve@example.com",
            "password": "SecurePassword123!",
        },
    )
    user_id = reg_response.json()["id"]

    # Activate user via marketplace service
    deps.marketplace_service.activate_user(UUID(user_id))

    # Now login
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "eve@example.com",
            "password": "SecurePassword123!",
        },
    )
    assert login_response.status_code == 200
    data = login_response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0
    assert "password" not in data


def test_inactive_user_cannot_log_in(jwt_secret):
    """User in PENDING status cannot log in."""
    client.post(
        "/api/v1/auth/register",
        json={
            "display_name": "Frank",
            "email": "frank@example.com",
            "password": "SecurePassword123!",
        },
    )
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "frank@example.com",
            "password": "SecurePassword123!",
        },
    )
    assert response.status_code == 401


def test_invalid_credentials_return_generic_401(jwt_secret):
    """Wrong password or email returns generic 401."""
    client.post(
        "/api/v1/auth/register",
        json={
            "display_name": "Grace",
            "email": "grace@example.com",
            "password": "SecurePassword123!",
        },
    )
    deps.marketplace_service.activate_user(
        deps.marketplace_service.user_repository.all()[0].id
    )

    # Wrong password
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "grace@example.com",
            "password": "WrongPassword!",
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"

    # Wrong email
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "SecurePassword123!",
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_login_works_with_different_email_capitalization(jwt_secret):
    """Login succeeds when using different capitalization of registered email."""
    client.post(
        "/api/v1/auth/register",
        json={
            "display_name": "Helen",
            "email": "Helen@Example.COM",
            "password": "SecurePassword123!",
        },
    )
    user = deps.marketplace_service.user_repository.all()[0]
    deps.marketplace_service.activate_user(user.id)

    # Login with different case
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "helen@example.com",
            "password": "SecurePassword123!",
        },
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_response_contains_no_password(jwt_secret):
    """Verify password never appears in login response."""
    client.post(
        "/api/v1/auth/register",
        json={
            "display_name": "Henry",
            "email": "henry@example.com",
            "password": "SecurePassword123!",
        },
    )
    user = deps.marketplace_service.user_repository.all()[0]
    deps.marketplace_service.activate_user(user.id)

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "henry@example.com",
            "password": "SecurePassword123!",
        },
    )
    assert response.status_code == 200
    assert "password" not in response.json()
    assert "SecurePassword123!" not in response.text


# ---------------------------------------------------------------------------
# /auth/me tests
# ---------------------------------------------------------------------------


def test_auth_me_returns_authenticated_user(jwt_secret):
    """GET /auth/me with valid token returns user."""
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "display_name": "Iris",
            "email": "iris@example.com",
            "password": "SecurePassword123!",
        },
    )
    user_id = reg.json()["id"]
    deps.marketplace_service.activate_user(UUID(user_id))

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "iris@example.com",
            "password": "SecurePassword123!",
        },
    )
    token = login_response.json()["access_token"]

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_response.status_code == 200
    me = me_response.json()
    assert me["id"] == user_id
    assert me["display_name"] == "Iris"


def test_missing_bearer_token_rejected(jwt_secret):
    """GET /auth/me without Authorization header returns 401."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_invalid_bearer_token_rejected(jwt_secret):
    """GET /auth/me with invalid token returns 401."""
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid-token-xyz"},
    )
    assert response.status_code == 401


def test_auth_me_response_has_no_password(jwt_secret):
    """GET /auth/me response never contains password."""
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "display_name": "Jack",
            "email": "jack@example.com",
            "password": "SecurePassword123!",
        },
    )
    user_id = reg.json()["id"]
    deps.marketplace_service.activate_user(UUID(user_id))

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "jack@example.com",
            "password": "SecurePassword123!",
        },
    )
    token = login_response.json()["access_token"]

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_response.status_code == 200
    assert "password" not in me_response.json()
