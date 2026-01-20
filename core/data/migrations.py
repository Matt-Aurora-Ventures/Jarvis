"""
Database Migration System for JARVIS.

Provides:
- Version tracking for database schema
- Forward migrations (upgrade)
- Backward migrations (rollback)
- Automatic migration on startup
- Migration history tracking
- Error handling and logging

Usage:
    runner = MigrationRunner(db_path="data/jarvis.db")
    runner.register(Migration(
        version=1,
        name="create_users",
        up_sql="CREATE TABLE users (...);",
        down_sql="DROP TABLE users;",
    ))
    await runner.initialize()
    await runner.migrate()
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, List, Optional, Union
import aiosqlite

logger = logging.getLogger(__name__)


class MigrationError(Exception):
    """Raised when a migration fails."""

    def __init__(self, message: str, version: int = 0, name: str = ""):
        self.message = message
        self.version = version
        self.name = name
        super().__init__(f"Migration {name} (v{version}) failed: {message}")


@dataclass
class Migration:
    """
    Represents a single database migration.

    Attributes:
        version: Unique version number (must be positive integer)
        name: Human-readable name for the migration
        up_sql: SQL string or async callable for forward migration
        down_sql: SQL string or async callable for backward migration (rollback)
        description: Optional description of what this migration does
    """

    version: int
    name: str
    up_sql: Union[str, Callable]
    down_sql: Union[str, Callable]
    description: str = ""

    def __lt__(self, other: Migration) -> bool:
        """Migrations are ordered by version."""
        return self.version < other.version

    def __gt__(self, other: Migration) -> bool:
        """Migrations are ordered by version."""
        return self.version > other.version

    def __eq__(self, other: object) -> bool:
        """Migrations are equal if they have the same version."""
        if not isinstance(other, Migration):
            return NotImplemented
        return self.version == other.version

    def __hash__(self) -> int:
        """Hash by version."""
        return hash(self.version)


@dataclass
class MigrationHistory:
    """
    Record of an applied migration.

    Attributes:
        version: The migration version that was applied
        name: The migration name
        applied_at: When the migration was applied
        success: Whether the migration succeeded
        error_message: Error message if migration failed
        duration_ms: How long the migration took in milliseconds
    """

    version: int
    name: str
    applied_at: datetime
    success: bool
    error_message: Optional[str] = None
    duration_ms: Optional[float] = None


@dataclass
class MigrationResult:
    """
    Result of a migration operation.

    Attributes:
        success: Whether the migration succeeded
        version: The current version after migration
        applied_count: Number of migrations applied
        dry_run: Whether this was a dry run
        would_apply: Migrations that would be applied (dry run only)
        error: Error message if failed
    """

    success: bool
    version: int
    applied_count: int = 0
    dry_run: bool = False
    would_apply: List[Migration] = field(default_factory=list)
    error: Optional[str] = None


class MigrationRunner:
    """
    Manages database migrations with version tracking and history.

    Features:
    - Automatic schema version tracking
    - Forward and backward migrations
    - Migration history with success/failure tracking
    - Concurrent access protection via locking
    - Dry run mode for testing
    - Auto-migrate on startup option

    Example:
        runner = MigrationRunner(db_path="data/app.db")
        runner.register(Migration(
            version=1,
            name="initial_schema",
            up_sql="CREATE TABLE users (id INTEGER PRIMARY KEY);",
            down_sql="DROP TABLE users;",
        ))
        await runner.initialize()
        await runner.migrate()
    """

    # SQL for creating migration tracking tables
    SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS _migrations_version (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        version INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS _migrations_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        version INTEGER NOT NULL,
        name TEXT NOT NULL,
        direction TEXT NOT NULL,
        applied_at TEXT NOT NULL,
        success INTEGER NOT NULL,
        error_message TEXT,
        duration_ms REAL
    );

    INSERT OR IGNORE INTO _migrations_version (id, version, updated_at)
    VALUES (1, 0, datetime('now'));
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        auto_migrate: bool = False,
    ):
        """
        Initialize migration runner.

        Args:
            db_path: Path to SQLite database file. Defaults to in-memory.
            auto_migrate: If True, automatically migrate to latest on initialize().
        """
        self.db_path = db_path or ":memory:"
        self.auto_migrate = auto_migrate
        self._migrations: List[Migration] = []
        self._initialized = False
        self._lock = asyncio.Lock()

    def register(self, migration: Migration) -> None:
        """
        Register a migration with the runner.

        Migrations are automatically sorted by version.

        Args:
            migration: The migration to register

        Raises:
            ValueError: If a migration with the same version already exists
        """
        # Check for duplicate versions
        for existing in self._migrations:
            if existing.version == migration.version:
                raise ValueError(
                    f"Migration version {migration.version} already registered "
                    f"(existing: {existing.name}, new: {migration.name})"
                )

        self._migrations.append(migration)
        self._migrations.sort()
        logger.debug(
            f"Registered migration v{migration.version}: {migration.name}"
        )

    async def initialize(self) -> None:
        """
        Initialize the migration system.

        Creates the migration tracking tables if they don't exist.
        If auto_migrate is True, runs all pending migrations.
        """
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.executescript(self.SCHEMA_SQL)
                await db.commit()

            self._initialized = True
            logger.info(f"Migration system initialized for {self.db_path}")

        if self.auto_migrate:
            await self.migrate()

    async def get_current_version(self) -> int:
        """
        Get the current schema version.

        Returns:
            The current version number (0 if no migrations applied)
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT version FROM _migrations_version WHERE id = 1"
            )
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def get_pending_migrations(self) -> List[Migration]:
        """
        Get list of migrations that haven't been applied yet.

        Returns:
            List of pending migrations sorted by version
        """
        current = await self.get_current_version()
        return [m for m in self._migrations if m.version > current]

    async def get_history(
        self, include_failed: bool = False, limit: int = 100
    ) -> List[MigrationHistory]:
        """
        Get migration history.

        Args:
            include_failed: Include failed migration attempts
            limit: Maximum number of records to return

        Returns:
            List of MigrationHistory entries
        """
        async with aiosqlite.connect(self.db_path) as db:
            if include_failed:
                query = """
                    SELECT version, name, applied_at, success, error_message, duration_ms
                    FROM _migrations_history
                    WHERE direction = 'up'
                    ORDER BY applied_at DESC
                    LIMIT ?
                """
            else:
                query = """
                    SELECT version, name, applied_at, success, error_message, duration_ms
                    FROM _migrations_history
                    WHERE direction = 'up' AND success = 1
                    ORDER BY applied_at DESC
                    LIMIT ?
                """

            cursor = await db.execute(query, (limit,))
            rows = await cursor.fetchall()

            history = []
            for row in rows:
                history.append(
                    MigrationHistory(
                        version=row[0],
                        name=row[1],
                        applied_at=datetime.fromisoformat(row[2]),
                        success=bool(row[3]),
                        error_message=row[4],
                        duration_ms=row[5],
                    )
                )

            # Return in chronological order (oldest first)
            return list(reversed(history))

    async def migrate(
        self,
        target_version: Optional[int] = None,
        dry_run: bool = False,
    ) -> MigrationResult:
        """
        Run migrations up to the target version.

        Args:
            target_version: Version to migrate to. None = latest.
            dry_run: If True, don't actually apply migrations.

        Returns:
            MigrationResult with details about the operation

        Raises:
            MigrationError: If a migration fails
        """
        if target_version is None:
            target_version = max((m.version for m in self._migrations), default=0)

        current = await self.get_current_version()

        if current >= target_version:
            logger.info(
                f"Already at version {current}, target is {target_version}"
            )
            return MigrationResult(success=True, version=current)

        # Get migrations to apply
        to_apply = [
            m for m in self._migrations
            if current < m.version <= target_version
        ]

        if dry_run:
            return MigrationResult(
                success=True,
                version=current,
                dry_run=True,
                would_apply=to_apply,
            )

        async with self._lock:
            applied_count = 0

            for migration in to_apply:
                logger.info(
                    f"Applying migration v{migration.version}: {migration.name}"
                )
                start_time = datetime.utcnow()

                try:
                    await self._apply_migration(migration, direction="up")
                    duration_ms = (
                        datetime.utcnow() - start_time
                    ).total_seconds() * 1000

                    # Update version
                    async with aiosqlite.connect(self.db_path) as db:
                        await db.execute(
                            """
                            UPDATE _migrations_version
                            SET version = ?, updated_at = datetime('now')
                            WHERE id = 1
                            """,
                            (migration.version,),
                        )
                        await db.commit()

                    # Record success
                    await self._record_history(
                        migration, direction="up", success=True,
                        duration_ms=duration_ms
                    )

                    applied_count += 1
                    logger.info(
                        f"Migration v{migration.version} completed in {duration_ms:.2f}ms"
                    )

                except Exception as e:
                    duration_ms = (
                        datetime.utcnow() - start_time
                    ).total_seconds() * 1000

                    # Record failure
                    await self._record_history(
                        migration,
                        direction="up",
                        success=False,
                        error_message=str(e),
                        duration_ms=duration_ms,
                    )

                    logger.error(
                        f"Migration v{migration.version} ({migration.name}) failed: {e}"
                    )
                    raise MigrationError(
                        str(e),
                        version=migration.version,
                        name=migration.name,
                    ) from e

            new_version = await self.get_current_version()
            return MigrationResult(
                success=True,
                version=new_version,
                applied_count=applied_count,
            )

    async def rollback(
        self,
        target_version: int = 0,
        dry_run: bool = False,
    ) -> MigrationResult:
        """
        Rollback migrations to target version.

        Args:
            target_version: Version to rollback to (default 0 = all)
            dry_run: If True, don't actually apply rollbacks

        Returns:
            MigrationResult with details about the operation

        Raises:
            MigrationError: If a rollback fails
        """
        current = await self.get_current_version()

        if current <= target_version:
            logger.info(
                f"Already at version {current}, target is {target_version}"
            )
            return MigrationResult(success=True, version=current)

        # Get migrations to rollback (in reverse order)
        to_rollback = [
            m for m in reversed(self._migrations)
            if target_version < m.version <= current
        ]

        if dry_run:
            return MigrationResult(
                success=True,
                version=current,
                dry_run=True,
                would_apply=to_rollback,
            )

        async with self._lock:
            applied_count = 0

            for migration in to_rollback:
                logger.info(
                    f"Rolling back migration v{migration.version}: {migration.name}"
                )
                start_time = datetime.utcnow()

                try:
                    await self._apply_migration(migration, direction="down")
                    duration_ms = (
                        datetime.utcnow() - start_time
                    ).total_seconds() * 1000

                    # Update version
                    new_version = migration.version - 1
                    async with aiosqlite.connect(self.db_path) as db:
                        await db.execute(
                            """
                            UPDATE _migrations_version
                            SET version = ?, updated_at = datetime('now')
                            WHERE id = 1
                            """,
                            (new_version,),
                        )
                        await db.commit()

                    # Record rollback
                    await self._record_history(
                        migration, direction="down", success=True,
                        duration_ms=duration_ms
                    )

                    applied_count += 1
                    logger.info(
                        f"Rollback v{migration.version} completed in {duration_ms:.2f}ms"
                    )

                except Exception as e:
                    duration_ms = (
                        datetime.utcnow() - start_time
                    ).total_seconds() * 1000

                    # Record failure
                    await self._record_history(
                        migration,
                        direction="down",
                        success=False,
                        error_message=str(e),
                        duration_ms=duration_ms,
                    )

                    logger.error(
                        f"Rollback v{migration.version} ({migration.name}) failed: {e}"
                    )
                    raise MigrationError(
                        str(e),
                        version=migration.version,
                        name=migration.name,
                    ) from e

            new_version = await self.get_current_version()
            return MigrationResult(
                success=True,
                version=new_version,
                applied_count=applied_count,
            )

    async def _apply_migration(
        self, migration: Migration, direction: str
    ) -> None:
        """
        Apply a single migration (up or down).

        Args:
            migration: The migration to apply
            direction: "up" for forward, "down" for rollback
        """
        sql_or_func = migration.up_sql if direction == "up" else migration.down_sql

        async with aiosqlite.connect(self.db_path) as db:
            if callable(sql_or_func):
                # It's a callable - pass the connection
                await sql_or_func(db)
            else:
                # It's a SQL string
                await db.executescript(sql_or_func)
            await db.commit()

    async def _record_history(
        self,
        migration: Migration,
        direction: str,
        success: bool,
        error_message: Optional[str] = None,
        duration_ms: Optional[float] = None,
    ) -> None:
        """Record a migration attempt in history."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO _migrations_history
                    (version, name, direction, applied_at, success, error_message, duration_ms)
                VALUES (?, ?, ?, datetime('now'), ?, ?, ?)
                """,
                (
                    migration.version,
                    migration.name,
                    direction,
                    1 if success else 0,
                    error_message,
                    duration_ms,
                ),
            )
            await db.commit()


# Global singleton instance
_migration_runner: Optional[MigrationRunner] = None


def get_migration_runner(
    db_path: Optional[str] = None,
    auto_migrate: bool = False,
    reset: bool = False,
) -> MigrationRunner:
    """
    Get the global migration runner instance.

    Args:
        db_path: Path to database file (only used on first call or reset)
        auto_migrate: Whether to auto-migrate (only used on first call or reset)
        reset: Force creation of a new instance

    Returns:
        The global MigrationRunner instance
    """
    global _migration_runner

    if _migration_runner is None or reset:
        _migration_runner = MigrationRunner(
            db_path=db_path,
            auto_migrate=auto_migrate,
        )

    return _migration_runner


__all__ = [
    "Migration",
    "MigrationError",
    "MigrationHistory",
    "MigrationResult",
    "MigrationRunner",
    "get_migration_runner",
]
