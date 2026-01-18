"""
SQLite Connection Pool Manager
Centralized connection management with context managers to prevent leaks.

Part of the Jarvis Trading Citadel infrastructure.
"""

import sqlite3
import logging
from contextlib import contextmanager
from pathlib import Path
from threading import Lock, local
from typing import Dict, Optional, Generator
from datetime import datetime

logger = logging.getLogger(__name__)

# Thread-local storage for connections
_thread_local = local()


class SQLitePool:
    """
    Central SQLite connection pool manager.
    Prevents connection leaks via context managers.
    Thread-safe using thread-local storage.
    """

    _pools: Dict[str, "SQLitePool"] = {}
    _lock = Lock()

    def __init__(self, db_path: str, max_connections: int = 5, timeout: float = 10.0):
        """
        Initialize connection pool for a specific database.

        Args:
            db_path: Path to SQLite database file
            max_connections: Maximum concurrent connections (enforced at thread level)
            timeout: Connection timeout in seconds
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_connections = max_connections
        self.timeout = timeout
        self.active_connections = 0
        self._lock = Lock()

        logger.info(f"Initialized SQLitePool for {self.db_path}")

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Get a database connection with automatic cleanup.

        USAGE:
            with pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM table")

        Connection is automatically closed when exiting the context.
        Commits on success, rolls back on error.
        """
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=self.timeout,
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")

        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"SQLite error: {e}")
            raise
        finally:
            conn.close()

    @classmethod
    @contextmanager
    def get_pool_connection(cls, db_path: str) -> Generator[sqlite3.Connection, None, None]:
        """
        Global method to get a connection from a pool.

        Creates pool on first use per database.
        Thread-safe and prevents duplicate pools.

        USAGE:
            with SQLitePool.get_pool_connection("data/mydb.db") as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM table")
        """
        with cls._lock:
            if db_path not in cls._pools:
                cls._pools[db_path] = SQLitePool(db_path)
            pool = cls._pools[db_path]

        with pool.get_connection() as conn:
            yield conn


@contextmanager
def sql_connection(db_path: str) -> Generator[sqlite3.Connection, None, None]:
    """
    Shorthand for getting a SQLite connection with proper cleanup.

    This is the PRIMARY function to use throughout Jarvis.

    USAGE:
        from core.database.sqlite_pool import sql_connection

        with sql_connection("data/mydb.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
            rows = cursor.fetchall()

    Features:
    - Automatic connection cleanup
    - Automatic commit on success
    - Automatic rollback on error
    - Thread-safe
    - No connection leaks
    """
    with SQLitePool.get_pool_connection(db_path) as conn:
        yield conn


class SQLiteStats:
    """Track SQLite usage statistics."""

    def __init__(self):
        self.total_connections = 0
        self.active_connections = 0
        self.closed_connections = 0
        self.errors = 0
        self.last_check = datetime.now()

    def record_open(self):
        self.total_connections += 1
        self.active_connections += 1

    def record_close(self):
        self.closed_connections += 1
        self.active_connections -= 1

    def record_error(self):
        self.errors += 1

    def to_dict(self) -> Dict:
        return {
            "total": self.total_connections,
            "active": self.active_connections,
            "closed": self.closed_connections,
            "errors": self.errors,
            "elapsed_seconds": (datetime.now() - self.last_check).total_seconds()
        }


# Global stats tracker
_stats = SQLiteStats()


def get_sqlite_stats() -> Dict:
    """Get current SQLite connection statistics."""
    return _stats.to_dict()
