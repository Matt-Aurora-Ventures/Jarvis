"""
StateBackup - Atomic writes and disaster recovery for state files.

Fixes Issue #2: State loss from incomplete writes/crashes.

Pattern:
- WRITE: Data → Temp File → Atomic Rename (no partial files)
- BACKUP: Hourly snapshots with timestamp
- CLEANUP: Auto-remove backups >24 hours old
- READ: Primary file with automatic fallback to last backup
"""

import json
import logging
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional, Dict, List
import shutil

logger = logging.getLogger("jarvis.state_backup")

# Backup retention (hours)
BACKUP_RETENTION_HOURS = 24
BACKUP_INTERVAL_HOURS = 1


class StateBackup:
    """
    Atomic state file management with backup and recovery.

    Features:
    - Atomic writes (temp file → atomic rename)
    - Hourly backups to archive/
    - Auto-cleanup of old backups
    - Automatic fallback to backups on read error
    """

    def __init__(self, state_dir: Optional[Path] = None):
        """
        Initialize StateBackup.

        Args:
            state_dir: Directory for state files (default: ~/.lifeos/trading/)
        """
        if state_dir is None:
            state_dir = Path.home() / ".lifeos" / "trading"

        self.state_dir = Path(state_dir)
        self.backup_dir = self.state_dir / "backups"
        self.archive_dir = self.state_dir / "archive"

        # Create directories
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)

        # Track last backup times per file (avoid duplicate backups)
        self._last_backup: Dict[str, datetime] = {}

        logger.info(
            f"StateBackup initialized: state={self.state_dir}, "
            f"backups={self.backup_dir}, archive={self.archive_dir}"
        )

    def write_atomic(
        self,
        filename: str,
        data: Any,
        create_backup: bool = True,
    ) -> bool:
        """
        Write state file atomically (temp → rename).

        Args:
            filename: Name of state file (relative to state_dir)
            data: Data to write (must be JSON-serializable)
            create_backup: Whether to create hourly backup

        Returns:
            True if write succeeded
        """
        file_path = self.state_dir / filename

        try:
            # Write to temp file first
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=self.state_dir,
                delete=False,
                suffix=".tmp",
                prefix=f"{filename}.",
            ) as tmp_file:
                json.dump(data, tmp_file, indent=2, default=str)
                tmp_path = Path(tmp_file.name)

            # Atomic rename (overwrites existing file)
            # On most filesystems, this is atomic or fail-completely
            tmp_path.replace(file_path)

            logger.debug(f"Atomic write succeeded: {filename}")

            # Create backup if needed
            if create_backup:
                self._maybe_create_backup(filename)

            return True

        except Exception as e:
            logger.error(f"Atomic write failed for {filename}: {e}")
            # Clean up temp file
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:  # noqa: BLE001 - intentional catch-all
                pass
            return False

    def _maybe_create_backup(self, filename: str) -> None:
        """
        Create hourly backup of state file.

        Args:
            filename: State file to backup
        """
        file_path = self.state_dir / filename

        # Check if we should create backup (hourly limit)
        last_backup = self._last_backup.get(filename)
        if last_backup and (datetime.utcnow() - last_backup) < timedelta(hours=BACKUP_INTERVAL_HOURS):
            return  # Too soon, skip

        # Don't backup if file doesn't exist
        if not file_path.exists():
            return

        try:
            # Create timestamped backup
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{filename.replace('.json', '')}__{timestamp}.json"
            backup_path = self.backup_dir / backup_name

            # Copy atomically (via temp file)
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=self.backup_dir,
                delete=False,
            ) as tmp_backup:
                with open(file_path, "rb") as src:
                    tmp_backup.write(src.read())
                tmp_backup_path = Path(tmp_backup.name)

            tmp_backup_path.replace(backup_path)

            self._last_backup[filename] = datetime.utcnow()
            logger.info(f"Backup created: {backup_name}")

            # Cleanup old backups
            self._cleanup_old_backups(filename)

        except Exception as e:
            logger.warning(f"Failed to create backup for {filename}: {e}")

    def _cleanup_old_backups(self, filename: str) -> None:
        """
        Delete backups older than retention window.

        Args:
            filename: State file to cleanup backups for
        """
        try:
            prefix = filename.replace(".json", "")
            cutoff = datetime.utcnow() - timedelta(hours=BACKUP_RETENTION_HOURS)

            deleted = 0
            for backup_file in self.backup_dir.glob(f"{prefix}__*.json"):
                # Extract timestamp from filename
                try:
                    # Format: filename__YYYYMMDD_HHMMSS.json
                    timestamp_str = backup_file.stem.split("__")[1]
                    backup_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")

                    if backup_time < cutoff:
                        backup_file.unlink()
                        deleted += 1
                except Exception:
                    pass  # Skip files we can't parse

            if deleted > 0:
                logger.info(f"Cleaned up {deleted} old backups for {filename}")

        except Exception as e:
            logger.warning(f"Cleanup failed: {e}")

    def read_safe(
        self,
        filename: str,
        default: Any = None,
    ) -> Any:
        """
        Read state file with automatic fallback to backups.

        If primary file is corrupted, falls back to most recent backup.

        Args:
            filename: Name of state file
            default: Default value if file not found

        Returns:
            Parsed JSON data or default
        """
        file_path = self.state_dir / filename

        # Try primary file first
        try:
            if file_path.exists():
                with open(file_path) as f:
                    return json.load(f)
        except json.JSONDecodeError as e:
            logger.warning(f"Primary file corrupted ({filename}): {e}, trying backups...")
        except Exception as e:
            logger.warning(f"Error reading primary file ({filename}): {e}")

        # Try most recent backup
        try:
            prefix = filename.replace(".json", "")
            backups = sorted(
                self.backup_dir.glob(f"{prefix}__*.json"),
                reverse=True  # Most recent first
            )

            for backup_file in backups:
                try:
                    with open(backup_file) as f:
                        data = json.load(f)
                    logger.info(f"Recovered from backup: {backup_file.name}")
                    return data
                except Exception as e:
                    logger.debug(f"Backup read failed ({backup_file.name}): {e}")
                    continue

        except Exception as e:
            logger.warning(f"Error searching backups: {e}")

        # Fall through to default
        logger.warning(f"No valid backup found for {filename}, returning default")
        return default

    def get_backup_list(self, filename: str) -> List[Dict[str, Any]]:
        """
        Get list of available backups for a file.

        Args:
            filename: State file to query

        Returns:
            List of backup metadata
        """
        try:
            prefix = filename.replace(".json", "")
            backups = []

            for backup_file in sorted(
                self.backup_dir.glob(f"{prefix}__*.json"),
                reverse=True
            ):
                try:
                    stat = backup_file.stat()
                    timestamp_str = backup_file.stem.split("__")[1]
                    backup_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")

                    backups.append({
                        "filename": backup_file.name,
                        "timestamp": backup_time.isoformat(),
                        "size_bytes": stat.st_size,
                        "age_hours": (datetime.utcnow() - backup_time).total_seconds() / 3600,
                    })
                except Exception:
                    pass

            return backups

        except Exception as e:
            logger.error(f"Error listing backups: {e}")
            return []

    def restore_backup(self, filename: str, backup_timestamp: str) -> bool:
        """
        Restore state file from specific backup.

        Args:
            filename: State file to restore to
            backup_timestamp: Backup timestamp (YYYYMMDD_HHMMSS format)

        Returns:
            True if restore succeeded
        """
        try:
            prefix = filename.replace(".json", "")
            backup_file = self.backup_dir / f"{prefix}__{backup_timestamp}.json"

            if not backup_file.exists():
                logger.error(f"Backup not found: {backup_file}")
                return False

            # Restore via atomic write
            with open(backup_file) as f:
                data = json.load(f)

            return self.write_atomic(filename, data, create_backup=False)

        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get backup statistics."""
        try:
            stats = {
                "state_files": len(list(self.state_dir.glob("*.json"))),
                "backups": len(list(self.backup_dir.glob("*.json"))),
                "state_dir_size_bytes": sum(
                    f.stat().st_size for f in self.state_dir.glob("*.json")
                ),
                "backup_dir_size_bytes": sum(
                    f.stat().st_size for f in self.backup_dir.glob("*.json")
                ),
            }
            return stats
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"error": str(e)}


# Global StateBackup instance
_state_backup: Optional[StateBackup] = None


def get_state_backup() -> StateBackup:
    """Get global StateBackup instance."""
    global _state_backup
    if not _state_backup:
        _state_backup = StateBackup()
    return _state_backup


def set_state_backup(backup: StateBackup) -> None:
    """Set global StateBackup instance (for testing)."""
    global _state_backup
    _state_backup = backup
