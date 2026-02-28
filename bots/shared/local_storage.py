"""SQLite local storage utilities for bot memory and settings."""

from __future__ import annotations

import base64
import hashlib
import json
import shutil
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class LocalMemoryStore:
    """SQLite local memory store with optional lightweight encryption."""

    def __init__(self, db_path: str, encryption_key: Optional[str] = None):
        self.db_path = str(db_path)
        self._encryption_key = encryption_key
        self._lock = threading.Lock()
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS credentials (
                    name TEXT NOT NULL,
                    bot TEXT NOT NULL DEFAULT 'default',
                    value TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (name, bot)
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT NOT NULL,
                    bot TEXT NOT NULL DEFAULT 'default',
                    value TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (key, bot)
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS strategies (
                    name TEXT NOT NULL,
                    bot TEXT NOT NULL DEFAULT 'default',
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (name, bot)
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS event_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    bot TEXT NOT NULL DEFAULT 'default',
                    data TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    expires_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )

    def _xor_bytes(self, payload: bytes) -> bytes:
        if not self._encryption_key:
            return payload
        key = hashlib.sha256(self._encryption_key.encode("utf-8")).digest()
        return bytes(b ^ key[i % len(key)] for i, b in enumerate(payload))

    def _encrypt(self, value: str) -> str:
        if not self._encryption_key:
            return value
        encrypted = self._xor_bytes(value.encode("utf-8"))
        return "enc:" + base64.urlsafe_b64encode(encrypted).decode("ascii")

    def _decrypt(self, value: str) -> Optional[str]:
        if not self._encryption_key:
            return value
        if not value.startswith("enc:"):
            return None
        try:
            raw = base64.urlsafe_b64decode(value[4:].encode("ascii"))
            plain = self._xor_bytes(raw)
            return plain.decode("utf-8")
        except Exception:
            return None

    # Credentials
    def store_credential(self, name: str, value: str, bot: str = "default") -> None:
        now = _utc_now_iso()
        payload = self._encrypt(value)
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO credentials(name, bot, value, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(name, bot) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
                (name, bot, payload, now, now),
            )

    def get_credential(self, name: str, bot: str = "default") -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM credentials WHERE name=? AND bot=?",
                (name, bot),
            ).fetchone()
        if not row:
            return None
        value = row["value"]
        if not self._encryption_key:
            return value
        return self._decrypt(value)

    def list_credentials(self, bot: Optional[str] = None) -> List[str]:
        with self._connect() as conn:
            if bot is None:
                rows = conn.execute("SELECT name FROM credentials").fetchall()
            else:
                rows = conn.execute("SELECT name FROM credentials WHERE bot=?", (bot,)).fetchall()
        return [r["name"] for r in rows]

    def delete_credential(self, name: str, bot: str = "default") -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM credentials WHERE name=? AND bot=?", (name, bot))
            return cur.rowcount > 0

    # Preferences
    def set_preference(self, key: str, value: Any, bot: str = "default") -> None:
        now = _utc_now_iso()
        payload = json.dumps(value)
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO preferences(key, bot, value, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(key, bot) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
                (key, bot, payload, now, now),
            )

    def get_preference(self, key: str, bot: str = "default", default: Any = None) -> Any:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM preferences WHERE key=? AND bot=?",
                (key, bot),
            ).fetchone()
        if not row:
            return default
        try:
            return json.loads(row["value"])
        except Exception:
            return default

    def get_all_preferences(self, bot: str = "default") -> Dict[str, Any]:
        with self._connect() as conn:
            rows = conn.execute("SELECT key, value FROM preferences WHERE bot=?", (bot,)).fetchall()
        result: Dict[str, Any] = {}
        for row in rows:
            result[row["key"]] = json.loads(row["value"])
        return result

    # Strategies
    def save_strategy(self, name: str, strategy: Dict[str, Any], bot: str = "default") -> None:
        now = _utc_now_iso()
        payload = json.dumps(strategy)
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO strategies(name, bot, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(name, bot) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at""",
                (name, bot, payload, now, now),
            )

    def get_strategy(self, name: str, bot: str = "default") -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM strategies WHERE name=? AND bot=?",
                (name, bot),
            ).fetchone()
        if not row:
            return None
        return json.loads(row["payload"])

    def list_strategies(self, bot: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            if bot is None:
                rows = conn.execute("SELECT name, bot, payload FROM strategies").fetchall()
            else:
                rows = conn.execute("SELECT name, bot, payload FROM strategies WHERE bot=?", (bot,)).fetchall()
        return [
            {"name": row["name"], "bot": row["bot"], "strategy": json.loads(row["payload"])}
            for row in rows
        ]

    # Event log
    def log_event(self, event_type: str, data: Dict[str, Any], bot: str = "default") -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO event_log(event_type, bot, data, timestamp) VALUES (?, ?, ?, ?)",
                (event_type, bot, json.dumps(data), _utc_now_iso()),
            )

    def get_events(self, event_type: Optional[str] = None, bot: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        query = "SELECT id, event_type, bot, data, timestamp FROM event_log"
        clauses: List[str] = []
        params: List[Any] = []
        if event_type is not None:
            clauses.append("event_type=?")
            params.append(event_type)
        if bot is not None:
            clauses.append("bot=?")
            params.append(bot)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [
            {
                "id": row["id"],
                "event_type": row["event_type"],
                "bot": row["bot"],
                "data": json.loads(row["data"]),
                "timestamp": row["timestamp"],
            }
            for row in rows
        ]

    def prune_events(self, older_than_days: int = 30) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM event_log WHERE timestamp < ?", (cutoff,))
            return cur.rowcount

    # Cache
    def cache_set(self, key: str, value: Any, ttl_seconds: int = 0) -> None:
        now = _utc_now_iso()
        expires = None
        if ttl_seconds > 0:
            expires = (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO cache(key, value, expires_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, expires_at=excluded.expires_at, updated_at=excluded.updated_at""",
                (key, json.dumps(value), expires, now, now),
            )

    def cache_get(self, key: str) -> Any:
        with self._connect() as conn:
            row = conn.execute("SELECT value, expires_at FROM cache WHERE key=?", (key,)).fetchone()
        if not row:
            return None
        expires = row["expires_at"]
        if expires and expires < _utc_now_iso():
            self.cache_clear(pattern=key)
            return None
        return json.loads(row["value"])

    def cache_clear(self, pattern: Optional[str] = None) -> int:
        with self._lock, self._connect() as conn:
            if pattern is None:
                cur = conn.execute("DELETE FROM cache")
            else:
                cur = conn.execute("DELETE FROM cache WHERE key LIKE ?", (pattern,))
            return cur.rowcount

    # Backup/restore and stats
    def backup(self, target_path: str) -> str:
        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.db_path, target)
        return str(target)

    def restore(self, source_path: str) -> None:
        shutil.copy2(source_path, self.db_path)

    def get_stats(self) -> Dict[str, Any]:
        with self._connect() as conn:
            credentials = conn.execute("SELECT COUNT(*) FROM credentials").fetchone()[0]
            preferences = conn.execute("SELECT COUNT(*) FROM preferences").fetchone()[0]
            strategies = conn.execute("SELECT COUNT(*) FROM strategies").fetchone()[0]
            events = conn.execute("SELECT COUNT(*) FROM event_log").fetchone()[0]
            cache_entries = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
        return {
            "credentials": credentials,
            "preferences": preferences,
            "strategies": strategies,
            "events": events,
            "cache_entries": cache_entries,
            "db_size_bytes": Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0,
        }


# Backwards compatibility for older callers.
LocalStorage = LocalMemoryStore

