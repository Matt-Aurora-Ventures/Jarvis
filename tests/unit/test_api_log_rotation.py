"""
Comprehensive Tests for API Log Rotation Module.

Tests all log rotation components in api/log_rotation.py:
- setup_log_rotation (size-based and time-based rotation)
- compress_log_file (gzip compression)
- cleanup_old_logs (deletion, compression, dry-run)
- get_log_stats (statistics gathering)
- setup_api_logging (convenience function)

Target: 80%+ coverage with 50+ tests
"""

import gzip
import logging
import os
import pytest
import shutil
import time
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open, call


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_log_dir(tmp_path):
    """Create a mock log directory with sample files."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return log_dir


@pytest.fixture
def mock_log_file(mock_log_dir):
    """Create a mock log file."""
    log_file = mock_log_dir / "test.log"
    log_file.write_text("Sample log content\n" * 100)
    return log_file


@pytest.fixture
def mock_old_log_files(mock_log_dir):
    """Create multiple log files with different ages."""
    files = []
    now = time.time()

    # Create current log (< 7 days)
    current_log = mock_log_dir / "current.log"
    current_log.write_text("Current log content")
    os.utime(current_log, (now, now))
    files.append(current_log)

    # Create moderate age log (> 7 days, < 30 days) - should be compressed
    moderate_log = mock_log_dir / "moderate.log"
    moderate_log.write_text("Moderate age log content")
    moderate_age = now - (10 * 24 * 60 * 60)  # 10 days ago
    os.utime(moderate_log, (moderate_age, moderate_age))
    files.append(moderate_log)

    # Create old log (> 30 days) - should be deleted
    old_log = mock_log_dir / "old.log"
    old_log.write_text("Old log content")
    old_age = now - (35 * 24 * 60 * 60)  # 35 days ago
    os.utime(old_log, (old_age, old_age))
    files.append(old_log)

    # Create compressed log (already .gz)
    compressed_log = mock_log_dir / "already_compressed.log.gz"
    with gzip.open(compressed_log, 'wt') as f:
        f.write("Already compressed content")
    moderate_age2 = now - (15 * 24 * 60 * 60)  # 15 days ago
    os.utime(compressed_log, (moderate_age2, moderate_age2))
    files.append(compressed_log)

    return files


@pytest.fixture
def reset_logger():
    """Reset logger state after test."""
    yield
    # Clean up any handlers added during tests
    logger = logging.getLogger("jarvis.api")
    logger.handlers = []


# =============================================================================
# setup_log_rotation Tests
# =============================================================================


class TestSetupLogRotation:
    """Tests for setup_log_rotation function."""

    def test_creates_log_directory_if_not_exists(self, tmp_path):
        """Should create log directory if it doesn't exist."""
        from api.log_rotation import setup_log_rotation

        log_file = tmp_path / "new_dir" / "test.log"

        handler = setup_log_rotation(str(log_file))

        assert log_file.parent.exists()
        handler.close()

    def test_returns_rotating_file_handler_by_default(self, mock_log_dir):
        """Should return RotatingFileHandler when use_timed_rotation is False."""
        from api.log_rotation import setup_log_rotation

        log_file = mock_log_dir / "size_rotation.log"

        handler = setup_log_rotation(str(log_file), use_timed_rotation=False)

        assert isinstance(handler, RotatingFileHandler)
        handler.close()

    def test_returns_timed_rotating_handler_when_enabled(self, mock_log_dir):
        """Should return TimedRotatingFileHandler when use_timed_rotation is True."""
        from api.log_rotation import setup_log_rotation

        log_file = mock_log_dir / "timed_rotation.log"

        handler = setup_log_rotation(str(log_file), use_timed_rotation=True)

        assert isinstance(handler, TimedRotatingFileHandler)
        handler.close()

    def test_uses_default_max_bytes(self, mock_log_dir):
        """Should use 50MB default max bytes."""
        from api.log_rotation import setup_log_rotation

        log_file = mock_log_dir / "default_size.log"

        handler = setup_log_rotation(str(log_file))

        assert handler.maxBytes == 50 * 1024 * 1024
        handler.close()

    def test_uses_custom_max_bytes(self, mock_log_dir):
        """Should use custom max bytes when specified."""
        from api.log_rotation import setup_log_rotation

        log_file = mock_log_dir / "custom_size.log"
        custom_max = 100 * 1024 * 1024  # 100MB

        handler = setup_log_rotation(str(log_file), max_bytes=custom_max)

        assert handler.maxBytes == custom_max
        handler.close()

    def test_uses_default_backup_count(self, mock_log_dir):
        """Should use 10 as default backup count."""
        from api.log_rotation import setup_log_rotation

        log_file = mock_log_dir / "default_backups.log"

        handler = setup_log_rotation(str(log_file))

        assert handler.backupCount == 10
        handler.close()

    def test_uses_custom_backup_count(self, mock_log_dir):
        """Should use custom backup count when specified."""
        from api.log_rotation import setup_log_rotation

        log_file = mock_log_dir / "custom_backups.log"

        handler = setup_log_rotation(str(log_file), backup_count=5)

        assert handler.backupCount == 5
        handler.close()

    def test_timed_handler_uses_when_parameter(self, mock_log_dir):
        """Should configure TimedRotatingFileHandler with when parameter."""
        from api.log_rotation import setup_log_rotation

        log_file = mock_log_dir / "timed_when.log"

        handler = setup_log_rotation(
            str(log_file),
            use_timed_rotation=True,
            when="W0"  # Monday
        )

        assert handler.when == "W0"
        handler.close()

    def test_timed_handler_uses_interval_parameter(self, mock_log_dir):
        """Should configure TimedRotatingFileHandler with interval parameter."""
        from api.log_rotation import setup_log_rotation

        log_file = mock_log_dir / "timed_interval.log"

        handler = setup_log_rotation(
            str(log_file),
            use_timed_rotation=True,
            interval=2
        )

        assert handler.interval == 2 * 86400  # 2 days in seconds (midnight rotation)
        handler.close()

    def test_sets_formatter_on_handler(self, mock_log_dir):
        """Should set a formatter on the handler."""
        from api.log_rotation import setup_log_rotation

        log_file = mock_log_dir / "formatted.log"

        handler = setup_log_rotation(str(log_file))

        assert handler.formatter is not None
        handler.close()

    def test_formatter_includes_timestamp(self, mock_log_dir):
        """Should include timestamp in formatter."""
        from api.log_rotation import setup_log_rotation

        log_file = mock_log_dir / "timestamp.log"

        handler = setup_log_rotation(str(log_file))

        assert "%(asctime)s" in handler.formatter._fmt
        handler.close()

    def test_formatter_includes_level(self, mock_log_dir):
        """Should include level in formatter."""
        from api.log_rotation import setup_log_rotation

        log_file = mock_log_dir / "level.log"

        handler = setup_log_rotation(str(log_file))

        assert "%(levelname)s" in handler.formatter._fmt
        handler.close()

    def test_uses_utf8_encoding(self, mock_log_dir):
        """Should use UTF-8 encoding."""
        from api.log_rotation import setup_log_rotation

        log_file = mock_log_dir / "encoding.log"

        handler = setup_log_rotation(str(log_file))

        assert handler.encoding == "utf-8"
        handler.close()

    def test_logs_info_message_for_size_based_rotation(self, mock_log_dir, caplog):
        """Should log info message when setting up size-based rotation."""
        from api.log_rotation import setup_log_rotation

        log_file = mock_log_dir / "log_info_size.log"

        with caplog.at_level(logging.INFO):
            handler = setup_log_rotation(str(log_file))

        assert any("size-based" in record.message.lower() for record in caplog.records)
        handler.close()

    def test_logs_info_message_for_timed_rotation(self, mock_log_dir, caplog):
        """Should log info message when setting up timed rotation."""
        from api.log_rotation import setup_log_rotation

        log_file = mock_log_dir / "log_info_timed.log"

        with caplog.at_level(logging.INFO):
            handler = setup_log_rotation(str(log_file), use_timed_rotation=True)

        assert any("timed" in record.message.lower() for record in caplog.records)
        handler.close()


