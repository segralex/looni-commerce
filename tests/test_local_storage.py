"""Tests for local filesystem storage provider."""
from pathlib import Path
import tempfile
import uuid
import pytest
from domain.storage import StoredFile
from infrastructure.storage.local import LocalStorageProvider


class TestLocalStorageProvider:
    """Tests for LocalStorageProvider."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for storage tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def storage(self, temp_dir):
        """Create a storage provider with temporary directory."""
        return LocalStorageProvider(temp_dir)
    
    @pytest.fixture
    def temp_source_file(self, temp_dir):
        """Create a temporary source file."""
        source = temp_dir / "source.jpg"
        source.write_bytes(b"fake jpeg data")
        return source
    
    def test_root_directory_created(self):
        """Test that root directory is created automatically."""
        with tempfile.TemporaryDirectory() as tmpdir:
            new_path = Path(tmpdir) / "storage" / "nested"
            provider = LocalStorageProvider(new_path)
            assert new_path.exists()
    
    def test_save_and_exists(self, storage, temp_source_file):
        """Test saving a file and checking it exists."""
        result = storage.save(str(temp_source_file), "image/jpeg")
        
        assert isinstance(result, StoredFile)
        assert storage.exists(result.storage_key)
    
    def test_saved_filename_is_uuid_based(self, storage, temp_source_file):
        """Test that saved filename is UUID-based, not original."""
        result = storage.save(str(temp_source_file), "image/jpeg")
        
        # Extract UUID from storage key (e.g., "123e4567-e89b-12d3-a456-426614174000.jpg")
        key_without_ext = result.storage_key.replace(".jpg", "")
        
        # Should be valid UUID
        uuid.UUID(key_without_ext)
        
        # Should NOT contain original filename
        assert "source" not in result.storage_key
    
    def test_save_preserves_supported_extension(self, storage, temp_source_file):
        """Test that supported extensions are preserved."""
        result = storage.save(str(temp_source_file), "image/jpeg")
        assert result.storage_key.endswith(".jpg")
    
    def test_save_png_extension(self, storage, temp_dir):
        """Test that PNG gets .png extension."""
        source = temp_dir / "image.png"
        source.write_bytes(b"fake png data")
        
        result = storage.save(str(source), "image/png")
        assert result.storage_key.endswith(".png")
    
    def test_save_webp_extension(self, storage, temp_dir):
        """Test that WebP gets .webp extension."""
        source = temp_dir / "image.webp"
        source.write_bytes(b"fake webp data")
        
        result = storage.save(str(source), "image/webp")
        assert result.storage_key.endswith(".webp")
    
    def test_save_gif_extension(self, storage, temp_dir):
        """Test that GIF gets .gif extension."""
        source = temp_dir / "image.gif"
        source.write_bytes(b"fake gif data")
        
        result = storage.save(str(source), "image/gif")
        assert result.storage_key.endswith(".gif")
    
    def test_open_returns_original_bytes(self, storage, temp_source_file):
        """Test that open returns the original bytes."""
        original_data = temp_source_file.read_bytes()
        
        result = storage.save(str(temp_source_file), "image/jpeg")
        
        with storage.open(result.storage_key) as f:
            retrieved_data = f.read()
        
        assert retrieved_data == original_data
    
    def test_open_returns_binary_handle(self, storage, temp_source_file):
        """Test that open returns a binary file handle."""
        result = storage.save(str(temp_source_file), "image/jpeg")
        
        handle = storage.open(result.storage_key)
        assert hasattr(handle, "read")
        assert hasattr(handle, "close")
        handle.close()
    
    def test_delete_removes_file(self, storage, temp_source_file):
        """Test that delete removes the stored file."""
        result = storage.save(str(temp_source_file), "image/jpeg")
        assert storage.exists(result.storage_key)
        
        storage.delete(result.storage_key)
        assert not storage.exists(result.storage_key)
    
    def test_repeated_delete_succeeds(self, storage, temp_source_file):
        """Test that repeated delete is idempotent."""
        result = storage.save(str(temp_source_file), "image/jpeg")
        
        storage.delete(result.storage_key)
        # Should not raise an exception
        storage.delete(result.storage_key)
        storage.delete(result.storage_key)
    
    def test_unsupported_type_rejected(self, storage, temp_dir):
        """Test that unsupported content types are rejected."""
        source = temp_dir / "document.pdf"
        source.write_bytes(b"fake pdf data")
        
        with pytest.raises(ValueError, match="Unsupported content type"):
            storage.save(str(source), "application/pdf")
    
    def test_missing_source_rejected(self, storage, temp_dir):
        """Test that missing source file is rejected."""
        nonexistent = temp_dir / "nonexistent.jpg"
        
        with pytest.raises(FileNotFoundError, match="Source file not found"):
            storage.save(str(nonexistent), "image/jpeg")
    
    def test_path_traversal_blocked_in_save(self, storage, temp_dir):
        """Test that path traversal is blocked in save."""
        source = temp_dir / "source.jpg"
        source.write_bytes(b"data")
        
        # Create a mock scenario - we can't actually save with traversal key
        # but we can verify the validation logic
        provider = storage
        malicious_key = "../../../etc/passwd"
        
        with pytest.raises(ValueError, match="path traversal"):
            provider._get_full_path(malicious_key)
    
    def test_path_traversal_blocked_in_delete(self, storage):
        """Test that path traversal is blocked in delete."""
        # Delete with traversal attempt should not raise, just be idempotent
        storage.delete("../../../etc/passwd")
        # Should succeed silently
    
    def test_path_traversal_blocked_in_exists(self, storage):
        """Test that path traversal is blocked in exists."""
        result = storage.exists("../../../etc/passwd")
        assert result is False
    
    def test_two_files_same_name_no_collision(self, storage, temp_dir):
        """Test that two files with same original name do not collide."""
        # Create two source files with same name in different directories
        dir1 = temp_dir / "dir1"
        dir2 = temp_dir / "dir2"
        dir1.mkdir()
        dir2.mkdir()
        
        source1 = dir1 / "image.jpg"
        source2 = dir2 / "image.jpg"
        source1.write_bytes(b"data1")
        source2.write_bytes(b"data2")
        
        result1 = storage.save(str(source1), "image/jpeg")
        result2 = storage.save(str(source2), "image/jpeg")
        
        # Should have different storage keys
        assert result1.storage_key != result2.storage_key
        
        # Should have different content
        with storage.open(result1.storage_key) as f:
            data1 = f.read()
        with storage.open(result2.storage_key) as f:
            data2 = f.read()
        
        assert data1 == b"data1"
        assert data2 == b"data2"
    
    def test_save_returns_correct_size(self, storage, temp_dir):
        """Test that save returns correct file size."""
        source = temp_dir / "image.jpg"
        test_data = b"x" * 1024  # 1 KB
        source.write_bytes(test_data)
        
        result = storage.save(str(source), "image/jpeg")
        assert result.size_bytes == 1024
    
    def test_save_preserves_content_type(self, storage, temp_dir):
        """Test that save preserves the provided content type."""
        source = temp_dir / "image.jpg"
        source.write_bytes(b"data")
        
        result = storage.save(str(source), "image/jpeg")
        assert result.content_type == "image/jpeg"
    
    def test_large_file_streaming(self, storage, temp_dir):
        """Test that large files are handled with streaming."""
        source = temp_dir / "large.jpg"
        # Create a 5 MB file
        large_data = b"x" * (5 * 1024 * 1024)
        source.write_bytes(large_data)
        
        result = storage.save(str(source), "image/jpeg")
        
        with storage.open(result.storage_key) as f:
            retrieved_data = f.read()
        
        assert len(retrieved_data) == len(large_data)
        assert retrieved_data == large_data
    
    def test_open_nonexistent_raises_error(self, storage):
        """Test that opening nonexistent file raises error."""
        with pytest.raises(FileNotFoundError, match="Stored file not found"):
            storage.open("nonexistent-uuid-key.jpg")
    
    def test_exists_nonexistent_returns_false(self, storage):
        """Test that exists returns False for nonexistent file."""
        assert storage.exists("nonexistent-uuid-key.jpg") is False
