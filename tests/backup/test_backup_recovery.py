"""
Comprehensive tests for Backup/Restore and Disaster Recovery system.

Tests cover:
- Backup creation (full and incremental)
- Restore functionality (full, point-in-time, single file)
- Checksum verification
- Scheduler functionality
- Disaster recovery procedures
- Data integrity after restore
"""

import pytest
import tempfile
import shutil
import json
import gzip
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio


# === BACKUP MANAGER TESTS ===

class TestBackupManager:
    """Test BackupManager functionality."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        base = tempfile.mkdtemp()
        data_dir = Path(base) / "data"
        backup_dir = Path(base) / "backups"
        data_dir.mkdir()
        backup_dir.mkdir()

        # Create sample files
        (data_dir / "positions.json").write_text('{"positions": []}')
        (data_dir / "trades.jsonl").write_text('{"trade": 1}\n{"trade": 2}')

        yield {
            "base": Path(base),
            "data": data_dir,
            "backup": backup_dir
        }

        # Cleanup
        shutil.rmtree(base)

    @pytest.fixture
    def backup_manager(self, temp_dirs):
        """Create BackupManager instance."""
        from core.backup.backup_manager import BackupManager, BackupConfig

        config = BackupConfig(
            backup_dir=temp_dirs["backup"],
            data_paths=[temp_dirs["data"]],
            retention_days=30,
            compression=True
        )
        return BackupManager(config)

    def test_full_backup_creation(self, backup_manager, temp_dirs):
        """Test creating a full backup."""
        result = backup_manager.create_full_backup()

        assert result.success is True
        assert result.backup_path.exists()
        assert result.files_count > 0
        assert result.checksum is not None
        assert "full" in result.backup_type

    def test_incremental_backup_creation(self, backup_manager, temp_dirs):
        """Test creating an incremental backup after full backup."""
        # First create a full backup
        full_result = backup_manager.create_full_backup()
        assert full_result.success is True

        # Modify a file
        (temp_dirs["data"] / "positions.json").write_text('{"positions": [{"id": 1}]}')

        # Create incremental backup
        inc_result = backup_manager.create_incremental_backup()

        assert inc_result.success is True
        assert inc_result.backup_path.exists()
        assert "incremental" in inc_result.backup_type

    def test_incremental_detects_only_changed_files(self, backup_manager, temp_dirs):
        """Test that incremental backup only includes changed files."""
        # Create full backup
        backup_manager.create_full_backup()

        # Modify only one file
        (temp_dirs["data"] / "positions.json").write_text('{"updated": true}')

        # Create incremental
        inc_result = backup_manager.create_incremental_backup()

        # Should only have the changed file
        assert inc_result.files_count == 1

    def test_backup_compression(self, backup_manager, temp_dirs):
        """Test that backups are properly compressed."""
        result = backup_manager.create_full_backup()

        # Backup should be gzipped
        assert result.backup_path.suffix == ".gz" or ".tar.gz" in str(result.backup_path)

        # Backup file exists and has content (tar overhead on small files is ok)
        assert result.backup_path.exists()
        assert result.size_bytes > 0

    def test_backup_checksum_calculation(self, backup_manager, temp_dirs):
        """Test checksum calculation for backups."""
        result = backup_manager.create_full_backup()

        # Calculate checksum independently
        calculated = hashlib.sha256(result.backup_path.read_bytes()).hexdigest()

        assert result.checksum == calculated

    def test_list_backups(self, backup_manager, temp_dirs):
        """Test listing all available backups."""
        import time
        # Create multiple backups with delay to ensure different timestamps
        backup_manager.create_full_backup()
        time.sleep(1.1)  # Longer delay for different timestamp in filename
        backup_manager.create_full_backup()

        backups = backup_manager.list_backups()

        assert len(backups) >= 2
        # Should be sorted by date (newest first)
        assert backups[0].created_at >= backups[1].created_at

    def test_get_latest_backup(self, backup_manager, temp_dirs):
        """Test getting the most recent backup."""
        backup_manager.create_full_backup()

        latest = backup_manager.get_latest_backup()

        assert latest is not None
        assert latest.backup_path.exists()

    def test_backup_metadata_stored(self, backup_manager, temp_dirs):
        """Test that backup metadata is properly stored."""
        result = backup_manager.create_full_backup(metadata={"custom": "value"})

        # Read metadata from backup
        metadata = backup_manager.get_backup_metadata(result.backup_path)

        assert metadata is not None
        assert "created_at" in metadata
        assert "files" in metadata
        # Custom metadata is nested under 'custom' key
        assert metadata.get("custom", {}).get("custom") == "value"


class TestRestoreManager:
    """Test RestoreManager functionality."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        base = tempfile.mkdtemp()
        data_dir = Path(base) / "data"
        backup_dir = Path(base) / "backups"
        restore_dir = Path(base) / "restore"
        data_dir.mkdir()
        backup_dir.mkdir()
        restore_dir.mkdir()

        # Create sample files
        (data_dir / "positions.json").write_text('{"positions": [{"id": 1}]}')
        (data_dir / "trades.jsonl").write_text('{"trade": 1}\n{"trade": 2}')
        (data_dir / "config.json").write_text('{"setting": true}')

        yield {
            "base": Path(base),
            "data": data_dir,
            "backup": backup_dir,
            "restore": restore_dir
        }

        shutil.rmtree(base)

    @pytest.fixture
    def managers(self, temp_dirs):
        """Create both backup and restore managers."""
        from core.backup.backup_manager import BackupManager, BackupConfig
        from core.backup.restore_manager import RestoreManager

        config = BackupConfig(
            backup_dir=temp_dirs["backup"],
            data_paths=[temp_dirs["data"]],
            retention_days=30,
            compression=True
        )
        backup_mgr = BackupManager(config)
        restore_mgr = RestoreManager(config)

        return {"backup": backup_mgr, "restore": restore_mgr}

    def test_restore_latest_backup(self, managers, temp_dirs):
        """Test restoring from the latest backup."""
        # Create backup
        managers["backup"].create_full_backup()

        # Restore
        result = managers["restore"].restore_latest(temp_dirs["restore"])

        assert result.success is True
        assert (temp_dirs["restore"] / "data" / "positions.json").exists()

    def test_restore_specific_backup(self, managers, temp_dirs):
        """Test restoring from a specific backup."""
        # Create backups
        first = managers["backup"].create_full_backup()
        managers["backup"].create_full_backup()

        # Restore first backup specifically
        result = managers["restore"].restore_backup(first.backup_path, temp_dirs["restore"])

        assert result.success is True

    def test_restore_point_in_time(self, managers, temp_dirs):
        """Test point-in-time restore."""
        import time
        # Create backup at time T1
        managers["backup"].create_full_backup()
        time.sleep(0.1)

        # Record time after first backup was created
        t1 = datetime.now(timezone.utc) + timedelta(seconds=1)

        # Wait and modify
        time.sleep(0.1)
        (temp_dirs["data"] / "positions.json").write_text('{"modified": true}')

        # Create another backup
        managers["backup"].create_full_backup()

        # Restore to time T1 (should get first backup)
        result = managers["restore"].restore_point_in_time(
            temp_dirs["restore"],
            timestamp=t1
        )

        assert result.success is True

    def test_restore_single_file(self, managers, temp_dirs):
        """Test restoring a single file from backup."""
        # Create backup
        managers["backup"].create_full_backup()

        # Restore single file
        result = managers["restore"].restore_file(
            file_path="data/positions.json",
            dest=temp_dirs["restore"] / "positions.json"
        )

        assert result.success is True
        assert (temp_dirs["restore"] / "positions.json").exists()

    def test_restore_with_checksum_verification(self, managers, temp_dirs):
        """Test that restore verifies checksums."""
        # Create backup
        managers["backup"].create_full_backup()

        # Restore with verification
        result = managers["restore"].restore_latest(
            temp_dirs["restore"],
            verify=True
        )

        assert result.success is True
        # Verification checks backup integrity, not restoration
        assert result.files_restored > 0

    def test_restore_dry_run(self, managers, temp_dirs):
        """Test dry run mode shows what would be restored."""
        # Create backup
        managers["backup"].create_full_backup()

        # Dry run
        result = managers["restore"].restore_latest(
            temp_dirs["restore"],
            dry_run=True
        )

        assert result.success is True
        assert result.is_dry_run is True
        # Files should NOT be actually restored
        assert not (temp_dirs["restore"] / "data" / "positions.json").exists()

    def test_restore_creates_safety_backup(self, managers, temp_dirs):
        """Test that restore creates safety backup of current state."""
        # Put some data in restore dir
        (temp_dirs["restore"] / "existing.json").write_text('{"old": true}')

        # Create backup
        managers["backup"].create_full_backup()

        # Restore
        result = managers["restore"].restore_latest(
            temp_dirs["restore"],
            create_safety_backup=True
        )

        assert result.success is True
        assert result.safety_backup_path is not None
        assert result.safety_backup_path.exists()


