from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.dependencies import reset_singletons, get_event_store
from tests.conftest import make_jpeg_bytes


@pytest.fixture(autouse=True)
def _reset_state():
    reset_singletons()
    yield


def test_full_marketplace_flow_and_licos_events():
    client = TestClient(app)

    def upload_minimum_images(listing_id: str) -> None:
        for index in range(2):
            response = client.post(
                f"/api/v1/listings/{listing_id}/images",
                files={"file": (f"photo{index}.jpg", make_jpeg_bytes(), "image/jpeg")},
            )
            assert response.status_code == 201

    # 1-2 Create and activate seller
    seller = client.post("/api/v1/users/", json={"display_name": "Seller", "email": "seller@example.com"}).json()
    client.post(f"/api/v1/users/{seller['id']}/activate")

    # 3-4 Create and activate buyer
    buyer = client.post("/api/v1/users/", json={"display_name": "Buyer", "email": "buyer@example.com"}).json()
    client.post(f"/api/v1/users/{buyer['id']}/activate")

    # 5 Create listing
    listing = client.post(
        "/api/v1/listings/",
        json={
            "seller_id": seller["id"],
            "title": "Acceptance Item",
            "description": "End-to-end",
            "price": "42.00",
            "currency": "USD",
            "category": "Gadgets",
            "condition": "GOOD",
            "location": "Online",
        },
    ).json()

    # 6 Publish listing
    upload_minimum_images(listing["id"])
    p = client.post(f"/api/v1/listings/{listing['id']}/publish")
    assert p.status_code == 200

    # 7 Search and verify listing appears
    s = client.get("/api/v1/search")
    assert s.status_code == 200
    ids = [it["id"] for it in s.json()["items"]]
    assert listing["id"] in ids

    # 8 Create reservation
    r = client.post("/api/v1/reservations/", json={"buyer_id": buyer['id'], "listing_id": listing['id']})
    assert r.status_code == 201
    reservation = r.json()

    # 9 Accept reservation
    a = client.post(f"/api/v1/reservations/{reservation['id']}/accept", json={"seller_id": seller['id']})
    assert a.status_code == 200

    # 10 Retrieve reservation and verify ACCEPTED
    got = client.get(f"/api/v1/reservations/{reservation['id']}")
    assert got.status_code == 200
    assert got.json()["status"] == "ACCEPTED"

    # 11 Retrieve listing and verify RESERVED
    l2 = client.get(f"/api/v1/listings/{listing['id']}")
    assert l2.status_code == 200
    assert l2.json()["status"] == "RESERVED"

    # 12 Verify LICOS events via EventStore
    store = get_event_store()
    types = [e.event_type for e in store.all_events()]

    expected = [
        "commerce.listing.created",
        "commerce.listing.published",
        "commerce.reservation.created",
        "commerce.reservation.accepted",
        "commerce.listing.reserved",
    ]

    for ev in expected:
        assert ev in types

    # Ensure ordering
    indexes = [types.index(ev) for ev in expected]
    assert indexes == sorted(indexes)
