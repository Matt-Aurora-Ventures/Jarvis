"""
API Request Log Rotation and Cleanup

Manages API request log files:
- Automatic rotation based on size or age
- Compression of old logs
- Cleanup of archived logs
- Preservation of recent logs for debugging

Usage:
    from api.log_rotation import setup_log_rotation, cleanup_old_logs

    # Setup rotation on app startup
    setup_log_rotation(
        log_file="/var/log/jarvis/api_requests.log",
        max_bytes=50 * 1024 * 1024,  # 50MB
        backup_count=10
    )

    # Cleanup old logs (run daily via cron)
    cleanup_old_logs(
        log_dir="/var/log/jarvis",
        max_age_days=30,
        compress_age_days=7
    )
"""

import gzip
import logging
import os
import shutil
import time
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def setup_log_rotation(
    log_file: str,
    max_bytes: int = 50 * 1024 * 1024,  # 50MB default
    backup_count: int = 10,
    use_timed_rotation: bool = False,
    when: str = "midnight",
    interval: int = 1,
) -> logging.Handler:
    """
    Setup log rotation for API request logs.

    Args:
        log_file: Path to log file
        max_bytes: Max size before rotation (for size-based rotation)
        backup_count: Number of backup files to keep
        use_timed_rotation: Use time-based rotation instead of size-based
        when: When to rotate (midnight, W0=Monday, etc.)
        interval: Rotation interval

    Returns:
        Configured logging handler
    """
    # Ensure log directory exists
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Create appropriate handler
    if use_timed_rotation:
        handler = TimedRotatingFileHandler(
            log_file,
            when=when,
            interval=interval,
            backupCount=backup_count,
            encoding="utf-8",
        )
        logger.info(
            f"Setup timed log rotation: {log_file} (when={when}, interval={interval}, backups={backup_count})"
        )
    else:
        handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        logger.info(
            f"Setup size-based log rotation: {log_file} (max={max_bytes / 1024 / 1024:.1f}MB, backups={backup_count})"
        )

    # Set formatter for structured logging
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)

    return handler


