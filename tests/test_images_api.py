"""Tests for image upload API."""
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import reset_singletons


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset singletons before each test."""
    reset_singletons()
    yield
    reset_singletons()


def _create_user_and_listing(client, email_suffix=""):
    """Helper to create a user and listing for tests."""
    # Create user
    user_email = f"user{uuid4().hex[:8]}{email_suffix}@example.com"
    user_response = client.post(
        "/api/v1/users",
        json={"display_name": "Test User", "email": user_email},
    )
    user_id = user_response.json()["id"]
    
    # Activate user (required for creating listings)
    client.post(f"/api/v1/users/{user_id}/activate")
    
    # Create listing
    listing_response = client.post(
        "/api/v1/listings",
        json={
            "seller_id": user_id,
            "title": "Test Item",
            "description": "Test description",
            "price": "10.00",
            "currency": "USD",
            "category": "Books",
            "condition": "GOOD",
            "location": "Online",
        },
    )
    listing_id = listing_response.json()["id"]
    return user_id, listing_id
    """Tests for image upload endpoints."""
    

class TestImageUploadAPI:
    """Tests for image upload endpoints."""
    
    def test_upload_image_to_listing(self):
        """Test uploading an image to a listing."""
        client = TestClient(app)
        user_id, listing_id = _create_user_and_listing(client)
        
        # Upload image
        image_data = b"\xff\xd8\xff\xe0\x00\x10JFIF"  # JPEG header
        response = client.post(
            f"/api/v1/listings/{listing_id}/images",
            files={"file": ("photo.jpg", image_data, "image/jpeg")},
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["listing_id"] == listing_id
        assert data["position"] == 1
        assert data["content_type"] == "image/jpeg"
        assert data["size_bytes"] == len(image_data)
        assert "id" in data
    
    def test_upload_multiple_images_increment_position(self):
        """Test that multiple uploads increment position."""
        client = TestClient(app)
        user_id, listing_id = _create_user_and_listing(client)
        
        # Upload first image
        image_data = b"jpeg_data_1"
        response1 = client.post(
            f"/api/v1/listings/{listing_id}/images",
            files={"file": ("photo1.jpg", image_data, "image/jpeg")},
        )
        assert response1.status_code == 201
        assert response1.json()["position"] == 1
        
        # Upload second image
        image_data = b"jpeg_data_2"
        response2 = client.post(
            f"/api/v1/listings/{listing_id}/images",
            files={"file": ("photo2.jpg", image_data, "image/jpeg")},
        )
        assert response2.status_code == 201
        assert response2.json()["position"] == 2
    
    def test_upload_png_image(self):
        """Test uploading PNG image."""
        client = TestClient(app)
        user_id, listing_id = _create_user_and_listing(client)
        
        png_data = b"\x89PNG\r\n\x1a\n"
        response = client.post(
            f"/api/v1/listings/{listing_id}/images",
            files={"file": ("image.png", png_data, "image/png")},
        )
        
        assert response.status_code == 201
        assert response.json()["content_type"] == "image/png"
    
    def test_upload_webp_image(self):
        """Test uploading WebP image."""
        client = TestClient(app)
        user_id, listing_id = _create_user_and_listing(client)
        
        webp_data = b"RIFF\x00\x00\x00\x00WEBP"
        response = client.post(
            f"/api/v1/listings/{listing_id}/images",
            files={"file": ("image.webp", webp_data, "image/webp")},
        )
        
        assert response.status_code == 201
        assert response.json()["content_type"] == "image/webp"
    
    def test_upload_gif_image(self):
        """Test uploading GIF image."""
        client = TestClient(app)
        user_id, listing_id = _create_user_and_listing(client)
        
        gif_data = b"GIF89a"
        response = client.post(
            f"/api/v1/listings/{listing_id}/images",
            files={"file": ("image.gif", gif_data, "image/gif")},
        )
        
        assert response.status_code == 201
        assert response.json()["content_type"] == "image/gif"
    
    def test_upload_unsupported_type_rejected(self):
        """Test that unsupported file types are rejected."""
        client = TestClient(app)
        user_id, listing_id = _create_user_and_listing(client)
        
        response = client.post(
            f"/api/v1/listings/{listing_id}/images",
            files={"file": ("document.pdf", b"PDF data", "application/pdf")},
        )
        
        assert response.status_code == 422
        assert "Unsupported content type" in response.json()["detail"]
    
    def test_upload_to_nonexistent_listing_returns_404(self):
        """Test uploading to nonexistent listing returns 404."""
        client = TestClient(app)
        
        nonexistent_id = uuid4()
        response = client.post(
            f"/api/v1/listings/{nonexistent_id}/images",
            files={"file": ("photo.jpg", b"data", "image/jpeg")},
        )
        
        assert response.status_code == 404
        assert "Listing not found" in response.json()["detail"]
    
    def test_maximum_ten_images_enforced(self):
        """Test that maximum 10 images per listing is enforced."""
        client = TestClient(app)
        user_id, listing_id = _create_user_and_listing(client)
        
        # Upload 10 images
        for i in range(10):
            response = client.post(
                f"/api/v1/listings/{listing_id}/images",
                files={"file": (f"photo{i}.jpg", b"data", "image/jpeg")},
            )
            assert response.status_code == 201
        
        # 11th upload should fail
        response = client.post(
            f"/api/v1/listings/{listing_id}/images",
            files={"file": ("photo11.jpg", b"data", "image/jpeg")},
        )
        assert response.status_code == 409
        assert "maximum" in response.json()["detail"].lower()
    
    def test_list_images_returns_metadata(self):
        """Test listing images returns metadata only."""
        client = TestClient(app)
        user_id, listing_id = _create_user_and_listing(client)
        
        # Upload two images
        for i in range(2):
            client.post(
                f"/api/v1/listings/{listing_id}/images",
                files={"file": (f"photo{i}.jpg", b"data", "image/jpeg")},
            )
        
        # List images
        response = client.get(f"/api/v1/listings/{listing_id}/images")
        
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert len(data["items"]) == 2
        
        # Check first image metadata
        first_image = data["items"][0]
        assert "id" in first_image
        assert first_image["listing_id"] == listing_id
        assert first_image["position"] == 1
        assert first_image["content_type"] == "image/jpeg"
        assert "size_bytes" in first_image
        
        # Check second image
        second_image = data["items"][1]
        assert second_image["position"] == 2
    
    def test_list_images_empty_listing(self):
        """Test listing images on listing with no images."""
        client = TestClient(app)
        user_id, listing_id = _create_user_and_listing(client)
        
        response = client.get(f"/api/v1/listings/{listing_id}/images")
        
        assert response.status_code == 200
        assert response.json()["count"] == 0
        assert response.json()["items"] == []
    
    def test_list_images_nonexistent_listing_returns_404(self):
        """Test listing images on nonexistent listing returns 404."""
        client = TestClient(app)
        
        response = client.get(f"/api/v1/listings/{uuid4()}/images")
        
        assert response.status_code == 404
    
    def test_delete_image(self):
        """Test deleting an image."""
        client = TestClient(app)
        user_id, listing_id = _create_user_and_listing(client)
        
        # Upload image
        upload_response = client.post(
            f"/api/v1/listings/{listing_id}/images",
            files={"file": ("photo.jpg", b"data", "image/jpeg")},
        )
        image_id = upload_response.json()["id"]
        
        # Delete image
        delete_response = client.delete(f"/api/v1/listings/{listing_id}/images/{image_id}")
        assert delete_response.status_code == 204
        
        # Verify deleted
        list_response = client.get(f"/api/v1/listings/{listing_id}/images")
        assert list_response.json()["count"] == 0
    
    def test_delete_nonexistent_image_returns_404(self):
        """Test deleting nonexistent image returns 404."""
        client = TestClient(app)
        user_id, listing_id = _create_user_and_listing(client)
        
        response = client.delete(f"/api/v1/listings/{listing_id}/images/{uuid4()}")
        assert response.status_code == 404
    
    def test_delete_from_nonexistent_listing_returns_404(self):
        """Test deleting image from nonexistent listing returns 404."""
        client = TestClient(app)
        
        response = client.delete(f"/api/v1/listings/{uuid4()}/images/{uuid4()}")
        assert response.status_code == 404
