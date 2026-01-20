"""
Tests for API Log Rotation and Cleanup

Tests:
- Log rotation (size-based and time-based)
- Log compression
- Old log cleanup
- Log statistics
"""

import gzip
import logging
import os
import tempfile
import time
from pathlib import Path

import pytest

from api.log_rotation import (
    setup_log_rotation,
    compress_log_file,
    cleanup_old_logs,
    get_log_stats,
    setup_api_logging,
)


# =============================================================================
# Log Rotation Tests
# =============================================================================


def test_setup_size_based_rotation():
    """Test size-based log rotation setup."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "test.log")

        handler = setup_log_rotation(
            log_file=log_file,
            max_bytes=1024,
            backup_count=5,
        )

        assert handler is not None
        assert os.path.exists(log_file)
        assert handler.maxBytes == 1024
        assert handler.backupCount == 5


def test_setup_timed_rotation():
    """Test time-based log rotation setup."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "test.log")

        handler = setup_log_rotation(
            log_file=log_file,
            use_timed_rotation=True,
            when="midnight",
            interval=1,
            backup_count=7,
        )

        assert handler is not None
        assert os.path.exists(log_file)
        assert handler.backupCount == 7


def test_log_rotation_creates_backups():
    """Test that rotation creates backup files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "test.log")

        # Setup with very small max size
        handler = setup_log_rotation(
            log_file=log_file,
            max_bytes=100,  # 100 bytes
            backup_count=3,
        )

        logger = logging.getLogger("test_rotation")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # Write enough logs to trigger rotation
        for i in range(20):
            logger.info(f"Log message {i} with enough text to trigger rotation when combined")

        # Should have created backup files
        log_dir = Path(tmpdir)
        log_files = list(log_dir.glob("test.log*"))

        # Should have main log + at least 1 backup
        assert len(log_files) > 1


# =============================================================================
# Compression Tests
# =============================================================================


def test_compress_log_file():
    """Test log file compression."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test.log"

        # Create a test log file
        log_file.write_text("Test log content\n" * 100)
        original_size = log_file.stat().st_size

        # Compress it
        compressed = compress_log_file(log_file)

        assert compressed is not None
        assert compressed.exists()
        assert compressed.suffix == ".gz"
        assert not log_file.exists()  # Original should be deleted

        # Compressed should be smaller
        compressed_size = compressed.stat().st_size
        assert compressed_size < original_size

        # Should be able to decompress
        with gzip.open(compressed, "rt") as f:
            content = f.read()
            assert "Test log content" in content


def test_compress_nonexistent_file():
    """Test compressing non-existent file."""
    result = compress_log_file(Path("/tmp/nonexistent.log"))
    assert result is None


# =============================================================================
# Cleanup Tests
# =============================================================================


def test_cleanup_old_logs():
    """Test cleanup of old log files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)

        # Create test log files with different ages
        now = time.time()

        # Recent log (1 day old)
        recent_log = log_dir / "recent.log"
        recent_log.write_text("Recent log")
        os.utime(recent_log, (now - 86400, now - 86400))  # 1 day old

        # Old log to compress (10 days old)
        old_log = log_dir / "old.log"
        old_log.write_text("Old log to compress")
        os.utime(old_log, (now - 10 * 86400, now - 10 * 86400))  # 10 days old

        # Very old log to delete (40 days old)
        very_old_log = log_dir / "very_old.log"
        very_old_log.write_text("Very old log to delete")
        os.utime(very_old_log, (now - 40 * 86400, now - 40 * 86400))  # 40 days old

        # Run cleanup
        stats = cleanup_old_logs(
            log_dir=str(log_dir),
            max_age_days=30,
            compress_age_days=7,
            pattern="*.log",
            dry_run=False,
        )

        # Check stats
        assert stats["scanned"] == 3
        assert stats["compressed"] == 1
        assert stats["deleted"] == 1
        assert stats["errors"] == 0

        # Check files
        assert recent_log.exists()  # Should still exist
        assert not old_log.exists()  # Should be compressed
        assert (log_dir / "old.log.gz").exists()  # Compressed version
        assert not very_old_log.exists()  # Should be deleted


def test_cleanup_dry_run():
    """Test dry run mode doesn't modify files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)

        # Create an old log file
        old_log = log_dir / "old.log"
        old_log.write_text("Old log")
        now = time.time()
        os.utime(old_log, (now - 40 * 86400, now - 40 * 86400))

        # Run dry run
        stats = cleanup_old_logs(
            log_dir=str(log_dir),
            max_age_days=30,
            dry_run=True,
        )

        # File should still exist
        assert old_log.exists()
        assert stats["scanned"] > 0
        assert stats["deleted"] == 0


def test_cleanup_nonexistent_directory():
    """Test cleanup on non-existent directory."""
    stats = cleanup_old_logs(
        log_dir="/tmp/nonexistent_log_dir_12345",
        max_age_days=30,
    )

    assert "error" in stats
    assert stats["error"] == "directory_not_found"


