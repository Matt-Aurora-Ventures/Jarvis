#!/usr/bin/env python3
"""
Migrate PostgreSQL archival_memory to SQLite facts.

Usage:
    python scripts/migrate_archival_memory.py
    python scripts/migrate_archival_memory.py --status
    python scripts/migrate_archival_memory.py --verify
    python scripts/migrate_archival_memory.py --dry-run
"""
import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.memory import init_workspace
from core.memory.database import get_db
from core.memory.migration import (
    get_migration_status,
    migrate_archival_memory,
    verify_migration,
)


def main():
    parser = argparse.ArgumentParser(
        description="Migrate PostgreSQL archival_memory to SQLite facts"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show migration status without migrating"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify migration completeness"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without actually migrating"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Batch size for migration (default: 50)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-migrate entries even if already migrated"
    )

    args = parser.parse_args()

    # Initialize workspace and database
    print("Initializing memory workspace...")
    init_workspace()

    # Initialize database by getting connection
    db = get_db()
    _ = db._get_connection()  # Force schema initialization
    print("Database initialized\n")

    if args.status or args.dry_run:
        status = get_migration_status()
        print("=== Migration Status ===")
        print(f"PostgreSQL available: {status['postgres_available']}")
        print(f"PostgreSQL entries:   {status['postgres_count']}")
        print(f"SQLite facts:         {status['sqlite_count']}")
        print(f"Already migrated:     {status['migrated_count']}")
        print(f"Pending migration:    {status['pending_count']}")

        if args.dry_run:
            print(f"\n[DRY RUN] Would migrate {status['pending_count']} entries")
        return 0

    if args.verify:
        result = verify_migration()
        print("\n=== Migration Verification ===")
        print(f"Complete: {result['is_complete']}")
        print(f"Pending: {result['status']['pending_count']}")

        if result['sample_facts']:
            print("\nSample migrated facts:")
            for fact in result['sample_facts']:
                content = fact['content'][:60] + "..." if len(fact['content']) > 60 else fact['content']
                print(f"  [{fact['id']}] pg:{fact['postgres_id']} - {content}")

        return 0 if result['is_complete'] else 1

    # Run migration
    print("=== Starting Migration ===")
    result = migrate_archival_memory(
        batch_size=args.batch_size,
        skip_existing=not args.force,
        verbose=True,
    )

    if not result['success']:
        print(f"\nMigration failed: {result.get('error', 'Unknown error')}")
        return 1

    print("\n=== Migration Summary ===")
    print(f"Migrated: {result['migrated_count']}")
    print(f"Skipped:  {result['skipped_count']}")
    print(f"Errors:   {result['error_count']}")

    if result['errors']:
        print("\nFirst few errors:")
        for pg_id, error in result['errors'][:5]:
            print(f"  [{pg_id}] {error}")

    # Verify after migration
    verification = verify_migration()
    if verification['is_complete']:
        print("\n✓ Migration verified complete!")
    else:
        print(f"\n⚠ Warning: {verification['status']['pending_count']} entries still pending")

    return 0


if __name__ == "__main__":
    sys.exit(main())
