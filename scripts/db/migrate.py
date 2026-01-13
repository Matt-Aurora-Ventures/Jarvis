#!/usr/bin/env python3
"""
JARVIS Database Migration Runner

Simple file-based migrations for SQLite/PostgreSQL:
- Sequential migration files (001_initial.sql, 002_add_users.sql)
- Tracks applied migrations
- Up/down migrations
- Dry run mode

Usage:
    python scripts/db/migrate.py up          # Apply all pending migrations
    python scripts/db/migrate.py down        # Rollback last migration
    python scripts/db/migrate.py status      # Show migration status
    python scripts/db/migrate.py create name # Create new migration

Migration file format:
    -- migrate:up
    CREATE TABLE users (...);

    -- migrate:down
    DROP TABLE users;
"""

import argparse
import hashlib
import logging
import os
import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Configuration
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "jarvis.db"


@dataclass
class Migration:
    """A database migration."""
    version: str
    name: str
    path: Path
    up_sql: str
    down_sql: str
    checksum: str

    @classmethod
    def from_file(cls, path: Path) -> "Migration":
        """Parse migration from file."""
        content = path.read_text(encoding="utf-8")

        # Extract version and name from filename (e.g., 001_initial.sql)
        match = re.match(r"(\d+)_(.+)\.sql", path.name)
        if not match:
            raise ValueError(f"Invalid migration filename: {path.name}")

        version = match.group(1)
        name = match.group(2)

        # Parse up/down sections
        up_sql = ""
        down_sql = ""
        current_section = None

        for line in content.split("\n"):
            if "-- migrate:up" in line.lower():
                current_section = "up"
                continue
            elif "-- migrate:down" in line.lower():
                current_section = "down"
                continue

            if current_section == "up":
                up_sql += line + "\n"
            elif current_section == "down":
                down_sql += line + "\n"

        if not up_sql.strip():
            raise ValueError(f"Migration {path.name} has no 'up' SQL")

        checksum = hashlib.md5(content.encode()).hexdigest()

        return cls(
            version=version,
            name=name,
            path=path,
            up_sql=up_sql.strip(),
            down_sql=down_sql.strip(),
            checksum=checksum,
        )


