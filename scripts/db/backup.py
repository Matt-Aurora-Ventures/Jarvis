#!/usr/bin/env python3
"""
JARVIS Database Backup Script

Automated database backup with:
- Timestamped backups
- Compression (gzip)
- Retention policy
- Backup verification
- Restore capability

Usage:
    python scripts/db/backup.py backup        # Create backup
    python scripts/db/backup.py restore FILE  # Restore from backup
    python scripts/db/backup.py list          # List backups
    python scripts/db/backup.py cleanup       # Remove old backups

Scheduling (cron example):
    0 2 * * * cd /path/to/jarvis && python scripts/db/backup.py backup
"""

import argparse
import gzip
import hashlib
import logging
import os
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Configuration
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "jarvis.db"
BACKUP_DIR = PROJECT_ROOT / "backups"
MAX_BACKUPS = 30  # Keep last 30 backups
BACKUP_PREFIX = "jarvis_db_"


@dataclass
class BackupInfo:
    """Information about a backup file."""
    path: Path
    created_at: datetime
    size_bytes: int
    checksum: str

    @property
    def size_mb(self) -> float:
        return self.size_bytes / (1024 * 1024)

    @property
    def age_days(self) -> float:
        delta = datetime.now(timezone.utc) - self.created_at
        return delta.total_seconds() / 86400

    def __str__(self) -> str:
        return f"{self.path.name} ({self.size_mb:.2f} MB, {self.age_days:.1f} days old)"


