#!/usr/bin/env python3
"""Restore archived legacy databases (EMERGENCY ROLLBACK).

This script restores legacy databases from archive/ back to data/ directory.
Use this ONLY if the system fails after archival and needs emergency rollback.

Usage:
    python scripts/restore_legacy_databases.py --dry-run  # Preview
    python scripts/restore_legacy_databases.py            # Execute
    python scripts/restore_legacy_databases.py --from data/archive/2026-01-26/  # Specific archive
"""

import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Optional


DATA_DIR = Path("data")
ARCHIVE_BASE = DATA_DIR / "archive"


def find_latest_archive() -> Optional[Path]:
    """Find the most recent archive directory."""
    if not ARCHIVE_BASE.exists():
        return None

    archives = [d for d in ARCHIVE_BASE.iterdir() if d.is_dir()]
    if not archives:
        return None

    # Sort by directory name (assumes YYYY-MM-DD format)
    archives.sort(reverse=True)
    return archives[0]


def restore_databases(archive_dir: Optional[Path] = None, dry_run: bool = False):
    """Restore databases from archive to data/ directory.

    Args:
        archive_dir: Specific archive directory (default: latest)
        dry_run: If True, preview actions without executing
    """
    print("\n" + "="*60)
    print("DATABASE RESTORE SCRIPT (EMERGENCY ROLLBACK)")
    print("="*60)

    if dry_run:
        print("🔍 DRY-RUN MODE: No files will be moved")
    else:
        print("⚠️  LIVE MODE: Databases will be restored")

    # Find archive directory
    if archive_dir is None:
        archive_dir = find_latest_archive()

    if archive_dir is None:
        print("\n❌ ERROR: No archive directory found")
        print(f"Expected location: {ARCHIVE_BASE}")
        return {"success": False, "error": "No archive found"}

    if not archive_dir.exists():
        print(f"\n❌ ERROR: Archive directory not found: {archive_dir}")
        return {"success": False, "error": "Archive directory missing"}

    print(f"\n📁 Restoring from: {archive_dir}")

    # Find databases in archive
    archived_dbs = list(archive_dir.glob("*.db"))

    if not archived_dbs:
        print("\n❌ ERROR: No databases found in archive")
        return {"success": False, "error": "Empty archive"}

    print(f"📊 Found {len(archived_dbs)} databases to restore")

    # Check for conflicts
    conflicts = []
    for archive_db in archived_dbs:
        target_path = DATA_DIR / archive_db.name
        if target_path.exists():
            conflicts.append(archive_db.name)

    if conflicts:
        print(f"\n⚠️  WARNING: {len(conflicts)} conflicts detected")
        print("The following databases already exist in data/:")
        for name in conflicts:
            print(f"   - {name}")
        print("\nThese will be OVERWRITTEN during restore!")

        if not dry_run:
            response = input("\nContinue with restore? (yes/no): ")
            if response.lower() != "yes":
                print("❌ Restore cancelled by user")
                return {"success": False, "error": "User cancelled"}

    # Restore each database
    restored = []
    print("\n=== Restore Operations ===")

    for archive_db in archived_dbs:
        target_path = DATA_DIR / archive_db.name
        size = archive_db.stat().st_size

        if dry_run:
            print(f"📦 Would restore: {archive_db.name}")
            print(f"   → {target_path}")
            print(f"   Size: {size / 1024:.1f}K")
        else:
            print(f"📦 Restoring: {archive_db.name}")
            shutil.move(str(archive_db), str(target_path))

            if target_path.exists():
                print(f"   ✅ Restored: {size / 1024:.1f}K")
                restored.append(archive_db.name)
            else:
                print(f"   ❌ ERROR: Restore failed")

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    if dry_run:
        print(f"🔍 DRY-RUN: {len(archived_dbs)} databases would be restored")
    else:
        print(f"✅ SUCCESS: {len(restored)} databases restored")

        # Show current database count
        all_dbs = list(DATA_DIR.glob("*.db"))
        print(f"📊 Total databases in data/: {len(all_dbs)}")

    print(f"📁 Archive location: {archive_dir}")

    if not dry_run and restored:
        print("\n" + "="*60)
        print("NEXT STEPS")
        print("="*60)
        print("1. Restart the supervisor:")
        print("   python bots/supervisor.py")
        print()
        print("2. Verify system is working correctly")
        print()
        print("3. Investigate why the archive caused issues")
        print("   (Check logs, database connections, etc.)")
        print()
        print("4. Fix underlying issues before re-attempting")
        print("   archival")
        print("="*60)

    return {"success": True, "restored": len(restored)}


def main():
    """Main entry point."""
    import sys

    # Check for flags
    dry_run = "--dry-run" in sys.argv
    archive_dir = None

    # Check for --from flag
    for i, arg in enumerate(sys.argv):
        if arg == "--from" and i + 1 < len(sys.argv):
            archive_dir = Path(sys.argv[i + 1])
            break

    result = restore_databases(archive_dir=archive_dir, dry_run=dry_run)

    if result.get("success") == False:
        print(f"\n❌ Restore failed: {result.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
