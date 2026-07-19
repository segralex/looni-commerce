from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

import app.dependencies as deps
from app.main import app
from infrastructure.sqlite.database import Database
from app.dependencies import get_event_dispatcher
from tests.conftest import make_jpeg_bytes


@pytest.fixture
def sqlite_env(monkeypatch, tmp_path):
    db_file = tmp_path / "search-fts.db"
    monkeypatch.setenv("LOONI_REPOSITORY_BACKEND", "sqlite")
    monkeypatch.setenv("LOONI_DATABASE_PATH", str(db_file))
    deps.reset_singletons()
    try:
        yield db_file
    finally:
        monkeypatch.delenv("LOONI_REPOSITORY_BACKEND", raising=False)
        monkeypatch.delenv("LOONI_DATABASE_PATH", raising=False)
        deps.reset_singletons()


def _create_active_user(client: TestClient, name: str, email: str) -> str:
    u = client.post("/api/v1/users/", json={"display_name": name, "email": email})
    user_id = u.json()["id"]
    client.post(f"/api/v1/users/{user_id}/activate")
    return user_id


def _create_listing(client: TestClient, seller_id: str, title: str, description: str, category: str, price: str = "10.00") -> str:
    response = client.post(
        "/api/v1/listings/",
        json={
            "seller_id": seller_id,
            "title": title,
            "description": description,
            "price": price,
            "currency": "USD",
            "category": category,
            "condition": "GOOD",
            "location": "Online",
        },
    )
    return response.json()["id"]


def _upload_min_images(client: TestClient, listing_id: str):
    for i in range(2):
        r = client.post(
            f"/api/v1/listings/{listing_id}/images",
            files={"file": (f"p{i}.jpg", make_jpeg_bytes(), "image/jpeg")},
        )
        assert r.status_code == 201
    assert get_event_dispatcher().wait_until_idle(timeout=2.0)


def test_sqlite_search_sync_and_filtering(sqlite_env):
    client = TestClient(app)
    seller_a = _create_active_user(client, "A", "a@example.com")
    seller_b = _create_active_user(client, "B", "b@example.com")

    listing_a = _create_listing(client, seller_a, "Special Bike", "special special fast bike", "Sports", price="12.00")
    listing_b = _create_listing(client, seller_b, "Bike", "ordinary bike", "Sports", price="18.00")

    _upload_min_images(client, listing_a)
    _upload_min_images(client, listing_b)

    assert client.post(f"/api/v1/listings/{listing_a}/publish").status_code == 200
    assert client.post(f"/api/v1/listings/{listing_b}/publish").status_code == 200

    # Ranked text search should prefer listing_a due to denser keyword frequency.
    resp = client.get("/api/v1/search", params={"q": "special"})
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.json()["items"]]
    assert ids[0] == listing_a

    # Structured filters.
    by_seller = client.get("/api/v1/search", params={"seller_id": seller_b})
    assert by_seller.status_code == 200
    assert [item["id"] for item in by_seller.json()["items"]] == [listing_b]

    by_price = client.get("/api/v1/search", params={"min_price": "15", "max_price": "20"})
    assert by_price.status_code == 200
    assert [item["id"] for item in by_price.json()["items"]] == [listing_b]

    by_category = client.get("/api/v1/search", params={"category": "Sports"})
    assert by_category.status_code == 200
    assert len(by_category.json()["items"]) == 2


def test_sqlite_search_pagination(sqlite_env):
    client = TestClient(app)
    seller = _create_active_user(client, "Seller", "seller@example.com")
    ids = []
    for i in range(4):
        listing_id = _create_listing(client, seller, f"Item {i}", "paged", "Misc", price=str(10 + i))
        _upload_min_images(client, listing_id)
        assert client.post(f"/api/v1/listings/{listing_id}/publish").status_code == 200
        ids.append(listing_id)

    page1 = client.get("/api/v1/search", params={"limit": 2, "offset": 0})
    page2 = client.get("/api/v1/search", params={"limit": 2, "offset": 2})
    assert page1.status_code == 200
    assert page2.status_code == 200
    assert len(page1.json()["items"]) == 2
    assert len(page2.json()["items"]) == 2
    assert set(item["id"] for item in page1.json()["items"]).isdisjoint(
        set(item["id"] for item in page2.json()["items"])
    )


def test_sqlite_search_index_updates_on_listing_status_changes(sqlite_env):
    client = TestClient(app)
    seller = _create_active_user(client, "Seller", "seller2@example.com")
    buyer = _create_active_user(client, "Buyer", "buyer2@example.com")
    listing_id = _create_listing(client, seller, "Reserve Me", "search sync", "Misc")
    _upload_min_images(client, listing_id)

    assert client.post(f"/api/v1/listings/{listing_id}/publish").status_code == 200
    visible = client.get("/api/v1/search", params={"q": "reserve"})
    assert listing_id in [item["id"] for item in visible.json()["items"]]

    reservation = client.post(
        "/api/v1/reservations/",
        json={"buyer_id": buyer, "listing_id": listing_id},
    )
    assert reservation.status_code == 201
    reservation_id = reservation.json()["id"]

    assert client.post(
        f"/api/v1/reservations/{reservation_id}/accept",
        json={"seller_id": seller},
    ).status_code == 200

    hidden = client.get("/api/v1/search", params={"q": "reserve"})
    assert listing_id not in [item["id"] for item in hidden.json()["items"]]


def test_sqlite_search_bootstrap_existing_published_rows(tmp_path):
    db_path = tmp_path / "bootstrap.db"
    db = Database(str(db_path))
    conn = db.connect()
    conn.execute(
        """
        INSERT INTO listings (
            id, seller_id, title, description, category, condition, price, currency, location, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "00000000-0000-0000-0000-000000000123",
            "00000000-0000-0000-0000-000000000001",
            "Bootstrapped",
            "from existing rows",
            "Legacy",
            "GOOD",
            str(Decimal("11.00")),
            "USD",
            "Online",
            "PUBLISHED",
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
        ),
    )
    conn.commit()
    db.close()

    # Re-open triggers schema/bootstrap migration path.
    db2 = Database(str(db_path))
    conn2 = db2.connect()
    row = conn2.execute(
        "SELECT listing_id FROM listing_search_fts WHERE listing_id = ?",
        ("00000000-0000-0000-0000-000000000123",),
    ).fetchone()
    assert row is not None


def test_memory_backend_search_still_works(monkeypatch):
    monkeypatch.setenv("LOONI_REPOSITORY_BACKEND", "memory")
    deps.reset_singletons()
    try:
        client = TestClient(app)
        seller = _create_active_user(client, "Mem", "mem@example.com")
        listing_id = _create_listing(client, seller, "Memory Item", "compatible", "Misc")
        _upload_min_images(client, listing_id)
        assert client.post(f"/api/v1/listings/{listing_id}/publish").status_code == 200

        resp = client.get("/api/v1/search", params={"q": "memory"})
        assert resp.status_code == 200
        assert listing_id in [item["id"] for item in resp.json()["items"]]
    finally:
        monkeypatch.delenv("LOONI_REPOSITORY_BACKEND", raising=False)
        deps.reset_singletons()
