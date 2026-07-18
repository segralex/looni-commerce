from fastapi.testclient import TestClient
from uuid import UUID, uuid4
import pytest

from app.main import app
from app.dependencies import reset_singletons
from domain.listings.models import ItemCondition

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_state():
    reset_singletons()
    yield
    reset_singletons()


def _create_user_and_listing(email: str, title: str = "Book") -> tuple[str, str]:
    user_response = client.post(
        "/api/v1/users/",
        json={"display_name": "Seller", "email": email},
    )
    assert user_response.status_code == 201
    seller_id = user_response.json()["id"]

    activate_response = client.post(f"/api/v1/users/{seller_id}/activate")
    assert activate_response.status_code == 200

    listing_response = client.post(
        "/api/v1/listings/",
        json={
            "seller_id": seller_id,
            "title": title,
            "description": f"{title} description",
            "price": "10.00",
            "currency": "USD",
            "category": "Books",
            "condition": "GOOD",
            "location": "Online",
        },
    )
    assert listing_response.status_code == 201
    return seller_id, listing_response.json()["id"]


def _upload_images(listing_id: str, count: int) -> None:
    for index in range(count):
        response = client.post(
            f"/api/v1/listings/{listing_id}/images",
            files={"file": (f"photo{index}.jpg", b"jpeg-data", "image/jpeg")},
        )
        assert response.status_code == 201


def test_create_listing():
    seller_id, listing_id = _create_user_and_listing("seller@example.com")

    response = client.get(f"/api/v1/listings/{listing_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["seller_id"] == seller_id
    assert payload["status"] == "DRAFT"
    assert UUID(payload["id"]) == UUID(listing_id)


def test_get_listing():
    _, listing_id = _create_user_and_listing("seller2@example.com", title="Gadget")

    response = client.get(f"/api/v1/listings/{listing_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == listing_id
    assert payload["title"] == "Gadget"


def test_publish_listing_fails_with_zero_images():
    _, listing_id = _create_user_and_listing(f"seller-zero-{uuid4().hex[:8]}@example.com", title="Device")

    response = client.post(f"/api/v1/listings/{listing_id}/publish")
    assert response.status_code == 409
    assert "at least 2 images" in response.json()["detail"]

    listing_response = client.get(f"/api/v1/listings/{listing_id}")
    assert listing_response.status_code == 200
    assert listing_response.json()["status"] == "DRAFT"


def test_publish_listing_fails_with_one_image():
    _, listing_id = _create_user_and_listing(f"seller-one-{uuid4().hex[:8]}@example.com", title="Device")
    _upload_images(listing_id, 1)

    response = client.post(f"/api/v1/listings/{listing_id}/publish")
    assert response.status_code == 409
    assert "at least 2 images" in response.json()["detail"]

    listing_response = client.get(f"/api/v1/listings/{listing_id}")
    assert listing_response.status_code == 200
    assert listing_response.json()["status"] == "DRAFT"


def test_publish_listing_succeeds_with_two_images():
    _, listing_id = _create_user_and_listing(f"seller-two-{uuid4().hex[:8]}@example.com", title="Device")
    _upload_images(listing_id, 2)

    response = client.post(f"/api/v1/listings/{listing_id}/publish")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "PUBLISHED"


def test_publish_listing_succeeds_with_ten_images():
    _, listing_id = _create_user_and_listing(f"seller-ten-{uuid4().hex[:8]}@example.com", title="Device")
    _upload_images(listing_id, 10)

    response = client.post(f"/api/v1/listings/{listing_id}/publish")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "PUBLISHED"
