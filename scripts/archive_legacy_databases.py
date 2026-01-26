#!/usr/bin/env python3
"""Archive legacy databases after consolidation.

This script moves 24 legacy databases from data/ to data/archive/YYYY-MM-DD/
while preserving the 3 consolidated databases for production use.

Safety features:
- Dry-run mode to preview actions
- Pre-flight checks before archival
- Detailed logging and manifest generation
- Rollback capability via restore script

Usage:
    python scripts/archive_legacy_databases.py --dry-run  # Preview
    python scripts/archive_legacy_databases.py            # Execute
"""

import os
import shutil
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple

# Databases to keep (consolidated databases)
KEEP_DATABASES = [
    "jarvis_core.db",
    "jarvis_analytics.db",
    "jarvis_cache.db"
]

# Legacy databases to archive (identified from inventory)
LEGACY_DATABASES = [
    "jarvis.db",                    # Original monolithic DB
    "llm_costs.db",                 # Migrated to analytics
    "telegram_memory.db",           # Memory data
    "jarvis_x_memory.db",          # X/Twitter memory
    "jarvis_admin.db",             # Admin data
    "jarvis_memory.db",            # Legacy memory
    "call_tracking.db",            # Token call tracking
    "raid_bot.db",                 # Raid campaigns
    "sentiment.db",                # Sentiment analysis
    "tax.db",                      # Tax events
    "whales.db",                   # Whale tracking
    "jarvis_spam_protection.db",   # Spam protection
    "rate_limiter.db",             # Rate limiter state
    "metrics.db",                  # System metrics
    "alerts.db",                   # Alert history
    "backtests.db",                # Backtest results
    "bot_health.db",               # Health checks
    "treasury_trades.db",          # Treasury trades
    "ai_memory.db",                # AI memory
    "health.db",                   # Health data
    "distributions.db",            # Token distributions
    "research.db",                 # Research data
    "custom.db",                   # Custom data
    "recycle_test.db",             # Test DB (can delete)
]

# Data directory
DATA_DIR = Path("data")


def calculate_md5(file_path: Path) -> str:
    """Calculate MD5 checksum of a file."""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def get_file_info(file_path: Path) -> Dict:
    """Get detailed file information."""
    if not file_path.exists():
        return None

    stat = file_path.stat()
    return {
        "path": str(file_path),
        "size": stat.st_size,
        "size_human": f"{stat.st_size / 1024:.1f}K",
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "checksum": calculate_md5(file_path)
    }


def verify_consolidated_databases() -> bool:
    """Verify that 3 consolidated databases exist and have data."""
    print("\n=== Pre-flight Checks ===")

    all_exist = True
    for db_name in KEEP_DATABASES:
        db_path = DATA_DIR / db_name
        if not db_path.exists():
            print(f"❌ CRITICAL: Missing consolidated database: {db_name}")
            all_exist = False
        else:
            size = db_path.stat().st_size
            print(f"✅ {db_name}: {size / 1024:.1f}K")

    return all_exist


def find_databases_to_archive() -> Tuple[List[Path], List[str]]:
    """Find legacy databases that exist and should be archived."""
    to_archive = []
    not_found = []

    for db_name in LEGACY_DATABASES:
        db_path = DATA_DIR / db_name
        if db_path.exists():
            to_archive.append(db_path)
        else:
            not_found.append(db_name)

    return to_archive, not_found


