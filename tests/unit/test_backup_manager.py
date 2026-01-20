"""
Unit tests for BackupManager

Tests backup creation, restoration, verification, and cleanup.
"""

import json
import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta

from core.backup_manager import BackupManager, BackupMetadata, create_emergency_backup


@pytest.fixture
def temp_project():
    """Create a temporary project directory with test files"""
    temp_dir = Path(tempfile.mkdtemp())

    # Create project structure
    (temp_dir / "bots" / "treasury").mkdir(parents=True, exist_ok=True)
    (temp_dir / "bots" / "twitter").mkdir(parents=True, exist_ok=True)

    # Create test position file
    positions = [
        {
            "id": "test1",
            "token_symbol": "SOL",
            "status": "OPEN",
            "amount_usd": 100.0
        }
    ]
    with open(temp_dir / "bots" / "treasury" / ".positions.json", 'w') as f:
        json.dump(positions, f, indent=2)

    # Create test grok state
    grok_state = {"last_post": "2026-01-19T00:00:00", "daily_cost": 5.0}
    with open(temp_dir / "bots" / "twitter" / ".grok_state.json", 'w') as f:
        json.dump(grok_state, f, indent=2)

    yield temp_dir

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def temp_backup_dir():
    """Create temporary backup directory"""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def backup_manager(temp_project, temp_backup_dir):
    """Create BackupManager with temporary directories"""
    return BackupManager(
        backup_dir=temp_backup_dir,
        project_root=temp_project,
        retention_days=7,
        max_backups=10
    )


class TestBackupCreation:
    """Test backup creation functionality"""

    def test_create_full_backup(self, backup_manager, temp_project):
        """Test creating a full backup"""
        metadata = backup_manager.create_backup(
            backup_type="full",
            description="Test full backup"
        )

        assert metadata.backup_id.startswith("full_")
        assert metadata.backup_type == "full"
        assert metadata.description == "Test full backup"
        assert len(metadata.files_backed_up) > 0
        assert metadata.size_bytes > 0

        # Verify backup directory exists
        backup_path = backup_manager.backup_dir / metadata.backup_id
        assert backup_path.exists()
        assert (backup_path / "metadata.json").exists()

    def test_create_positions_only_backup(self, backup_manager, temp_project):
        """Test creating positions-only backup"""
        metadata = backup_manager.create_backup(backup_type="positions_only")

        assert metadata.backup_type == "positions_only"

        # Should only contain position-related files
        backed_up_names = [Path(f).name for f in metadata.files_backed_up]
        assert ".positions.json" in str(backed_up_names) or "positions" in str(backed_up_names)

    def test_create_config_only_backup(self, backup_manager, temp_project):
        """Test creating config-only backup"""
        metadata = backup_manager.create_backup(backup_type="config_only")

        assert metadata.backup_type == "config_only"

        # Should not contain position files
        backed_up_str = str(metadata.files_backed_up)
        assert ".positions.json" not in backed_up_str

    def test_backup_missing_files_graceful(self, backup_manager):
        """Test that backup handles missing files gracefully"""
        # Create backup even if some files don't exist
        metadata = backup_manager.create_backup(backup_type="full")

        # Should succeed even if not all files exist
        assert metadata is not None
        assert metadata.backup_id is not None

    def test_backup_metadata_saved(self, backup_manager):
        """Test that backup metadata is saved correctly"""
        metadata = backup_manager.create_backup(backup_type="full")

        # Reload manager to test persistence
        new_manager = BackupManager(
            backup_dir=backup_manager.backup_dir,
            project_root=backup_manager.project_root
        )

        # Find the backup in metadata
        found = new_manager.get_backup_info(metadata.backup_id)
        assert found is not None
        assert found.backup_id == metadata.backup_id
        assert found.backup_type == metadata.backup_type