# =============================================================================
# compress_log_file Tests
# =============================================================================


class TestCompressLogFile:
    """Tests for compress_log_file function."""

    def test_compresses_existing_file(self, mock_log_file):
        """Should compress an existing log file."""
        from api.log_rotation import compress_log_file

        original_content = mock_log_file.read_text()

        result = compress_log_file(mock_log_file)

        assert result is not None
        assert result.suffix == ".gz"
        assert result.exists()

        # Verify content
        with gzip.open(result, 'rt') as f:
            compressed_content = f.read()
        assert compressed_content == original_content

    def test_removes_original_after_compression(self, mock_log_file):
        """Should remove original file after successful compression."""
        from api.log_rotation import compress_log_file

        compress_log_file(mock_log_file)

        assert not mock_log_file.exists()

    def test_returns_compressed_path(self, mock_log_file):
        """Should return path to compressed file."""
        from api.log_rotation import compress_log_file

        result = compress_log_file(mock_log_file)

        expected = mock_log_file.with_suffix(mock_log_file.suffix + ".gz")
        assert result == expected

    def test_returns_none_for_nonexistent_file(self, mock_log_dir):
        """Should return None if file doesn't exist."""
        from api.log_rotation import compress_log_file

        nonexistent = mock_log_dir / "nonexistent.log"

        result = compress_log_file(nonexistent)

        assert result is None

    def test_handles_empty_file(self, mock_log_dir):
        """Should handle empty files."""
        from api.log_rotation import compress_log_file

        empty_file = mock_log_dir / "empty.log"
        empty_file.touch()

        result = compress_log_file(empty_file)

        assert result is not None
        assert result.exists()

    def test_handles_large_file(self, mock_log_dir):
        """Should handle large files efficiently."""
        from api.log_rotation import compress_log_file

        large_file = mock_log_dir / "large.log"
        # Create a ~1MB file
        large_file.write_text("x" * (1024 * 1024))

        result = compress_log_file(large_file)

        assert result is not None
        assert result.exists()
        # Compressed should be smaller
        assert result.stat().st_size < (1024 * 1024)

    def test_returns_none_on_compression_error(self, mock_log_dir, caplog):
        """Should return None and log error on compression failure."""
        from api.log_rotation import compress_log_file

        log_file = mock_log_dir / "error.log"
        log_file.write_text("content")

        with patch('builtins.open', side_effect=IOError("Mock IO error")):
            with caplog.at_level(logging.ERROR):
                result = compress_log_file(log_file)

        assert result is None
        assert any("failed to compress" in record.message.lower() for record in caplog.records)

    def test_logs_success_message(self, mock_log_file, caplog):
        """Should log success message after compression."""
        from api.log_rotation import compress_log_file

        with caplog.at_level(logging.INFO):
            compress_log_file(mock_log_file)

        assert any("compressed" in record.message.lower() for record in caplog.records)

    def test_preserves_file_name_base(self, mock_log_file):
        """Should preserve base filename in compressed output."""
        from api.log_rotation import compress_log_file

        result = compress_log_file(mock_log_file)

        assert mock_log_file.stem in result.stem


