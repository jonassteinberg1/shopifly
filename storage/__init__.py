"""Storage modules for persisting data."""

from .base import StorageBackend
from .airtable import AirtableStorage
from .sqlite import SQLiteStorage


def get_storage(backend: str = "airtable", **kwargs) -> StorageBackend:
    """Factory function to get a storage backend.

    Args:
        backend: The backend type ("airtable" or "sqlite").
        **kwargs: Additional arguments passed to the backend constructor.

    Returns:
        A StorageBackend instance.

    Raises:
        ValueError: If backend type is unknown.
    """
    if backend == "airtable":
        return AirtableStorage()
    elif backend == "sqlite":
        return SQLiteStorage(**kwargs)
    else:
        raise ValueError(f"Unknown storage backend: {backend}")


__all__ = [
    "StorageBackend",
    "AirtableStorage",
    "SQLiteStorage",
    "get_storage",
]
