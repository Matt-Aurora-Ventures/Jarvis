"""Database connection pooling."""
import sqlite3
import threading
from queue import Queue, Empty
from typing import Optional
from contextlib import contextmanager
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ConnectionPool:
    """SQLite connection pool for thread-safe database access."""
    
    def __init__(self, database: str, max_connections: int = 10, timeout: float = 30.0):
        self.database = database
        self.max_connections = max_connections
        self.timeout = timeout
        self._pool: Queue = Queue(maxsize=max_connections)
        self._size = 0
        self._lock = threading.Lock()
        
        Path(database).parent.mkdir(parents=True, exist_ok=True)
    
    def _create_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database, check_same_thread=False, timeout=self.timeout)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-64000")
        return conn
    
    def get_connection(self) -> sqlite3.Connection:
        try:
            conn = self._pool.get_nowait()
            try:
                conn.execute("SELECT 1")
                return conn
            except sqlite3.Error:
                with self._lock:
                    self._size -= 1
        except Empty:
            pass
        
        with self._lock:
            if self._size < self.max_connections:
                self._size += 1
                return self._create_connection()
        
        try:
            return self._pool.get(timeout=self.timeout)
        except Empty:
            raise TimeoutError("Could not get database connection from pool")
    
    def return_connection(self, conn: sqlite3.Connection):
        try:
            self._pool.put_nowait(conn)
        except Exception:
            conn.close()
            with self._lock:
                self._size -= 1
    
    @contextmanager
    def connection(self):
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self.return_connection(conn)
    
    @contextmanager
    def cursor(self):
        with self.connection() as conn:
            cursor = conn.cursor()
            try:
                yield cursor
            finally:
                cursor.close()
    
    def execute(self, query: str, params: tuple = None):
        with self.cursor() as cursor:
            cursor.execute(query, params or ())
            return cursor.fetchall()
    
    def execute_many(self, query: str, params_list: list):
        with self.cursor() as cursor:
            cursor.executemany(query, params_list)
    
    def close_all(self):
        while True:
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except Empty:
                break
        with self._lock:
            self._size = 0
    
    @property
    def size(self) -> int:
        return self._size
    
    @property
    def available(self) -> int:
        return self._pool.qsize()


_pools: dict[str, ConnectionPool] = {}


def get_pool(database: str = "data/jarvis.db", **kwargs) -> ConnectionPool:
    if database not in _pools:
        _pools[database] = ConnectionPool(database, **kwargs)
    return _pools[database]
