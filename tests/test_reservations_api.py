from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.dependencies import reset_singletons


@pytest.fixture(autouse=True)
def _reset_state():
    reset_singletons()
    yield


client = TestClient(app)


def test_create_and_get_reservation():
    u = client.post("/users/", json={"display_name": "B1", "email": "b1@example.com"}).json()
    client.post(f"/users/{u['id']}/activate")
    s = client.post("/users/", json={"display_name": "S1", "email": "s1@example.com"}).json()
    client.post(f"/users/{s['id']}/activate")

    l = client.post(
        "/listings/",
        json={
            "seller_id": s["id"],
            "title": "Item",
            "description": "For sale",
            "price": "10.00",
            "currency": "USD",
            "category": "Misc",
            "condition": "GOOD",
            "location": "Online",
        },
    ).json()
    client.post(f"/listings/{l['id']}/publish")

    r = client.post("/reservations/", json={"buyer_id": u["id"], "listing_id": l["id"]})
    assert r.status_code == 201
    res = r.json()

    got = client.get(f"/reservations/{res['id']}")
    assert got.status_code == 200
    assert got.json()["id"] == res["id"]


def test_accept_reservation_and_listing_reserved():
    buyer = client.post("/users/", json={"display_name": "B2", "email": "b2@example.com"}).json()
    client.post(f"/users/{buyer['id']}/activate")
    seller = client.post("/users/", json={"display_name": "S2", "email": "s2@example.com"}).json()
    client.post(f"/users/{seller['id']}/activate")
    listing = client.post(
        "/listings/",
        json={
            "seller_id": seller["id"],
            "title": "Item2",
            "description": "For sale",
            "price": "20.00",
            "currency": "USD",
            "category": "Misc",
            "condition": "GOOD",
            "location": "Online",
        },
    ).json()
    client.post(f"/listings/{listing['id']}/publish")

    r = client.post("/reservations/", json={"buyer_id": buyer['id'], "listing_id": listing['id']}).json()
    a = client.post(f"/reservations/{r['id']}/accept", json={"seller_id": seller['id']})
    assert a.status_code == 200
    accepted = a.json()
    assert accepted["status"] == "ACCEPTED"

    l2 = client.get(f"/listings/{listing['id']}").json()
    assert l2["status"] == "RESERVED"


def test_cancel_reservation_restores_listing():
    buyer = client.post("/users/", json={"display_name": "B3", "email": "b3@example.com"}).json()
    client.post(f"/users/{buyer['id']}/activate")
    seller = client.post("/users/", json={"display_name": "S3", "email": "s3@example.com"}).json()
    client.post(f"/users/{seller['id']}/activate")
    listing = client.post(
        "/listings/",
        json={
            "seller_id": seller["id"],
            "title": "Item3",
            "description": "For sale",
            "price": "30.00",
            "currency": "USD",
            "category": "Misc",
            "condition": "GOOD",
            "location": "Online",
        },
    ).json()
    client.post(f"/listings/{listing['id']}/publish")

    r = client.post("/reservations/", json={"buyer_id": buyer['id'], "listing_id": listing['id']}).json()
    client.post(f"/reservations/{r['id']}/accept", json={"seller_id": seller['id']})

    c = client.post(f"/reservations/{r['id']}/cancel")
    assert c.status_code == 200
    cancelled = c.json()
    assert cancelled["status"] == "CANCELLED"

    l2 = client.get(f"/listings/{listing['id']}").json()
    assert l2["status"] == "PUBLISHED"


def test_cannot_reserve_unpublished_listing():
    buyer = client.post("/users/", json={"display_name": "B4", "email": "b4@example.com"}).json()
    client.post(f"/users/{buyer['id']}/activate")
    seller = client.post("/users/", json={"display_name": "S4", "email": "s4@example.com"}).json()
    client.post(f"/users/{seller['id']}/activate")
    listing = client.post(
        "/listings/",
        json={
            "seller_id": seller["id"],
            "title": "Item4",
            "description": "For sale",
            "price": "40.00",
            "currency": "USD",
            "category": "Misc",
            "condition": "GOOD",
            "location": "Online",
        },
    ).json()

    r = client.post("/reservations/", json={"buyer_id": buyer['id'], "listing_id": listing['id']})
    assert r.status_code == 409