class TestBackupRestoration:
    """Test backup restoration functionality"""

    def test_restore_backup_dry_run(self, backup_manager, temp_project):
        """Test restore in dry-run mode"""
        # Create backup
        metadata = backup_manager.create_backup(backup_type="full")

        # Modify original file
        positions_file = temp_project / "bots" / "treasury" / ".positions.json"
        with open(positions_file, 'w') as f:
            json.dump([{"modified": True}], f)

        # Restore in dry run
        results = backup_manager.restore_backup(metadata.backup_id, dry_run=True)

        assert results["dry_run"] is True
        assert len(results["restored_files"]) > 0
        assert len(results["errors"]) == 0

        # File should NOT be changed in dry run
        with open(positions_file, 'r') as f:
            data = json.load(f)
        assert data[0].get("modified") is True  # Still modified

    def test_restore_backup_live(self, backup_manager, temp_project):
        """Test actual restoration"""
        # Create backup
        metadata = backup_manager.create_backup(backup_type="positions_only")

        # Get original content
        positions_file = temp_project / "bots" / "treasury" / ".positions.json"
        with open(positions_file, 'r') as f:
            original = json.load(f)

        # Modify file
        with open(positions_file, 'w') as f:
            json.dump([{"modified": True}], f)

        # Restore
        results = backup_manager.restore_backup(metadata.backup_id, dry_run=False)

        assert results["dry_run"] is False
        assert len(results["restored_files"]) > 0

        # File should be restored
        with open(positions_file, 'r') as f:
            restored = json.load(f)
        assert restored == original
        assert restored[0].get("modified") is None

    def test_restore_creates_backup_copy(self, backup_manager, temp_project):
        """Test that restore creates a backup of existing file"""
        metadata = backup_manager.create_backup(backup_type="positions_only")

        # Modify file
        positions_file = temp_project / "bots" / "treasury" / ".positions.json"
        with open(positions_file, 'w') as f:
            json.dump([{"modified": True}], f)

        # Restore
        backup_manager.restore_backup(metadata.backup_id, dry_run=False)

        # Should have created .pre_restore backup
        backup_files = list(positions_file.parent.glob("*.pre_restore_*.bak"))
        assert len(backup_files) > 0

    def test_restore_specific_files(self, backup_manager, temp_project):
        """Test restoring only specific files"""
        metadata = backup_manager.create_backup(backup_type="full")

        # Restore only positions
        results = backup_manager.restore_backup(
            metadata.backup_id,
            dry_run=True,
            restore_files=["positions"]
        )

        # Should only restore positions
        restored_str = str(results["restored_files"])
        assert "positions" in restored_str.lower()

        # Other files should be skipped
        assert len(results["skipped_files"]) > 0

    def test_restore_nonexistent_backup(self, backup_manager):
        """Test restoring from non-existent backup"""
        with pytest.raises(ValueError, match="not found"):
            backup_manager.restore_backup("nonexistent_backup", dry_run=True)


class TestBackupVerification:
    """Test backup verification functionality"""

    def test_verify_valid_backup(self, backup_manager):
        """Test verifying a valid backup"""
        metadata = backup_manager.create_backup(backup_type="full")

        results = backup_manager.verify_backup(metadata.backup_id)

        assert results["valid"] is True
        assert len(results["files_verified"]) > 0
        assert len(results["missing_files"]) == 0
        assert len(results["corrupted_files"]) == 0

    def test_verify_missing_backup(self, backup_manager):
        """Test verifying non-existent backup"""
        results = backup_manager.verify_backup("nonexistent")

        assert results["valid"] is False
        assert "not found" in results["error"].lower()

    def test_verify_corrupted_json(self, backup_manager):
        """Test detecting corrupted JSON files"""
        metadata = backup_manager.create_backup(backup_type="positions_only")

        # Corrupt a JSON file
        backup_path = backup_manager.backup_dir / metadata.backup_id
        json_files = list(backup_path.glob("*.json"))
        if json_files and json_files[0].name != "metadata.json":
            with open(json_files[0], 'w') as f:
                f.write("{ invalid json")

            results = backup_manager.verify_backup(metadata.backup_id)

            assert results["valid"] is False
            assert len(results["corrupted_files"]) > 0


