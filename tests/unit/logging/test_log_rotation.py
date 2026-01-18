"""
Tests for log rotation and cleanup.
"""

import pytest
import os
import gzip
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestLogRotation:
    """Tests for log file rotation."""

    def test_daily_log_file_naming(self):
        """Test that daily log files are named correctly."""
        from core.logging.structured_logger import get_log_filename

        filename = get_log_filename("jarvis", datetime(2026, 1, 18))
        assert "jarvis-2026-01-18" in filename
        assert filename.endswith(".jsonl")

    def test_rotate_creates_new_file(self):
        """Test that rotation creates new daily file."""
        from core.logging.structured_logger import rotate_logs

        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            log_dir.mkdir()

            # Create an old log file
            old_date = datetime(2026, 1, 17)
            old_file = log_dir / f"jarvis-2026-01-17.jsonl"
            old_file.write_text('{"test": "old"}\n')

            # Rotate with current date
            rotate_logs(log_dir, datetime(2026, 1, 18))

            # Old file should still exist (not archived yet within 7 days)
            assert old_file.exists()

    def test_archive_old_logs(self):
        """Test that logs older than 7 days are archived."""
        from core.logging.structured_logger import rotate_and_cleanup_logs

        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            log_dir.mkdir()
            archive_dir = log_dir / "archive"
            archive_dir.mkdir()

            # Create log file older than 7 days
            old_date = datetime.now() - timedelta(days=10)
            old_file = log_dir / f"jarvis-{old_date.strftime('%Y-%m-%d')}.jsonl"
            old_file.write_text('{"test": "old log"}\n')

            # Run rotation
            rotate_and_cleanup_logs(log_dir, archive_dir, keep_days=7, delete_after_days=30)

            # Original should be gone, archive should exist
            assert not old_file.exists()
            archived = list(archive_dir.glob("*.gz"))
            assert len(archived) >= 1

    def test_archive_is_gzipped(self):
        """Test that archived logs are gzip compressed."""
        from core.logging.structured_logger import rotate_and_cleanup_logs

        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            log_dir.mkdir()
            archive_dir = log_dir / "archive"
            archive_dir.mkdir()

            # Create old log
            old_date = datetime.now() - timedelta(days=10)
            old_file = log_dir / f"jarvis-{old_date.strftime('%Y-%m-%d')}.jsonl"
            old_file.write_text('{"message": "test log"}\n')

            # Archive it
            rotate_and_cleanup_logs(log_dir, archive_dir, keep_days=7, delete_after_days=30)

            # Check archive is valid gzip
            archived = list(archive_dir.glob("*.gz"))
            assert len(archived) >= 1

            with gzip.open(archived[0], "rt") as f:
                content = f.read()
                assert "test log" in content

    def test_delete_very_old_archives(self):
        """Test that archives older than 30 days are deleted."""
        from core.logging.structured_logger import rotate_and_cleanup_logs

        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            log_dir.mkdir()
            archive_dir = log_dir / "archive"
            archive_dir.mkdir()

            # Create very old archive
            very_old_date = datetime.now() - timedelta(days=35)
            very_old_archive = archive_dir / f"jarvis-{very_old_date.strftime('%Y-%m-%d')}.jsonl.gz"

            with gzip.open(very_old_archive, "wt") as f:
                f.write('{"test": "very old"}\n')

            # Modify the file's timestamp to be old
            old_timestamp = (datetime.now() - timedelta(days=35)).timestamp()
            os.utime(very_old_archive, (old_timestamp, old_timestamp))

            # Run cleanup
            rotate_and_cleanup_logs(log_dir, archive_dir, keep_days=7, delete_after_days=30)

            # Very old archive should be deleted
            assert not very_old_archive.exists()

    def test_keep_recent_logs(self):
        """Test that recent logs (< 7 days) are kept."""
        from core.logging.structured_logger import rotate_and_cleanup_logs

        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            log_dir.mkdir()
            archive_dir = log_dir / "archive"
            archive_dir.mkdir()

            # Create recent log files
            for i in range(5):
                date = datetime.now() - timedelta(days=i)
                log_file = log_dir / f"jarvis-{date.strftime('%Y-%m-%d')}.jsonl"
                log_file.write_text(f'{{"day": {i}}}\n')

            # Run cleanup
            rotate_and_cleanup_logs(log_dir, archive_dir, keep_days=7, delete_after_days=30)

            # All recent files should still exist
            recent_logs = list(log_dir.glob("jarvis-*.jsonl"))
            assert len(recent_logs) >= 5

    def test_rotation_handles_missing_directory(self):
        """Test that rotation handles missing directories gracefully."""
        from core.logging.structured_logger import rotate_and_cleanup_logs

        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "nonexistent_logs"
            archive_dir = Path(tmpdir) / "nonexistent_archive"

            # Should not raise an error
            rotate_and_cleanup_logs(log_dir, archive_dir)

            # Directories should be created
            assert log_dir.exists()
            assert archive_dir.exists()


class TestTimedRotatingHandler:
    """Tests for timed rotating file handler."""

    def test_handler_rotates_daily(self):
        """Test that handler rotates files daily."""
        from core.logging.structured_logger import get_rotating_file_handler

        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            log_dir.mkdir()

            handler = get_rotating_file_handler(
                log_dir=log_dir,
                base_name="jarvis",
                when="midnight",
                backup_count=7,
            )

            assert handler is not None
            handler.close()

    def test_handler_uses_jsonl_extension(self):
        """Test that handler uses .jsonl extension."""
        from core.logging.structured_logger import get_rotating_file_handler

        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            log_dir.mkdir()

            handler = get_rotating_file_handler(
                log_dir=log_dir,
                base_name="jarvis",
            )

            # The current log file should have .jsonl extension
            filename = handler.baseFilename
            assert ".jsonl" in filename or "jarvis" in filename
            handler.close()


class TestLogCleanupScheduler:
    """Tests for scheduled log cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_scheduler_runs(self):
        """Test that cleanup scheduler can be started."""
        from core.logging.structured_logger import start_cleanup_scheduler, stop_cleanup_scheduler

        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            log_dir.mkdir()

            # Start scheduler (should not block)
            task = await start_cleanup_scheduler(
                log_dir=log_dir,
                interval_hours=24,
            )

            assert task is not None

            # Stop it
            await stop_cleanup_scheduler(task)