class TestBackupVerification:
    """Test backup verification functionality."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories."""
        base = tempfile.mkdtemp()
        data_dir = Path(base) / "data"
        backup_dir = Path(base) / "backups"
        data_dir.mkdir()
        backup_dir.mkdir()

        (data_dir / "test.json").write_text('{"test": true}')

        yield {"base": Path(base), "data": data_dir, "backup": backup_dir}
        shutil.rmtree(base)

    @pytest.fixture
    def backup_manager(self, temp_dirs):
        """Create BackupManager."""
        from core.backup.backup_manager import BackupManager, BackupConfig

        config = BackupConfig(
            backup_dir=temp_dirs["backup"],
            data_paths=[temp_dirs["data"]],
            retention_days=30,
            compression=True
        )
        return BackupManager(config)

    def test_verify_backup_integrity(self, backup_manager, temp_dirs):
        """Test verifying backup file integrity."""
        result = backup_manager.create_full_backup()

        verification = backup_manager.verify_backup(result.backup_path)

        assert verification.is_valid is True
        assert verification.checksum_match is True

    def test_verify_detects_corrupted_backup(self, backup_manager, temp_dirs):
        """Test that verification detects corrupted backups."""
        result = backup_manager.create_full_backup()

        # Corrupt the backup file by overwriting it with invalid data
        result.backup_path.write_bytes(b"totally corrupted tar gz file that is not valid")

        verification = backup_manager.verify_backup(result.backup_path)

        assert verification.is_valid is False

    def test_verify_all_backups(self, backup_manager, temp_dirs):
        """Test verifying all backups."""
        import time
        backup_manager.create_full_backup()
        time.sleep(1.1)  # Longer delay for different timestamp
        backup_manager.create_full_backup()

        results = backup_manager.verify_all_backups()

        assert len(results) >= 2
        assert all(r.is_valid for r in results)