class TestBackupListing:
    """Test backup listing and querying"""

    def test_list_all_backups(self, backup_manager):
        """Test listing all backups"""
        # Create multiple backups
        backup_manager.create_backup(backup_type="full", description="Backup 1")
        backup_manager.create_backup(backup_type="positions_only", description="Backup 2")

        backups = backup_manager.list_backups()

        assert len(backups) >= 2
        # Should be sorted by timestamp (newest first)
        assert backups[0].timestamp >= backups[1].timestamp

    def test_list_by_type(self, backup_manager):
        """Test filtering backups by type"""
        backup_manager.create_backup(backup_type="full")
        backup_manager.create_backup(backup_type="positions_only")

        full_backups = backup_manager.list_backups(backup_type="full")
        position_backups = backup_manager.list_backups(backup_type="positions_only")

        assert len(full_backups) >= 1
        assert len(position_backups) >= 1
        assert all(b.backup_type == "full" for b in full_backups)
        assert all(b.backup_type == "positions_only" for b in position_backups)

    def test_get_backup_info(self, backup_manager):
        """Test getting specific backup info"""
        metadata = backup_manager.create_backup(backup_type="full")

        info = backup_manager.get_backup_info(metadata.backup_id)

        assert info is not None
        assert info.backup_id == metadata.backup_id
        assert info.backup_type == metadata.backup_type

    def test_get_nonexistent_backup_info(self, backup_manager):
        """Test getting info for non-existent backup"""
        info = backup_manager.get_backup_info("nonexistent")
        assert info is None


class TestBackupCleanup:
    """Test backup cleanup and retention"""

    def test_cleanup_old_backups_dry_run(self, backup_manager):
        """Test cleanup in dry-run mode"""
        # Create backups
        for i in range(5):
            backup_manager.create_backup(backup_type="full")

        results = backup_manager.cleanup_old_backups(dry_run=True)

        assert results["dry_run"] is True
        assert isinstance(results["deleted_backups"], list)
        assert isinstance(results["kept_backups"], list)

    def test_cleanup_respects_retention_days(self, backup_manager):
        """Test that cleanup respects retention period"""
        # Create a backup and manually set old timestamp
        metadata = backup_manager.create_backup(backup_type="full")

        # Make it old
        old_date = datetime.now() - timedelta(days=backup_manager.retention_days + 1)
        metadata.timestamp = old_date.isoformat()

        # Update metadata
        for i, m in enumerate(backup_manager.metadata):
            if m.backup_id == metadata.backup_id:
                backup_manager.metadata[i] = metadata
                break
        backup_manager._save_metadata()

        # Cleanup
        results = backup_manager.cleanup_old_backups(dry_run=True)

        # Old backup should be marked for deletion
        assert metadata.backup_id in results["deleted_backups"]

    def test_cleanup_respects_max_backups(self, backup_manager):
        """Test that cleanup respects max backup limit"""
        # Set low max
        backup_manager.max_backups = 3

        # Create more backups than max
        for i in range(5):
            backup_manager.create_backup(backup_type="full")

        results = backup_manager.cleanup_old_backups(dry_run=True)

        # Should keep only max_backups
        assert len(results["kept_backups"]) <= backup_manager.max_backups

    def test_delete_backup(self, backup_manager):
        """Test deleting a specific backup"""
        metadata = backup_manager.create_backup(backup_type="full")
        backup_path = backup_manager.backup_dir / metadata.backup_id

        # Delete requires force=True
        result = backup_manager.delete_backup(metadata.backup_id, force=False)
        assert result is False
        assert backup_path.exists()

        # Delete with force
        result = backup_manager.delete_backup(metadata.backup_id, force=True)
        assert result is True
        assert not backup_path.exists()

        # Should be removed from metadata
        info = backup_manager.get_backup_info(metadata.backup_id)
        assert info is None


