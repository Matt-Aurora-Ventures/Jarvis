#!/usr/bin/env python3
"""
Position State Backup Script

Quick utility to backup current position state before risky operations.
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.backup_manager import BackupManager, create_emergency_backup


def main():
    parser = argparse.ArgumentParser(description="Backup Jarvis position state")
    parser.add_argument("--type", choices=["full", "positions_only", "config_only"],
                       default="positions_only",
                       help="Type of backup to create")
    parser.add_argument("--description", type=str,
                       help="Optional description for this backup")
    parser.add_argument("--emergency", action="store_true",
                       help="Create emergency full backup")
    parser.add_argument("--backup-dir", type=Path,
                       help="Custom backup directory")

    args = parser.parse_args()

    if args.emergency:
        print("Creating emergency full backup...")
        metadata = create_emergency_backup(
            description=args.description or "Emergency backup via CLI"
        )
    else:
        manager = BackupManager(
            backup_dir=args.backup_dir,
            project_root=PROJECT_ROOT
        )

        print(f"Creating {args.type} backup...")
        metadata = manager.create_backup(
            backup_type=args.type,
            description=args.description
        )

    print(f"\n✓ Backup created: {metadata.backup_id}")
    print(f"  Timestamp: {metadata.timestamp}")
    print(f"  Files backed up: {len(metadata.files_backed_up)}")
    print(f"  Total size: {metadata.size_bytes:,} bytes")
    print(f"  Location: {manager.backup_dir / metadata.backup_id}")

    if metadata.files_backed_up:
        print("\n  Backed up files:")
        for file in metadata.files_backed_up:
            print(f"    - {file}")


if __name__ == "__main__":
    main()
