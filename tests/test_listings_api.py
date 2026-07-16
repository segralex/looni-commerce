from fastapi.testclient import TestClient
from uuid import UUID

from app.main import app
from domain.listings.models import ItemCondition

client = TestClient(app)


def test_create_listing():
    user_response = client.post(
        "/api/v1/users/",
        json={"display_name": "Seller", "email": "seller@example.com"},
    )
    assert user_response.status_code == 201
    seller_id = user_response.json()["id"]

    activate_response = client.post(f"/api/v1/users/{seller_id}/activate")
    assert activate_response.status_code == 200

    response = client.post(
        "/api/v1/listings/",
        json={
            "seller_id": seller_id,
            "title": "Book",
            "description": "A book",
            "price": "10.00",
            "currency": "USD",
            "category": "Books",
            "condition": "GOOD",
            "location": "Online",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["seller_id"] == seller_id
    assert payload["status"] == "DRAFT"
    assert UUID(payload["id"])


def test_get_listing():
    user_response = client.post(
        "/api/v1/users/",
        json={"display_name": "Seller2", "email": "seller2@example.com"},
    )
    seller_id = user_response.json()["id"]
    client.post(f"/api/v1/users/{seller_id}/activate")

    listing_response = client.post(
        "/api/v1/listings/",
        json={
            "seller_id": seller_id,
            "title": "Gadget",
            "description": "A gadget",
            "price": "20.00",
            "currency": "USD",
            "category": "Electronics",
            "condition": "GOOD",
            "location": "Online",
        },
    )
    listing_id = listing_response.json()["id"]

    response = client.get(f"/api/v1/listings/{listing_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == listing_id
    assert payload["title"] == "Gadget"


def test_publish_listing():
    user_response = client.post(
        "/api/v1/users/",
        json={"display_name": "Seller3", "email": "seller3@example.com"},
    )
    seller_id = user_response.json()["id"]
    client.post(f"/api/v1/users/{seller_id}/activate")

    listing_response = client.post(
        "/api/v1/listings/",
        json={
            "seller_id": seller_id,
            "title": "Device",
            "description": "A device",
            "price": "30.00",
            "currency": "USD",
            "category": "Electronics",
            "condition": "GOOD",
            "location": "Online",
        },
    )
    listing_id = listing_response.json()["id"]

    response = client.post(f"/api/v1/listings/{listing_id}/publish")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "PUBLISHED"