class MigrationRunner:
    """Database migration runner."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        """Get database connection."""
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._ensure_migrations_table()
        return self._conn

    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def _ensure_migrations_table(self):
        """Create migrations tracking table if needed."""
        self.connect().execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                checksum TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
        """)
        self.connect().commit()

    def get_applied_migrations(self) -> List[dict]:
        """Get list of applied migrations."""
        cursor = self.connect().execute(
            "SELECT version, name, checksum, applied_at FROM schema_migrations ORDER BY version"
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_pending_migrations(self) -> List[Migration]:
        """Get list of pending migrations."""
        applied = {m["version"] for m in self.get_applied_migrations()}
        all_migrations = self.discover_migrations()
        return [m for m in all_migrations if m.version not in applied]

    def discover_migrations(self) -> List[Migration]:
        """Discover all migration files."""
        if not MIGRATIONS_DIR.exists():
            return []

        migrations = []
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            try:
                migrations.append(Migration.from_file(path))
            except Exception as e:
                logger.warning(f"Skipping invalid migration {path.name}: {e}")

        return migrations

    def apply_migration(self, migration: Migration, dry_run: bool = False) -> bool:
        """Apply a single migration."""
        logger.info(f"Applying migration: {migration.version}_{migration.name}")

        if dry_run:
            logger.info(f"[DRY RUN] Would execute:\n{migration.up_sql[:500]}...")
            return True

        try:
            conn = self.connect()
            conn.executescript(migration.up_sql)

            conn.execute(
                """INSERT INTO schema_migrations (version, name, checksum, applied_at)
                   VALUES (?, ?, ?, ?)""",
                (
                    migration.version,
                    migration.name,
                    migration.checksum,
                    datetime.now(timezone.utc).isoformat(),
                )
            )
            conn.commit()
            logger.info(f"Applied: {migration.version}_{migration.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to apply migration: {e}")
            conn.rollback()
            return False

    def rollback_migration(self, migration: Migration, dry_run: bool = False) -> bool:
        """Rollback a single migration."""
        if not migration.down_sql:
            logger.error(f"Migration {migration.version} has no down SQL")
            return False

        logger.info(f"Rolling back migration: {migration.version}_{migration.name}")

        if dry_run:
            logger.info(f"[DRY RUN] Would execute:\n{migration.down_sql[:500]}...")
            return True

        try:
            conn = self.connect()
            conn.executescript(migration.down_sql)

            conn.execute(
                "DELETE FROM schema_migrations WHERE version = ?",
                (migration.version,)
            )
            conn.commit()
            logger.info(f"Rolled back: {migration.version}_{migration.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to rollback migration: {e}")
            conn.rollback()
            return False

    def migrate_up(self, steps: int = 0, dry_run: bool = False) -> int:
        """Apply pending migrations."""
        pending = self.get_pending_migrations()

        if not pending:
            logger.info("No pending migrations")
            return 0

        if steps > 0:
            pending = pending[:steps]

        applied = 0
        for migration in pending:
            if self.apply_migration(migration, dry_run):
                applied += 1
            else:
                break

        logger.info(f"Applied {applied} migration(s)")
        return applied

    def migrate_down(self, steps: int = 1, dry_run: bool = False) -> int:
        """Rollback applied migrations."""
        applied = self.get_applied_migrations()

        if not applied:
            logger.info("No migrations to rollback")
            return 0

        # Get migrations to rollback (most recent first)
        to_rollback = list(reversed(applied[-steps:]))

        rolled_back = 0
        for migration_info in to_rollback:
            # Find the migration file
            migration = None
            for m in self.discover_migrations():
                if m.version == migration_info["version"]:
                    migration = m
                    break

            if not migration:
                logger.error(f"Migration file not found: {migration_info['version']}")
                break

            if self.rollback_migration(migration, dry_run):
                rolled_back += 1
            else:
                break

        logger.info(f"Rolled back {rolled_back} migration(s)")
        return rolled_back

    def status(self) -> None:
        """Print migration status."""
        applied = self.get_applied_migrations()
        pending = self.get_pending_migrations()

        print("\n=== Migration Status ===\n")
        print(f"Database: {self.db_path}")
        print(f"Migrations directory: {MIGRATIONS_DIR}")
        print()

        if applied:
            print("Applied migrations:")
            for m in applied:
                print(f"  [x] {m['version']}_{m['name']} (applied: {m['applied_at'][:19]})")
        else:
            print("No applied migrations")

        print()

        if pending:
            print("Pending migrations:")
            for m in pending:
                print(f"  [ ] {m.version}_{m.name}")
        else:
            print("No pending migrations")

        print()


def create_migration(name: str) -> Path:
    """Create a new migration file."""
    MIGRATIONS_DIR.mkdir(parents=True, exist_ok=True)

    # Find next version number
    existing = list(MIGRATIONS_DIR.glob("*.sql"))
    if existing:
        versions = [int(re.match(r"(\d+)", p.name).group(1)) for p in existing]
        next_version = max(versions) + 1
    else:
        next_version = 1

    # Clean name
    clean_name = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")

    filename = f"{next_version:03d}_{clean_name}.sql"
    path = MIGRATIONS_DIR / filename

    template = f"""-- Migration: {name}
-- Created: {datetime.now().isoformat()}

-- migrate:up
-- Add your UP migration SQL here


-- migrate:down
-- Add your DOWN migration SQL here (for rollback)

"""

    path.write_text(template, encoding="utf-8")
    logger.info(f"Created migration: {path}")
    return path


def main():
    parser = argparse.ArgumentParser(
        description="JARVIS Database Migration Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python migrate.py up              Apply all pending migrations
    python migrate.py up --steps 1    Apply only the next migration
    python migrate.py down            Rollback the last migration
    python migrate.py down --steps 2  Rollback the last 2 migrations
    python migrate.py status          Show migration status
    python migrate.py create "Add users table"
        """
    )

    parser.add_argument(
        "command",
        choices=["up", "down", "status", "create"],
        help="Migration command"
    )
    parser.add_argument(
        "name",
        nargs="?",
        help="Migration name (for create command)"
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=0,
        help="Number of migrations to apply/rollback (0 = all)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Database path (default: {DEFAULT_DB_PATH})"
    )

    args = parser.parse_args()

    if args.command == "create":
        if not args.name:
            parser.error("Migration name required for create command")
        create_migration(args.name)
        return

    runner = MigrationRunner(args.db)

    try:
        if args.command == "up":
            runner.migrate_up(args.steps, args.dry_run)
        elif args.command == "down":
            steps = args.steps or 1
            runner.migrate_down(steps, args.dry_run)
        elif args.command == "status":
            runner.status()
    finally:
        runner.close()


if __name__ == "__main__":
    main()
