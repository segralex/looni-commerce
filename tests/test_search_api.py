from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.dependencies import reset_singletons


@pytest.fixture(autouse=True)
def _reset_state():
    reset_singletons()
    yield


client = TestClient(app)


def test_empty_search():
    resp = client.get("/search")
    assert resp.status_code == 200
    assert resp.json()["count"] == 0


def test_published_listing_found():
    u = client.post("/users/", json={"display_name": "S", "email": "s@example.com"}).json()
    client.post(f"/users/{u['id']}/activate")
    l = client.post(
        "/listings/",
        json={
            "seller_id": u["id"],
            "title": "Book",
            "description": "Nice",
            "price": "5.00",
            "currency": "USD",
            "category": "Books",
            "condition": "GOOD",
            "location": "Online",
        },
    ).json()

    # publish so it becomes discoverable
    client.post(f"/listings/{l['id']}/publish")
    resp = client.get("/search")
    assert resp.status_code == 200
    assert resp.json()["count"] >= 1


def test_unpublished_excluded_by_default():
    u = client.post("/users/", json={"display_name": "S2", "email": "s2@example.com"}).json()
    client.post(f"/users/{u['id']}/activate")
    l = client.post(
        "/listings/",
        json={
            "seller_id": u["id"],
            "title": "Draft",
            "description": "Not published",
            "price": "5.00",
            "currency": "USD",
            "category": "Books",
            "condition": "GOOD",
            "location": "Online",
        },
    ).json()

    resp = client.get("/search")
    # ensure listing not present when only published expected
    ids = [item["id"] for item in resp.json()["items"]]
    assert l["id"] not in ids


def test_category_filter():
    u = client.post("/users/", json={"display_name": "C", "email": "c@example.com"}).json()
    client.post(f"/users/{u['id']}/activate")
    l = client.post(
        "/listings/",
        json={
            "seller_id": u["id"],
            "title": "Tech",
            "description": "Gadget",
            "price": "15.00",
            "currency": "USD",
            "category": "Electronics",
            "condition": "GOOD",
            "location": "Online",
        },
    ).json()

    # publish before searching
    client.post(f"/listings/{l['id']}/publish")
    resp = client.get("/search", params={"category": "Electronics"})
    assert resp.status_code == 200
    assert resp.json()["count"] >= 1


def test_seller_filter():
    u = client.post("/users/", json={"display_name": "SF", "email": "sf@example.com"}).json()
    client.post(f"/users/{u['id']}/activate")
    l = client.post(
        "/listings/",
        json={
            "seller_id": u["id"],
            "title": "Unique",
            "description": "By SF",
            "price": "25.00",
            "currency": "USD",
            "category": "Misc",
            "condition": "GOOD",
            "location": "Online",
        },
    ).json()

    # publish before searching
    client.post(f"/listings/{l['id']}/publish")
    resp = client.get("/search", params={"seller_id": u["id"]})
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.json()["items"]]
    assert l["id"] in ids


def test_text_query_and_combined_filters():
    u = client.post("/users/", json={"display_name": "TQ", "email": "tq@example.com"}).json()
    client.post(f"/users/{u['id']}/activate")
    l = client.post(
        "/listings/",
        json={
            "seller_id": u["id"],
            "title": "Special Book",
            "description": "A very special book",
            "price": "9.99",
            "currency": "USD",
            "category": "Books",
            "condition": "GOOD",
            "location": "Online",
        },
    ).json()

    # publish before searching
    client.post(f"/listings/{l['id']}/publish")
    resp = client.get("/search", params={"q": "special", "category": "Books", "seller_id": u["id"]})
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.json()["items"]]
    assert l["id"] in ids
