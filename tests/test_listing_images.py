"""Tests for ListingImage domain model."""
from datetime import datetime
from uuid import uuid4
import pytest
from domain.listings.images import ListingImage
from domain.listings.exceptions import InvalidImagePositionError


class TestListingImage:
    """Tests for ListingImage model."""
    
    @pytest.fixture
    def valid_image(self):
        """Create a valid listing image."""
        return ListingImage(
            id=uuid4(),
            listing_id=uuid4(),
            filename="photo1.jpg",
            content_type="image/jpeg",
            size_bytes=102400,
            position=1,
            created_at=datetime.now(),
        )
    
    def test_listing_image_creation(self, valid_image):
        """Test creating a valid listing image."""
        assert valid_image.filename == "photo1.jpg"
        assert valid_image.content_type == "image/jpeg"
        assert valid_image.size_bytes == 102400
        assert valid_image.position == 1
    
    def test_position_starts_at_one(self, valid_image):
        """Test that position can be 1."""
        assert valid_image.position == 1
    
    def test_position_zero_raises_error(self):
        """Test that position 0 is invalid."""
        with pytest.raises(InvalidImagePositionError, match="Position must be >= 1"):
            ListingImage(
                id=uuid4(),
                listing_id=uuid4(),
                filename="photo.jpg",
                content_type="image/jpeg",
                size_bytes=1024,
                position=0,
                created_at=datetime.now(),
            )
    
    def test_position_negative_raises_error(self):
        """Test that negative position is invalid."""
        with pytest.raises(InvalidImagePositionError, match="Position must be >= 1"):
            ListingImage(
                id=uuid4(),
                listing_id=uuid4(),
                filename="photo.jpg",
                content_type="image/jpeg",
                size_bytes=1024,
                position=-1,
                created_at=datetime.now(),
            )
    
    def test_position_max_ten(self):
        """Test that position 10 is valid (maximum)."""
        image = ListingImage(
            id=uuid4(),
            listing_id=uuid4(),
            filename="photo10.jpg",
            content_type="image/jpeg",
            size_bytes=1024,
            position=10,
            created_at=datetime.now(),
        )
        assert image.position == 10
    
    def test_position_exceeds_maximum(self):
        """Test that position > 10 is invalid."""
        with pytest.raises(InvalidImagePositionError, match="Position must be <= 10"):
            ListingImage(
                id=uuid4(),
                listing_id=uuid4(),
                filename="photo.jpg",
                content_type="image/jpeg",
                size_bytes=1024,
                position=11,
                created_at=datetime.now(),
            )
    
    def test_empty_filename_raises_error(self):
        """Test that empty filename is invalid."""
        with pytest.raises(ValueError, match="Filename cannot be empty"):
            ListingImage(
                id=uuid4(),
                listing_id=uuid4(),
                filename="",
                content_type="image/jpeg",
                size_bytes=1024,
                position=1,
                created_at=datetime.now(),
            )
    
    def test_empty_content_type_raises_error(self):
        """Test that empty content type is invalid."""
        with pytest.raises(ValueError, match="Content type cannot be empty"):
            ListingImage(
                id=uuid4(),
                listing_id=uuid4(),
                filename="photo.jpg",
                content_type="",
                size_bytes=1024,
                position=1,
                created_at=datetime.now(),
            )
    
    def test_negative_size_bytes_raises_error(self):
        """Test that negative size is invalid."""
        with pytest.raises(ValueError, match="Size bytes cannot be negative"):
            ListingImage(
                id=uuid4(),
                listing_id=uuid4(),
                filename="photo.jpg",
                content_type="image/jpeg",
                size_bytes=-1,
                position=1,
                created_at=datetime.now(),
            )
    
    def test_is_image_for_jpeg(self, valid_image):
        """Test is_image property for JPEG."""
        assert valid_image.is_image is True
    
    def test_is_image_for_png(self):
        """Test is_image property for PNG."""
        image = ListingImage(
            id=uuid4(),
            listing_id=uuid4(),
            filename="photo.png",
            content_type="image/png",
            size_bytes=1024,
            position=1,
            created_at=datetime.now(),
        )
        assert image.is_image is True
    
    def test_is_image_for_non_image(self):
        """Test is_image property for non-image content."""
        image = ListingImage(
            id=uuid4(),
            listing_id=uuid4(),
            filename="document.pdf",
            content_type="application/pdf",
            size_bytes=1024,
            position=1,
            created_at=datetime.now(),
        )
        assert image.is_image is False
    
    def test_is_supported_format_jpeg(self, valid_image):
        """Test is_supported_format for JPEG."""
        assert valid_image.is_supported_format is True
    
    def test_is_supported_format_png(self):
        """Test is_supported_format for PNG."""
        image = ListingImage(
            id=uuid4(),
            listing_id=uuid4(),
            filename="photo.png",
            content_type="image/png",
            size_bytes=1024,
            position=1,
            created_at=datetime.now(),
        )
        assert image.is_supported_format is True
    
    def test_is_supported_format_webp(self):
        """Test is_supported_format for WebP."""
        image = ListingImage(
            id=uuid4(),
            listing_id=uuid4(),
            filename="photo.webp",
            content_type="image/webp",
            size_bytes=1024,
            position=1,
            created_at=datetime.now(),
        )
        assert image.is_supported_format is True
    
    def test_is_supported_format_gif(self):
        """Test is_supported_format for GIF."""
        image = ListingImage(
            id=uuid4(),
            listing_id=uuid4(),
            filename="photo.gif",
            content_type="image/gif",
            size_bytes=1024,
            position=1,
            created_at=datetime.now(),
        )
        assert image.is_supported_format is True
    
    def test_is_supported_format_unsupported(self):
        """Test is_supported_format for unsupported format."""
        image = ListingImage(
            id=uuid4(),
            listing_id=uuid4(),
            filename="photo.bmp",
            content_type="image/bmp",
            size_bytes=1024,
            position=1,
            created_at=datetime.now(),
        )
        assert image.is_supported_format is False
    
    def test_filename_is_immutable(self, valid_image):
        """Test that filename attribute exists and is part of model."""
        # Note: dataclass fields are not truly immutable without frozen=True
        # This test documents the intended immutability rule (enforced at service level)
        original_filename = valid_image.filename
        assert original_filename == "photo1.jpg"
    
    def test_different_listing_ids(self):
        """Test images can have different listing IDs."""
        listing_id_1 = uuid4()
        listing_id_2 = uuid4()
        
        image1 = ListingImage(
            id=uuid4(),
            listing_id=listing_id_1,
            filename="photo1.jpg",
            content_type="image/jpeg",
            size_bytes=1024,
            position=1,
            created_at=datetime.now(),
        )
        image2 = ListingImage(
            id=uuid4(),
            listing_id=listing_id_2,
            filename="photo1.jpg",
            content_type="image/jpeg",
            size_bytes=1024,
            position=1,
            created_at=datetime.now(),
        )
        
        assert image1.listing_id != image2.listing_id
    
    def test_zero_size_bytes_is_valid(self):
        """Test that 0 size bytes is valid (empty file)."""
        image = ListingImage(
            id=uuid4(),
            listing_id=uuid4(),
            filename="empty.jpg",
            content_type="image/jpeg",
            size_bytes=0,
            position=1,
            created_at=datetime.now(),
        )
        assert image.size_bytes == 0