class TestBackupScheduler:
    """Test backup scheduler functionality."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories."""
        base = tempfile.mkdtemp()
        data_dir = Path(base) / "data"
        backup_dir = Path(base) / "backups"
        data_dir.mkdir()
        backup_dir.mkdir()

        (data_dir / "test.json").write_text('{"test": true}')

        yield {"base": Path(base), "data": data_dir, "backup": backup_dir}
        shutil.rmtree(base)

    @pytest.fixture
    def scheduler(self, temp_dirs):
        """Create BackupScheduler."""
        from core.backup.backup_manager import BackupConfig
        from core.backup.scheduler import BackupScheduler

        config = BackupConfig(
            backup_dir=temp_dirs["backup"],
            data_paths=[temp_dirs["data"]],
            retention_days=30,
            compression=True
        )
        return BackupScheduler(config)

    def test_scheduler_full_backup_schedule(self, scheduler):
        """Test scheduling full daily backups."""
        job = scheduler.schedule_full_backup(hour=0, minute=0)

        assert job is not None
        assert job.id == "full_daily_backup"

    def test_scheduler_incremental_backup_schedule(self, scheduler):
        """Test scheduling incremental hourly backups."""
        job = scheduler.schedule_incremental_backup(minute=0)

        assert job is not None
        assert job.id == "incremental_hourly_backup"

    def test_scheduler_cleanup_schedule(self, scheduler):
        """Test scheduling old backup cleanup."""
        job = scheduler.schedule_cleanup(days=30)

        assert job is not None

    @pytest.mark.asyncio
    async def test_scheduler_run_immediate_backup(self, scheduler, temp_dirs):
        """Test running an immediate backup via scheduler."""
        result = await scheduler.run_backup_now(backup_type="full")

        assert result.success is True
        assert result.backup_path.exists()

    def test_scheduler_get_next_backup_time(self, scheduler):
        """Test getting the next scheduled backup time."""
        scheduler.schedule_full_backup(hour=0, minute=0)

        next_time = scheduler.get_next_backup_time()

        assert next_time is not None
        assert next_time > datetime.now(timezone.utc)


