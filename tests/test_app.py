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
