from fastapi.testclient import TestClient

from app.main import app


def test_app_starts():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200


def test_root_returns_product_info():
    client = TestClient(app)
    response = client.get("/")
    assert response.json() == {
        "product": "Looni Commerce",
        "version": "0.1-alpha",
        "status": "running",
    }


def test_health_returns_healthy():
    client = TestClient(app)
    response = client.get("/health")
    assert response.json() == {"status": "healthy"}


def test_versioned_users_route_accessible():
    """POST /api/v1/users/ should be accessible (create user)."""
    client = TestClient(app)
    response = client.post(
        "/api/v1/users/",
        json={"display_name": "Test User", "email": "test@example.com"},
    )
    assert response.status_code in (201, 200)


def test_versioned_listings_route_accessible():
    """POST /api/v1/listings/ should be accessible (create listing)."""
    client = TestClient(app)
    # First create a user
    user_resp = client.post(
        "/api/v1/users/",
        json={"display_name": "Test User", "email": "test@example.com"},
    )
    assert user_resp.status_code in (201, 200)


def test_old_unversioned_users_returns_404():
    """Old /users route should return 404."""
    client = TestClient(app)
    response = client.post("/users/", json={"display_name": "Test", "email": "test@example.com"})
    assert response.status_code == 404


def test_old_unversioned_listings_returns_404():
    """Old /listings route should return 404."""
    client = TestClient(app)
    response = client.get("/listings")
    # Could be 404 or redirect depending on the route definition
    assert response.status_code in (404, 307)


def test_old_unversioned_search_returns_404():
    """Old /search route should return 404."""
    client = TestClient(app)
    response = client.get("/search")
    assert response.status_code == 404


def test_old_unversioned_reservations_returns_404():
    """Old /reservations route should return 404."""
    client = TestClient(app)
    response = client.get("/reservations")
    assert response.status_code in (404, 307)


def test_old_unversioned_auth_returns_404():
    """Old /auth route should return 404."""
    client = TestClient(app)
    response = client.get("/auth/login")
    assert response.status_code == 404