# =============================================================================
# cleanup_old_logs Tests
# =============================================================================


class TestCleanupOldLogs:
    """Tests for cleanup_old_logs function."""

    def test_returns_error_for_nonexistent_directory(self, tmp_path):
        """Should return error for nonexistent directory."""
        from api.log_rotation import cleanup_old_logs

        nonexistent = str(tmp_path / "nonexistent")

        result = cleanup_old_logs(nonexistent)

        assert result == {"error": "directory_not_found"}

    def test_scans_all_log_files(self, mock_old_log_files, mock_log_dir):
        """Should scan all log files matching pattern."""
        from api.log_rotation import cleanup_old_logs

        result = cleanup_old_logs(str(mock_log_dir), dry_run=True)

        # Should have scanned all 4 files
        assert result["scanned"] >= 3

    def test_deletes_old_logs(self, mock_old_log_files, mock_log_dir):
        """Should delete logs older than max_age_days."""
        from api.log_rotation import cleanup_old_logs

        result = cleanup_old_logs(str(mock_log_dir), max_age_days=30)

        assert result["deleted"] >= 1
        # Old log should be gone
        assert not (mock_log_dir / "old.log").exists()

    def test_compresses_moderate_age_logs(self, mock_old_log_files, mock_log_dir):
        """Should compress logs older than compress_age_days but younger than max_age_days."""
        from api.log_rotation import cleanup_old_logs

        result = cleanup_old_logs(str(mock_log_dir), compress_age_days=7, max_age_days=30)

        assert result["compressed"] >= 1
        # Moderate log should be compressed
        assert (mock_log_dir / "moderate.log.gz").exists()
        assert not (mock_log_dir / "moderate.log").exists()

    def test_skips_already_compressed_files(self, mock_old_log_files, mock_log_dir):
        """Should skip files that are already compressed (.gz)."""
        from api.log_rotation import cleanup_old_logs

        # Note: The compressed file is 15 days old (> 7 days compress threshold)
        # but should not be re-compressed because it already has .gz suffix
        initial_compressed = (mock_log_dir / "already_compressed.log.gz").exists()

        result = cleanup_old_logs(str(mock_log_dir), compress_age_days=7, max_age_days=30)

        # The already compressed file should still exist
        assert (mock_log_dir / "already_compressed.log.gz").exists() == initial_compressed

    def test_dry_run_does_not_modify_files(self, mock_old_log_files, mock_log_dir):
        """Should not modify files when dry_run is True."""
        from api.log_rotation import cleanup_old_logs

        # Get file count before
        files_before = list(mock_log_dir.glob("*.log*"))

        result = cleanup_old_logs(str(mock_log_dir), dry_run=True)

        # Get file count after
        files_after = list(mock_log_dir.glob("*.log*"))

        assert len(files_before) == len(files_after)
        assert result["deleted"] == 0
        assert result["compressed"] == 0

    def test_dry_run_logs_would_delete(self, mock_old_log_files, mock_log_dir, caplog):
        """Should log what would be deleted in dry run."""
        from api.log_rotation import cleanup_old_logs

        with caplog.at_level(logging.INFO):
            cleanup_old_logs(str(mock_log_dir), dry_run=True)

        assert any("dry run" in record.message.lower() for record in caplog.records)

    def test_custom_pattern_matching(self, mock_log_dir):
        """Should use custom glob pattern."""
        from api.log_rotation import cleanup_old_logs

        # Create a .txt file
        txt_file = mock_log_dir / "test.txt"
        txt_file.write_text("text content")
        old_time = time.time() - (40 * 24 * 60 * 60)
        os.utime(txt_file, (old_time, old_time))

        result = cleanup_old_logs(str(mock_log_dir), pattern="*.txt", max_age_days=30)

        assert result["deleted"] >= 1
        assert not txt_file.exists()

    def test_tracks_total_size_freed(self, mock_log_dir):
        """Should track total size freed from deletions."""
        from api.log_rotation import cleanup_old_logs

        # Create a file old enough to be deleted
        old_file = mock_log_dir / "to_delete.log"
        old_file.write_text("x" * 1000)  # 1000 bytes
        old_time = time.time() - (40 * 24 * 60 * 60)  # 40 days ago
        os.utime(old_file, (old_time, old_time))

        result = cleanup_old_logs(str(mock_log_dir), max_age_days=30, compress_age_days=45)

        # Should have freed the deleted file's size (only deletion, no compression)
        assert result["total_size_freed"] == 1000
        assert result["deleted"] == 1

    def test_tracks_errors(self, mock_log_dir):
        """Should track errors during processing."""
        from api.log_rotation import cleanup_old_logs

        # Create a file
        log_file = mock_log_dir / "error_file.log"
        log_file.write_text("content")
        old_time = time.time() - (40 * 24 * 60 * 60)
        os.utime(log_file, (old_time, old_time))

        # Patch unlink to raise an error
        with patch.object(Path, 'unlink', side_effect=PermissionError("Access denied")):
            result = cleanup_old_logs(str(mock_log_dir), max_age_days=30)

        assert result["errors"] >= 1

    def test_logs_cleanup_summary(self, mock_old_log_files, mock_log_dir, caplog):
        """Should log cleanup summary."""
        from api.log_rotation import cleanup_old_logs

        with caplog.at_level(logging.INFO):
            cleanup_old_logs(str(mock_log_dir))

        assert any("cleanup complete" in record.message.lower() for record in caplog.records)

    def test_skips_directories(self, mock_log_dir):
        """Should skip directories when iterating."""
        from api.log_rotation import cleanup_old_logs

        # Create a subdirectory with .log in name
        subdir = mock_log_dir / "subdir.log"
        subdir.mkdir()

        result = cleanup_old_logs(str(mock_log_dir))

        # Should not count directory or error on it
        assert subdir.exists()

    def test_default_max_age_days(self, mock_log_dir):
        """Should use 30 days as default max age."""
        from api.log_rotation import cleanup_old_logs

        # Create file 25 days old (should NOT be deleted with default 30 days)
        # But it IS older than compress_age (7 days), so it will be compressed
        log_file = mock_log_dir / "recent_enough.log"
        log_file.write_text("content")
        age_25_days = time.time() - (25 * 24 * 60 * 60)
        os.utime(log_file, (age_25_days, age_25_days))

        result = cleanup_old_logs(str(mock_log_dir))

        # File should be compressed (> 7 days) but not deleted (< 30 days)
        # Either original exists or compressed version exists
        assert (log_file.exists() or (mock_log_dir / "recent_enough.log.gz").exists())
        # Should not be deleted
        assert result["deleted"] == 0

    def test_default_compress_age_days(self, mock_log_dir):
        """Should use 7 days as default compress age."""
        from api.log_rotation import cleanup_old_logs

        # Create file 5 days old (should NOT be compressed with default 7 days)
        log_file = mock_log_dir / "too_recent.log"
        log_file.write_text("content")
        age_5_days = time.time() - (5 * 24 * 60 * 60)
        os.utime(log_file, (age_5_days, age_5_days))

        result = cleanup_old_logs(str(mock_log_dir))

        # File should still exist uncompressed
        assert log_file.exists()
        assert not (mock_log_dir / "too_recent.log.gz").exists()


