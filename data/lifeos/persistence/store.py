"""
Persistence Store

Backend implementations for persistent storage.

Implementations:
- JSONStore: Simple JSON file storage
- SQLiteStore: SQLite database storage
"""

import json
import logging
import sqlite3
import threading
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class PersistenceStore(ABC):
    """Abstract base class for persistence stores."""

    @abstractmethod
    def get(self, namespace: str, key: str) -> Optional[Any]:
        """Get a value from storage."""
        pass

    @abstractmethod
    def set(self, namespace: str, key: str, value: Any) -> bool:
        """Set a value in storage."""
        pass

    @abstractmethod
    def delete(self, namespace: str, key: str) -> bool:
        """Delete a value from storage."""
        pass

    @abstractmethod
    def list_keys(self, namespace: str) -> List[str]:
        """List all keys in a namespace."""
        pass

    @abstractmethod
    def list_namespaces(self) -> List[str]:
        """List all namespaces."""
        pass

    @abstractmethod
    def clear_namespace(self, namespace: str) -> int:
        """Clear all keys in a namespace. Returns count deleted."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the store and release resources."""
        pass


class JSONStore(PersistenceStore):
    """
    JSON file-based persistence store.

    Simple but effective for small to medium amounts of data.
    Each namespace is stored in a separate JSON file.
    """

    def __init__(self, base_path: Union[str, Path] = "~/.lifeos/data"):
        """
        Initialize JSON store.

        Args:
            base_path: Base directory for storing JSON files
        """
        self._base_path = Path(base_path).expanduser()
        self._base_path.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._dirty: set = set()

    def _get_file_path(self, namespace: str) -> Path:
        """Get file path for a namespace."""
        safe_name = namespace.replace("/", "_").replace("\\", "_")
        return self._base_path / f"{safe_name}.json"

    def _load_namespace(self, namespace: str) -> Dict[str, Any]:
        """Load a namespace from disk."""
        if namespace in self._cache:
            return self._cache[namespace]

        file_path = self._get_file_path(namespace)
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._cache[namespace] = data
                    return data
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load namespace {namespace}: {e}")

        self._cache[namespace] = {}
        return self._cache[namespace]

    def _save_namespace(self, namespace: str) -> bool:
        """Save a namespace to disk."""
        if namespace not in self._cache:
            return True

        file_path = self._get_file_path(namespace)
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self._cache[namespace], f, indent=2, default=str)
            self._dirty.discard(namespace)
            return True
        except IOError as e:
            logger.error(f"Failed to save namespace {namespace}: {e}")
            return False

    def get(self, namespace: str, key: str) -> Optional[Any]:
        """Get a value from storage."""
        with self._lock:
            data = self._load_namespace(namespace)
            return data.get(key)

    def set(self, namespace: str, key: str, value: Any) -> bool:
        """Set a value in storage."""
        with self._lock:
            data = self._load_namespace(namespace)
            data[key] = value
            self._dirty.add(namespace)
            return self._save_namespace(namespace)

    def delete(self, namespace: str, key: str) -> bool:
        """Delete a value from storage."""
        with self._lock:
            data = self._load_namespace(namespace)
            if key in data:
                del data[key]
                self._dirty.add(namespace)
                return self._save_namespace(namespace)
            return False

    def list_keys(self, namespace: str) -> List[str]:
        """List all keys in a namespace."""
        with self._lock:
            data = self._load_namespace(namespace)
            return list(data.keys())

    def list_namespaces(self) -> List[str]:
        """List all namespaces."""
        namespaces = []
        for file_path in self._base_path.glob("*.json"):
            namespace = file_path.stem
            namespaces.append(namespace)
        return namespaces

    def clear_namespace(self, namespace: str) -> int:
        """Clear all keys in a namespace."""
        with self._lock:
            data = self._load_namespace(namespace)
            count = len(data)
            data.clear()
            self._dirty.add(namespace)
            self._save_namespace(namespace)
            return count

    def close(self) -> None:
        """Save all dirty namespaces and close."""
        with self._lock:
            for namespace in list(self._dirty):
                self._save_namespace(namespace)
            self._cache.clear()


class SQLiteStore(PersistenceStore):
    """
    SQLite database persistence store.

    More robust for larger amounts of data and concurrent access.
    """

    def __init__(self, db_path: Union[str, Path] = "~/.lifeos/data/lifeos.db"):
        """
        Initialize SQLite store.

        Args:
            db_path: Path to SQLite database file
        """
        self._db_path = Path(db_path).expanduser()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                str(self._db_path),
                check_same_thread=False,
            )
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kv_store (
                namespace TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (namespace, key)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_kv_namespace
            ON kv_store (namespace)
        """)
        conn.commit()

    def get(self, namespace: str, key: str) -> Optional[Any]:
        """Get a value from storage."""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT value FROM kv_store WHERE namespace = ? AND key = ?",
            (namespace, key),
        )
        row = cursor.fetchone()
        if row:
            try:
                return json.loads(row["value"])
            except json.JSONDecodeError:
                return row["value"]
        return None

    def set(self, namespace: str, key: str, value: Any) -> bool:
        """Set a value in storage."""
        conn = self._get_connection()
        now = datetime.now(timezone.utc).isoformat()
        value_str = json.dumps(value, default=str)

        try:
            conn.execute(
                """
                INSERT INTO kv_store (namespace, key, value, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (namespace, key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (namespace, key, value_str, now, now),
            )
            conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"SQLite error setting {namespace}/{key}: {e}")
            return False

    def delete(self, namespace: str, key: str) -> bool:
        """Delete a value from storage."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM kv_store WHERE namespace = ? AND key = ?",
                (namespace, key),
            )
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"SQLite error deleting {namespace}/{key}: {e}")
            return False

    def list_keys(self, namespace: str) -> List[str]:
        """List all keys in a namespace."""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT key FROM kv_store WHERE namespace = ?",
            (namespace,),
        )
        return [row["key"] for row in cursor.fetchall()]

    def list_namespaces(self) -> List[str]:
        """List all namespaces."""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT DISTINCT namespace FROM kv_store",
        )
        return [row["namespace"] for row in cursor.fetchall()]

    def clear_namespace(self, namespace: str) -> int:
        """Clear all keys in a namespace."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM kv_store WHERE namespace = ?",
                (namespace,),
            )
            conn.commit()
            return cursor.rowcount
        except sqlite3.Error as e:
            logger.error(f"SQLite error clearing {namespace}: {e}")
            return 0

    def close(self) -> None:
        """Close database connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None


# Default store singleton
_default_store: Optional[PersistenceStore] = None


def get_default_store() -> PersistenceStore:
    """Get the default persistence store."""
    global _default_store
    if _default_store is None:
        _default_store = JSONStore()
    return _default_store


def set_default_store(store: PersistenceStore) -> None:
    """Set the default persistence store."""
    global _default_store
    _default_store = store
