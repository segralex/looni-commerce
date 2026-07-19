from __future__ import annotations

from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_event_dispatcher, reset_singletons
from app.main import app
from tests.conftest import make_jpeg_bytes


@pytest.fixture(autouse=True)
def _reset_state():
    reset_singletons()
    yield
    reset_singletons()


def _create_user_and_listing(client: TestClient) -> str:
    user = client.post("/api/v1/users/", json={"display_name": "Seller", "email": f"seller-{uuid4().hex[:8]}@example.com"}).json()
    client.post(f"/api/v1/users/{user['id']}/activate")
    listing = client.post(
        "/api/v1/listings/",
        json={
            "seller_id": user["id"],
            "title": "Async Item",
            "description": "Async",
            "price": "12.00",
            "currency": "USD",
            "category": "Books",
            "condition": "GOOD",
            "location": "Online",
        },
    ).json()
    return listing["id"]


def test_upload_returns_pending_then_ready_after_dispatcher_drains():
    client = TestClient(app)
    listing_id = _create_user_and_listing(client)

    response = client.post(
        f"/api/v1/listings/{listing_id}/images",
        files={"file": ("photo.jpg", make_jpeg_bytes(), "image/jpeg")},
    )
    assert response.status_code == 201
    assert response.json()["processing_status"] == "PENDING"

    dispatcher = get_event_dispatcher()
    assert dispatcher.wait_until_idle(timeout=2.0)

    listing_images = client.get(f"/api/v1/listings/{listing_id}/images")
    assert listing_images.status_code == 200
    item = listing_images.json()["items"][0]
    assert item["processing_status"] == "READY"
    assert item["thumbnails"]
