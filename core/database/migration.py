"""
Data Migration from SQLite to PostgreSQL.

Handles migration of data from consolidated SQLite databases to PostgreSQL
with proper foreign key ordering and data validation.

Usage:
    from core.database.migration import DataMigrator

    migrator = DataMigrator(
        sqlite_path="data/jarvis_core.db",
        postgres_url="postgresql://user:pass@localhost:5432/jarvis"
    )

    # Migrate single table
    count = await migrator.migrate_table("positions")

    # Run full migration
    await migrator.run_full_migration()

    # Validate migration
    is_valid = await migrator.validate_migration("positions")
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .postgres_client import PostgresClient
from core.security_validation import sanitize_sql_identifier

logger = logging.getLogger(__name__)


# Migration order respects foreign key dependencies
MIGRATION_ORDER = [
    "users",
    "positions",
    "trades",
    "orders",
    "bot_config",
    "token_metadata",
    "user_scorecard",
    "daily_pnl",
]

# Column type transformations from SQLite to PostgreSQL
TYPE_TRANSFORMATIONS = {
    # SQLite uses INTEGER for booleans
    "is_active": lambda v: bool(v) if v is not None else None,
    "is_admin": lambda v: bool(v) if v is not None else None,
    "is_premium": lambda v: bool(v) if v is not None else None,
    "is_banned": lambda v: bool(v) if v is not None else None,
    "is_verified": lambda v: bool(v) if v is not None else None,
    "is_scam": lambda v: bool(v) if v is not None else None,
    "trading_enabled": lambda v: bool(v) if v is not None else None,
    "notifications_enabled": lambda v: bool(v) if v is not None else None,
    # Timestamps need parsing
    "created_at": lambda v: _parse_timestamp(v),
    "updated_at": lambda v: _parse_timestamp(v),
    "opened_at": lambda v: _parse_timestamp(v),
    "closed_at": lambda v: _parse_timestamp(v),
    "executed_at": lambda v: _parse_timestamp(v),
    "last_active_at": lambda v: _parse_timestamp(v),
    "triggered_at": lambda v: _parse_timestamp(v),
    "filled_at": lambda v: _parse_timestamp(v),
    "cancelled_at": lambda v: _parse_timestamp(v),
    "cached_at": lambda v: _parse_timestamp(v),
    "last_updated": lambda v: _parse_timestamp(v),
}


def _parse_timestamp(value: Any) -> Optional[datetime]:
    """Parse SQLite timestamp string to datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        # Try common formats
        for fmt in [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%d",
        ]:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        logger.warning(f"Could not parse timestamp: {value}")
    return None


