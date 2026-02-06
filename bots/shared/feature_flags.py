"""
Feature Flags for ClawdBots.

Simple feature flag system backed by SQLite.
Supports per-bot flags, global flags, and percentage rollouts.
"""

import json
import logging
import os
import random
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("CLAWDBOT_DATA_DIR", "/root/clawdbots/data"))
FLAGS_DB = DATA_DIR / "feature_flags.db"


class FeatureFlags:
    """SQLite-backed feature flag system."""

    def __init__(self, bot_name: str, db_path: Optional[str] = None):
        self.bot_name = bot_name
        self.db_path = db_path or str(FLAGS_DB)
        self._lock = threading.Lock()
        self._cache: Dict[str, Any] = {}
        self._init_db()

    def _init_db(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS flags (
                name TEXT NOT NULL,
                scope TEXT NOT NULL DEFAULT 'global',
                enabled INTEGER NOT NULL DEFAULT 0,
                rollout_pct INTEGER NOT NULL DEFAULT 100,
                metadata TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (name, scope)
            )""")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def is_enabled(self, flag: str) -> bool:
        """Check if a flag is enabled for this bot. Checks bot-specific first, then global."""
        # Check cache
        cache_key = f"{self.bot_name}:{flag}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        with self._connect() as conn:
            # Bot-specific override
            row = conn.execute(
                "SELECT enabled, rollout_pct FROM flags WHERE name = ? AND scope = ?",
                (flag, self.bot_name),
            ).fetchone()
            if row:
                result = bool(row[0]) and (row[1] >= 100 or random.randint(1, 100) <= row[1])
                self._cache[cache_key] = result
                return result

            # Global fallback
            row = conn.execute(
                "SELECT enabled, rollout_pct FROM flags WHERE name = ? AND scope = 'global'",
                (flag,),
            ).fetchone()
            if row:
                result = bool(row[0]) and (row[1] >= 100 or random.randint(1, 100) <= row[1])
                self._cache[cache_key] = result
                return result

        self._cache[cache_key] = False
        return False

    def set_flag(self, flag: str, enabled: bool, scope: str = "global", rollout_pct: int = 100, metadata: Dict = None):
        """Set a feature flag."""
        now = datetime.utcnow().isoformat()
        meta_str = json.dumps(metadata) if metadata else None
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """INSERT INTO flags (name, scope, enabled, rollout_pct, metadata, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(name, scope) DO UPDATE SET
                        enabled=excluded.enabled, rollout_pct=excluded.rollout_pct,
                        metadata=excluded.metadata, updated_at=excluded.updated_at""",
                    (flag, scope, int(enabled), rollout_pct, meta_str, now),
                )
        # Invalidate cache
        self._cache.pop(f"{self.bot_name}:{flag}", None)

    def list_flags(self) -> List[Dict[str, Any]]:
        """List all flags relevant to this bot."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT name, scope, enabled, rollout_pct, metadata, updated_at FROM flags WHERE scope IN ('global', ?)",
                (self.bot_name,),
            ).fetchall()
        return [
            {
                "name": r[0],
                "scope": r[1],
                "enabled": bool(r[2]),
                "rollout_pct": r[3],
                "metadata": json.loads(r[4]) if r[4] else None,
                "updated_at": r[5],
            }
            for r in rows
        ]

    def clear_cache(self):
        """Clear the in-memory flag cache."""
        self._cache.clear()