class DatabaseBackup:
    """Database backup manager."""

    def __init__(
        self,
        db_path: Path = DEFAULT_DB_PATH,
        backup_dir: Path = BACKUP_DIR,
        max_backups: int = MAX_BACKUPS,
    ):
        self.db_path = db_path
        self.backup_dir = backup_dir
        self.max_backups = max_backups

        # Ensure backup directory exists
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self, compress: bool = True) -> Optional[BackupInfo]:
        """
        Create a database backup.

        Args:
            compress: Whether to gzip the backup

        Returns:
            BackupInfo if successful, None otherwise
        """
        if not self.db_path.exists():
            logger.error(f"Database not found: {self.db_path}")
            return None

        # Generate backup filename with timestamp
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        extension = ".db.gz" if compress else ".db"
        backup_name = f"{BACKUP_PREFIX}{timestamp}{extension}"
        backup_path = self.backup_dir / backup_name

        logger.info(f"Creating backup: {backup_name}")

        try:
            # Use SQLite backup API for consistent backup
            source = sqlite3.connect(str(self.db_path))
            temp_path = self.backup_dir / f"temp_{timestamp}.db"

            # Create temp backup
            dest = sqlite3.connect(str(temp_path))
            source.backup(dest)
            dest.close()
            source.close()

            # Compress if requested
            if compress:
                with open(temp_path, "rb") as f_in:
                    with gzip.open(backup_path, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
                temp_path.unlink()
            else:
                shutil.move(str(temp_path), str(backup_path))

            # Calculate checksum
            checksum = self._calculate_checksum(backup_path)

            # Create checksum file
            checksum_path = backup_path.with_suffix(backup_path.suffix + ".md5")
            checksum_path.write_text(f"{checksum}  {backup_path.name}\n")

            backup_info = BackupInfo(
                path=backup_path,
                created_at=datetime.now(timezone.utc),
                size_bytes=backup_path.stat().st_size,
                checksum=checksum,
            )

            logger.info(f"Backup created: {backup_info}")
            return backup_info

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            # Cleanup on failure
            for path in [backup_path, temp_path]:
                if path.exists():
                    path.unlink()
            return None

    def restore_backup(self, backup_path: Path, target_path: Optional[Path] = None) -> bool:
        """
        Restore database from backup.

        Args:
            backup_path: Path to backup file
            target_path: Where to restore (defaults to original location)

        Returns:
            True if successful
        """
        if not backup_path.exists():
            logger.error(f"Backup not found: {backup_path}")
            return False

        target_path = target_path or self.db_path

        # Verify checksum if available
        checksum_path = backup_path.with_suffix(backup_path.suffix + ".md5")
        if checksum_path.exists():
            stored_checksum = checksum_path.read_text().split()[0]
            actual_checksum = self._calculate_checksum(backup_path)

            if stored_checksum != actual_checksum:
                logger.error("Checksum verification failed!")
                return False
            logger.info("Checksum verified")

        logger.info(f"Restoring backup to: {target_path}")

        try:
            # Create backup of current database
            if target_path.exists():
                pre_restore_backup = target_path.with_suffix(".db.pre_restore")
                shutil.copy(str(target_path), str(pre_restore_backup))
                logger.info(f"Created pre-restore backup: {pre_restore_backup.name}")

            # Decompress if needed
            if backup_path.suffix == ".gz":
                with gzip.open(backup_path, "rb") as f_in:
                    with open(target_path, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                shutil.copy(str(backup_path), str(target_path))

            # Verify restored database
            conn = sqlite3.connect(str(target_path))
            conn.execute("SELECT 1")
            conn.close()

            logger.info("Restore completed successfully")
            return True

        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False

    def list_backups(self) -> List[BackupInfo]:
        """List all available backups."""
        backups = []

        for path in sorted(self.backup_dir.glob(f"{BACKUP_PREFIX}*")):
            if path.suffix in [".db", ".gz"] and not path.suffix == ".md5":
                try:
                    # Parse timestamp from filename
                    timestamp_str = path.name.replace(BACKUP_PREFIX, "").split(".")[0]
                    created_at = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                    created_at = created_at.replace(tzinfo=timezone.utc)

                    checksum = ""
                    checksum_path = path.with_suffix(path.suffix + ".md5")
                    if checksum_path.exists():
                        checksum = checksum_path.read_text().split()[0]

                    backups.append(BackupInfo(
                        path=path,
                        created_at=created_at,
                        size_bytes=path.stat().st_size,
                        checksum=checksum,
                    ))
                except Exception as e:
                    logger.warning(f"Could not parse backup {path.name}: {e}")

        return sorted(backups, key=lambda b: b.created_at, reverse=True)

    def cleanup_old_backups(self) -> int:
        """Remove old backups beyond retention limit."""
        backups = self.list_backups()

        if len(backups) <= self.max_backups:
            logger.info(f"No cleanup needed ({len(backups)} backups, limit: {self.max_backups})")
            return 0

        to_remove = backups[self.max_backups:]
        removed = 0

        for backup in to_remove:
            try:
                backup.path.unlink()
                # Remove checksum file too
                checksum_path = backup.path.with_suffix(backup.path.suffix + ".md5")
                if checksum_path.exists():
                    checksum_path.unlink()
                removed += 1
                logger.info(f"Removed old backup: {backup.path.name}")
            except Exception as e:
                logger.error(f"Failed to remove {backup.path.name}: {e}")

        logger.info(f"Cleanup complete: removed {removed} backups")
        return removed

    def verify_backup(self, backup_path: Path) -> bool:
        """Verify backup integrity."""
        if not backup_path.exists():
            logger.error(f"Backup not found: {backup_path}")
            return False

        logger.info(f"Verifying backup: {backup_path.name}")

        # Check checksum
        checksum_path = backup_path.with_suffix(backup_path.suffix + ".md5")
        if checksum_path.exists():
            stored_checksum = checksum_path.read_text().split()[0]
            actual_checksum = self._calculate_checksum(backup_path)

            if stored_checksum != actual_checksum:
                logger.error("Checksum mismatch!")
                return False
            logger.info("Checksum OK")

        # Try to read the database
        try:
            if backup_path.suffix == ".gz":
                with gzip.open(backup_path, "rb") as f:
                    # Read first few bytes to verify it's valid gzip
                    f.read(1024)
            else:
                conn = sqlite3.connect(str(backup_path))
                conn.execute("SELECT 1")
                conn.close()

            logger.info("Backup verification passed")
            return True

        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return False

    def _calculate_checksum(self, path: Path) -> str:
        """Calculate MD5 checksum of a file."""
        md5 = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                md5.update(chunk)
        return md5.hexdigest()

    def get_status(self) -> dict:
        """Get backup status summary."""
        backups = self.list_backups()

        total_size = sum(b.size_bytes for b in backups)
        latest = backups[0] if backups else None

        return {
            "backup_count": len(backups),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "latest_backup": latest.path.name if latest else None,
            "latest_age_hours": round(latest.age_days * 24, 1) if latest else None,
            "max_backups": self.max_backups,
            "backup_dir": str(self.backup_dir),
        }


def main():
    parser = argparse.ArgumentParser(
        description="JARVIS Database Backup Utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python backup.py backup              Create a compressed backup
    python backup.py backup --no-compress Create uncompressed backup
    python backup.py restore backup.db.gz Restore from backup
    python backup.py list                List all backups
    python backup.py cleanup             Remove old backups
    python backup.py verify backup.db.gz Verify backup integrity
    python backup.py status              Show backup status
        """
    )

    parser.add_argument(
        "command",
        choices=["backup", "restore", "list", "cleanup", "verify", "status"],
        help="Backup command"
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="Backup file (for restore/verify commands)"
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Database path (default: {DEFAULT_DB_PATH})"
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=BACKUP_DIR,
        help=f"Backup directory (default: {BACKUP_DIR})"
    )
    parser.add_argument(
        "--no-compress",
        action="store_true",
        help="Don't compress the backup"
    )
    parser.add_argument(
        "--max-backups",
        type=int,
        default=MAX_BACKUPS,
        help=f"Maximum backups to keep (default: {MAX_BACKUPS})"
    )

    args = parser.parse_args()

    backup_mgr = DatabaseBackup(
        db_path=args.db,
        backup_dir=args.backup_dir,
        max_backups=args.max_backups,
    )

    if args.command == "backup":
        result = backup_mgr.create_backup(compress=not args.no_compress)
        if result:
            # Auto cleanup after successful backup
            backup_mgr.cleanup_old_backups()
        sys.exit(0 if result else 1)

    elif args.command == "restore":
        if not args.file:
            parser.error("Backup file required for restore command")
        backup_path = Path(args.file)
        if not backup_path.is_absolute():
            backup_path = args.backup_dir / backup_path
        success = backup_mgr.restore_backup(backup_path)
        sys.exit(0 if success else 1)

    elif args.command == "list":
        backups = backup_mgr.list_backups()
        if backups:
            print(f"\n{'Backup':<45} {'Size':>10} {'Age':>10}")
            print("-" * 70)
            for b in backups:
                print(f"{b.path.name:<45} {b.size_mb:>8.2f}MB {b.age_days:>8.1f}d")
            print(f"\nTotal: {len(backups)} backups")
        else:
            print("No backups found")

    elif args.command == "cleanup":
        backup_mgr.cleanup_old_backups()

    elif args.command == "verify":
        if not args.file:
            parser.error("Backup file required for verify command")
        backup_path = Path(args.file)
        if not backup_path.is_absolute():
            backup_path = args.backup_dir / backup_path
        success = backup_mgr.verify_backup(backup_path)
        sys.exit(0 if success else 1)

    elif args.command == "status":
        status = backup_mgr.get_status()
        print("\n=== Backup Status ===")
        for key, value in status.items():
            print(f"  {key}: {value}")
        print()


if __name__ == "__main__":
    main()
