"""
SQLite Local Storage for ClawdBots.

Per-bot key-value store with TTL support, namespaces, and atomic operations.
Each bot gets isolated storage but can share via explicit namespaces.
"""

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("CLAWDBOT_DATA_DIR", "/root/clawdbots/data"))


class LocalStorage:
    """Per-bot SQLite key-value store."""

    def __init__(self, bot_name: str, db_path: Optional[str] = None):
        self.bot_name = bot_name
        self.db_path = db_path or str(DATA_DIR / f"{bot_name}_storage.db")
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS kv (
                namespace TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                expires_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (namespace, key)
            )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_kv_expires ON kv(expires_at)")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def set(self, key: str, value: Any, namespace: str = "default", ttl_seconds: int = 0):
        """Store a value. Supports any JSON-serializable value."""
        now = datetime.utcnow().isoformat()
        expires = None
        if ttl_seconds > 0:
            expires = (datetime.utcnow() + timedelta(seconds=ttl_seconds)).isoformat()

        val_str = json.dumps(value)
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """INSERT INTO kv (namespace, key, value, expires_at, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(namespace, key) DO UPDATE SET
                        value=excluded.value, expires_at=excluded.expires_at, updated_at=excluded.updated_at""",
                    (namespace, key, val_str, expires, now, now),
                )

    def get(self, key: str, namespace: str = "default", default: Any = None) -> Any:
        """Retrieve a value. Returns default if not found or expired."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value, expires_at FROM kv WHERE namespace=? AND key=?",
                (namespace, key),
            ).fetchone()
        if not row:
            return default
        val, expires = row
        if expires and expires < datetime.utcnow().isoformat():
            self.delete(key, namespace)
            return default
        return json.loads(val)

    def delete(self, key: str, namespace: str = "default") -> bool:
        """Delete a key. Returns True if it existed."""
        with self._lock:
            with self._connect() as conn:
                c = conn.execute(
                    "DELETE FROM kv WHERE namespace=? AND key=?",
                    (namespace, key),
                )
                return c.rowcount > 0

    def list_keys(self, namespace: str = "default", prefix: str = "") -> List[str]:
        """List all keys in a namespace, optionally filtered by prefix."""
        with self._connect() as conn:
            if prefix:
                rows = conn.execute(
                    "SELECT key FROM kv WHERE namespace=? AND key LIKE ?",
                    (namespace, f"{prefix}%"),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT key FROM kv WHERE namespace=?",
                    (namespace,),
                ).fetchall()
        return [r[0] for r in rows]

    def clear_namespace(self, namespace: str = "default") -> int:
        """Clear all keys in a namespace. Returns count deleted."""
        with self._lock:
            with self._connect() as conn:
                c = conn.execute("DELETE FROM kv WHERE namespace=?", (namespace,))
                return c.rowcount

    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count removed."""
        now = datetime.utcnow().isoformat()
        with self._lock:
            with self._connect() as conn:
                c = conn.execute(
                    "DELETE FROM kv WHERE expires_at IS NOT NULL AND expires_at < ?",
                    (now,),
                )
                return c.rowcount

    def stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM kv").fetchone()[0]
            namespaces = conn.execute("SELECT DISTINCT namespace FROM kv").fetchall()
            size = Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0
        return {
            "bot": self.bot_name,
            "total_keys": total,
            "namespaces": [n[0] for n in namespaces],
            "db_size_bytes": size,
        }