def compress_log_file(log_file: Path) -> Optional[Path]:
    """
    Compress a log file with gzip.

    Args:
        log_file: Path to log file

    Returns:
        Path to compressed file, or None if failed
    """
    if not log_file.exists():
        return None

    compressed_path = log_file.with_suffix(log_file.suffix + ".gz")

    try:
        with open(log_file, "rb") as f_in:
            with gzip.open(compressed_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

        # Remove original after successful compression
        log_file.unlink()
        logger.info(f"Compressed log: {log_file} -> {compressed_path}")
        return compressed_path

    except Exception as e:
        logger.error(f"Failed to compress {log_file}: {e}")
        return None


def cleanup_old_logs(
    log_dir: str,
    max_age_days: int = 30,
    compress_age_days: int = 7,
    pattern: str = "*.log*",
    dry_run: bool = False,
) -> dict:
    """
    Cleanup old log files.

    Args:
        log_dir: Directory containing logs
        max_age_days: Delete logs older than this many days
        compress_age_days: Compress logs older than this many days
        pattern: Glob pattern for log files
        dry_run: If True, only report what would be done

    Returns:
        Dict with cleanup statistics
    """
    log_path = Path(log_dir)

    if not log_path.exists():
        logger.warning(f"Log directory does not exist: {log_dir}")
        return {"error": "directory_not_found"}

    now = time.time()
    max_age_seconds = max_age_days * 24 * 60 * 60
    compress_age_seconds = compress_age_days * 24 * 60 * 60

    stats = {
        "scanned": 0,
        "compressed": 0,
        "deleted": 0,
        "total_size_freed": 0,
        "errors": 0,
    }

    # Find all log files
    for log_file in log_path.glob(pattern):
        if not log_file.is_file():
            continue

        stats["scanned"] += 1

        try:
            file_age = now - log_file.stat().st_mtime
            file_size = log_file.stat().st_size

            # Delete very old logs
            if file_age > max_age_seconds:
                if dry_run:
                    logger.info(f"[DRY RUN] Would delete: {log_file} (age: {file_age / 86400:.1f} days)")
                else:
                    log_file.unlink()
                    stats["deleted"] += 1
                    stats["total_size_freed"] += file_size
                    logger.info(f"Deleted old log: {log_file} (age: {file_age / 86400:.1f} days)")

            # Compress moderately old logs (not already compressed)
            elif file_age > compress_age_seconds and not log_file.suffix == ".gz":
                if dry_run:
                    logger.info(f"[DRY RUN] Would compress: {log_file} (age: {file_age / 86400:.1f} days)")
                else:
                    compressed = compress_log_file(log_file)
                    if compressed:
                        stats["compressed"] += 1
                        # Calculate size saved by compression
                        compressed_size = compressed.stat().st_size
                        stats["total_size_freed"] += file_size - compressed_size

        except Exception as e:
            logger.error(f"Error processing {log_file}: {e}")
            stats["errors"] += 1

    logger.info(
        f"Log cleanup complete: scanned={stats['scanned']}, "
        f"compressed={stats['compressed']}, deleted={stats['deleted']}, "
        f"freed={stats['total_size_freed'] / 1024 / 1024:.2f}MB, errors={stats['errors']}"
    )

    return stats


def get_log_stats(log_dir: str, pattern: str = "*.log*") -> dict:
    """
    Get statistics about log files.

    Args:
        log_dir: Directory containing logs
        pattern: Glob pattern for log files

    Returns:
        Dict with log statistics
    """
    log_path = Path(log_dir)

    if not log_path.exists():
        return {"error": "directory_not_found"}

    stats = {
        "total_files": 0,
        "total_size": 0,
        "compressed_files": 0,
        "compressed_size": 0,
        "uncompressed_files": 0,
        "uncompressed_size": 0,
        "oldest_log": None,
        "newest_log": None,
    }

    oldest_time = None
    newest_time = None

    for log_file in log_path.glob(pattern):
        if not log_file.is_file():
            continue

        file_size = log_file.stat().st_size
        file_time = log_file.stat().st_mtime

        stats["total_files"] += 1
        stats["total_size"] += file_size

        if log_file.suffix == ".gz":
            stats["compressed_files"] += 1
            stats["compressed_size"] += file_size
        else:
            stats["uncompressed_files"] += 1
            stats["uncompressed_size"] += file_size

        # Track oldest/newest
        if oldest_time is None or file_time < oldest_time:
            oldest_time = file_time
            stats["oldest_log"] = {
                "file": str(log_file),
                "age_days": (time.time() - file_time) / 86400,
            }

        if newest_time is None or file_time > newest_time:
            newest_time = file_time
            stats["newest_log"] = {
                "file": str(log_file),
                "age_days": (time.time() - file_time) / 86400,
            }

    # Convert sizes to MB
    stats["total_size_mb"] = stats["total_size"] / 1024 / 1024
    stats["compressed_size_mb"] = stats["compressed_size"] / 1024 / 1024
    stats["uncompressed_size_mb"] = stats["uncompressed_size"] / 1024 / 1024

    return stats


# Convenience function for setting up API logging with rotation
def setup_api_logging(
    log_dir: str = "/var/log/jarvis",
    log_level: str = "INFO",
    max_size_mb: int = 50,
    backup_count: int = 10,
) -> logging.Logger:
    """
    Setup comprehensive API logging with rotation.

    Args:
        log_dir: Directory for log files
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        max_size_mb: Max log file size in MB
        backup_count: Number of backup files to keep

    Returns:
        Configured logger
    """
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Create logger
    api_logger = logging.getLogger("jarvis.api")
    api_logger.setLevel(getattr(logging, log_level.upper()))

    # Add rotating file handler
    handler = setup_log_rotation(
        log_file=str(log_path / "api_requests.log"),
        max_bytes=max_size_mb * 1024 * 1024,
        backup_count=backup_count,
    )
    api_logger.addHandler(handler)

    return api_logger
