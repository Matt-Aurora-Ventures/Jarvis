"""
Database Migration Validation Script

Phase 1, Task 4: Validate database migration completed successfully

This script validates that the 29→3 database consolidation:
1. Migrated all expected rows
2. Preserved foreign key relationships
3. No data corruption occurred
4. Performance is acceptable

Usage:
    python scripts/validate_migration.py
"""

import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Add parent directory to path for core imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.security_validation import sanitize_sql_identifier

# Paths
DATA_DIR = Path.home() / ".lifeos" / "data"
BACKUP_DIR = DATA_DIR / "backup"

# Target databases
TARGET_DBS = {
    "jarvis_core": DATA_DIR / "jarvis_core.db",
    "jarvis_analytics": DATA_DIR / "jarvis_analytics.db",
    "jarvis_cache": DATA_DIR / "jarvis_cache.db",
}


class MigrationValidator:
    """Validates database migration integrity."""

    def __init__(self):
        self.errors = []
        self.warnings = []

    def log_error(self, message: str):
        """Log a validation error."""
        print(f"  ✗ ERROR: {message}")
        self.errors.append(message)

    def log_warning(self, message: str):
        """Log a validation warning."""
        print(f"  ⚠ WARNING: {message}")
        self.warnings.append(message)

    def log_success(self, message: str):
        """Log a validation success."""
        print(f"  ✓ {message}")

    def validate_database_exists(self, db_path: Path, name: str) -> bool:
        """Check if database file exists."""
        if not db_path.exists():
            self.log_error(f"{name} not found at {db_path}")
            return False
        self.log_success(f"{name} exists ({db_path.stat().st_size / 1024:.1f} KB)")
        return True

    def validate_foreign_keys(self, conn: sqlite3.Connection, db_name: str) -> bool:
        """Validate foreign key constraints."""
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_key_check")
        violations = cursor.fetchall()

        if violations:
            self.log_error(f"{db_name}: Foreign key violations detected")
            for violation in violations:
                print(f"    {violation}")
            return False

        self.log_success(f"{db_name}: Foreign key constraints valid")
        return True

    def validate_table_counts(self, conn: sqlite3.Connection, db_name: str, expected_tables: List[str]) -> bool:
        """Validate expected tables exist and have data."""
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        actual_tables = [row[0] for row in cursor.fetchall()]

        # Remove system tables
        actual_tables = [t for t in actual_tables if not t.startswith("sqlite_")]

        missing_tables = set(expected_tables) - set(actual_tables)
        extra_tables = set(actual_tables) - set(expected_tables)

        if missing_tables:
            self.log_warning(f"{db_name}: Missing tables: {missing_tables}")

        if extra_tables:
            self.log_warning(f"{db_name}: Unexpected tables: {extra_tables}")

        # Count rows in each table
        print(f"\n  Table row counts ({db_name}):")
        for table in sorted(actual_tables):
            safe_table = sanitize_sql_identifier(table)
            cursor.execute(f"SELECT COUNT(*) FROM {safe_table}")
            count = cursor.fetchone()[0]
            status = "OK" if count > 0 else "EMPTY"
            print(f"    {table:30} {count:6} rows [{status}]")

        return len(missing_tables) == 0

    def validate_core_db(self) -> bool:
        """Validate jarvis_core.db."""
        print("\n" + "=" * 60)
        print("Validating jarvis_core.db")
        print("=" * 60)

        db_path = TARGET_DBS["jarvis_core"]
        if not self.validate_database_exists(db_path, "jarvis_core.db"):
            return False

        expected_tables = [
            "positions",
            "trades",
            "treasury_orders",
            "scorecard",
            "tax_lots",
            "wash_sales",
            "config",
        ]

        conn = sqlite3.connect(db_path)

        # Check tables
        if not self.validate_table_counts(conn, "jarvis_core.db", expected_tables):
            self.log_error("Missing expected tables")

        # Check foreign keys
        valid_fk = self.validate_foreign_keys(conn, "jarvis_core.db")

        # Specific validations
        cursor = conn.cursor()

        # 1. Check position-trade relationships
        print("\n  Relationship validations:")
        cursor.execute("SELECT COUNT(*) FROM trades WHERE position_id IS NOT NULL AND position_id NOT IN (SELECT id FROM positions)")
        orphaned_trades = cursor.fetchone()[0]
        if orphaned_trades > 0:
            self.log_error(f"Found {orphaned_trades} trades with invalid position_id")
        else:
            self.log_success("All trades reference valid positions")

        # 2. Check config defaults
        cursor.execute("SELECT COUNT(*) FROM config")
        config_count = cursor.fetchone()[0]
        if config_count < 5:
            self.log_warning(f"Only {config_count} config entries (expected 7+)")
        else:
            self.log_success(f"Config table has {config_count} entries")

        conn.close()
        return valid_fk and orphaned_trades == 0

    def validate_analytics_db(self) -> bool:
        """Validate jarvis_analytics.db."""
        print("\n" + "=" * 60)
        print("Validating jarvis_analytics.db")
        print("=" * 60)

        db_path = TARGET_DBS["jarvis_analytics"]
        if not self.validate_database_exists(db_path, "jarvis_analytics.db"):
            return False

        expected_tables = [
            "telegram_messages",
            "telegram_users",
            "tweets",
            "ai_entities",
            "ai_facts",
            "ai_reflections",
            "sentiment_readings",
            "calls",
            "call_outcomes",
            "whale_wallets",
            "whale_movements",
            "metrics",
            "llm_costs",
        ]

        conn = sqlite3.connect(db_path)

        # Check tables
        if not self.validate_table_counts(conn, "jarvis_analytics.db", expected_tables):
            self.log_warning("Some expected tables missing")

        # Check foreign keys
        valid_fk = self.validate_foreign_keys(conn, "jarvis_analytics.db")

        # FTS5 validation
        print("\n  FTS5 virtual table validation:")
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM ai_reflections")
            fts_count = cursor.fetchone()[0]
            self.log_success(f"FTS5 ai_reflections has {fts_count} entries")
        except Exception as e:
            self.log_error(f"FTS5 table error: {e}")

        conn.close()
        return valid_fk

    def validate_cache_db(self) -> bool:
        """Validate jarvis_cache.db."""
        print("\n" + "=" * 60)
        print("Validating jarvis_cache.db")
        print("=" * 60)

        db_path = TARGET_DBS["jarvis_cache"]
        if not self.validate_database_exists(db_path, "jarvis_cache.db"):
            return False

        expected_tables = [
            "cache_entries",
            "rate_limiter_logs",
            "sessions",
        ]

        conn = sqlite3.connect(db_path)

        # Check tables
        if not self.validate_table_counts(conn, "jarvis_cache.db", expected_tables):
            self.log_warning("Some expected tables missing")

        # Cache tables can be empty - not an error
        self.log_success("Cache database validated (empty tables OK)")

        conn.close()
        return True

    def compare_row_counts(self):
        """Compare row counts between source and target databases."""
        print("\n" + "=" * 60)
        print("Row Count Comparison (Source vs Target)")
        print("=" * 60)

        # Find most recent backup
        if not BACKUP_DIR.exists():
            self.log_warning("No backup directory found - skipping comparison")
            return

        backups = sorted([d for d in BACKUP_DIR.iterdir() if d.is_dir()], reverse=True)
        if not backups:
            self.log_warning("No backups found - skipping comparison")
            return

        latest_backup = backups[0]
        print(f"  Comparing against backup: {latest_backup.name}")

        # Compare jarvis.db → jarvis_core.db
        source_jarvis = latest_backup / "jarvis.db"
        if source_jarvis.exists():
            source_conn = sqlite3.connect(source_jarvis)
            target_conn = sqlite3.connect(TARGET_DBS["jarvis_core"])

            for table in ["positions", "trades", "scorecard"]:
                safe_table = sanitize_sql_identifier(table)
                source_count = source_conn.execute(f"SELECT COUNT(*) FROM {safe_table}").fetchone()[0]
                try:
                    target_count = target_conn.execute(f"SELECT COUNT(*) FROM {safe_table}").fetchone()[0]
                    match = "✓" if source_count == target_count else "✗ MISMATCH"
                    print(f"    {table:20} {source_count:6} → {target_count:6} [{match}]")
                    if source_count != target_count:
                        self.log_error(f"{table}: Row count mismatch ({source_count} != {target_count})")
                except Exception as e:
                    self.log_warning(f"{table}: Could not compare ({e})")

            source_conn.close()
            target_conn.close()

    def performance_check(self):
        """Basic performance check - query latency."""
        print("\n" + "=" * 60)
        print("Performance Check")
        print("=" * 60)

        import time

        for db_name, db_path in TARGET_DBS.items():
            if not db_path.exists():
                continue

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Check WAL mode
            cursor.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]
            if mode == "wal":
                self.log_success(f"{db_name}: WAL mode enabled")
            else:
                self.log_warning(f"{db_name}: Not in WAL mode (current: {mode})")

            # Simple query timing
            start = time.time()
            cursor.execute("SELECT COUNT(*) FROM sqlite_master")
            elapsed = (time.time() - start) * 1000

            if elapsed < 50:
                self.log_success(f"{db_name}: Query latency OK ({elapsed:.1f}ms)")
            else:
                self.log_warning(f"{db_name}: Query latency high ({elapsed:.1f}ms)")

            conn.close()

    def run_validation(self) -> bool:
        """Run full validation suite."""
        print("=" * 60)
        print("DATABASE MIGRATION VALIDATION")
        print("=" * 60)

        # Validate each database
        core_ok = self.validate_core_db()
        analytics_ok = self.validate_analytics_db()
        cache_ok = self.validate_cache_db()

        # Compare counts
        self.compare_row_counts()

        # Performance check
        self.performance_check()

        # Summary
        print("\n" + "=" * 60)
        print("VALIDATION SUMMARY")
        print("=" * 60)

        if self.errors:
            print(f"\n✗ FAILED - {len(self.errors)} error(s) detected:")
            for error in self.errors:
                print(f"  - {error}")
        else:
            print("\n✓ PASSED - No errors detected")

        if self.warnings:
            print(f"\n⚠ {len(self.warnings)} warning(s):")
            for warning in self.warnings:
                print(f"  - {warning}")

        print("\nNext steps:")
        if self.errors:
            print("  1. Review errors and fix migration script")
            print("  2. Rollback: python scripts/migrate_databases.py --rollback")
            print("  3. Fix issues and retry migration")
        else:
            print("  1. Test application with consolidated databases")
            print("  2. Monitor for errors over 7 days")
            print("  3. Update code to use new database paths")
            print("  4. Clean up old databases after confirmation")

        return len(self.errors) == 0


def main():
    validator = MigrationValidator()
    success = validator.run_validation()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