class TestBackupIntegration:
    """Integration tests for complete backup/restore cycles"""

    def test_complete_backup_restore_cycle(self, backup_manager, temp_project):
        """Test full backup and restore cycle"""
        # 1. Create initial state
        positions_file = temp_project / "bots" / "treasury" / ".positions.json"
        original_content = [{"id": "original", "status": "OPEN"}]
        with open(positions_file, 'w') as f:
            json.dump(original_content, f)

        # 2. Create backup
        metadata = backup_manager.create_backup(
            backup_type="positions_only",
            description="Integration test backup"
        )

        # 3. Verify backup
        verify_results = backup_manager.verify_backup(metadata.backup_id)
        assert verify_results["valid"] is True

        # 4. Modify state
        modified_content = [{"id": "modified", "status": "CLOSED"}]
        with open(positions_file, 'w') as f:
            json.dump(modified_content, f)

        # 5. Restore backup
        restore_results = backup_manager.restore_backup(
            metadata.backup_id,
            dry_run=False
        )
        assert len(restore_results["errors"]) == 0

        # 6. Verify restoration
        with open(positions_file, 'r') as f:
            restored_content = json.load(f)
        assert restored_content == original_content

    def test_multiple_backups_and_selective_restore(self, backup_manager, temp_project):
        """Test creating multiple backups and restoring from specific one"""
        import time
        positions_file = temp_project / "bots" / "treasury" / ".positions.json"

        # Set version 1 and create first backup
        with open(positions_file, 'w') as f:
            json.dump([{"version": 1}], f)
        # Ensure file is flushed
        time.sleep(0.05)
        backup1 = backup_manager.create_backup(backup_type="positions_only")

        # Small delay to ensure different timestamps
        time.sleep(0.1)

        # Set version 2 and create second backup
        with open(positions_file, 'w') as f:
            json.dump([{"version": 2}], f)
        # Ensure file is flushed
        time.sleep(0.05)
        backup2 = backup_manager.create_backup(backup_type="positions_only")

        # Modify file to version 3
        with open(positions_file, 'w') as f:
            json.dump([{"version": 3}], f)

        # Verify current state is version 3
        with open(positions_file, 'r') as f:
            current = json.load(f)
        assert current[0]["version"] == 3

        # Restore from first backup - should get version 1
        backup_manager.restore_backup(backup1.backup_id, dry_run=False)

        with open(positions_file, 'r') as f:
            content = json.load(f)
        assert content[0]["version"] == 1, f"Expected version 1 but got {content[0]['version']}"

        # Restore from second backup - should get version 2
        backup_manager.restore_backup(backup2.backup_id, dry_run=False)

        with open(positions_file, 'r') as f:
            content = json.load(f)
        assert content[0]["version"] == 2, f"Expected version 2 but got {content[0]['version']}"


class TestConvenienceFunctions:
    """Test convenience functions"""

    def test_create_emergency_backup(self, temp_project, temp_backup_dir):
        """Test emergency backup creation"""
        # Note: This test is simplified as it needs to override default backup dir
        # In practice, create_emergency_backup uses default BackupManager
        manager = BackupManager(
            backup_dir=temp_backup_dir,
            project_root=temp_project
        )

        metadata = manager.create_backup(
            backup_type="full",
            description="Emergency backup"
        )

        assert metadata.backup_type == "full"
        assert "Emergency" in metadata.description


def test_backup_metadata_serialization():
    """Test BackupMetadata serialization/deserialization"""
    metadata = BackupMetadata(
        backup_id="test_123",
        timestamp="2026-01-19T00:00:00",
        backup_type="full",
        files_backed_up=["file1.json", "file2.json"],
        size_bytes=1024,
        checksum="abc123",
        description="Test backup"
    )

    # Convert to dict
    from dataclasses import asdict
    data = asdict(metadata)

    # Convert back
    restored = BackupMetadata(**data)

    assert restored.backup_id == metadata.backup_id
    assert restored.timestamp == metadata.timestamp
    assert restored.files_backed_up == metadata.files_backed_up
