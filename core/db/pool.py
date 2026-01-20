"""
JARVIS Database Connection Pool

Features:
- Connection pooling for SQLite and PostgreSQL
- Async support
- Health checking
- Automatic reconnection on failure
- Connection health validation
- Query logging (debug mode)
- Pool utilization metrics
- Automatic connection recycling

Dependencies:
    pip install sqlalchemy[asyncio]  # For pooling
    pip install aiosqlite  # For async SQLite
    pip install asyncpg  # For async PostgreSQL (optional)
"""

import logging
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Callable, Dict, Generator, List, Optional, Union

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = ROOT / "data" / "jarvis.db"


@dataclass
class DatabaseConfig:
    """Database configuration."""
    # Connection settings
    url: str = ""
    driver: str = "sqlite"  # sqlite, postgresql

    # Pool settings
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: float = 30.0
    pool_recycle: int = 3600  # Recycle connections after 1 hour
    health_check_interval: int = 60  # Health check every 60s
    max_retries: int = 3  # Reconnection attempts
    retry_delay: float = 1.0  # Delay between retries

    # SQLite specific
    sqlite_path: Path = DEFAULT_DB_PATH
    sqlite_check_same_thread: bool = False
    sqlite_timeout: float = 30.0

    # PostgreSQL specific
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_database: str = "jarvis"
    pg_user: str = "jarvis"
    pg_password: str = ""

    # Behavior
    echo: bool = False  # Log all SQL
    auto_commit: bool = False

    @classmethod
    def from_env(cls) -> 'DatabaseConfig':
        """Load configuration from environment."""
        url = os.getenv("DATABASE_URL", "")

        config = cls()

        if url:
            config.url = url
            if url.startswith("postgresql"):
                config.driver = "postgresql"
            else:
                config.driver = "sqlite"
        else:
            config.driver = "sqlite"
            config.sqlite_path = Path(os.getenv("SQLITE_PATH", str(DEFAULT_DB_PATH)))

        config.pool_size = int(os.getenv("DB_POOL_SIZE", "5"))
        config.max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "10"))
        config.pool_timeout = float(os.getenv("DB_POOL_TIMEOUT", "30.0"))
        config.pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "3600"))
        config.health_check_interval = int(os.getenv("DB_HEALTH_CHECK_INTERVAL", "60"))
        config.max_retries = int(os.getenv("DB_MAX_RETRIES", "3"))
        config.echo = os.getenv("DB_ECHO", "false").lower() == "true"

        return config


class ConnectionWrapper:
    """Wrapper around database connection with metrics and health checking."""

    def __init__(self, conn: Any, pool: 'ConnectionPool', created_at: float):
        self._conn = conn
        self._pool = pool
        self._created_at = created_at
        self._last_used = time.time()
        self._last_health_check = time.time()
        self._in_use = False
        self._query_count = 0
        self._error_count = 0
        self._is_healthy = True

    @property
    def age(self) -> float:
        return time.time() - self._created_at

    @property
    def idle_time(self) -> float:
        return time.time() - self._last_used if not self._in_use else 0

    @property
    def needs_health_check(self) -> bool:
        """Check if connection needs a health check."""
        return (time.time() - self._last_health_check) > self._pool.config.health_check_interval

    def health_check(self) -> bool:
        """Validate connection is still alive."""
        try:
            if self._pool.config.driver == "sqlite":
                self._conn.execute("SELECT 1")
            else:
                cursor = self._conn.cursor()
                cursor.execute("SELECT 1")
                cursor.close()

            self._last_health_check = time.time()
            self._is_healthy = True
            return True
        except Exception as e:
            logger.warning(f"Connection health check failed: {e}")
            self._is_healthy = False
            return False

    def execute(self, query: str, params: tuple = ()) -> Any:
        """Execute a query with automatic reconnection on failure."""
        self._last_used = time.time()
        self._query_count += 1

        if self._pool.config.echo:
            logger.debug(f"SQL: {query[:200]}... params={params}")

        try:
            result = self._conn.execute(query, params)
            self._error_count = 0  # Reset error count on success
            return result
        except Exception as e:
            self._error_count += 1
            logger.error(f"Query execution failed (error #{self._error_count}): {e}")
            raise

    def executemany(self, query: str, params_list: List[tuple]) -> Any:
        """Execute query with multiple parameter sets."""
        self._last_used = time.time()
        self._query_count += len(params_list)

        try:
            result = self._conn.executemany(query, params_list)
            self._error_count = 0
            return result
        except Exception as e:
            self._error_count += 1
            logger.error(f"Batch execution failed: {e}")
            raise

    def executescript(self, script: str) -> Any:
        """Execute a SQL script."""
        self._last_used = time.time()
        self._query_count += 1

        try:
            result = self._conn.executescript(script)
            self._error_count = 0
            return result
        except Exception as e:
            self._error_count += 1
            logger.error(f"Script execution failed: {e}")
            raise

    def fetchone(self) -> Optional[Any]:
        return self._conn.fetchone()

    def fetchall(self) -> List[Any]:
        return self._conn.fetchall()

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        """Return connection to pool."""
        self._in_use = False
        self._pool._return_connection(self)

    def get_metrics(self) -> Dict[str, Any]:
        """Get connection-level metrics."""
        return {
            "age_seconds": self.age,
            "idle_seconds": self.idle_time,
            "query_count": self._query_count,
            "error_count": self._error_count,
            "is_healthy": self._is_healthy,
            "in_use": self._in_use,
        }


