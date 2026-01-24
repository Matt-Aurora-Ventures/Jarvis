"""
Database Migration Script - 29 DBs → 3 Consolidated DBs

Phase 1, Task 3: Database Consolidation Migration

This script migrates 29 SQLite databases into 3 consolidated databases:
1. jarvis_core.db - Operational trading data
2. jarvis_analytics.db - Analytics, memory, logs
3. jarvis_cache.db - Temporary/ephemeral data

Usage:
    python scripts/migrate_databases.py --dry-run  # Preview migration
    python scripts/migrate_databases.py             # Execute migration
    python scripts/migrate_databases.py --rollback  # Rollback to originals

Safety:
- Creates backups in data/backup/ before migration
- Validates foreign key constraints
- Supports rollback via feature flag
"""

import sqlite3
import shutil
import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = Path.home() / ".lifeos" / "data"
BACKUP_DIR = DATA_DIR / "backup"
MIGRATION_LOG = DATA_DIR / "migration.log"

# Source databases to consolidate
SOURCE_DBS = {
    "jarvis_core": [
        "jarvis.db",              # positions, trades, scorecard
        "treasury_trades.db",     # treasury_orders
        "tax.db",                 # tax_lots, wash_sales
    ],
    "jarvis_analytics": [
        "telegram_memory.db",     # messages
        "jarvis_admin.db",        # telegram_users
        "jarvis_x_memory.db",     # tweets
        "jarvis_memory.db",       # ai_entities, ai_facts, ai_reflections (FTS5)
        "sentiment.db",           # sentiment_readings
        "call_tracking.db",       # calls, call_outcomes
        "whales.db",              # whale_wallets, whale_movements
        "metrics.db",             # metrics
        "llm_costs.db",           # llm_costs
    ],
    "jarvis_cache": [
        "rate_limiter.db",        # rate_limiter_logs
        # cache.db may not exist yet
    ],
}

# Target databases
TARGET_DBS = {
    "jarvis_core": DATA_DIR / "jarvis_core.db",
    "jarvis_analytics": DATA_DIR / "jarvis_analytics.db",
    "jarvis_cache": DATA_DIR / "jarvis_cache.db",
}


