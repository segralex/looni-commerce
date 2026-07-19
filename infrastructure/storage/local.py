"""Local filesystem storage provider."""
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4
from domain.storage import StorageProvider, StoredFile



class LocalStorageProvider:
    """Local filesystem storage implementation."""
    
    # Supported content types and their safe extensions
    SUPPORTED_TYPES = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    
    def __init__(self, root_path: Path | str):
        """Initialize local storage provider.
        
        Args:
            root_path: Root directory for storing files
        """
        self.root_path = Path(root_path)
        self.root_path.mkdir(parents=True, exist_ok=True)
    
    def _get_full_path(self, storage_key: str) -> Path:
        """Get full filesystem path from storage key.
        
        Args:
            storage_key: Storage key to resolve
            
        Returns:
            Full Path object
            
        Raises:
            ValueError: If key attempts path traversal
        """
        full_path = (self.root_path / storage_key).resolve()
        
        # Prevent path traversal attacks
        if not str(full_path).startswith(str(self.root_path.resolve())):
            raise ValueError(f"Invalid storage key (path traversal detected): {storage_key}")
        
        return full_path
    
    def save(self, source_path: str, content_type: str) -> StoredFile:
        """Save a file from source path.
        
        Args:
            source_path: Path to source file to save
            content_type: MIME type (e.g. "image/jpeg")
            
        Returns:
            StoredFile with storage_key, size_bytes, content_type
            
        Raises:
            FileNotFoundError: If source_path does not exist
            ValueError: If content_type is not supported
        """
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")
        
        if content_type not in self.SUPPORTED_TYPES:
            raise ValueError(f"Unsupported content type: {content_type}")
        
        extension = self.SUPPORTED_TYPES[content_type]
        storage_key = f"{uuid4()}{extension}"
        return self.save_as(source_path, storage_key, content_type)

    def save_as(self, source_path: str, storage_key: str, content_type: str) -> StoredFile:
        """Save a file to an explicit storage key."""
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")

        if content_type not in self.SUPPORTED_TYPES:
            raise ValueError(f"Unsupported content type: {content_type}")

        full_path = self._get_full_path(storage_key)
        full_path.parent.mkdir(parents=True, exist_ok=True)

        size_bytes = 0
        chunk_size = 1024 * 1024
        with open(source, "rb") as src, open(full_path, "wb") as dst:
            while True:
                chunk = src.read(chunk_size)
                if not chunk:
                    break
                dst.write(chunk)
                size_bytes += len(chunk)

        return StoredFile(storage_key=storage_key, size_bytes=size_bytes, content_type=content_type)
    
    def open(self, storage_key: str) -> BinaryIO:
        """Open a stored file for reading.
        
        Args:
            storage_key: Storage key from StoredFile
            
        Returns:
            Binary file-like object for reading
            
        Raises:
            FileNotFoundError: If storage_key does not exist
        """
        full_path = self._get_full_path(storage_key)
        if not full_path.exists():
            raise FileNotFoundError(f"Stored file not found: {storage_key}")
        return open(full_path, "rb")
    
    def delete(self, storage_key: str) -> None:
        """Delete a stored file.
        
        Args:
            storage_key: Storage key to delete
            
        Note:
            Delete is idempotent - succeeds even if key doesn't exist
        """
        try:
            full_path = self._get_full_path(storage_key)
            if full_path.exists():
                try:
                    full_path.unlink()
                except PermissionError:
                    # Best-effort delete: a concurrent reader may still have the file open.
                    pass
        except ValueError:
            # Path traversal attempt - silently ignore for idempotency
            pass
    
    def exists(self, storage_key: str) -> bool:
        """Check if a storage key exists.
        
        Args:
            storage_key: Storage key to check
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            full_path = self._get_full_path(storage_key)
            return full_path.exists()
        except ValueError:
            # Path traversal attempt
            return False