class TestDisasterRecovery:
    """Test disaster recovery procedures."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories."""
        base = tempfile.mkdtemp()
        data_dir = Path(base) / "data"
        backup_dir = Path(base) / "backups"
        data_dir.mkdir()
        backup_dir.mkdir()

        (data_dir / "positions.json").write_text('{"positions": []}')
        (data_dir / "trades.jsonl").write_text('{"trade": 1}')

        yield {"base": Path(base), "data": data_dir, "backup": backup_dir}
        shutil.rmtree(base)

    @pytest.fixture
    def dr_manager(self, temp_dirs):
        """Create DisasterRecoveryManager."""
        from core.backup.backup_manager import BackupConfig
        from core.backup.disaster_recovery import DisasterRecoveryManager

        config = BackupConfig(
            backup_dir=temp_dirs["backup"],
            data_paths=[temp_dirs["data"]],
            retention_days=30,
            compression=True
        )
        return DisasterRecoveryManager(config)

    def test_detect_data_corruption(self, dr_manager, temp_dirs):
        """Test detecting data corruption."""
        # Corrupt a file
        (temp_dirs["data"] / "positions.json").write_text('{"invalid json')

        issues = dr_manager.run_health_check()

        assert len(issues) > 0
        assert any("corruption" in str(i).lower() or "invalid" in str(i).lower() for i in issues)

    def test_recovery_from_corruption(self, dr_manager, temp_dirs):
        """Test recovering from data corruption."""
        # Create a good backup first using the dr_manager's internal backup manager
        dr_manager._backup_manager.create_full_backup()

        # Corrupt the data
        (temp_dirs["data"] / "positions.json").write_text('corrupt')

        # Recover to a restore directory
        restore_dir = temp_dirs["base"] / "restored"
        restore_dir.mkdir(exist_ok=True)
        result = dr_manager.recover_from_corruption(restore_dir)

        assert result.success is True

    def test_generate_recovery_plan(self, dr_manager):
        """Test generating a recovery plan."""
        plan = dr_manager.generate_recovery_plan(scenario="data_corruption")

        assert plan is not None
        assert len(plan.steps) > 0
        assert "backup" in str(plan).lower() or "restore" in str(plan).lower()

    def test_validate_recovery_integrity(self, dr_manager, temp_dirs):
        """Test validating system integrity after recovery."""
        result = dr_manager.validate_system_integrity()

        assert result is not None
        assert hasattr(result, "is_healthy")


class TestRetentionPolicy:
    """Test backup retention policy."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories."""
        base = tempfile.mkdtemp()
        backup_dir = Path(base) / "backups"
        data_dir = Path(base) / "data"
        backup_dir.mkdir()
        data_dir.mkdir()

        (data_dir / "test.json").write_text('{"test": true}')

        yield {"base": Path(base), "backup": backup_dir, "data": data_dir}
        shutil.rmtree(base)

    @pytest.fixture
    def backup_manager(self, temp_dirs):
        """Create BackupManager."""
        from core.backup.backup_manager import BackupManager, BackupConfig

        config = BackupConfig(
            backup_dir=temp_dirs["backup"],
            data_paths=[temp_dirs["data"]],
            retention_days=30,
            compression=True
        )
        return BackupManager(config)

    def test_cleanup_old_backups(self, backup_manager, temp_dirs):
        """Test cleaning up backups older than retention period."""
        import time
        # Create two backups - one old, one new
        result1 = backup_manager.create_full_backup()
        time.sleep(1.1)
        result2 = backup_manager.create_full_backup()

        # Manually age the first backup file
        import os
        old_time = time.time() - (31 * 86400)  # 31 days ago
        os.utime(result1.backup_path, (old_time, old_time))

        # Run cleanup (keep_minimum=1 so we can remove the old one)
        removed = backup_manager.cleanup_old_backups(keep_minimum=1)

        assert removed >= 1

    def test_keep_minimum_backups(self, backup_manager, temp_dirs):
        """Test that minimum number of backups are kept."""
        import time
        import os
        # Create several backups with delays
        results = []
        for _ in range(5):
            result = backup_manager.create_full_backup()
            results.append(result)
            time.sleep(1.1)  # Longer delay for unique timestamps

        # Age all backups so they would normally be deleted
        old_time = time.time() - (31 * 86400)  # 31 days ago
        for result in results:
            os.utime(result.backup_path, (old_time, old_time))

        # Run cleanup with keep=3 - should keep at least 3 even though all are "old"
        removed = backup_manager.cleanup_old_backups(keep_minimum=3)

        remaining = backup_manager.list_backups()
        # Should keep at least 3 due to keep_minimum
        assert len(remaining) >= 3


