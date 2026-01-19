#!/usr/bin/env python3
"""
Backup Verification Tool - Verify backup integrity and data health.

Usage:
    python scripts/verify_backup.py --latest         # Check latest backup
    python scripts/verify_backup.py --date 2026-01-15  # Check specific date
    python scripts/verify_backup.py --all            # Check all backups
    python scripts/verify_backup.py --check-data     # Check live data integrity
    python scripts/verify_backup.py --cleanup --days 30  # Remove old backups
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
from core.backup.disaster_recovery import DisasterRecoveryManager

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


def verify_latest(manager: BackupManager) -> bool:
    """Verify the latest backup."""
    latest = manager.get_latest_backup()

    if not latest:
        print("ERROR: No backups found")
        return False

    print(f"\nVerifying latest backup: {latest.name}")
    print(f"  Path: {latest.backup_path}")
    print(f"  Created: {latest.created_at}")
    print(f"  Size: {latest.size_bytes / 1024:.1f} KB")
    print(f"  Files: {latest.files_count}")

    result = manager.verify_backup(latest.backup_path)

    if result.is_valid:
        print(f"  Status: VALID ({result.files_verified} files verified)")
        return True
    else:
        print(f"  Status: INVALID")
        for error in result.errors:
            print(f"    - {error}")
        return False


def verify_date(manager: BackupManager, date_str: str) -> bool:
    """Verify backup from a specific date."""
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        print(f"ERROR: Invalid date format. Use YYYY-MM-DD")
        return False

    backups = manager.list_backups()

    # Find backup from target date
    matching = [
        b for b in backups
        if b.created_at.date() == target_date.date()
    ]

    if not matching:
        print(f"ERROR: No backup found for {date_str}")
        print("\nAvailable backups:")
        for b in backups[:5]:
            print(f"  - {b.created_at.date()}: {b.name}")
        return False

    all_valid = True
    for backup in matching:
        print(f"\nVerifying backup: {backup.name}")
        result = manager.verify_backup(backup.backup_path)

        if result.is_valid:
            print(f"  Status: VALID")
        else:
            print(f"  Status: INVALID")
            for error in result.errors:
                print(f"    - {error}")
            all_valid = False

    return all_valid


def verify_all(manager: BackupManager) -> bool:
    """Verify all backups."""
    backups = manager.list_backups()

    if not backups:
        print("ERROR: No backups found")
        return False

    print(f"\nVerifying {len(backups)} backups...")

    valid_count = 0
    invalid_count = 0

    for backup in backups:
        result = manager.verify_backup(backup.backup_path)
        status = "VALID" if result.is_valid else "INVALID"
        print(f"  {backup.name}: {status}")

        if result.is_valid:
            valid_count += 1
        else:
            invalid_count += 1
            for error in result.errors:
                print(f"    - {error}")

    print(f"\nSummary: {valid_count} valid, {invalid_count} invalid")
    return invalid_count == 0


def check_data(dr_manager: DisasterRecoveryManager) -> bool:
    """Check live data integrity."""
    print("\nRunning data health check...")

    issues = dr_manager.run_health_check()

    if not issues:
        print("  Status: HEALTHY - No issues detected")
        return True

    critical = [i for i in issues if i.severity == "critical"]
    warnings = [i for i in issues if i.severity == "warning"]

    print(f"\nFound {len(issues)} issues:")
    print(f"  Critical: {len(critical)}")
    print(f"  Warnings: {len(warnings)}")

    for issue in issues:
        severity_icon = "!!!" if issue.severity == "critical" else "!"
        print(f"\n  [{severity_icon}] {issue.category.upper()}")
        print(f"      {issue.description}")
        if issue.file_path:
            print(f"      File: {issue.file_path}")
        if issue.recoverable:
            print(f"      Recoverable: Yes")

    return len(critical) == 0


def cleanup_backups(manager: BackupManager, days: int) -> None:
    """Remove backups older than specified days."""
    print(f"\nCleaning up backups older than {days} days...")

    # Temporarily update retention
    original_retention = manager.config.retention_days
    manager.config.retention_days = days

    removed = manager.cleanup_old_backups(keep_minimum=1)

    manager.config.retention_days = original_retention

    print(f"Removed {removed} old backups")


def show_status(manager: BackupManager, dr_manager: DisasterRecoveryManager) -> None:
    """Show backup system status."""
    integrity = dr_manager.validate_system_integrity()
    backups = manager.list_backups()

    print("\n=== Backup System Status ===")
    print(f"\nSystem Health: {'HEALTHY' if integrity.is_healthy else 'UNHEALTHY'}")
    print(f"Files Checked: {integrity.files_checked}")
    print(f"Issues Found: {len(integrity.issues)}")

    print(f"\nBackup Status:")
    print(f"  Total Backups: {len(backups)}")
    print(f"  Backup Available: {integrity.backup_available}")

    if integrity.last_backup:
        age = datetime.now(timezone.utc) - integrity.last_backup
        print(f"  Last Backup: {integrity.last_backup.strftime('%Y-%m-%d %H:%M')} UTC")
        print(f"  Backup Age: {age.days}d {age.seconds // 3600}h")

    if backups:
        print(f"\nRecent Backups:")
        for backup in backups[:5]:
            print(f"  - {backup.name} ({backup.size_bytes / 1024:.1f} KB)")


def main():
    parser = argparse.ArgumentParser(
        description="Verify backup integrity and data health"
    )

    parser.add_argument(
        "--latest",
        action="store_true",
        help="Verify the latest backup"
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Verify backup from specific date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Verify all backups"
    )
    parser.add_argument(
        "--check-data",
        action="store_true",
        help="Check live data integrity"
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Remove old backups"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Days to retain for cleanup (default: 30)"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show backup system status"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format"
    )

    args = parser.parse_args()

    # Initialize managers
    config = get_default_config()
    manager = BackupManager(config)
    dr_manager = DisasterRecoveryManager(config)

    # Default to status if no action specified
    if not any([args.latest, args.date, args.all, args.check_data, args.cleanup]):
        args.status = True

    success = True

    if args.status:
        show_status(manager, dr_manager)

    if args.latest:
        success = verify_latest(manager) and success

    if args.date:
        success = verify_date(manager, args.date) and success

    if args.all:
        success = verify_all(manager) and success

    if args.check_data:
        success = check_data(dr_manager) and success

    if args.cleanup:
        cleanup_backups(manager, args.days)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