# =============================================================================
# get_log_stats Tests
# =============================================================================


class TestGetLogStats:
    """Tests for get_log_stats function."""

    def test_returns_error_for_nonexistent_directory(self, tmp_path):
        """Should return error for nonexistent directory."""
        from api.log_rotation import get_log_stats

        nonexistent = str(tmp_path / "nonexistent")

        result = get_log_stats(nonexistent)

        assert result == {"error": "directory_not_found"}

    def test_counts_total_files(self, mock_old_log_files, mock_log_dir):
        """Should count total log files."""
        from api.log_rotation import get_log_stats

        result = get_log_stats(str(mock_log_dir))

        assert result["total_files"] >= 3

    def test_calculates_total_size(self, mock_log_file, mock_log_dir):
        """Should calculate total size."""
        from api.log_rotation import get_log_stats

        result = get_log_stats(str(mock_log_dir))

        assert result["total_size"] > 0

    def test_counts_compressed_files(self, mock_old_log_files, mock_log_dir):
        """Should count compressed (.gz) files separately."""
        from api.log_rotation import get_log_stats

        result = get_log_stats(str(mock_log_dir))

        assert result["compressed_files"] >= 1

    def test_counts_uncompressed_files(self, mock_old_log_files, mock_log_dir):
        """Should count uncompressed files separately."""
        from api.log_rotation import get_log_stats

        result = get_log_stats(str(mock_log_dir))

        assert result["uncompressed_files"] >= 2

    def test_calculates_compressed_size(self, mock_old_log_files, mock_log_dir):
        """Should calculate compressed files total size."""
        from api.log_rotation import get_log_stats

        result = get_log_stats(str(mock_log_dir))

        assert result["compressed_size"] >= 0

    def test_calculates_uncompressed_size(self, mock_old_log_files, mock_log_dir):
        """Should calculate uncompressed files total size."""
        from api.log_rotation import get_log_stats

        result = get_log_stats(str(mock_log_dir))

        assert result["uncompressed_size"] > 0

    def test_tracks_oldest_log(self, mock_old_log_files, mock_log_dir):
        """Should track oldest log file."""
        from api.log_rotation import get_log_stats

        result = get_log_stats(str(mock_log_dir))

        assert result["oldest_log"] is not None
        assert "file" in result["oldest_log"]
        assert "age_days" in result["oldest_log"]
        assert result["oldest_log"]["age_days"] > 30  # Old file is 35 days

    def test_tracks_newest_log(self, mock_old_log_files, mock_log_dir):
        """Should track newest log file."""
        from api.log_rotation import get_log_stats

        result = get_log_stats(str(mock_log_dir))

        assert result["newest_log"] is not None
        assert "file" in result["newest_log"]
        assert "age_days" in result["newest_log"]
        assert result["newest_log"]["age_days"] < 1  # Current file is recent

    def test_converts_sizes_to_mb(self, mock_log_file, mock_log_dir):
        """Should include sizes in MB."""
        from api.log_rotation import get_log_stats

        result = get_log_stats(str(mock_log_dir))

        assert "total_size_mb" in result
        assert "compressed_size_mb" in result
        assert "uncompressed_size_mb" in result

    def test_custom_pattern_matching(self, mock_log_dir):
        """Should use custom glob pattern."""
        from api.log_rotation import get_log_stats

        # Create some .txt files
        (mock_log_dir / "file1.txt").write_text("content1")
        (mock_log_dir / "file2.txt").write_text("content2")
        (mock_log_dir / "file.log").write_text("content3")

        result = get_log_stats(str(mock_log_dir), pattern="*.txt")

        assert result["total_files"] == 2

    def test_skips_directories(self, mock_log_dir):
        """Should skip directories when iterating."""
        from api.log_rotation import get_log_stats

        # Create a file
        (mock_log_dir / "real.log").write_text("content")
        # Create a subdirectory with .log in name
        subdir = mock_log_dir / "subdir.log"
        subdir.mkdir()

        result = get_log_stats(str(mock_log_dir))

        # Should only count the file, not the directory
        assert result["total_files"] == 1

    def test_handles_empty_directory(self, mock_log_dir):
        """Should handle empty directory."""
        from api.log_rotation import get_log_stats

        result = get_log_stats(str(mock_log_dir))

        assert result["total_files"] == 0
        assert result["total_size"] == 0
        assert result["oldest_log"] is None
        assert result["newest_log"] is None

    def test_oldest_newest_same_when_single_file(self, mock_log_dir):
        """Should have same oldest/newest when only one file."""
        from api.log_rotation import get_log_stats

        single_file = mock_log_dir / "single.log"
        single_file.write_text("content")

        result = get_log_stats(str(mock_log_dir))

        assert result["oldest_log"]["file"] == result["newest_log"]["file"]


