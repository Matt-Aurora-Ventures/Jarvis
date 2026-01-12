"""
Backup & Restore Utilities - Data protection and recovery.
"""

import os
import json
import shutil
import logging
import zipfile
import hashlib
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class BackupConfig:
    """Backup configuration."""
    backup_dir: Path
    max_backups: int = 10
    include_patterns: List[str] = None
    exclude_patterns: List[str] = None
    compress: bool = True


@dataclass
class BackupInfo:
    """Information about a backup."""
    name: str
    path: Path
    created_at: str
    size_bytes: int
    checksum: str
    files_count: int
    metadata: Dict[str, Any]


class BackupManager:
    """
    Manage backups of important data.

    Usage:
        manager = BackupManager(Path("backups"))

        # Create backup
        backup = manager.create_backup(
            name="daily_backup",
            source_dirs=[
                Path("data"),
                Path("secrets")
            ]
        )

        # Restore from backup
        manager.restore_backup(backup.name, Path("restored"))

        # Clean old backups
        manager.cleanup_old_backups(keep=5)
    """

    DEFAULT_INCLUDE = [
        "*.json",
        "*.db",
        "*.sqlite",
        "*.vault",
        "*.csv",
    ]

    DEFAULT_EXCLUDE = [
        "__pycache__",
        "*.pyc",
        "*.log",
        "node_modules",
        ".git",
        "*.tmp",
    ]

    def __init__(self, backup_dir: Path, config: Optional[BackupConfig] = None):
        self.backup_dir = backup_dir
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        self.config = config or BackupConfig(
            backup_dir=backup_dir,
            include_patterns=self.DEFAULT_INCLUDE,
            exclude_patterns=self.DEFAULT_EXCLUDE
        )

    def _should_include_file(self, file_path: Path) -> bool:
        """Check if file should be included in backup."""
        name = file_path.name

        # Check exclude patterns
        for pattern in (self.config.exclude_patterns or []):
            if pattern.startswith("*"):
                if name.endswith(pattern[1:]):
                    return False
            elif pattern in str(file_path):
                return False

        # Check include patterns
        if self.config.include_patterns:
            for pattern in self.config.include_patterns:
                if pattern.startswith("*"):
                    if name.endswith(pattern[1:]):
                        return True
                elif pattern in name:
                    return True
            return False

        return True

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def create_backup(
        self,
        name: str,
        source_dirs: List[Path],
        metadata: Dict[str, Any] = None
    ) -> BackupInfo:
        """
        Create a new backup.

        Args:
            name: Backup name (used in filename)
            source_dirs: Directories to backup
            metadata: Optional metadata to include

        Returns:
            BackupInfo with details about the backup
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_name = f"{name}_{timestamp}"

        if self.config.compress:
            backup_path = self.backup_dir / f"{backup_name}.zip"
        else:
            backup_path = self.backup_dir / backup_name

        files_count = 0
        files_list = []

        logger.info(f"Creating backup: {backup_name}")

        if self.config.compress:
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for source_dir in source_dirs:
                    if not source_dir.exists():
                        logger.warning(f"Source directory not found: {source_dir}")
                        continue

                    for file_path in source_dir.rglob("*"):
                        if file_path.is_file() and self._should_include_file(file_path):
                            arcname = file_path.relative_to(source_dir.parent)
                            zf.write(file_path, arcname)
                            files_count += 1
                            files_list.append(str(arcname))

                # Add metadata
                meta = {
                    "backup_name": backup_name,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "source_dirs": [str(d) for d in source_dirs],
                    "files": files_list,
                    "custom": metadata or {}
                }
                zf.writestr("_backup_metadata.json", json.dumps(meta, indent=2))
        else:
            backup_path.mkdir(parents=True, exist_ok=True)

            for source_dir in source_dirs:
                if not source_dir.exists():
                    continue

                for file_path in source_dir.rglob("*"):
                    if file_path.is_file() and self._should_include_file(file_path):
                        rel_path = file_path.relative_to(source_dir.parent)
                        dest_path = backup_path / rel_path
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(file_path, dest_path)
                        files_count += 1
                        files_list.append(str(rel_path))

            # Add metadata
            meta = {
                "backup_name": backup_name,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "source_dirs": [str(d) for d in source_dirs],
                "files": files_list,
                "custom": metadata or {}
            }
            with open(backup_path / "_backup_metadata.json", "w") as f:
                json.dump(meta, f, indent=2)

        # Calculate size and checksum
        if self.config.compress:
            size = backup_path.stat().st_size
            checksum = self._calculate_checksum(backup_path)
        else:
            size = sum(f.stat().st_size for f in backup_path.rglob("*") if f.is_file())
            checksum = "directory"

        info = BackupInfo(
            name=backup_name,
            path=backup_path,
            created_at=datetime.now(timezone.utc).isoformat(),
            size_bytes=size,
            checksum=checksum,
            files_count=files_count,
            metadata=metadata or {}
        )

        logger.info(f"Backup created: {backup_name} ({files_count} files, {size / 1024:.1f} KB)")
        return info

    def list_backups(self) -> List[BackupInfo]:
        """List all available backups."""
        backups = []

        for item in self.backup_dir.iterdir():
            if item.name.startswith("_"):
                continue

            try:
                if item.is_file() and item.suffix == ".zip":
                    with zipfile.ZipFile(item, 'r') as zf:
                        if "_backup_metadata.json" in zf.namelist():
                            meta = json.loads(zf.read("_backup_metadata.json"))
                            backups.append(BackupInfo(
                                name=meta.get("backup_name", item.stem),
                                path=item,
                                created_at=meta.get("created_at", ""),
                                size_bytes=item.stat().st_size,
                                checksum=self._calculate_checksum(item),
                                files_count=len(meta.get("files", [])),
                                metadata=meta.get("custom", {})
                            ))
                elif item.is_dir():
                    meta_path = item / "_backup_metadata.json"
                    if meta_path.exists():
                        with open(meta_path) as f:
                            meta = json.load(f)
                        backups.append(BackupInfo(
                            name=meta.get("backup_name", item.name),
                            path=item,
                            created_at=meta.get("created_at", ""),
                            size_bytes=sum(f.stat().st_size for f in item.rglob("*") if f.is_file()),
                            checksum="directory",
                            files_count=len(meta.get("files", [])),
                            metadata=meta.get("custom", {})
                        ))
            except Exception as e:
                logger.warning(f"Could not read backup {item}: {e}")

        return sorted(backups, key=lambda b: b.created_at, reverse=True)

    def restore_backup(
        self,
        backup_name: str,
        restore_dir: Path,
        overwrite: bool = False
    ) -> bool:
        """
        Restore from a backup.

        Args:
            backup_name: Name of backup to restore
            restore_dir: Directory to restore to
            overwrite: Whether to overwrite existing files

        Returns:
            True if successful
        """
        backups = self.list_backups()
        backup = next((b for b in backups if b.name == backup_name or b.path.stem == backup_name), None)

        if not backup:
            logger.error(f"Backup not found: {backup_name}")
            return False

        logger.info(f"Restoring backup: {backup.name} to {restore_dir}")

        if restore_dir.exists() and not overwrite:
            logger.error(f"Restore directory exists: {restore_dir}. Use overwrite=True to proceed.")
            return False

        restore_dir.mkdir(parents=True, exist_ok=True)

        try:
            if backup.path.suffix == ".zip":
                with zipfile.ZipFile(backup.path, 'r') as zf:
                    for member in zf.namelist():
                        if member == "_backup_metadata.json":
                            continue
                        zf.extract(member, restore_dir)
            else:
                for item in backup.path.rglob("*"):
                    if item.name == "_backup_metadata.json":
                        continue
                    if item.is_file():
                        rel_path = item.relative_to(backup.path)
                        dest = restore_dir / rel_path
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, dest)

            logger.info(f"Restore completed: {backup.files_count} files")
            return True

        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False

    def cleanup_old_backups(self, keep: int = None) -> int:
        """
        Remove old backups, keeping only the most recent.

        Args:
            keep: Number of backups to keep (default from config)

        Returns:
            Number of backups removed
        """
        keep = keep or self.config.max_backups
        backups = self.list_backups()

        if len(backups) <= keep:
            return 0

        to_remove = backups[keep:]
        removed = 0

        for backup in to_remove:
            try:
                if backup.path.is_file():
                    backup.path.unlink()
                else:
                    shutil.rmtree(backup.path)
                removed += 1
                logger.info(f"Removed old backup: {backup.name}")
            except Exception as e:
                logger.warning(f"Could not remove backup {backup.name}: {e}")

        return removed

    def verify_backup(self, backup_name: str) -> bool:
        """Verify backup integrity."""
        backups = self.list_backups()
        backup = next((b for b in backups if b.name == backup_name), None)

        if not backup:
            logger.error(f"Backup not found: {backup_name}")
            return False

        if backup.path.suffix == ".zip":
            try:
                with zipfile.ZipFile(backup.path, 'r') as zf:
                    result = zf.testzip()
                    if result is not None:
                        logger.error(f"Backup corrupted at: {result}")
                        return False
                logger.info(f"Backup verified: {backup_name}")
                return True
            except Exception as e:
                logger.error(f"Backup verification failed: {e}")
                return False

        return True


# === AUTO BACKUP SCHEDULER ===

class AutoBackupScheduler:
    """Schedule automatic backups."""

    def __init__(self, manager: BackupManager, source_dirs: List[Path]):
        self.manager = manager
        self.source_dirs = source_dirs
        self._running = False

    async def run_schedule(self, interval_hours: int = 24):
        """Run backup on schedule."""
        import asyncio

        self._running = True
        logger.info(f"Auto backup started, interval: {interval_hours} hours")

        while self._running:
            try:
                # Create backup
                self.manager.create_backup(
                    name="auto",
                    source_dirs=self.source_dirs,
                    metadata={"type": "automatic"}
                )

                # Cleanup old backups
                self.manager.cleanup_old_backups()

            except Exception as e:
                logger.error(f"Auto backup failed: {e}")

            await asyncio.sleep(interval_hours * 3600)

    def stop(self):
        """Stop the scheduler."""
        self._running = False


# === SINGLETON ===

_backup_manager: Optional[BackupManager] = None

def get_backup_manager() -> BackupManager:
    """Get singleton backup manager."""
    global _backup_manager
    if _backup_manager is None:
        _backup_manager = BackupManager(Path(__file__).parent.parent / "backups")
    return _backup_manager