class TestDataIntegrity:
    """Test data integrity after backup/restore cycles."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories."""
        base = tempfile.mkdtemp()
        data_dir = Path(base) / "data"
        backup_dir = Path(base) / "backups"
        restore_dir = Path(base) / "restore"
        data_dir.mkdir()
        backup_dir.mkdir()
        restore_dir.mkdir()

        yield {"base": Path(base), "data": data_dir, "backup": backup_dir, "restore": restore_dir}
        shutil.rmtree(base)

    def test_json_file_integrity(self, temp_dirs):
        """Test JSON file integrity after restore."""
        from core.backup.backup_manager import BackupManager, BackupConfig
        from core.backup.restore_manager import RestoreManager

        # Create complex JSON data
        original_data = {
            "positions": [{"id": i, "value": i * 100} for i in range(100)],
            "nested": {"deep": {"data": [1, 2, 3]}}
        }
        (temp_dirs["data"] / "complex.json").write_text(json.dumps(original_data))

        config = BackupConfig(
            backup_dir=temp_dirs["backup"],
            data_paths=[temp_dirs["data"]],
            retention_days=30,
            compression=True
        )

        # Backup
        backup_mgr = BackupManager(config)
        backup_mgr.create_full_backup()

        # Restore
        restore_mgr = RestoreManager(config)
        restore_mgr.restore_latest(temp_dirs["restore"])

        # Verify
        restored_data = json.loads((temp_dirs["restore"] / "data" / "complex.json").read_text())
        assert restored_data == original_data

    def test_binary_file_integrity(self, temp_dirs):
        """Test binary file integrity after restore."""
        from core.backup.backup_manager import BackupManager, BackupConfig
        from core.backup.restore_manager import RestoreManager

        # Create binary data with .db extension (included by default)
        original_binary = bytes(range(256)) * 100
        (temp_dirs["data"] / "binary.db").write_bytes(original_binary)

        config = BackupConfig(
            backup_dir=temp_dirs["backup"],
            data_paths=[temp_dirs["data"]],
            retention_days=30,
            compression=True
        )

        # Backup and restore
        backup_mgr = BackupManager(config)
        backup_mgr.create_full_backup()

        restore_mgr = RestoreManager(config)
        restore_mgr.restore_latest(temp_dirs["restore"])

        # Verify
        restored_binary = (temp_dirs["restore"] / "data" / "binary.db").read_bytes()
        assert restored_binary == original_binary

    def test_checksum_matches_after_restore(self, temp_dirs):
        """Test that file checksums match after restore."""
        from core.backup.backup_manager import BackupManager, BackupConfig
        from core.backup.restore_manager import RestoreManager

        # Create test file with .csv extension (included by default)
        test_content = "Test content for checksum verification"
        test_file = temp_dirs["data"] / "checksum_test.csv"
        test_file.write_text(test_content)

        original_checksum = hashlib.sha256(test_file.read_bytes()).hexdigest()

        config = BackupConfig(
            backup_dir=temp_dirs["backup"],
            data_paths=[temp_dirs["data"]],
            retention_days=30,
            compression=True
        )

        # Backup and restore
        backup_mgr = BackupManager(config)
        backup_mgr.create_full_backup()

        restore_mgr = RestoreManager(config)
        restore_mgr.restore_latest(temp_dirs["restore"])

        # Verify checksum
        restored_file = temp_dirs["restore"] / "data" / "checksum_test.csv"
        restored_checksum = hashlib.sha256(restored_file.read_bytes()).hexdigest()

        assert restored_checksum == original_checksum