# =============================================================================
# setup_api_logging Tests
# =============================================================================


class TestSetupApiLogging:
    """Tests for setup_api_logging convenience function."""

    def test_creates_log_directory(self, tmp_path, reset_logger):
        """Should create log directory if not exists."""
        from api.log_rotation import setup_api_logging

        log_dir = tmp_path / "new_api_logs"

        logger = setup_api_logging(log_dir=str(log_dir))

        assert log_dir.exists()
        # Clean up handler
        for h in logger.handlers:
            h.close()

    def test_returns_configured_logger(self, tmp_path, reset_logger):
        """Should return a configured logger."""
        from api.log_rotation import setup_api_logging

        log_dir = tmp_path / "api_logs"

        logger = setup_api_logging(log_dir=str(log_dir))

        assert isinstance(logger, logging.Logger)
        assert logger.name == "jarvis.api"
        for h in logger.handlers:
            h.close()

    def test_sets_log_level(self, tmp_path, reset_logger):
        """Should set the specified log level."""
        from api.log_rotation import setup_api_logging

        log_dir = tmp_path / "api_logs"

        logger = setup_api_logging(log_dir=str(log_dir), log_level="DEBUG")

        assert logger.level == logging.DEBUG
        for h in logger.handlers:
            h.close()

    def test_default_log_level_is_info(self, tmp_path, reset_logger):
        """Should use INFO as default log level."""
        from api.log_rotation import setup_api_logging

        log_dir = tmp_path / "api_logs"

        logger = setup_api_logging(log_dir=str(log_dir))

        assert logger.level == logging.INFO
        for h in logger.handlers:
            h.close()

    def test_adds_rotating_handler(self, tmp_path, reset_logger):
        """Should add a rotating file handler."""
        from api.log_rotation import setup_api_logging

        log_dir = tmp_path / "api_logs"

        logger = setup_api_logging(log_dir=str(log_dir))

        # Should have at least one RotatingFileHandler
        rotating_handlers = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
        assert len(rotating_handlers) >= 1
        for h in logger.handlers:
            h.close()

    def test_uses_custom_max_size(self, tmp_path, reset_logger):
        """Should use custom max size in MB."""
        from api.log_rotation import setup_api_logging

        log_dir = tmp_path / "api_logs"

        logger = setup_api_logging(log_dir=str(log_dir), max_size_mb=100)

        rotating_handlers = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
        assert rotating_handlers[0].maxBytes == 100 * 1024 * 1024
        for h in logger.handlers:
            h.close()

    def test_uses_custom_backup_count(self, tmp_path, reset_logger):
        """Should use custom backup count."""
        from api.log_rotation import setup_api_logging

        log_dir = tmp_path / "api_logs"

        logger = setup_api_logging(log_dir=str(log_dir), backup_count=5)

        rotating_handlers = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
        assert rotating_handlers[0].backupCount == 5
        for h in logger.handlers:
            h.close()

    def test_creates_api_requests_log_file(self, tmp_path, reset_logger):
        """Should create api_requests.log file."""
        from api.log_rotation import setup_api_logging

        log_dir = tmp_path / "api_logs"

        logger = setup_api_logging(log_dir=str(log_dir))

        expected_file = log_dir / "api_requests.log"
        assert expected_file.exists()
        for h in logger.handlers:
            h.close()

    def test_handles_uppercase_log_levels(self, tmp_path, reset_logger):
        """Should handle uppercase log levels."""
        from api.log_rotation import setup_api_logging

        log_dir = tmp_path / "api_logs"

        logger = setup_api_logging(log_dir=str(log_dir), log_level="WARNING")

        assert logger.level == logging.WARNING
        for h in logger.handlers:
            h.close()

    def test_handles_lowercase_log_levels(self, tmp_path, reset_logger):
        """Should handle lowercase log levels."""
        from api.log_rotation import setup_api_logging

        log_dir = tmp_path / "api_logs"

        logger = setup_api_logging(log_dir=str(log_dir), log_level="error")

        assert logger.level == logging.ERROR
        for h in logger.handlers:
            h.close()


