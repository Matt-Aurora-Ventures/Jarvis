"""
Backup and Recovery Manager for Jarvis Trading System

Handles backup and restoration of:
- Position state (.positions.json)
- Configuration files
- Trading state (exit_intents, grok_state)
- System configuration
"""

import json
import shutil
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class BackupMetadata:
    """Metadata for a backup snapshot"""
    backup_id: str
    timestamp: str
    backup_type: str  # full, incremental, positions_only, config_only
    files_backed_up: List[str]
    size_bytes: int
    checksum: Optional[str] = None
    description: Optional[str] = None


class BackupManager:
    """Manages backup and recovery of Jarvis state and configuration"""

    DEFAULT_BACKUP_DIR = Path.home() / ".lifeos" / "backups"

    # Critical files to backup
    BACKUP_TARGETS = {
        "positions": "bots/treasury/.positions.json",
        "exit_intents": Path.home() / ".lifeos" / "trading" / "exit_intents.json",
        "grok_state": "bots/twitter/.grok_state.json",
        "supervisor_config": "bots/supervisor_config.json",
        "treasury_config": "bots/treasury/config.json",
        "telegram_config": "tg_bot/config.py",
    }

    def __init__(self,
                 backup_dir: Optional[Path] = None,
                 project_root: Optional[Path] = None,
                 retention_days: int = 30,
                 max_backups: int = 100):
        """
        Initialize backup manager

        Args:
            backup_dir: Directory to store backups (default: ~/.lifeos/backups)
            project_root: Root directory of Jarvis project
            retention_days: Days to keep backups before auto-cleanup
            max_backups: Maximum number of backups to keep
        """
        self.backup_dir = backup_dir or self.DEFAULT_BACKUP_DIR
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        self.project_root = project_root or Path.cwd()
        self.retention_days = retention_days
        self.max_backups = max_backups

        # Metadata file
        self.metadata_file = self.backup_dir / "backup_metadata.json"
        self.metadata: List[BackupMetadata] = self._load_metadata()

    def _load_metadata(self) -> List[BackupMetadata]:
        """Load backup metadata from disk"""
        if not self.metadata_file.exists():
            return []

        try:
            with open(self.metadata_file, 'r') as f:
                data = json.load(f)
                return [BackupMetadata(**item) for item in data]
        except Exception as e:
            logger.error(f"Failed to load metadata: {e}")
            return []

    def _save_metadata(self):
        """Save backup metadata to disk"""
        try:
            with open(self.metadata_file, 'w') as f:
                data = [asdict(m) for m in self.metadata]
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")

    def _generate_backup_id(self, backup_type: str) -> str:
        """Generate unique backup ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{backup_type}_{timestamp}"

    def _get_file_checksum(self, file_path: Path) -> str:
        """Calculate simple checksum (file size + mtime)"""
        if not file_path.exists():
            return "missing"
        stat = file_path.stat()
        return f"{stat.st_size}_{stat.st_mtime}"

    def create_backup(self,
                      backup_type: str = "full",
                      description: Optional[str] = None,
                      include_files: Optional[List[str]] = None) -> BackupMetadata:
        """
        Create a backup snapshot

        Args:
            backup_type: Type of backup (full, incremental, positions_only, config_only)
            description: Optional description of this backup
            include_files: Optional list of specific files to backup (overrides type)

        Returns:
            BackupMetadata for the created backup
        """
        backup_id = self._generate_backup_id(backup_type)
        backup_path = self.backup_dir / backup_id
        backup_path.mkdir(parents=True, exist_ok=True)

        # Determine which files to backup
        if include_files:
            targets = {k: v for k, v in self.BACKUP_TARGETS.items()
                      if k in include_files}
        elif backup_type == "positions_only":
            targets = {k: v for k, v in self.BACKUP_TARGETS.items()
                      if k in ["positions", "exit_intents"]}
        elif backup_type == "config_only":
            targets = {k: v for k, v in self.BACKUP_TARGETS.items()
                      if "config" in k}
        else:  # full or incremental
            targets = self.BACKUP_TARGETS.copy()

        backed_up_files = []
        total_size = 0

        # Copy each target file
        for name, rel_path in targets.items():
            source = self.project_root / rel_path if not isinstance(rel_path, Path) else rel_path

            if not source.exists():
                logger.warning(f"Backup target not found: {source}")
                continue

            # Preserve directory structure
            if isinstance(rel_path, Path):
                dest_name = f"{name}.json"
            else:
                dest_name = str(rel_path).replace("/", "_").replace("\\", "_")

            dest = backup_path / dest_name

            try:
                shutil.copy2(source, dest)
                backed_up_files.append(str(rel_path))
                total_size += dest.stat().st_size
                logger.info(f"Backed up {source} -> {dest}")
            except Exception as e:
                logger.error(f"Failed to backup {source}: {e}")

        # Create metadata
        metadata = BackupMetadata(
            backup_id=backup_id,
            timestamp=datetime.now().isoformat(),
            backup_type=backup_type,
            files_backed_up=backed_up_files,
            size_bytes=total_size,
            description=description
        )

        # Save metadata file in backup dir
        metadata_path = backup_path / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(asdict(metadata), f, indent=2)

        # Add to global metadata
        self.metadata.append(metadata)
        self._save_metadata()

        logger.info(f"Created backup {backup_id} ({len(backed_up_files)} files, {total_size} bytes)")
        return metadata

    def restore_backup(self, backup_id: str,
                       dry_run: bool = False,
                       restore_files: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Restore from a backup

        Args:
            backup_id: ID of backup to restore
            dry_run: If True, only simulate restoration
            restore_files: Optional list of specific files to restore

        Returns:
            Dictionary with restoration results
        """
        backup_path = self.backup_dir / backup_id

        if not backup_path.exists():
            raise ValueError(f"Backup {backup_id} not found")

        # Load backup metadata
        metadata_path = backup_path / "metadata.json"
        if not metadata_path.exists():
            raise ValueError(f"Backup metadata missing for {backup_id}")

        with open(metadata_path, 'r') as f:
            metadata = BackupMetadata(**json.load(f))

        results = {
            "backup_id": backup_id,
            "dry_run": dry_run,
            "restored_files": [],
            "skipped_files": [],
            "errors": []
        }

        # Get all backup files
        backup_files = [f for f in backup_path.iterdir()
                       if f.is_file() and f.name != "metadata.json"]

        for backup_file in backup_files:
            # Map backup filename back to target
            target_path = None
            for name, rel_path in self.BACKUP_TARGETS.items():
                expected_name = str(rel_path).replace("/", "_").replace("\\", "_")
                if backup_file.name == expected_name or backup_file.name == f"{name}.json":
                    if restore_files and name not in restore_files:
                        results["skipped_files"].append(str(rel_path))
                        continue

                    target_path = self.project_root / rel_path if not isinstance(rel_path, Path) else rel_path
                    break

            if not target_path:
                logger.warning(f"Cannot map backup file {backup_file.name} to target")
                continue

            if dry_run:
                results["restored_files"].append(str(target_path))
                logger.info(f"[DRY RUN] Would restore {backup_file} -> {target_path}")
            else:
                try:
                    # Create parent directory if needed
                    target_path.parent.mkdir(parents=True, exist_ok=True)

                    # Backup existing file before overwriting
                    if target_path.exists():
                        backup_copy = target_path.with_suffix(f".pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak")
                        shutil.copy2(target_path, backup_copy)
                        logger.info(f"Backed up existing file to {backup_copy}")

                    # Restore
                    shutil.copy2(backup_file, target_path)
                    results["restored_files"].append(str(target_path))
                    logger.info(f"Restored {backup_file} -> {target_path}")

                except Exception as e:
                    error_msg = f"Failed to restore {backup_file}: {e}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)

        return results

    def list_backups(self, backup_type: Optional[str] = None) -> List[BackupMetadata]:
        """
        List available backups

        Args:
            backup_type: Optional filter by backup type

        Returns:
            List of BackupMetadata
        """
        backups = self.metadata
        if backup_type:
            backups = [b for b in backups if b.backup_type == backup_type]

        # Sort by timestamp (newest first)
        backups.sort(key=lambda x: x.timestamp, reverse=True)
        return backups

    def get_backup_info(self, backup_id: str) -> Optional[BackupMetadata]:
        """Get metadata for a specific backup"""
        for backup in self.metadata:
            if backup.backup_id == backup_id:
                return backup
        return None

    def delete_backup(self, backup_id: str, force: bool = False) -> bool:
        """
        Delete a backup

        Args:
            backup_id: ID of backup to delete
            force: Skip confirmation (use with caution)

        Returns:
            True if deleted successfully
        """
        backup_path = self.backup_dir / backup_id

        if not backup_path.exists():
            logger.warning(f"Backup {backup_id} not found")
            return False

        if not force:
            logger.warning("Use force=True to confirm deletion")
            return False

        try:
            shutil.rmtree(backup_path)

            # Remove from metadata
            self.metadata = [b for b in self.metadata if b.backup_id != backup_id]
            self._save_metadata()

            logger.info(f"Deleted backup {backup_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete backup {backup_id}: {e}")
            return False

    def cleanup_old_backups(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Clean up old backups based on retention policy

        Args:
            dry_run: If True, only simulate cleanup

        Returns:
            Dictionary with cleanup results
        """
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)

        results = {
            "dry_run": dry_run,
            "deleted_backups": [],
            "kept_backups": [],
            "total_freed_bytes": 0
        }

        # Sort backups by age (newest first)
        backups_by_age = sorted(self.metadata, key=lambda x: x.timestamp, reverse=True)

        for backup in backups_by_age:
            backup_date = datetime.fromisoformat(backup.timestamp)

            # Keep if within retention period AND under max_backups
            if backup_date >= cutoff_date and len(results["kept_backups"]) < self.max_backups:
                results["kept_backups"].append(backup.backup_id)
            else:
                # Delete old backup (too old OR over max limit)
                if dry_run:
                    results["deleted_backups"].append(backup.backup_id)
                    results["total_freed_bytes"] += backup.size_bytes
                else:
                    if self.delete_backup(backup.backup_id, force=True):
                        results["deleted_backups"].append(backup.backup_id)
                        results["total_freed_bytes"] += backup.size_bytes

        logger.info(f"Cleanup: deleted {len(results['deleted_backups'])} backups, "
                   f"freed {results['total_freed_bytes']} bytes")

        return results

    def verify_backup(self, backup_id: str) -> Dict[str, Any]:
        """
        Verify integrity of a backup

        Args:
            backup_id: ID of backup to verify

        Returns:
            Dictionary with verification results
        """
        backup_path = self.backup_dir / backup_id

        if not backup_path.exists():
            return {"valid": False, "error": "Backup not found"}

        metadata_path = backup_path / "metadata.json"
        if not metadata_path.exists():
            return {"valid": False, "error": "Metadata missing"}

        try:
            with open(metadata_path, 'r') as f:
                metadata = BackupMetadata(**json.load(f))
        except Exception as e:
            return {"valid": False, "error": f"Invalid metadata: {e}"}

        results = {
            "valid": True,
            "backup_id": backup_id,
            "files_verified": [],
            "missing_files": [],
            "corrupted_files": []
        }

        # Check each backed up file exists
        backup_files = [f for f in backup_path.iterdir()
                       if f.is_file() and f.name != "metadata.json"]

        for backup_file in backup_files:
            if backup_file.exists():
                # Try to load JSON to verify format
                try:
                    if backup_file.suffix == ".json":
                        with open(backup_file, 'r') as f:
                            json.load(f)
                    results["files_verified"].append(backup_file.name)
                except Exception as e:
                    results["corrupted_files"].append(backup_file.name)
                    logger.error(f"Corrupted file {backup_file}: {e}")
            else:
                results["missing_files"].append(backup_file.name)

        if results["missing_files"] or results["corrupted_files"]:
            results["valid"] = False

        return results

    def schedule_backup(self, interval_hours: int = 6, backup_type: str = "incremental"):
        """
        Schedule automatic backups (placeholder for integration with scheduler)

        Args:
            interval_hours: Hours between automatic backups
            backup_type: Type of backup to create
        """
        # This would integrate with a task scheduler like APScheduler
        logger.info(f"Backup scheduling: every {interval_hours}h, type={backup_type}")
        # Implementation would depend on scheduler integration
        raise NotImplementedError("Scheduler integration needed")


def create_emergency_backup(description: str = "Emergency backup") -> BackupMetadata:
    """Convenience function to quickly create an emergency full backup"""
    manager = BackupManager()
    return manager.create_backup(backup_type="full", description=description)


def restore_latest_backup(backup_type: Optional[str] = None, dry_run: bool = True) -> Dict[str, Any]:
    """Convenience function to restore the most recent backup"""
    manager = BackupManager()
    backups = manager.list_backups(backup_type=backup_type)

    if not backups:
        raise ValueError("No backups found")

    latest = backups[0]  # Already sorted by timestamp
    return manager.restore_backup(latest.backup_id, dry_run=dry_run)
