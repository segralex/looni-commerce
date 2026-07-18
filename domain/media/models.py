"""Media domain models."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class MediaFile:
    """Domain model for a media file."""
    
    id: UUID
    owner_id: UUID
    filename: str
    mime_type: str
    size_bytes: int
    storage_key: str
    created_at: datetime
    updated_at: datetime
    
    @property
    def is_image(self) -> bool:
        """Check if media is an image."""
        return self.mime_type.startswith("image/")
    
    @property
    def is_document(self) -> bool:
        """Check if media is a document."""
        return self.mime_type in ("application/pdf", "application/msword")