def archive_databases(dry_run: bool = False) -> Dict:
    """Archive legacy databases to timestamped directory.

    Args:
        dry_run: If True, preview actions without executing

    Returns:
        Dictionary with archival results
    """
    print("\n" + "="*60)
    print("DATABASE ARCHIVAL SCRIPT")
    print("="*60)

    if dry_run:
        print("🔍 DRY-RUN MODE: No files will be moved")
    else:
        print("⚠️  LIVE MODE: Files will be archived")

    # Verify consolidated databases exist
    if not verify_consolidated_databases():
        print("\n❌ Pre-flight checks FAILED")
        print("Cannot proceed without consolidated databases")
        return {"success": False, "error": "Missing consolidated databases"}

    # Find databases to archive
    to_archive, not_found = find_databases_to_archive()

    print(f"\n📊 Found {len(to_archive)} legacy databases to archive")
    if not_found:
        print(f"ℹ️  {len(not_found)} databases not found (likely already archived)")

    # Create archive directory
    timestamp = datetime.now().strftime("%Y-%m-%d")
    archive_dir = DATA_DIR / "archive" / timestamp

    print(f"\n📁 Archive directory: {archive_dir}")

    if not dry_run:
        archive_dir.mkdir(parents=True, exist_ok=True)

    # Archive each database
    archived_files = []
    total_size = 0

    print("\n=== Archival Operations ===")
    for db_path in to_archive:
        file_info = get_file_info(db_path)
        archive_path = archive_dir / db_path.name

        if dry_run:
            print(f"📦 Would archive: {db_path.name}")
            print(f"   → {archive_path}")
            print(f"   Size: {file_info['size_human']}, Modified: {file_info['modified']}")
        else:
            print(f"📦 Archiving: {db_path.name}")
            shutil.move(str(db_path), str(archive_path))

            # Verify archive succeeded
            if not archive_path.exists():
                print(f"   ❌ ERROR: Archive failed for {db_path.name}")
                continue

            # Verify checksum matches
            archive_checksum = calculate_md5(archive_path)
            if archive_checksum != file_info['checksum']:
                print(f"   ⚠️  WARNING: Checksum mismatch for {db_path.name}")
            else:
                print(f"   ✅ Verified: {file_info['size_human']}")

        archived_files.append({
            "name": db_path.name,
            "original": str(db_path),
            "archive": str(archive_path),
            "info": file_info
        })
        total_size += file_info['size']

    # Generate manifest
    manifest = {
        "timestamp": datetime.now().isoformat(),
        "dry_run": dry_run,
        "archived_count": len(archived_files),
        "total_size": total_size,
        "total_size_human": f"{total_size / 1024:.1f}K",
        "files": archived_files,
        "not_found": not_found
    }

    # Write manifest and log
    if not dry_run:
        manifest_path = archive_dir / "ARCHIVE-MANIFEST.txt"
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write("="*60 + "\n")
            f.write("DATABASE ARCHIVAL MANIFEST\n")
            f.write("="*60 + "\n\n")
            f.write(f"Timestamp: {manifest['timestamp']}\n")
            f.write(f"Archived: {manifest['archived_count']} databases\n")
            f.write(f"Total Size: {manifest['total_size_human']}\n\n")

            f.write("="*60 + "\n")
            f.write("ARCHIVED FILES\n")
            f.write("="*60 + "\n\n")

            for file in archived_files:
                f.write(f"File: {file['name']}\n")
                f.write(f"  Size: {file['info']['size_human']}\n")
                f.write(f"  Modified: {file['info']['modified']}\n")
                f.write(f"  Checksum: {file['info']['checksum']}\n")
                f.write(f"  Original: {file['original']}\n")
                f.write(f"  Archive: {file['archive']}\n\n")

            if not_found:
                f.write("="*60 + "\n")
                f.write("NOT FOUND (Already Archived?)\n")
                f.write("="*60 + "\n\n")
                for name in not_found:
                    f.write(f"  - {name}\n")

        print(f"\n📝 Manifest written to: {manifest_path}")

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    if dry_run:
        print(f"🔍 DRY-RUN: {len(archived_files)} databases would be archived")
    else:
        print(f"✅ SUCCESS: {len(archived_files)} databases archived")

    print(f"📊 Total size: {manifest['total_size_human']}")
    print(f"📁 Location: {archive_dir}")

    if not_found:
        print(f"ℹ️  {len(not_found)} databases not found (already archived?)")

    # Verify final state
    if not dry_run:
        remaining_dbs = list(DATA_DIR.glob("*.db"))
        print(f"\n✅ Databases remaining in data/: {len(remaining_dbs)}")
        for db in remaining_dbs:
            print(f"   - {db.name}")

        if len(remaining_dbs) == 3:
            print("\n🎉 GOAL ACHIEVED: Exactly 3 consolidated databases remain!")
        else:
            print(f"\n⚠️  Expected 3 databases, found {len(remaining_dbs)}")

    return manifest


def main():
    """Main entry point."""
    import sys

    # Check for dry-run flag
    dry_run = "--dry-run" in sys.argv

    result = archive_databases(dry_run=dry_run)

    if result.get("success") == False:
        print(f"\n❌ Archival failed: {result.get('error')}")
        sys.exit(1)

    if not dry_run:
        print("\n" + "="*60)
        print("NEXT STEPS")
        print("="*60)
        print("1. Test system functionality:")
        print("   python bots/supervisor.py")
        print("   (Monitor for database connection errors)")
        print()
        print("2. If issues occur, restore with:")
        print(f"   python scripts/restore_legacy_databases.py")
        print()
        print("3. Monitor for 24-48 hours before considering")
        print("   archival permanent")
        print("="*60)


if __name__ == "__main__":
    main()
