from fastapi.testclient import TestClient
from uuid import UUID

from app.main import app


client = TestClient(app)


def test_app_can_create_user():
    response = client.post(
        "/api/v1/users/",
        json={"display_name": "Alice", "email": "Alice@example.com", "phone": "123"},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["display_name"] == "Alice"
    assert payload["email"] == "alice@example.com"
    assert payload["phone"] == "123"
    assert payload["status"] == "PENDING"
    assert UUID(payload["id"])
    assert payload["created_at"]
    assert payload["updated_at"]


def test_app_can_get_user():
    response = client.post(
        "/api/v1/users/",
        json={"display_name": "Bob", "email": "bob@example.com"},
    )
    assert response.status_code == 201
    user_id = response.json()["id"]

    response = client.get(f"/api/v1/users/{user_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == user_id
    assert payload["display_name"] == "Bob"
    assert payload["email"] == "bob@example.com"


def test_app_can_activate_user():
    response = client.post(
        "/api/v1/users/",
        json={"display_name": "Carol", "email": "carol@example.com"},
    )
    assert response.status_code == 201
    user_id = response.json()["id"]

    response = client.post(f"/api/v1/users/{user_id}/activate")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ACTIVE"
    assert payload["id"] == user_id


def test_get_missing_user_returns_404():
    response = client.get("/api/v1/users/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_activate_missing_user_returns_404():
    response = client.post("/api/v1/users/00000000-0000-0000-0000-000000000000/activate")
    assert response.status_code == 404


def test_create_user_invalid_request_returns_422():
    response = client.post("/api/v1/users/", json={"email": "no-name@example.com"})
    assert response.status_code == 422


def test_activation_conflict_for_non_pending_user():
    response = client.post(
        "/api/v1/users/",
        json={"display_name": "Dave", "email": "dave@example.com"},
    )
    assert response.status_code == 201
    user = response.json()
    user_id = user["id"]

    response = client.post(f"/api/v1/users/{user_id}/activate")
    assert response.status_code == 200

    response = client.post(f"/api/v1/users/{user_id}/activate")
    assert response.status_code == 409
