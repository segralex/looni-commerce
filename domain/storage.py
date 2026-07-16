"""Storage provider interface and models."""
from dataclasses import dataclass
from typing import BinaryIO, Protocol


@dataclass
class StoredFile:
    """Result of a file save operation."""
    
    storage_key: str
    size_bytes: int
    content_type: str


class StorageProvider(Protocol):
    """Protocol for file storage backends."""
    
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
        ...
    
    def open(self, storage_key: str) -> BinaryIO:
        """Open a stored file for reading.
        
        Args:
            storage_key: Storage key from SavedFile
            
        Returns:
            Binary file-like object for reading
            
        Raises:
            FileNotFoundError: If storage_key does not exist
        """
        ...
    
    def delete(self, storage_key: str) -> None:
        """Delete a stored file.
        
        Args:
            storage_key: Storage key to delete
            
        Note:
            Delete is idempotent - succeeds even if key doesn't exist
        """
        ...
    
    def exists(self, storage_key: str) -> bool:
        """Check if a storage key exists.
        
        Args:
            storage_key: Storage key to check
            
        Returns:
            True if file exists, False otherwise
        """
        ...
