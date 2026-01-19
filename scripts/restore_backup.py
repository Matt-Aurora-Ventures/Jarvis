#!/usr/bin/env python3
"""
Backup Restore Tool - Restore data from backups with safety features.

Usage:
    python scripts/restore_backup.py --latest              # Restore latest backup
    python scripts/restore_backup.py --date 2026-01-15 --dry-run  # Preview restore
    python scripts/restore_backup.py --file positions.json --latest  # Restore single file
    python scripts/restore_backup.py --safety-backup       # Create safety backup only
    python scripts/restore_backup.py --list                # List available backups
"""

import argparse
import sys
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.backup.backup_manager import BackupManager, BackupConfig
from core.backup.restore_manager import RestoreManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_default_config() -> BackupConfig:
    """Get default backup configuration."""
    project_root = Path(__file__).parent.parent
    return BackupConfig(
        backup_dir=project_root / "data" / "backups",
        data_paths=[
            project_root / "data",
            project_root / "bots" / "treasury",
            Path.home() / ".lifeos" / "trading"
        ],
        retention_days=30,
        compression=True
    )


def confirm_action(message: str) -> bool:
    """Ask for user confirmation."""
    response = input(f"\n{message} [y/N]: ").strip().lower()
    return response in ("y", "yes")


def list_backups(manager: BackupManager) -> None:
    """List all available backups."""
    backups = manager.list_backups()

    if not backups:
        print("No backups found")
        return

    print(f"\n=== Available Backups ({len(backups)}) ===\n")
    print(f"{'Date':<20} {'Type':<12} {'Size':<12} {'Files':<8} Name")
    print("-" * 80)

    for backup in backups:
        date_str = backup.created_at.strftime("%Y-%m-%d %H:%M")
        size_str = f"{backup.size_bytes / 1024:.1f} KB"
        print(f"{date_str:<20} {backup.backup_type:<12} {size_str:<12} {backup.files_count:<8} {backup.name}")


def restore_latest(
    restore_mgr: RestoreManager,
    dest_dir: Path,
    dry_run: bool = False,
    no_confirm: bool = False
) -> bool:
    """Restore from the latest backup."""
    latest = restore_mgr._backup_manager.get_latest_backup()

    if not latest:
        print("ERROR: No backups found")
        return False

    print(f"\nRestore from: {latest.name}")
    print(f"  Created: {latest.created_at}")
    print(f"  Files: {latest.files_count}")
    print(f"  Size: {latest.size_bytes / 1024:.1f} KB")
    print(f"  Destination: {dest_dir}")

    if dry_run:
        print("\n[DRY RUN MODE - No changes will be made]")

    if not no_confirm and not dry_run:
        if not confirm_action("Proceed with restore?"):
            print("Restore cancelled")
            return False

    result = restore_mgr.restore_latest(
        dest_dir,
        verify=True,
        dry_run=dry_run,
        create_safety_backup=True
    )

    if result.success:
        print(f"\n{'[DRY RUN] ' if dry_run else ''}Restore completed successfully")
        print(f"  Files restored: {result.files_restored}")
        print(f"  Verified: {result.verified}")

        if result.safety_backup_path:
            print(f"  Safety backup: {result.safety_backup_path}")

        if result.warnings:
            print("\nWarnings:")
            for warning in result.warnings:
                print(f"  - {warning}")

        return True
    else:
        print(f"\nRestore FAILED: {result.error}")
        return False


def restore_date(
    restore_mgr: RestoreManager,
    date_str: str,
    dest_dir: Path,
    dry_run: bool = False,
    no_confirm: bool = False
) -> bool:
    """Restore from a specific date."""
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d")
        target_date = target_date.replace(
            hour=23, minute=59, second=59,
            tzinfo=timezone.utc
        )
    except ValueError:
        print(f"ERROR: Invalid date format. Use YYYY-MM-DD")
        return False

    print(f"\nRestoring to point-in-time: {date_str}")
    print(f"  Destination: {dest_dir}")

    if dry_run:
        print("\n[DRY RUN MODE - No changes will be made]")

    if not no_confirm and not dry_run:
        if not confirm_action("Proceed with restore?"):
            print("Restore cancelled")
            return False

    result = restore_mgr.restore_point_in_time(
        dest_dir,
        timestamp=target_date,
        verify=True,
        dry_run=dry_run,
        create_safety_backup=True
    )

    if result.success:
        print(f"\n{'[DRY RUN] ' if dry_run else ''}Restore completed successfully")
        print(f"  Files restored: {result.files_restored}")
        return True
    else:
        print(f"\nRestore FAILED: {result.error}")
        return False


