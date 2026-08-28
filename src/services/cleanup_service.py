"""
Compatibility shim for cleanup_service.
Now located in `src.business_logic.storage`.
"""

from src.business_logic.storage import (
    run_cleanup_worker,
    cleanup_expired_files,
)

__all__ = [
    "run_cleanup_worker",
    "cleanup_expired_files",
]
