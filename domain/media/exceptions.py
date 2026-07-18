"""Media domain exceptions."""


class MediaException(Exception):
    """Base exception for media operations."""
    pass


class MediaNotFoundError(MediaException):
    """Raised when media file is not found."""
    pass


class InvalidMediaTypeError(MediaException):
    """Raised when media type is not allowed."""
    pass


class FileSizeExceededError(MediaException):
    """Raised when file size exceeds maximum."""
    pass


class MediaStorageError(MediaException):
    """Raised when storage operation fails."""
    pass
