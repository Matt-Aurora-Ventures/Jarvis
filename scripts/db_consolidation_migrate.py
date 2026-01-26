#!/usr/bin/env python3
"""
Database Consolidation Migration Script

Migrates 35 fragmented databases → 3 consolidated databases:
- jarvis_core.db (operational data)
- jarvis_analytics.db (analytics & metrics)
- jarvis_cache.db (transient cache)

Phase: 1.1 - Database Consolidation
Task: 3 - Migration Implementation
Created: 2026-01-25

Usage:
    python scripts/db_consolidation_migrate.py [--dry-run] [--backup-only]
"""

import sqlite3
import shutil
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
BOTS_DIR = PROJECT_ROOT / "bots"
BACKUP_DIR = DATA_DIR / "backups" / datetime.now().strftime("%Y%m%d_%H%M%S")
SCHEMA_FILE = PROJECT_ROOT / ".planning/phases/01-database-consolidation/unified_schema.sql"

# Target databases
TARGET_CORE = DATA_DIR / "jarvis_core.db"
TARGET_ANALYTICS = DATA_DIR / "jarvis_analytics.db"
TARGET_CACHE = DATA_DIR / "jarvis_cache.db"


class DatabaseMigrator:
    """Handles database consolidation migration"""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.backup_dir = BACKUP_DIR
        self.errors = []
        self.migration_log = []
        self.stats = {
            'tables_migrated': 0,
            'rows_migrated': 0,
            'databases_created': 0
        }

    def log(self, message: str, level: str = "INFO"):
        """Log message"""
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] {level}: {message}"
        self.migration_log.append(log_entry)

        if level == "INFO":
            logger.info(message)
        elif level == "WARNING":
            logger.warning(message)
        elif level == "ERROR":
            logger.error(message)
            self.errors.append(message)

    def backup_databases(self) -> bool:
        """Backup all existing databases"""
        self.log("Creating backups...")
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Critical databases to backup
        databases = [
            DATA_DIR / "jarvis.db",
            DATA_DIR / "telegram_memory.db",
            DATA_DIR / "llm_costs.db",
            DATA_DIR / "metrics.db",
            DATA_DIR / "rate_limiter.db",
        ]

        backed_up = 0
        for db_path in databases:
            if db_path.exists():
                backup_path = self.backup_dir / db_path.name
                if not self.dry_run:
                    shutil.copy2(db_path, backup_path)
                self.log(f"Backed up: {db_path.name}")
                backed_up += 1

        self.log(f"Backed up {backed_up} databases to {self.backup_dir}")
        return True

    def create_target_databases(self) -> bool:
        """Create consolidated databases with schema"""
        self.log("Creating target databases...")

        if not SCHEMA_FILE.exists():
            self.log(f"Schema file not found: {SCHEMA_FILE}", "ERROR")
            return False

        if self.dry_run:
            self.log("[DRY RUN] Would create 3 target databases")
            return True

        # Read and apply schema
        with open(SCHEMA_FILE, 'r') as f:
            schema = f.read()

        # Create each database
        for db_path in [TARGET_CORE, TARGET_ANALYTICS, TARGET_CACHE]:
            try:
                conn = sqlite3.connect(db_path)
                conn.executescript(schema)
                conn.commit()
                conn.close()
                self.log(f"Created: {db_path.name}")
                self.stats['databases_created'] += 1
            except Exception as e:
                self.log(f"Failed to create {db_path.name}: {e}", "ERROR")
                return False

        return True

    def migrate_table_data(
        self,
        source_path: Path,
        source_table: str,
        target_db: Path,
        target_table: str,
        transform_fn=None
    ) -> int:
        """Migrate data from source table to target table"""
        if not source_path.exists():
            self.log(f"Source not found: {source_path}", "WARNING")
            return 0

        try:
            source_conn = sqlite3.connect(source_path)
            source_conn.row_factory = sqlite3.Row

            # Check if source table exists
            cursor = source_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (source_table,)
            )
            if not cursor.fetchone():
                self.log(f"Table not found: {source_table} in {source_path.name}", "WARNING")
                source_conn.close()
                return 0

            # Get data
            rows = source_conn.execute(f"SELECT * FROM {source_table}").fetchall()
            source_conn.close()

            if not rows:
                self.log(f"No data in {source_table}")
                return 0

            # Transform if needed
            if transform_fn:
                rows = [transform_fn(dict(row)) for row in rows]
            else:
                rows = [dict(row) for row in rows]

            if self.dry_run:
                self.log(f"[DRY RUN] Would migrate {len(rows)} rows: {source_table} → {target_table}")
                return len(rows)

            # Insert into target
            target_conn = sqlite3.connect(target_db)

            for row in rows:
                columns = ', '.join(row.keys())
                placeholders = ', '.join(['?' for _ in row])
                target_conn.execute(
                    f"INSERT INTO {target_table} ({columns}) VALUES ({placeholders})",
                    list(row.values())
                )

            target_conn.commit()
            target_conn.close()

            self.log(f"Migrated {len(rows)} rows: {source_table} → {target_table}")
            self.stats['rows_migrated'] += len(rows)
            self.stats['tables_migrated'] += 1
            return len(rows)

        except Exception as e:
            self.log(f"Migration error {source_table} → {target_table}: {e}", "ERROR")
            return 0

    def run_migration(self) -> bool:
        """Execute migration"""
        self.log("=" * 80)
        self.log("DATABASE CONSOLIDATION MIGRATION")
        self.log("35 databases → 3 consolidated databases")
        if self.dry_run:
            self.log("[DRY RUN MODE - No changes will be made]")
        self.log("=" * 80)

        # Step 1: Backup
        if not self.backup_databases():
            return False

        # Step 2: Create targets
        if not self.create_target_databases():
            return False

        # Step 3: Migrate core data
        self.log("\nMigrating core operational data...")

        # jarvis.db → jarvis_core.db
        core_tables = ['positions', 'trades', 'treasury_orders', 'users', 'items']
        for table in core_tables:
            self.migrate_table_data(
                DATA_DIR / "jarvis.db",
                table,
                TARGET_CORE,
                table
            )

        # telegram_memory.db → jarvis_core.db
        telegram_tables = {
            'messages': 'telegram_messages',
            'memories': 'telegram_memories',
            'instructions': 'telegram_instructions',
            'learnings': 'telegram_learnings'
        }
        for src, tgt in telegram_tables.items():
            self.migrate_table_data(
                DATA_DIR / "telegram_memory.db",
                src,
                TARGET_CORE,
                tgt
            )

        # Step 4: Migrate analytics
        self.log("\nMigrating analytics data...")

        # llm_costs.db → jarvis_analytics.db
        analytics_tables = ['llm_usage', 'llm_daily_stats', 'budget_alerts']
        for table in analytics_tables:
            self.migrate_table_data(
                DATA_DIR / "llm_costs.db",
                table,
                TARGET_ANALYTICS,
                table
            )

        # metrics.db → jarvis_analytics.db
        metrics_tables = ['metrics_1m', 'metrics_1h', 'alert_history']
        for table in metrics_tables:
            self.migrate_table_data(
                DATA_DIR / "metrics.db",
                table,
                TARGET_ANALYTICS,
                table
            )

        # Step 5: Migrate cache
        self.log("\nMigrating cache data...")

        # rate_limiter.db → jarvis_cache.db
        cache_tables = ['rate_configs', 'request_log', 'limit_stats']
        for table in cache_tables:
            self.migrate_table_data(
                DATA_DIR / "rate_limiter.db",
                table,
                TARGET_CACHE,
                table
            )

        # Report
        self.log("\n" + "=" * 80)
        self.log("MIGRATION SUMMARY")
        self.log(f"Databases created: {self.stats['databases_created']}")
        self.log(f"Tables migrated: {self.stats['tables_migrated']}")
        self.log(f"Rows migrated: {self.stats['rows_migrated']}")
        self.log(f"Errors: {len(self.errors)}")
        self.log("=" * 80)

        # Save report
        report_path = self.backup_dir / "migration_report.txt"
        with open(report_path, 'w') as f:
            for entry in self.migration_log:
                f.write(entry + "\n")
        self.log(f"Report saved: {report_path}")

        return len(self.errors) == 0


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description="Database consolidation migration")
    parser.add_argument('--dry-run', action='store_true', help="Simulate migration without changes")
    parser.add_argument('--backup-only', action='store_true', help="Only create backups")
    args = parser.parse_args()

    migrator = DatabaseMigrator(dry_run=args.dry_run)

    if args.backup_only:
        success = migrator.backup_databases()
    else:
        success = migrator.run_migration()

    if success:
        print("\n✅ Migration complete!")
        print(f"📁 Backup: {migrator.backup_dir}")
    else:
        print(f"\n❌ Migration failed with {len(migrator.errors)} errors")
        print(f"📁 Backup preserved: {migrator.backup_dir}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
