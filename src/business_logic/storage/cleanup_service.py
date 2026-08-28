"""
Background media cleanup worker: automatically deletes expired temporary media files
based on configured TTL and interval.
"""

import os
import time
import asyncio
import logging
from src.config import settings

logger = logging.getLogger(__name__)


def cleanup_expired_files(directory: str, ttl_minutes: int) -> int:
    """
    Deletes files in directory that are older than ttl_minutes.
    Preserves hidden files like .gitkeep.
    """
    if not os.path.exists(directory):
        return 0

    now = time.time()
    ttl_seconds = ttl_minutes * 60
    deleted_count = 0

    for root, _, files in os.walk(directory):
        for file in files:
            if file.startswith("."):
                continue  # Skip .gitkeep, .gitignore, etc.

            file_path = os.path.join(root, file)
            try:
                mtime = os.path.getmtime(file_path)
                age_seconds = now - mtime
                if age_seconds > ttl_seconds:
                    os.remove(file_path)
                    deleted_count += 1
                    logger.info(f"Cleaned up expired media file: {file_path} (Age: {age_seconds / 60:.1f} min)")
            except OSError as e:
                logger.warning(f"Error removing expired file {file_path}: {e}")

    return deleted_count


async def run_cleanup_worker():
    """
    Background worker that runs cleanup periodically if enabled.
    """
    if not settings.MEDIA_CLEANUP_ENABLED:
        logger.info("Media auto-cleanup is disabled in configuration.")
        return

    logger.info(
        f"Media auto-cleanup worker started. TTL: {settings.MEDIA_TTL_MINUTES} min, "
        f"Interval: {settings.MEDIA_CLEANUP_INTERVAL_MINUTES} min, Directory: '{settings.LOCAL_STORAGE_DIR}'"
    )

    while True:
        try:
            interval_seconds = max(1, settings.MEDIA_CLEANUP_INTERVAL_MINUTES) * 60
            await asyncio.sleep(interval_seconds)
            deleted = cleanup_expired_files(settings.LOCAL_STORAGE_DIR, settings.MEDIA_TTL_MINUTES)
            if deleted > 0:
                logger.info(f"Automated cleanup cycle completed. Removed {deleted} expired media file(s).")
        except asyncio.CancelledError:
            logger.info("Media cleanup worker cancelled.")
            break
        except Exception as e:
            logger.error(f"Unexpected error in media cleanup worker: {e}")
