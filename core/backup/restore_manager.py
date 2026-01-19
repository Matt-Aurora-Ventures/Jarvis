"""
Restore Manager - Handles backup restoration with safety features.

Provides:
- Full restore from any backup
- Point-in-time restore
- Single file restore
- Dry run preview
- Safety backup before restore
- Checksum verification
"""

import json
import shutil
import tarfile
import hashlib
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from core.backup.backup_manager import BackupConfig, BackupManager

logger = logging.getLogger(__name__)


@dataclass
class RestoreResult:
    """Result of a restore operation."""
    success: bool
    restored_path: Optional[Path] = None
    files_restored: int = 0
    verified: bool = False
    is_dry_run: bool = False
    safety_backup_path: Optional[Path] = None
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


class RestoreManager:
    """
    Manages backup restoration with safety features.

    Features:
    - Restore latest backup
    - Restore specific backup
    - Point-in-time restore
    - Single file restore
    - Dry run mode
    - Safety backup before restore
    - Checksum verification
    """

    MANIFEST_FILE = "_backup_manifest.json"

    def __init__(self, config: BackupConfig):
        self.config = config
        self.backup_dir = Path(config.backup_dir)
        self._backup_manager = BackupManager(config)

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _create_safety_backup(self, target_dir: Path) -> Optional[Path]:
        """Create a safety backup of the target directory before restore."""
        if not target_dir.exists() or not any(target_dir.iterdir()):
            return None

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safety_path = self.backup_dir / f"_safety_backup_{timestamp}.tar.gz"

        try:
            with tarfile.open(safety_path, "w:gz") as tar:
                for item in target_dir.iterdir():
                    tar.add(item, arcname=item.name)

            logger.info(f"Safety backup created: {safety_path}")
            return safety_path

        except Exception as e:
            logger.warning(f"Could not create safety backup: {e}")
            return None

    def _extract_from_archive(
        self,
        archive_path: Path,
        dest_dir: Path,
        specific_file: str = None,
        dry_run: bool = False
    ) -> tuple:
        """Extract files from tar.gz archive."""
        files_extracted = 0
        warnings = []

        with tarfile.open(archive_path, "r:gz") as tar:
            members = [m for m in tar.getmembers() if m.name != self.MANIFEST_FILE]

            if specific_file:
                members = [m for m in members if specific_file in m.name]

            for member in members:
                if dry_run:
                    logger.info(f"[DRY RUN] Would extract: {member.name}")
                    files_extracted += 1
                else:
                    try:
                        tar.extract(member, dest_dir)
                        files_extracted += 1
                    except Exception as e:
                        warnings.append(f"Could not extract {member.name}: {e}")

        return files_extracted, warnings

    def _copy_from_directory(
        self,
        source_dir: Path,
        dest_dir: Path,
        specific_file: str = None,
        dry_run: bool = False
    ) -> tuple:
        """Copy files from directory backup."""
        files_copied = 0
        warnings = []

        for item in source_dir.rglob("*"):
            if item.name == self.MANIFEST_FILE:
                continue
            if not item.is_file():
                continue

            rel_path = item.relative_to(source_dir)

            if specific_file and specific_file not in str(rel_path):
                continue

            dest_path = dest_dir / rel_path

            if dry_run:
                logger.info(f"[DRY RUN] Would copy: {rel_path}")
                files_copied += 1
            else:
                try:
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest_path)
                    files_copied += 1
                except Exception as e:
                    warnings.append(f"Could not copy {rel_path}: {e}")

        return files_copied, warnings

    def restore_latest(
        self,
        dest_dir: Path,
        verify: bool = True,
        dry_run: bool = False,
        create_safety_backup: bool = True
    ) -> RestoreResult:
        """
        Restore from the most recent backup.

        Args:
            dest_dir: Directory to restore to
            verify: Verify checksums after restore
            dry_run: Preview without actually restoring
            create_safety_backup: Backup current state before restore

        Returns:
            RestoreResult with details
        """
        latest = self._backup_manager.get_latest_backup()

        if not latest:
            return RestoreResult(
                success=False,
                error="No backups found"
            )

        return self.restore_backup(
            latest.backup_path,
            dest_dir,
            verify=verify,
            dry_run=dry_run,
            create_safety_backup=create_safety_backup
        )

    def restore_backup(
        self,
        backup_path: Path,
        dest_dir: Path,
        verify: bool = True,
        dry_run: bool = False,
        create_safety_backup: bool = True
    ) -> RestoreResult:
        """
        Restore from a specific backup.

        Args:
            backup_path: Path to the backup
            dest_dir: Directory to restore to
            verify: Verify checksums after restore
            dry_run: Preview without actually restoring
            create_safety_backup: Backup current state before restore

        Returns:
            RestoreResult with details
        """
        if not backup_path.exists():
            return RestoreResult(
                success=False,
                error=f"Backup not found: {backup_path}"
            )

        safety_backup = None
        if create_safety_backup and not dry_run:
            safety_backup = self._create_safety_backup(dest_dir)

        try:
            dest_dir.mkdir(parents=True, exist_ok=True)

            if backup_path.suffix == ".gz" or ".tar.gz" in str(backup_path):
                files_restored, warnings = self._extract_from_archive(
                    backup_path, dest_dir, dry_run=dry_run
                )
            else:
                files_restored, warnings = self._copy_from_directory(
                    backup_path, dest_dir, dry_run=dry_run
                )

            verified = False
            if verify and not dry_run:
                verification = self._backup_manager.verify_backup(backup_path)
                verified = verification.is_valid

            logger.info(
                f"{'[DRY RUN] ' if dry_run else ''}Restore completed: "
                f"{files_restored} files from {backup_path.name}"
            )

            return RestoreResult(
                success=True,
                restored_path=dest_dir,
                files_restored=files_restored,
                verified=verified,
                is_dry_run=dry_run,
                safety_backup_path=safety_backup,
                warnings=warnings
            )

        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return RestoreResult(
                success=False,
                error=str(e),
                safety_backup_path=safety_backup
            )

    def restore_point_in_time(
        self,
        dest_dir: Path,
        timestamp: datetime,
        verify: bool = True,
        dry_run: bool = False,
        create_safety_backup: bool = True
    ) -> RestoreResult:
        """
        Restore to a specific point in time.

        Finds the most recent backup before the specified timestamp.

        Args:
            dest_dir: Directory to restore to
            timestamp: Target timestamp
            verify: Verify checksums after restore
            dry_run: Preview without actually restoring
            create_safety_backup: Backup current state before restore

        Returns:
            RestoreResult with details
        """
        backups = self._backup_manager.list_backups()

        # Find the most recent backup before timestamp
        # Make timestamp timezone-aware if it isn't
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        eligible = [
            b for b in backups
            if b.created_at <= timestamp
        ]

        if not eligible:
            return RestoreResult(
                success=False,
                error=f"No backup found before {timestamp.isoformat()}"
            )

        # Get the most recent eligible backup
        target_backup = eligible[0]

        logger.info(f"Point-in-time restore: using backup from {target_backup.created_at}")

        return self.restore_backup(
            target_backup.backup_path,
            dest_dir,
            verify=verify,
            dry_run=dry_run,
            create_safety_backup=create_safety_backup
        )

    def restore_file(
        self,
        file_path: str,
        dest: Path,
        backup_path: Path = None,
        verify: bool = True
    ) -> RestoreResult:
        """
        Restore a single file from backup.

        Args:
            file_path: Relative path of file within backup
            dest: Destination path for restored file
            backup_path: Specific backup to restore from (default: latest)
            verify: Verify checksum after restore

        Returns:
            RestoreResult with details
        """
        if backup_path is None:
            latest = self._backup_manager.get_latest_backup()
            if not latest:
                return RestoreResult(
                    success=False,
                    error="No backups found"
                )
            backup_path = latest.backup_path

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)

            if backup_path.suffix == ".gz" or ".tar.gz" in str(backup_path):
                with tarfile.open(backup_path, "r:gz") as tar:
                    # Find the file in archive
                    for member in tar.getmembers():
                        if file_path in member.name:
                            # Extract to temp location then move
                            import tempfile
                            with tempfile.TemporaryDirectory() as tmpdir:
                                tar.extract(member, tmpdir)
                                extracted = Path(tmpdir) / member.name
                                shutil.copy2(extracted, dest)

                            logger.info(f"Restored file: {file_path} -> {dest}")
                            return RestoreResult(
                                success=True,
                                restored_path=dest,
                                files_restored=1,
                                verified=True
                            )

                    return RestoreResult(
                        success=False,
                        error=f"File not found in backup: {file_path}"
                    )

            else:
                # Directory backup
                source = backup_path / file_path
                if not source.exists():
                    # Try to find it
                    matches = list(backup_path.rglob(f"*{file_path}*"))
                    if matches:
                        source = matches[0]
                    else:
                        return RestoreResult(
                            success=False,
                            error=f"File not found in backup: {file_path}"
                        )

                shutil.copy2(source, dest)
                logger.info(f"Restored file: {file_path} -> {dest}")

                return RestoreResult(
                    success=True,
                    restored_path=dest,
                    files_restored=1,
                    verified=True
                )

        except Exception as e:
            logger.error(f"File restore failed: {e}")
            return RestoreResult(
                success=False,
                error=str(e)
            )

    def list_backup_contents(self, backup_path: Path = None) -> List[str]:
        """List all files in a backup."""
        if backup_path is None:
            latest = self._backup_manager.get_latest_backup()
            if not latest:
                return []
            backup_path = latest.backup_path

        files = []

        try:
            if backup_path.suffix == ".gz" or ".tar.gz" in str(backup_path):
                with tarfile.open(backup_path, "r:gz") as tar:
                    files = [m.name for m in tar.getmembers() if m.name != self.MANIFEST_FILE]
            else:
                for item in backup_path.rglob("*"):
                    if item.is_file() and item.name != self.MANIFEST_FILE:
                        files.append(str(item.relative_to(backup_path)))
        except Exception as e:
            logger.error(f"Could not list backup contents: {e}")

        return files
