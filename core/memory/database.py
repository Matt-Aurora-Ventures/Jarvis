"""SQLite database manager with WAL mode and connection pooling."""
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Generator

from .config import get_config, MemoryConfig
from .schema import get_all_schema_sql, get_migration_sql, SCHEMA_VERSION


class DatabaseManager:
    """Thread-safe SQLite database manager with WAL mode."""

    def __init__(self, config: Optional[MemoryConfig] = None):
        """
        Initialize database manager.

        Args:
            config: Optional config override. Uses get_config() if not provided.
        """
        if config is None:
            config = get_config()

        self.config = config
        self.db_path = config.db_path
        self._local = threading.local()
        self._initialized = False
        self._init_lock = threading.Lock()

    def _get_connection(self) -> sqlite3.Connection:
        """
        Get thread-local connection.

        Creates new connection if needed for this thread.
        Enables WAL mode and foreign keys on first connection.

        Returns:
            Thread-local SQLite connection.
        """
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            # Ensure parent directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            # Create connection with optimizations
            conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                isolation_level=None  # Autocommit mode for WAL
            )
            conn.row_factory = sqlite3.Row  # Access columns by name

            # Enable WAL mode (Write-Ahead Logging for concurrency)
            if self.config.enable_wal:
                conn.execute("PRAGMA journal_mode=WAL")

            # Enable foreign key constraints
            conn.execute("PRAGMA foreign_keys=ON")

            # Performance optimizations
            conn.execute("PRAGMA synchronous=NORMAL")  # Faster than FULL, safe with WAL
            conn.execute("PRAGMA cache_size=-64000")    # 64MB cache
            conn.execute("PRAGMA temp_store=MEMORY")    # Use RAM for temp tables

            self._local.connection = conn

            # Initialize schema if needed
            if not self._initialized:
                self._initialize_schema(conn)

        return self._local.connection

    def _initialize_schema(self, conn: sqlite3.Connection) -> None:
        """
        Initialize database schema.

        Creates all tables, indexes, and FTS5 virtual tables.
        Safe to call multiple times (uses IF NOT EXISTS).

        Args:
            conn: Database connection.
        """
        with self._init_lock:
            if self._initialized:
                return

            # Check current schema version
            try:
                cursor = conn.execute("SELECT version FROM schema_info ORDER BY version DESC LIMIT 1")
                row = cursor.fetchone()
                current_version = row[0] if row else 0
            except sqlite3.OperationalError:
                # Table doesn't exist yet
                current_version = 0

            # Apply schema if needed
            if current_version < SCHEMA_VERSION:
                if current_version == 0:
                    # Fresh database - apply full schema
                    schema_sql = get_all_schema_sql()
                    conn.executescript(schema_sql)
                else:
                    # Existing database - apply migrations
                    migration_sql = get_migration_sql(current_version)
                    if migration_sql:
                        conn.executescript(migration_sql)
                        # Update schema version
                        conn.execute(f"INSERT OR REPLACE INTO schema_info (version) VALUES ({SCHEMA_VERSION})")
                conn.commit()

            self._initialized = True

    @contextmanager
    def get_cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        """
        Get database cursor with automatic transaction management.

        Usage:
            with db.get_cursor() as cursor:
                cursor.execute("SELECT * FROM facts")
                results = cursor.fetchall()

        Yields:
            Database cursor with transaction context.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """
        Execute SQL statement.

        Args:
            sql: SQL statement.
            params: Query parameters.

        Returns:
            Cursor with results.
        """
        conn = self._get_connection()
        return conn.execute(sql, params)

    def executemany(self, sql: str, params_list: list) -> sqlite3.Cursor:
        """
        Execute SQL statement with multiple parameter sets.

        Args:
            sql: SQL statement.
            params_list: List of parameter tuples.

        Returns:
            Cursor with results.
        """
        conn = self._get_connection()
        return conn.executemany(sql, params_list)

    def commit(self) -> None:
        """Commit current transaction."""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.commit()

    def rollback(self) -> None:
        """Rollback current transaction."""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.rollback()

    def close(self) -> None:
        """Close thread-local connection."""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None

    def vacuum(self) -> None:
        """
        Vacuum database to reclaim space and optimize.

        Should be run periodically (e.g., during daily reflect).
        """
        conn = self._get_connection()
        conn.execute("VACUUM")


# Global database instance
_db: Optional[DatabaseManager] = None
_db_lock = threading.Lock()


def get_db(config: Optional[MemoryConfig] = None) -> DatabaseManager:
    """
    Get or create global DatabaseManager instance.

    Args:
        config: Optional config override.

    Returns:
        Global DatabaseManager singleton.
    """
    global _db
    if _db is None:
        with _db_lock:
            if _db is None:
                _db = DatabaseManager(config)
    return _db
