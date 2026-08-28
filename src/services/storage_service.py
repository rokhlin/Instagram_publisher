"""
Compatibility shim for storage_service.
Now located in `src.business_logic.storage`.
"""

from src.business_logic.storage import StorageService, storage_service

__all__ = ["StorageService", "storage_service"]
