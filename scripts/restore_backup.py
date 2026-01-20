#!/usr/bin/env python3
"""
Backup Restoration Script

Restore Jarvis state from a backup snapshot.
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.backup_manager import BackupManager


def list_backups(manager: BackupManager, backup_type: str = None):
    """Display available backups"""
    backups = manager.list_backups(backup_type=backup_type)

    if not backups:
        print("No backups found.")
        return

    # Prepare table data
    print("\nAvailable Backups:")
    print("-" * 100)
    for backup in backups:
        size_mb = backup.size_bytes / (1024 * 1024)
        print(f"ID: {backup.backup_id}")
        print(f"  Time: {backup.timestamp[:19]}")
        print(f"  Type: {backup.backup_type}")
        print(f"  Files: {len(backup.files_backed_up)}")
        print(f"  Size: {size_mb:.2f} MB")
        if backup.description:
            print(f"  Description: {backup.description}")
        print("-" * 100)


def verify_backup(manager: BackupManager, backup_id: str):
    """Verify backup integrity"""
    print(f"Verifying backup {backup_id}...")
    results = manager.verify_backup(backup_id)

    if results["valid"]:
        print(f"✓ Backup is valid")
        print(f"  Files verified: {len(results['files_verified'])}")
        for file in results["files_verified"]:
            print(f"    - {file}")
    else:
        print(f"✗ Backup verification failed")
        if "error" in results:
            print(f"  Error: {results['error']}")
        if results.get("missing_files"):
            print(f"  Missing files: {results['missing_files']}")
        if results.get("corrupted_files"):
            print(f"  Corrupted files: {results['corrupted_files']}")


def restore_backup(manager: BackupManager, backup_id: str, dry_run: bool, restore_files: list = None):
    """Restore from backup"""
    mode = "DRY RUN" if dry_run else "LIVE"
    print(f"[{mode}] Restoring from backup {backup_id}...")

    if not dry_run:
        confirm = input("\n⚠ This will overwrite current files. Continue? (yes/no): ")
        if confirm.lower() != "yes":
            print("Restoration cancelled.")
            return

    results = manager.restore_backup(backup_id, dry_run=dry_run, restore_files=restore_files)

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Restoration complete:")
    print(f"  Restored files: {len(results['restored_files'])}")
    for file in results['restored_files']:
        print(f"    ✓ {file}")

    if results['skipped_files']:
        print(f"  Skipped files: {len(results['skipped_files'])}")
        for file in results['skipped_files']:
            print(f"    - {file}")

    if results['errors']:
        print(f"  Errors: {len(results['errors'])}")
        for error in results['errors']:
            print(f"    ✗ {error}")

    if dry_run:
        print("\n💡 Run without --dry-run to actually restore files")


def cleanup_backups(manager: BackupManager, dry_run: bool):
    """Clean up old backups"""
    mode = "DRY RUN" if dry_run else "LIVE"
    print(f"[{mode}] Cleaning up old backups...")
    print(f"  Retention policy: {manager.retention_days} days, max {manager.max_backups} backups")

    results = manager.cleanup_old_backups(dry_run=dry_run)

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Cleanup complete:")
    print(f"  Deleted backups: {len(results['deleted_backups'])}")
    for backup_id in results['deleted_backups']:
        print(f"    ✗ {backup_id}")

    freed_mb = results['total_freed_bytes'] / (1024 * 1024)
    print(f"  Space freed: {freed_mb:.2f} MB")
    print(f"  Remaining backups: {len(results['kept_backups'])}")

    if dry_run:
        print("\n💡 Run without --dry-run to actually delete backups")


def main():
    parser = argparse.ArgumentParser(description="Restore Jarvis from backup")
    parser.add_argument("--list", action="store_true",
                       help="List available backups")
    parser.add_argument("--type", choices=["full", "positions_only", "config_only"],
                       help="Filter backups by type (for --list)")
    parser.add_argument("--restore", type=str, metavar="BACKUP_ID",
                       help="Restore from specific backup ID")
    parser.add_argument("--latest", action="store_true",
                       help="Restore from latest backup")
    parser.add_argument("--verify", type=str, metavar="BACKUP_ID",
                       help="Verify backup integrity")
    parser.add_argument("--cleanup", action="store_true",
                       help="Clean up old backups")
    parser.add_argument("--dry-run", action="store_true",
                       help="Simulate restore without actually changing files")
    parser.add_argument("--files", nargs="+",
                       help="Restore only specific files (e.g., positions exit_intents)")
    parser.add_argument("--backup-dir", type=Path,
                       help="Custom backup directory")

    args = parser.parse_args()

    manager = BackupManager(
        backup_dir=args.backup_dir,
        project_root=PROJECT_ROOT
    )

    # List backups
    if args.list:
        list_backups(manager, backup_type=args.type)
        return

    # Verify backup
    if args.verify:
        verify_backup(manager, args.verify)
        return

    # Cleanup backups
    if args.cleanup:
        cleanup_backups(manager, dry_run=args.dry_run)
        return

    # Restore from latest
    if args.latest:
        backups = manager.list_backups(backup_type=args.type)
        if not backups:
            print("No backups found.")
            return
        args.restore = backups[0].backup_id

    # Restore from specific backup
    if args.restore:
        restore_backup(manager, args.restore, args.dry_run, args.files)
        return

    # No action specified
    parser.print_help()


if __name__ == "__main__":
    main()