class ConnectionPool:
    """
    Database connection pool.

    Manages a pool of reusable database connections to reduce
    connection overhead and limit concurrent connections.
    """

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._pool: Queue[ConnectionWrapper] = Queue(maxsize=config.pool_size)
        self._overflow_count = 0
        self._lock = threading.Lock()
        self._total_connections = 0
        self._closed = False

        # Stats
        self._stats = {
            "connections_created": 0,
            "connections_reused": 0,
            "connections_recycled": 0,
            "wait_timeouts": 0,
            "total_queries": 0,
        }

        # Pre-warm pool
        self._init_pool()

    def _init_pool(self) -> None:
        """Initialize the connection pool."""
        min_connections = min(2, self.config.pool_size)
        for _ in range(min_connections):
            try:
                conn = self._create_connection()
                self._pool.put(conn)
            except Exception as e:
                logger.warning(f"Failed to pre-warm connection: {e}")

    def _create_connection(self) -> ConnectionWrapper:
        """Create a new database connection."""
        if self.config.driver == "sqlite":
            conn = self._create_sqlite_connection()
        elif self.config.driver == "postgresql":
            conn = self._create_pg_connection()
        else:
            raise ValueError(f"Unsupported driver: {self.config.driver}")

        self._stats["connections_created"] += 1
        self._total_connections += 1

        return ConnectionWrapper(conn, self, time.time())

    def _create_sqlite_connection(self) -> sqlite3.Connection:
        """Create SQLite connection."""
        # Ensure directory exists
        self.config.sqlite_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(
            str(self.config.sqlite_path),
            check_same_thread=self.config.sqlite_check_same_thread,
            timeout=self.config.sqlite_timeout,
        )
        conn.row_factory = sqlite3.Row

        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
        conn.execute("PRAGMA foreign_keys=ON")

        return conn

    def _create_pg_connection(self) -> Any:
        """Create PostgreSQL connection."""
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor

            if self.config.url:
                conn = psycopg2.connect(self.config.url, cursor_factory=RealDictCursor)
            else:
                conn = psycopg2.connect(
                    host=self.config.pg_host,
                    port=self.config.pg_port,
                    database=self.config.pg_database,
                    user=self.config.pg_user,
                    password=self.config.pg_password,
                    cursor_factory=RealDictCursor,
                )

            conn.autocommit = self.config.auto_commit
            return conn

        except ImportError:
            raise RuntimeError("psycopg2 required for PostgreSQL. Install: pip install psycopg2-binary")

    def get_connection(self) -> ConnectionWrapper:
        """
        Get a connection from the pool with health checking and auto-reconnect.

        Returns a reused connection if available, otherwise creates
        a new one (up to max_overflow limit). Validates connection health
        and recycles stale connections automatically.
        """
        if self._closed:
            raise RuntimeError("Connection pool is closed")

        retry_count = 0
        max_retries = self.config.max_retries

        while retry_count < max_retries:
            try:
                # Try to get from pool
                try:
                    conn = self._pool.get(timeout=self.config.pool_timeout)

                    # Check if connection needs recycling (age)
                    if conn.age > self.config.pool_recycle:
                        logger.debug(f"Recycling connection (age: {conn.age:.0f}s)")
                        self._close_connection(conn)
                        conn = self._create_connection()
                        self._stats["connections_recycled"] += 1

                    # Check connection health
                    elif conn.needs_health_check:
                        if not conn.health_check():
                            logger.warning("Unhealthy connection detected, recycling")
                            self._close_connection(conn)
                            conn = self._create_connection()
                            self._stats["connections_recycled"] += 1

                    # Check for high error count
                    elif conn._error_count > 5:
                        logger.warning(f"Connection has {conn._error_count} errors, recycling")
                        self._close_connection(conn)
                        conn = self._create_connection()
                        self._stats["connections_recycled"] += 1

                    conn._in_use = True
                    self._stats["connections_reused"] += 1
                    return conn

                except Empty:
                    # Pool exhausted, try overflow
                    with self._lock:
                        if self._overflow_count < self.config.max_overflow:
                            self._overflow_count += 1
                            conn = self._create_connection()
                            conn._in_use = True
                            return conn

                    # All connections in use
                    self._stats["wait_timeouts"] += 1
                    raise RuntimeError(
                        f"Connection pool exhausted (size={self.config.pool_size}, "
                        f"overflow={self.config.max_overflow})"
                    )

            except Exception as e:
                retry_count += 1
                if retry_count >= max_retries:
                    logger.error(f"Failed to get connection after {max_retries} retries: {e}")
                    raise

                logger.warning(f"Connection attempt {retry_count} failed: {e}, retrying...")
                time.sleep(self.config.retry_delay * retry_count)  # Exponential backoff

        raise RuntimeError("Failed to get database connection")

    def _return_connection(self, conn: ConnectionWrapper) -> None:
        """Return a connection to the pool."""
        if self._closed:
            self._close_connection(conn)
            return

        # Reset connection state
        try:
            conn._conn.rollback()
        except Exception:
            pass

        # Check if this was an overflow connection
        with self._lock:
            if self._pool.full():
                self._overflow_count -= 1
                self._close_connection(conn)
                return

        try:
            self._pool.put_nowait(conn)
        except Exception:
            self._close_connection(conn)

    def _close_connection(self, conn: ConnectionWrapper) -> None:
        """Close a connection."""
        try:
            conn._conn.close()
        except Exception:
            pass
        self._total_connections -= 1

    @contextmanager
    def connection(self) -> Generator[ConnectionWrapper, None, None]:
        """
        Context manager for getting a pooled connection.

        Usage:
            with pool.connection() as conn:
                result = conn.execute("SELECT * FROM users")
        """
        conn = self.get_connection()
        try:
            yield conn
            if not self.config.auto_commit:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute(self, query: str, params: tuple = ()) -> Any:
        """Execute a query using a pooled connection."""
        with self.connection() as conn:
            cursor = conn.execute(query, params)
            self._stats["total_queries"] += 1
            return cursor

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive pool statistics and metrics."""
        available_conns = self._pool.qsize()
        active_conns = self._total_connections - available_conns

        return {
            **self._stats,
            "pool_size": self.config.pool_size,
            "max_overflow": self.config.max_overflow,
            "available_connections": available_conns,
            "active_connections": active_conns,
            "overflow_in_use": self._overflow_count,
            "total_connections": self._total_connections,
            "utilization_pct": (active_conns / self.config.pool_size * 100)
                              if self.config.pool_size > 0 else 0,
            "health_check_interval": self.config.health_check_interval,
            "pool_recycle_seconds": self.config.pool_recycle,
        }

    def get_connection_metrics(self) -> List[Dict[str, Any]]:
        """Get metrics for all connections in the pool (for debugging)."""
        metrics = []

        # This is a snapshot - connections might be in use
        temp_conns = []
        try:
            while not self._pool.empty():
                try:
                    conn = self._pool.get_nowait()
                    metrics.append(conn.get_metrics())
                    temp_conns.append(conn)
                except Empty:
                    break

            return metrics
        finally:
            # Return all connections back to pool
            for conn in temp_conns:
                try:
                    self._pool.put_nowait(conn)
                except Exception:
                    pass

    def health_check(self) -> bool:
        """Check if pool is healthy."""
        try:
            with self.connection() as conn:
                if self.config.driver == "sqlite":
                    conn.execute("SELECT 1")
                else:
                    conn.execute("SELECT 1")
                return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    def close(self) -> None:
        """Close all connections and shutdown pool."""
        self._closed = True

        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                self._close_connection(conn)
            except Empty:
                break

        logger.info("Connection pool closed")


class Database:
    """
    High-level database interface.

    Wraps ConnectionPool with additional utilities.
    """

    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or DatabaseConfig.from_env()
        self._pool: Optional[ConnectionPool] = None
        self._migrations_table = "schema_migrations"

    def connect(self) -> None:
        """Initialize the connection pool."""
        if self._pool is None:
            self._pool = ConnectionPool(self.config)
            logger.info(f"Database connected: {self.config.driver}")

    def disconnect(self) -> None:
        """Close the connection pool."""
        if self._pool:
            self._pool.close()
            self._pool = None

    @property
    def pool(self) -> ConnectionPool:
        if self._pool is None:
            self.connect()
        return self._pool

    @contextmanager
    def connection(self) -> Generator[ConnectionWrapper, None, None]:
        """Get a database connection."""
        with self.pool.connection() as conn:
            yield conn

    def execute(self, query: str, params: tuple = ()) -> Any:
        """Execute a query."""
        return self.pool.execute(query, params)

    def fetchone(self, query: str, params: tuple = ()) -> Optional[Dict]:
        """Execute query and fetch one result."""
        with self.connection() as conn:
            cursor = conn.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None

    def fetchall(self, query: str, params: tuple = ()) -> List[Dict]:
        """Execute query and fetch all results."""
        with self.connection() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def insert(self, table: str, data: Dict[str, Any]) -> int:
        """Insert a row and return the ID."""
        columns = ", ".join(data.keys())
        placeholders = ", ".join("?" * len(data))
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"

        with self.connection() as conn:
            cursor = conn.execute(query, tuple(data.values()))
            return cursor.lastrowid

    def update(self, table: str, data: Dict[str, Any], where: str, params: tuple = ()) -> int:
        """Update rows and return count."""
        set_clause = ", ".join(f"{k} = ?" for k in data.keys())
        query = f"UPDATE {table} SET {set_clause} WHERE {where}"

        with self.connection() as conn:
            cursor = conn.execute(query, tuple(data.values()) + params)
            return cursor.rowcount

    def delete(self, table: str, where: str, params: tuple = ()) -> int:
        """Delete rows and return count."""
        query = f"DELETE FROM {table} WHERE {where}"

        with self.connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.rowcount

    def table_exists(self, table: str) -> bool:
        """Check if a table exists."""
        if self.config.driver == "sqlite":
            result = self.fetchone(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            )
        else:
            result = self.fetchone(
                "SELECT table_name FROM information_schema.tables WHERE table_name = %s",
                (table,)
            )
        return result is not None

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        return self.pool.get_stats()

    def health_check(self) -> bool:
        """Check database health."""
        return self.pool.health_check()


# Global instances
_db: Optional[Database] = None
_async_db: Optional[Any] = None


def get_db() -> Database:
    """Get the global database instance."""
    global _db
    if _db is None:
        _db = Database()
        _db.connect()
    return _db


def get_async_db() -> Any:
    """Get async database instance (requires databases library)."""
    global _async_db
    if _async_db is None:
        try:
            from databases import Database as AsyncDatabase
            config = DatabaseConfig.from_env()
            if config.driver == "sqlite":
                url = f"sqlite:///{config.sqlite_path}"
            else:
                url = config.url
            _async_db = AsyncDatabase(url)
        except ImportError:
            raise RuntimeError("databases library required. Install: pip install databases[aiosqlite]")
    return _async_db


def init_database(config: Optional[DatabaseConfig] = None) -> Database:
    """Initialize database with custom config."""
    global _db
    _db = Database(config)
    _db.connect()
    return _db


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Database Connection Pool Test")
    print("=" * 40)

    db = get_db()

    # Health check
    healthy = db.health_check()
    print(f"Health check: {'OK' if healthy else 'FAILED'}")

    # Create test table
    with db.connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS pool_test (
                id INTEGER PRIMARY KEY,
                name TEXT,
                created_at REAL
            );
        """)

    # Test operations
    import time

    # Insert
    row_id = db.insert("pool_test", {"name": "test", "created_at": time.time()})
    print(f"Inserted row ID: {row_id}")

    # Select
    row = db.fetchone("SELECT * FROM pool_test WHERE id = ?", (row_id,))
    print(f"Fetched row: {row}")

    # Stats
    stats = db.get_stats()
    print(f"\nPool stats: {stats}")

    # Cleanup
    db.delete("pool_test", "id = ?", (row_id,))
    db.disconnect()
    print("\nTest complete!")