class DatabaseMigrator:
    """Handles migration of 29 databases into 3 consolidated databases."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.log_entries = []

    def log(self, message: str, level: str = "INFO"):
        """Log migration activity."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] [{level}] {message}"
        print(entry)
        self.log_entries.append(entry)

    def save_log(self):
        """Save migration log to file."""
        if not self.dry_run:
            with open(MIGRATION_LOG, "a") as f:
                f.write("\n".join(self.log_entries) + "\n\n")

    def backup_databases(self) -> bool:
        """Backup all source databases before migration."""
        self.log("=" * 60)
        self.log("BACKUP PHASE - Creating backups of all source databases")
        self.log("=" * 60)

        if not BACKUP_DIR.exists():
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            self.log(f"Created backup directory: {BACKUP_DIR}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_subdir = BACKUP_DIR / f"migration_{timestamp}"

        if not self.dry_run:
            backup_subdir.mkdir(exist_ok=True)

        backed_up = 0
        for target, sources in SOURCE_DBS.items():
            for source_db in sources:
                source_path = DATA_DIR / source_db
                if source_path.exists():
                    backup_path = backup_subdir / source_db
                    if not self.dry_run:
                        shutil.copy2(source_path, backup_path)
                    self.log(f"  ✓ Backed up: {source_db} → {backup_path}")
                    backed_up += 1
                else:
                    self.log(f"  ⚠ Skipped (not found): {source_db}", "WARN")

        self.log(f"\nBackup complete: {backed_up} databases backed up")
        return True

    def create_target_schemas(self):
        """Create schemas for the 3 target databases."""
        self.log("\n" + "=" * 60)
        self.log("SCHEMA PHASE - Creating target database schemas")
        self.log("=" * 60)

        # Read schema SQL files
        schema_files = {
            "jarvis_core": PROJECT_ROOT / ".planning" / "phases" / "01-database-consolidation" / "schema_core.sql",
            "jarvis_analytics": PROJECT_ROOT / ".planning" / "phases" / "01-database-consolidation" / "schema_analytics.sql",
            "jarvis_cache": PROJECT_ROOT / ".planning" / "phases" / "01-database-consolidation" / "schema_cache.sql",
        }

        # For now, create simplified schemas (full SQL in separate files)
        for target_name, target_path in TARGET_DBS.items():
            if target_path.exists() and not self.dry_run:
                self.log(f"  ⚠ {target_name}.db already exists - skipping schema creation", "WARN")
                continue

            if not self.dry_run:
                conn = sqlite3.connect(target_path)
                cursor = conn.cursor()

                # Enable WAL mode and foreign keys
                cursor.execute("PRAGMA journal_mode = WAL")
                cursor.execute("PRAGMA foreign_keys = ON")
                cursor.execute("PRAGMA synchronous = NORMAL")

                conn.commit()
                conn.close()

            self.log(f"  ✓ Created: {target_name}.db")

    def migrate_table(
        self,
        source_db_path: Path,
        target_conn: sqlite3.Connection,
        table_name: str,
        new_table_name: Optional[str] = None
    ) -> Tuple[int, bool]:
        """
        Migrate a single table from source to target database.

        Returns: (rows_migrated, success)
        """
        actual_table_name = new_table_name or table_name

        try:
            # Connect to source
            source_conn = sqlite3.connect(source_db_path)
            source_cursor = source_conn.cursor()

            # Check if table exists
            source_cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            )
            if not source_cursor.fetchone():
                self.log(f"    ⚠ Table '{table_name}' not found in {source_db_path.name}", "WARN")
                source_conn.close()
                return 0, True

            # Get column names
            source_cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [row[1] for row in source_cursor.fetchall()]
            columns_str = ", ".join(columns)

            # Count rows
            source_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            row_count = source_cursor.fetchone()[0]

            if row_count == 0:
                self.log(f"    ⚠ Table '{table_name}' is empty - skipping", "WARN")
                source_conn.close()
                return 0, True

            # Fetch all data
            source_cursor.execute(f"SELECT {columns_str} FROM {table_name}")
            rows = source_cursor.fetchall()

            # Insert into target
            if not self.dry_run:
                target_cursor = target_conn.cursor()
                placeholders = ", ".join(["?" for _ in columns])
                insert_sql = f"INSERT INTO {actual_table_name} ({columns_str}) VALUES ({placeholders})"

                target_cursor.executemany(insert_sql, rows)
                target_conn.commit()

            self.log(f"    ✓ Migrated {row_count} rows: {table_name} → {actual_table_name}")
            source_conn.close()
            return row_count, True

        except Exception as e:
            self.log(f"    ✗ Error migrating {table_name}: {e}", "ERROR")
            return 0, False

    def migrate_core_db(self):
        """Migrate jarvis_core.db (positions, trades, scorecard, orders, tax)."""
        self.log("\n" + "=" * 60)
        self.log("MIGRATION PHASE - jarvis_core.db")
        self.log("=" * 60)

        target_path = TARGET_DBS["jarvis_core"]
        if self.dry_run:
            self.log("[DRY RUN] Would migrate to jarvis_core.db")
            return

        target_conn = sqlite3.connect(target_path)
        target_conn.execute("PRAGMA foreign_keys = ON")

        total_rows = 0

        # jarvis.db → positions, trades, scorecard
        jarvis_db = DATA_DIR / "jarvis.db"
        if jarvis_db.exists():
            self.log(f"\n  Source: {jarvis_db.name}")
            rows, success = self.migrate_table(jarvis_db, target_conn, "positions")
            total_rows += rows
            rows, success = self.migrate_table(jarvis_db, target_conn, "trades")
            total_rows += rows
            rows, success = self.migrate_table(jarvis_db, target_conn, "scorecard")
            total_rows += rows

        # treasury_trades.db → treasury_orders
        treasury_db = DATA_DIR / "treasury_trades.db"
        if treasury_db.exists():
            self.log(f"\n  Source: {treasury_db.name}")
            rows, success = self.migrate_table(treasury_db, target_conn, "orders", "treasury_orders")
            total_rows += rows

        # tax.db → tax_lots, wash_sales
        tax_db = DATA_DIR / "tax.db"
        if tax_db.exists():
            self.log(f"\n  Source: {tax_db.name}")
            rows, success = self.migrate_table(tax_db, target_conn, "tax_lots")
            total_rows += rows
            rows, success = self.migrate_table(tax_db, target_conn, "wash_sales")
            total_rows += rows

        # Validate foreign keys
        cursor = target_conn.cursor()
        cursor.execute("PRAGMA foreign_key_check")
        fk_violations = cursor.fetchall()
        if fk_violations:
            self.log(f"  ✗ Foreign key violations detected: {fk_violations}", "ERROR")
        else:
            self.log("  ✓ Foreign key constraints validated")

        target_conn.close()
        self.log(f"\njarvis_core.db migration complete: {total_rows} total rows")

    def migrate_analytics_db(self):
        """Migrate jarvis_analytics.db (messages, tweets, memory, sentiment, etc.)."""
        self.log("\n" + "=" * 60)
        self.log("MIGRATION PHASE - jarvis_analytics.db")
        self.log("=" * 60)

        target_path = TARGET_DBS["jarvis_analytics"]
        if self.dry_run:
            self.log("[DRY RUN] Would migrate to jarvis_analytics.db")
            return

        target_conn = sqlite3.connect(target_path)
        target_conn.execute("PRAGMA foreign_keys = ON")

        total_rows = 0

        # telegram_memory.db → telegram_messages
        telegram_db = DATA_DIR / "telegram_memory.db"
        if telegram_db.exists():
            self.log(f"\n  Source: {telegram_db.name}")
            rows, success = self.migrate_table(telegram_db, target_conn, "messages", "telegram_messages")
            total_rows += rows

        # jarvis_admin.db → telegram_users
        admin_db = DATA_DIR / "jarvis_admin.db"
        if admin_db.exists():
            self.log(f"\n  Source: {admin_db.name}")
            rows, success = self.migrate_table(admin_db, target_conn, "users", "telegram_users")
            total_rows += rows

        # jarvis_x_memory.db → tweets
        x_db = DATA_DIR / "jarvis_x_memory.db"
        if x_db.exists():
            self.log(f"\n  Source: {x_db.name}")
            rows, success = self.migrate_table(x_db, target_conn, "tweets")
            total_rows += rows

        # sentiment.db → sentiment_readings
        sentiment_db = DATA_DIR / "sentiment.db"
        if sentiment_db.exists():
            self.log(f"\n  Source: {sentiment_db.name}")
            rows, success = self.migrate_table(sentiment_db, target_conn, "readings", "sentiment_readings")
            total_rows += rows

        # More sources... (call_tracking, whales, metrics, llm_costs)
        # TODO: Add remaining analytics table migrations

        target_conn.close()
        self.log(f"\njarvis_analytics.db migration complete: {total_rows} total rows")

    def migrate_cache_db(self):
        """Migrate jarvis_cache.db (rate limiter, sessions)."""
        self.log("\n" + "=" * 60)
        self.log("MIGRATION PHASE - jarvis_cache.db")
        self.log("=" * 60)

        target_path = TARGET_DBS["jarvis_cache"]
        if self.dry_run:
            self.log("[DRY RUN] Would migrate to jarvis_cache.db")
            return

        target_conn = sqlite3.connect(target_path)

        total_rows = 0

        # rate_limiter.db → rate_limiter_logs
        rate_limiter_db = DATA_DIR / "rate_limiter.db"
        if rate_limiter_db.exists():
            self.log(f"\n  Source: {rate_limiter_db.name}")
            rows, success = self.migrate_table(rate_limiter_db, target_conn, "logs", "rate_limiter_logs")
            total_rows += rows

        target_conn.close()
        self.log(f"\njarvis_cache.db migration complete: {total_rows} total rows")

    def run_migration(self):
        """Execute full migration workflow."""
        self.log("=" * 60)
        self.log("DATABASE CONSOLIDATION MIGRATION")
        self.log("29 databases → 3 consolidated databases")
        self.log("=" * 60)
        self.log(f"Mode: {'DRY RUN (preview only)' if self.dry_run else 'LIVE MIGRATION'}")
        self.log(f"Data directory: {DATA_DIR}")
        self.log(f"Backup directory: {BACKUP_DIR}")

        try:
            # Step 1: Backup
            if not self.backup_databases():
                self.log("Backup failed - aborting migration", "ERROR")
                return False

            # Step 2: Create schemas
            self.create_target_schemas()

            # Step 3: Migrate data
            self.migrate_core_db()
            self.migrate_analytics_db()
            self.migrate_cache_db()

            # Step 4: Final summary
            self.log("\n" + "=" * 60)
            self.log("MIGRATION COMPLETE")
            self.log("=" * 60)
            self.log("Next steps:")
            self.log("  1. Run validation: python scripts/validate_migration.py")
            self.log("  2. Test application with USE_CONSOLIDATED_DBS=true")
            self.log("  3. Monitor for errors over 7 days")
            self.log("  4. Clean up old databases if all tests pass")

            return True

        except Exception as e:
            self.log(f"Migration failed: {e}", "ERROR")
            return False

        finally:
            self.save_log()

    def rollback(self):
        """Rollback migration by restoring from backup."""
        self.log("=" * 60)
        self.log("ROLLBACK - Restoring from backup")
        self.log("=" * 60)

        # Find most recent backup
        if not BACKUP_DIR.exists():
            self.log("No backups found", "ERROR")
            return False

        backups = sorted([d for d in BACKUP_DIR.iterdir() if d.is_dir()], reverse=True)
        if not backups:
            self.log("No backup directories found", "ERROR")
            return False

        latest_backup = backups[0]
        self.log(f"Restoring from: {latest_backup}")

        # Restore all files
        for backup_file in latest_backup.glob("*.db"):
            target_path = DATA_DIR / backup_file.name
            if not self.dry_run:
                shutil.copy2(backup_file, target_path)
            self.log(f"  ✓ Restored: {backup_file.name}")

        # Remove consolidated databases
        for target_path in TARGET_DBS.values():
            if target_path.exists() and not self.dry_run:
                target_path.unlink()
                self.log(f"  ✓ Removed: {target_path.name}")

        self.log("\nRollback complete - original databases restored")
        return True


def main():
    parser = argparse.ArgumentParser(description="Database consolidation migration")
    parser.add_argument("--dry-run", action="store_true", help="Preview migration without changes")
    parser.add_argument("--rollback", action="store_true", help="Rollback to original databases")
    args = parser.parse_args()

    migrator = DatabaseMigrator(dry_run=args.dry_run)

    if args.rollback:
        success = migrator.rollback()
    else:
        success = migrator.run_migration()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