def restore_file(
    restore_mgr: RestoreManager,
    file_path: str,
    dest_dir: Path,
    use_latest: bool = True,
    no_confirm: bool = False
) -> bool:
    """Restore a single file from backup."""
    dest = dest_dir / Path(file_path).name

    print(f"\nRestore file: {file_path}")
    print(f"  Destination: {dest}")

    if not no_confirm:
        if not confirm_action("Proceed with restore?"):
            print("Restore cancelled")
            return False

    result = restore_mgr.restore_file(
        file_path=file_path,
        dest=dest,
        backup_path=None if use_latest else None
    )

    if result.success:
        print(f"\nRestore completed successfully")
        print(f"  Restored to: {dest}")
        return True
    else:
        print(f"\nRestore FAILED: {result.error}")
        return False


def create_safety_backup(backup_mgr: BackupManager) -> bool:
    """Create a safety backup of current state."""
    print("\nCreating safety backup of current state...")

    result = backup_mgr.create_full_backup(
        metadata={"type": "safety_backup", "manual": True}
    )

    if result.success:
        print(f"\nSafety backup created successfully")
        print(f"  Path: {result.backup_path}")
        print(f"  Files: {result.files_count}")
        print(f"  Size: {result.size_bytes / 1024:.1f} KB")
        return True
    else:
        print(f"\nSafety backup FAILED: {result.error}")
        return False


def list_backup_contents(restore_mgr: RestoreManager, backup_path: Path = None) -> None:
    """List contents of a backup."""
    files = restore_mgr.list_backup_contents(backup_path)

    if not files:
        print("No files found in backup")
        return

    print(f"\n=== Backup Contents ({len(files)} files) ===\n")
    for f in sorted(files):
        print(f"  {f}")


def main():
    parser = argparse.ArgumentParser(
        description="Restore data from backups"
    )

    parser.add_argument(
        "--latest",
        action="store_true",
        help="Restore from latest backup"
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Restore from specific date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Restore specific file"
    )
    parser.add_argument(
        "--dest",
        type=str,
        help="Destination directory (default: data/restore)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without actually restoring"
    )
    parser.add_argument(
        "--safety-backup",
        action="store_true",
        help="Create safety backup only"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available backups"
    )
    parser.add_argument(
        "--contents",
        action="store_true",
        help="List contents of latest backup"
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompts"
    )

    args = parser.parse_args()

    # Initialize
    config = get_default_config()
    backup_mgr = BackupManager(config)
    restore_mgr = RestoreManager(config)

    project_root = Path(__file__).parent.parent
    dest_dir = Path(args.dest) if args.dest else project_root / "data" / "restore"

    success = True

    if args.list:
        list_backups(backup_mgr)

    elif args.contents:
        list_backup_contents(restore_mgr)

    elif args.safety_backup:
        success = create_safety_backup(backup_mgr)

    elif args.file and args.latest:
        success = restore_file(
            restore_mgr,
            args.file,
            dest_dir,
            use_latest=True,
            no_confirm=args.yes
        )

    elif args.date:
        success = restore_date(
            restore_mgr,
            args.date,
            dest_dir,
            dry_run=args.dry_run,
            no_confirm=args.yes
        )

    elif args.latest:
        success = restore_latest(
            restore_mgr,
            dest_dir,
            dry_run=args.dry_run,
            no_confirm=args.yes
        )

    else:
        parser.print_help()
        print("\n\nExample commands:")
        print("  python scripts/restore_backup.py --list")
        print("  python scripts/restore_backup.py --latest --dry-run")
        print("  python scripts/restore_backup.py --date 2026-01-15")
        print("  python scripts/restore_backup.py --file positions.json --latest")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