def test_cleanup_preserves_compressed_logs():
    """Test that already compressed logs are not re-compressed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)

        # Create a compressed log file
        compressed_log = log_dir / "old.log.gz"
        with gzip.open(compressed_log, "wt") as f:
            f.write("Compressed log")

        # Make it old
        now = time.time()
        os.utime(compressed_log, (now - 10 * 86400, now - 10 * 86400))

        # Run cleanup
        stats = cleanup_old_logs(
            log_dir=str(log_dir),
            max_age_days=30,
            compress_age_days=7,
        )

        # Should not try to re-compress
        assert stats["compressed"] == 0
        assert compressed_log.exists()


# =============================================================================
# Log Statistics Tests
# =============================================================================


def test_get_log_stats():
    """Test log statistics collection."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)

        # Create test files
        log1 = log_dir / "test1.log"
        log1.write_text("Log 1 content")

        log2 = log_dir / "test2.log"
        log2.write_text("Log 2 content" * 10)

        compressed_log = log_dir / "test3.log.gz"
        with gzip.open(compressed_log, "wt") as f:
            f.write("Compressed log content")

        # Get stats
        stats = get_log_stats(str(log_dir))

        assert stats["total_files"] == 3
        assert stats["uncompressed_files"] == 2
        assert stats["compressed_files"] == 1
        assert stats["total_size"] > 0
        assert stats["total_size_mb"] > 0

        # Check oldest/newest tracking
        assert stats["oldest_log"] is not None
        assert stats["newest_log"] is not None
        assert "file" in stats["oldest_log"]
        assert "age_days" in stats["oldest_log"]


def test_get_log_stats_empty_directory():
    """Test stats on empty directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        stats = get_log_stats(str(tmpdir))

        assert stats["total_files"] == 0
        assert stats["total_size"] == 0
        assert stats["oldest_log"] is None
        assert stats["newest_log"] is None


def test_get_log_stats_nonexistent_directory():
    """Test stats on non-existent directory."""
    stats = get_log_stats("/tmp/nonexistent_12345")

    assert "error" in stats
    assert stats["error"] == "directory_not_found"


# =============================================================================
# Setup API Logging Tests
# =============================================================================


def test_setup_api_logging():
    """Test full API logging setup."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = setup_api_logging(
            log_dir=tmpdir,
            log_level="INFO",
            max_size_mb=10,
            backup_count=5,
        )

        assert logger is not None
        assert logger.level == logging.INFO
        assert len(logger.handlers) > 0

        # Test logging
        logger.info("Test message")

        # Log file should exist
        log_file = Path(tmpdir) / "api_requests.log"
        assert log_file.exists()

        # Should contain the message
        content = log_file.read_text()
        assert "Test message" in content


# =============================================================================
# Integration Tests
# =============================================================================


def test_full_rotation_and_cleanup_workflow():
    """Test complete workflow: rotation -> compression -> cleanup."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "api.log")

        # Setup rotation
        handler = setup_log_rotation(
            log_file=log_file,
            max_bytes=500,
            backup_count=10,
        )

        logger = logging.getLogger("test_full_workflow")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # Generate logs to trigger rotation
        for i in range(100):
            logger.info(f"Log entry {i} with some content to make it larger")

        # Wait for rotation to complete
        handler.close()

        # Make backup logs appear old
        log_dir = Path(tmpdir)
        now = time.time()
        for backup in log_dir.glob("api.log.*"):
            os.utime(backup, (now - 10 * 86400, now - 10 * 86400))

        # Run cleanup
        stats = cleanup_old_logs(
            log_dir=str(log_dir),
            max_age_days=30,
            compress_age_days=7,
            pattern="api.log*",
        )

        # Should have compressed some backups
        assert stats["compressed"] > 0

        # Should have compressed files
        compressed_files = list(log_dir.glob("*.gz"))
        assert len(compressed_files) > 0


def test_pattern_filtering():
    """Test that cleanup respects file patterns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)

        # Create different types of files
        api_log = log_dir / "api.log"
        api_log.write_text("API log")

        error_log = log_dir / "error.log"
        error_log.write_text("Error log")

        other_file = log_dir / "data.txt"
        other_file.write_text("Not a log")

        # Make them old
        now = time.time()
        for f in [api_log, error_log, other_file]:
            os.utime(f, (now - 40 * 86400, now - 40 * 86400))

        # Cleanup only .log files
        stats = cleanup_old_logs(
            log_dir=str(log_dir),
            max_age_days=30,
            pattern="*.log",
        )

        # Should have processed only .log files
        assert stats["scanned"] == 2
        assert stats["deleted"] == 2

        # Other file should remain
        assert other_file.exists()
        assert not api_log.exists()
        assert not error_log.exists()