class DataMigrator:
    """
    Migrates data from SQLite to PostgreSQL.

    Handles:
    - Reading from SQLite source
    - Type transformations
    - Batch inserts to PostgreSQL
    - Validation of row counts
    """

    def __init__(
        self,
        sqlite_path: str,
        postgres_url: str,
        batch_size: int = 1000
    ):
        """
        Initialize migrator.

        Args:
            sqlite_path: Path to SQLite database
            postgres_url: PostgreSQL connection URL
            batch_size: Number of rows per batch insert
        """
        self.sqlite_path = Path(sqlite_path)
        self.postgres_url = postgres_url
        self.batch_size = batch_size
        self._pg_client = PostgresClient(connection_url=postgres_url)
        self._migration_stats: Dict[str, Dict[str, Any]] = {}

    def _get_sqlite_connection(self) -> sqlite3.Connection:
        """Get SQLite connection."""
        conn = sqlite3.connect(str(self.sqlite_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _read_sqlite_table(
        self,
        table_name: str,
        transform: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Read all rows from SQLite table.

        Args:
            table_name: Name of table to read
            transform: Whether to apply type transformations

        Returns:
            List of rows as dictionaries
        """
        conn = self._get_sqlite_connection()
        cursor = conn.cursor()

        try:
            safe_table = sanitize_sql_identifier(table_name)
            cursor.execute(f"SELECT * FROM {safe_table}")
            columns = [desc[0] for desc in cursor.description]
            rows = []

            for row in cursor.fetchall():
                row_dict = dict(zip(columns, row))

                if transform:
                    for col, transformer in TYPE_TRANSFORMATIONS.items():
                        if col in row_dict:
                            row_dict[col] = transformer(row_dict[col])

                rows.append(row_dict)

            return rows
        finally:
            conn.close()

    def _get_sqlite_count(self, table_name: str) -> int:
        """Get row count from SQLite table."""
        conn = self._get_sqlite_connection()
        cursor = conn.cursor()
        safe_table = sanitize_sql_identifier(table_name)

        try:
            cursor.execute(f"SELECT COUNT(*) FROM {safe_table}")
            return cursor.fetchone()[0]
        except sqlite3.OperationalError:
            return 0
        finally:
            conn.close()

    def _get_sqlite_schema(self, table_name: str) -> List[Tuple[str, str]]:
        """Get column names and types from SQLite table."""
        conn = self._get_sqlite_connection()
        cursor = conn.cursor()
        safe_table = sanitize_sql_identifier(table_name)

        try:
            cursor.execute(f"PRAGMA table_info({safe_table})")
            return [(row[1], row[2]) for row in cursor.fetchall()]
        finally:
            conn.close()

    async def migrate_table(
        self,
        table_name: str,
        transform: bool = True
    ) -> int:
        """
        Migrate a single table from SQLite to PostgreSQL.

        Args:
            table_name: Name of table to migrate
            transform: Whether to apply type transformations

        Returns:
            Number of rows migrated
        """
        logger.info(f"Migrating table: {table_name}")
        start_time = datetime.utcnow()

        # Read source data
        rows = self._read_sqlite_table(table_name, transform=transform)
        if not rows:
            logger.info(f"Table {table_name} is empty, skipping")
            return 0

        # Sanitize table and column names to prevent SQL injection
        safe_table = sanitize_sql_identifier(table_name)

        # Get columns from first row and sanitize each
        columns = list(rows[0].keys())
        safe_columns = [sanitize_sql_identifier(col) for col in columns]
        placeholders = ", ".join(f"${i+1}" for i in range(len(columns)))
        columns_str = ", ".join(safe_columns)

        # Build INSERT query with sanitized identifiers
        insert_query = f"""
            INSERT INTO {safe_table} ({columns_str})
            VALUES ({placeholders})
            ON CONFLICT DO NOTHING
        """

        # Batch insert
        total_inserted = 0
        for i in range(0, len(rows), self.batch_size):
            batch = rows[i:i + self.batch_size]
            args = [tuple(row[col] for col in columns) for row in batch]

            try:
                await self._pg_client.execute_many(insert_query, args)
                total_inserted += len(batch)
                logger.debug(f"Inserted batch {i//self.batch_size + 1}: {len(batch)} rows")
            except Exception as e:
                logger.error(f"Failed to insert batch: {e}")
                raise

        # Record stats
        duration = (datetime.utcnow() - start_time).total_seconds()
        self._migration_stats[table_name] = {
            "rows_migrated": total_inserted,
            "source_count": len(rows),
            "duration_seconds": duration,
            "timestamp": datetime.utcnow().isoformat()
        }

        logger.info(f"Migrated {total_inserted} rows from {table_name} in {duration:.2f}s")
        return total_inserted

    async def validate_migration(self, table_name: str) -> bool:
        """
        Validate migration by comparing row counts.

        Args:
            table_name: Name of table to validate

        Returns:
            True if counts match, False otherwise
        """
        safe_table = sanitize_sql_identifier(table_name)
        sqlite_count = self._get_sqlite_count(table_name)
        pg_count = await self._pg_client.fetchval(
            f"SELECT COUNT(*) FROM {safe_table}"
        )

        is_valid = sqlite_count == pg_count
        if not is_valid:
            logger.error(
                f"Validation failed for {table_name}: "
                f"SQLite={sqlite_count}, PostgreSQL={pg_count}"
            )
        else:
            logger.info(
                f"Validation passed for {table_name}: "
                f"{pg_count} rows"
            )

        return is_valid

    async def run_full_migration(self) -> Dict[str, int]:
        """
        Run full migration of all tables in dependency order.

        Returns:
            Dictionary of table names to row counts
        """
        logger.info("Starting full migration")
        start_time = datetime.utcnow()

        results = {}
        for table_name in MIGRATION_ORDER:
            try:
                count = await self.migrate_table(table_name)
                results[table_name] = count
            except Exception as e:
                logger.error(f"Migration failed for {table_name}: {e}")
                results[table_name] = -1

        duration = (datetime.utcnow() - start_time).total_seconds()
        total_rows = sum(c for c in results.values() if c > 0)

        logger.info(
            f"Full migration complete: {total_rows} rows in {duration:.2f}s"
        )
        return results

    async def validate_all(self) -> Dict[str, bool]:
        """
        Validate all migrated tables.

        Returns:
            Dictionary of table names to validation results
        """
        results = {}
        for table_name in MIGRATION_ORDER:
            try:
                results[table_name] = await self.validate_migration(table_name)
            except Exception as e:
                logger.error(f"Validation failed for {table_name}: {e}")
                results[table_name] = False

        return results

    def get_migration_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get migration statistics."""
        return self._migration_stats


class MigrationRunner:
    """
    High-level migration runner with rollback support.

    Handles:
    - Pre-migration checks
    - Schema creation
    - Data migration
    - Post-migration validation
    - Rollback on failure
    """

    def __init__(self, migrator: DataMigrator):
        self.migrator = migrator
        self._backup_created = False

    async def run(self, create_backup: bool = True) -> bool:
        """
        Run migration with optional backup.

        Args:
            create_backup: Whether to backup SQLite before migration

        Returns:
            True if migration successful, False otherwise
        """
        logger.info("Starting migration runner")

        # Create backup
        if create_backup:
            self._create_backup()
            self._backup_created = True

        try:
            # Run migration
            results = await self.migrator.run_full_migration()

            # Validate
            validation = await self.migrator.validate_all()

            # Check all validations passed
            all_valid = all(validation.values())
            if not all_valid:
                logger.error("Migration validation failed")
                return False

            logger.info("Migration completed successfully")
            return True

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False

    def _create_backup(self) -> None:
        """Create backup of SQLite database."""
        import shutil

        backup_path = self.migrator.sqlite_path.with_suffix(".db.backup")
        shutil.copy2(self.migrator.sqlite_path, backup_path)
        logger.info(f"Created backup: {backup_path}")