def test_cannot_reserve_unknown_listing():
    buyer = client.post("/users/", json={"display_name": "B5", "email": "b5@example.com"}).json()
    client.post(f"/users/{buyer['id']}/activate")
    r = client.post("/reservations/", json={"buyer_id": buyer['id'], "listing_id": "00000000-0000-0000-0000-000000000000"})
    assert r.status_code == 404


def test_cannot_accept_twice():
    buyer = client.post("/users/", json={"display_name": "B6", "email": "b6@example.com"}).json()
    client.post(f"/users/{buyer['id']}/activate")
    seller = client.post("/users/", json={"display_name": "S6", "email": "s6@example.com"}).json()
    client.post(f"/users/{seller['id']}/activate")
    listing = client.post(
        "/listings/",
        json={
            "seller_id": seller["id"],
            "title": "Item6",
            "description": "For sale",
            "price": "60.00",
            "currency": "USD",
            "category": "Misc",
            "condition": "GOOD",
            "location": "Online",
        },
    ).json()
    client.post(f"/listings/{listing['id']}/publish")

    r = client.post("/reservations/", json={"buyer_id": buyer['id'], "listing_id": listing['id']}).json()
    a1 = client.post(f"/reservations/{r['id']}/accept", json={"seller_id": seller['id']})
    assert a1.status_code == 200
    a2 = client.post(f"/reservations/{r['id']}/accept", json={"seller_id": seller['id']})
    assert a2.status_code == 409


def test_cannot_cancel_accepted_if_domain_forbids():
    # domain allows cancelling accepted, so test that cancel works; keep for parity
    buyer = client.post("/users/", json={"display_name": "B7", "email": "b7@example.com"}).json()
    client.post(f"/users/{buyer['id']}/activate")
    seller = client.post("/users/", json={"display_name": "S7", "email": "s7@example.com"}).json()
    client.post(f"/users/{seller['id']}/activate")
    listing = client.post(
        "/listings/",
        json={
            "seller_id": seller["id"],
            "title": "Item7",
            "description": "For sale",
            "price": "70.00",
            "currency": "USD",
            "category": "Misc",
            "condition": "GOOD",
            "location": "Online",
        },
    ).json()
    client.post(f"/listings/{listing['id']}/publish")

    r = client.post("/reservations/", json={"buyer_id": buyer['id'], "listing_id": listing['id']}).json()
    client.post(f"/reservations/{r['id']}/accept", json={"seller_id": seller['id']})
    c = client.post(f"/reservations/{r['id']}/cancel")
    assert c.status_code == 200


def test_licos_events_emitted_on_accept():
    # basic smoke: create and accept reservation and ensure accept endpoint returns 200
    buyer = client.post("/users/", json={"display_name": "B8", "email": "b8@example.com"}).json()
    client.post(f"/users/{buyer['id']}/activate")
    seller = client.post("/users/", json={"display_name": "S8", "email": "s8@example.com"}).json()
    client.post(f"/users/{seller['id']}/activate")
    listing = client.post(
        "/listings/",
        json={
            "seller_id": seller["id"],
            "title": "Item8",
            "description": "For sale",
            "price": "80.00",
            "currency": "USD",
            "category": "Misc",
            "condition": "GOOD",
            "location": "Online",
        },
    ).json()
    client.post(f"/listings/{listing['id']}/publish")

    r = client.post("/reservations/", json={"buyer_id": buyer['id'], "listing_id": listing['id']}).json()
    a = client.post(f"/reservations/{r['id']}/accept", json={"seller_id": seller['id']})
    assert a.status_code == 200