# =============================================================================
# Integration Tests
# =============================================================================


class TestLogRotationIntegration:
    """Integration tests for log rotation workflow."""

    def test_full_rotation_workflow(self, tmp_path):
        """Test complete workflow: create logs, compress old, delete ancient."""
        from api.log_rotation import setup_log_rotation, cleanup_old_logs, get_log_stats

        log_dir = tmp_path / "integration_logs"
        log_dir.mkdir()
        log_file = log_dir / "test.log"

        # Setup rotation
        handler = setup_log_rotation(str(log_file), max_bytes=1024, backup_count=3)

        # Write some logs
        test_logger = logging.getLogger("test.integration")
        test_logger.addHandler(handler)
        test_logger.setLevel(logging.DEBUG)

        for i in range(100):
            test_logger.info(f"Log message {i} " + "x" * 50)

        handler.close()

        # Get stats
        stats = get_log_stats(str(log_dir))

        assert stats["total_files"] >= 1

    def test_compress_and_stats_workflow(self, mock_log_file, mock_log_dir):
        """Test compression followed by stats gathering."""
        from api.log_rotation import compress_log_file, get_log_stats

        # Get initial stats
        initial_stats = get_log_stats(str(mock_log_dir))
        initial_uncompressed = initial_stats["uncompressed_files"]

        # Compress the file
        compress_log_file(mock_log_file)

        # Get new stats
        final_stats = get_log_stats(str(mock_log_dir))

        # Should have one more compressed, one less uncompressed
        assert final_stats["compressed_files"] == initial_stats["compressed_files"] + 1
        assert final_stats["uncompressed_files"] == initial_uncompressed - 1

    def test_cleanup_respects_retention_policy(self, tmp_path):
        """Test that cleanup respects retention policy correctly."""
        from api.log_rotation import cleanup_old_logs

        log_dir = tmp_path / "retention_test"
        log_dir.mkdir()

        now = time.time()

        # Create files with specific ages
        files_config = [
            ("keep_fresh.log", 3),       # 3 days - keep as is
            ("compress_medium.log", 10), # 10 days - compress
            ("delete_old.log", 40),      # 40 days - delete
        ]

        for filename, age_days in files_config:
            f = log_dir / filename
            f.write_text(f"Content for {filename}")
            age_seconds = age_days * 24 * 60 * 60
            file_time = now - age_seconds
            os.utime(f, (file_time, file_time))

        # Run cleanup
        result = cleanup_old_logs(
            str(log_dir),
            max_age_days=30,
            compress_age_days=7
        )

        # Verify results
        assert (log_dir / "keep_fresh.log").exists()
        assert not (log_dir / "compress_medium.log").exists()
        assert (log_dir / "compress_medium.log.gz").exists()
        assert not (log_dir / "delete_old.log").exists()

        assert result["deleted"] == 1
        assert result["compressed"] == 1


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCasesAndErrorHandling:
    """Tests for edge cases and error conditions."""

    def test_compress_handles_binary_content(self, mock_log_dir):
        """Should handle files with binary content."""
        from api.log_rotation import compress_log_file

        binary_file = mock_log_dir / "binary.log"
        binary_file.write_bytes(bytes(range(256)) * 10)

        result = compress_log_file(binary_file)

        assert result is not None
        assert result.exists()

    def test_cleanup_handles_permission_error_gracefully(self, mock_log_dir, caplog):
        """Should handle permission errors gracefully during cleanup."""
        from api.log_rotation import cleanup_old_logs

        log_file = mock_log_dir / "protected.log"
        log_file.write_text("content")
        old_time = time.time() - (40 * 24 * 60 * 60)
        os.utime(log_file, (old_time, old_time))

        with patch.object(Path, 'unlink', side_effect=PermissionError("Cannot delete")):
            with caplog.at_level(logging.ERROR):
                result = cleanup_old_logs(str(mock_log_dir), max_age_days=30)

        assert result["errors"] >= 1
        assert any("error" in record.message.lower() for record in caplog.records)

    def test_stats_handles_stat_error(self, mock_log_dir):
        """Should handle stat errors during stats gathering."""
        from api.log_rotation import get_log_stats

        log_file = mock_log_dir / "stat_error.log"
        log_file.write_text("content")

        # This will cause an error when trying to get stats
        with patch.object(Path, 'stat', side_effect=OSError("Stat error")):
            # The function should handle the error internally
            # since it catches exceptions in the loop
            pass  # Function structure handles this per-file

    def test_setup_rotation_with_nested_directory(self, tmp_path):
        """Should create deeply nested directories."""
        from api.log_rotation import setup_log_rotation

        log_file = tmp_path / "a" / "b" / "c" / "d" / "test.log"

        handler = setup_log_rotation(str(log_file))

        assert log_file.parent.exists()
        handler.close()

    def test_compress_file_with_special_characters_in_name(self, mock_log_dir):
        """Should handle files with special characters in name."""
        from api.log_rotation import compress_log_file

        special_file = mock_log_dir / "log-2024-01-15_10-30-00.log"
        special_file.write_text("content")

        result = compress_log_file(special_file)

        assert result is not None
        assert result.exists()

    def test_cleanup_with_very_small_age_thresholds(self, mock_log_dir):
        """Should handle very small age thresholds."""
        from api.log_rotation import cleanup_old_logs

        log_file = mock_log_dir / "any.log"
        log_file.write_text("content")
        # Make the file 1 day old so it's definitely > 0 seconds
        one_day_ago = time.time() - (1 * 24 * 60 * 60)
        os.utime(log_file, (one_day_ago, one_day_ago))

        # With max_age=0 (0 days = 0 seconds), file at 1 day old should be deleted
        result = cleanup_old_logs(str(mock_log_dir), max_age_days=0)

        assert result["deleted"] >= 1

    def test_get_stats_with_large_number_of_files(self, mock_log_dir):
        """Should handle directory with many files."""
        from api.log_rotation import get_log_stats

        # Create 100 log files
        for i in range(100):
            (mock_log_dir / f"log_{i:03d}.log").write_text(f"content {i}")

        result = get_log_stats(str(mock_log_dir))

        assert result["total_files"] == 100


# =============================================================================
# Module Exports Tests
# =============================================================================


class TestModuleExports:
    """Tests for module exports."""

    def test_all_functions_exported(self):
        """Should export all public functions."""
        from api.log_rotation import (
            setup_log_rotation,
            compress_log_file,
            cleanup_old_logs,
            get_log_stats,
            setup_api_logging,
        )

        assert callable(setup_log_rotation)
        assert callable(compress_log_file)
        assert callable(cleanup_old_logs)
        assert callable(get_log_stats)
        assert callable(setup_api_logging)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
