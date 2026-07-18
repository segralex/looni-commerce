"""Tests for media domain models."""
from datetime import datetime
from uuid import uuid4
import pytest
from domain.media.models import MediaFile


class TestMediaFile:
    """Tests for MediaFile model."""
    
    @pytest.fixture
    def media_file(self):
        """Create a sample media file."""
        return MediaFile(
            id=uuid4(),
            owner_id=uuid4(),
            filename="test.jpg",
            mime_type="image/jpeg",
            size_bytes=1024,
            storage_key="media/test.jpg",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
    
    def test_media_file_creation(self, media_file):
        """Test creating a media file."""
        assert media_file.filename == "test.jpg"
        assert media_file.mime_type == "image/jpeg"
        assert media_file.size_bytes == 1024
    
    def test_is_image(self, media_file):
        """Test image type detection."""
        assert media_file.is_image is True
    
    def test_is_not_image(self):
        """Test non-image type detection."""
        media_file = MediaFile(
            id=uuid4(),
            owner_id=uuid4(),
            filename="test.pdf",
            mime_type="application/pdf",
            size_bytes=2048,
            storage_key="media/test.pdf",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert media_file.is_image is False
    
    def test_is_document(self):
        """Test document type detection."""
        media_file = MediaFile(
            id=uuid4(),
            owner_id=uuid4(),
            filename="test.pdf",
            mime_type="application/pdf",
            size_bytes=2048,
            storage_key="media/test.pdf",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert media_file.is_document is True
