"""
Inter-bot Message Queue for ClawdBots.

Simple async message queue for bot-to-bot communication.
Uses SQLite for persistence so messages survive restarts.
"""

import json
import logging
import sqlite3
import threading
from datetime import datetime, timedelta
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

import os

DATA_DIR = Path(os.environ.get("CLAWDBOT_DATA_DIR", "/root/clawdbots/data"))
QUEUE_DB = DATA_DIR / "message_queue.db"


class Priority(IntEnum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


class MessageQueue:
    """SQLite-backed inter-bot message queue."""

    def __init__(self, bot_name: str, db_path: Optional[str] = None):
        self.bot_name = bot_name
        self.db_path = db_path or str(QUEUE_DB)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender TEXT NOT NULL,
                recipient TEXT NOT NULL,
                channel TEXT NOT NULL DEFAULT 'default',
                payload TEXT NOT NULL,
                priority INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                expires_at TEXT,
                read_at TEXT,
                acked_at TEXT
            )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_recipient ON messages(recipient, read_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_channel ON messages(channel)")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def send(
        self,
        recipient: str,
        payload: Any,
        channel: str = "default",
        priority: Priority = Priority.NORMAL,
        ttl_seconds: int = 0,
    ) -> int:
        """Send a message to another bot. Returns message ID."""
        now = datetime.utcnow().isoformat()
        expires = None
        if ttl_seconds > 0:
            expires = (datetime.utcnow() + timedelta(seconds=ttl_seconds)).isoformat()

        with self._lock:
            with self._connect() as conn:
                cur = conn.execute(
                    """INSERT INTO messages (sender, recipient, channel, payload, priority, created_at, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (self.bot_name, recipient, channel, json.dumps(payload), int(priority), now, expires),
                )
                msg_id = cur.lastrowid
        logger.debug(f"[MQ] {self.bot_name} -> {recipient} (ch={channel}, id={msg_id})")
        return msg_id

    def receive(
        self,
        channel: str = "default",
        limit: int = 10,
        mark_read: bool = True,
    ) -> List[Dict[str, Any]]:
        """Receive unread messages for this bot. Oldest first, highest priority first."""
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM messages
                WHERE recipient = ? AND channel = ? AND read_at IS NULL
                AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY priority DESC, created_at ASC
                LIMIT ?""",
                (self.bot_name, channel, now, limit),
            ).fetchall()

            messages = [dict(r) for r in rows]
            for m in messages:
                m["payload"] = json.loads(m["payload"])

            if mark_read and messages:
                ids = [m["id"] for m in messages]
                placeholders = ",".join("?" * len(ids))
                conn.execute(
                    f"UPDATE messages SET read_at = ? WHERE id IN ({placeholders})",
                    [now] + ids,
                )
        return messages

    def peek(self, channel: str = "default") -> int:
        """Count unread messages without consuming them."""
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            row = conn.execute(
                """SELECT COUNT(*) FROM messages
                WHERE recipient = ? AND channel = ? AND read_at IS NULL
                AND (expires_at IS NULL OR expires_at > ?)""",
                (self.bot_name, channel, now),
            ).fetchone()
        return row[0]

    def ack(self, message_id: int):
        """Acknowledge a message (mark as processed)."""
        now = datetime.utcnow().isoformat()
        with self._lock:
            with self._connect() as conn:
                conn.execute("UPDATE messages SET acked_at = ? WHERE id = ?", (now, message_id))

    def broadcast(self, payload: Any, channel: str = "broadcast", recipients: Optional[List[str]] = None):
        """Send to multiple bots. If recipients is None, sends to all known bots."""
        targets = recipients or ["matt", "jarvis", "friday"]
        targets = [t for t in targets if t != self.bot_name]
        for t in targets:
            self.send(t, payload, channel=channel)

    def cleanup(self, days: int = 7) -> int:
        """Remove old acknowledged/expired messages."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        with self._lock:
            with self._connect() as conn:
                cur = conn.execute(
                    "DELETE FROM messages WHERE (acked_at IS NOT NULL AND acked_at < ?) OR (expires_at IS NOT NULL AND expires_at < ?)",
                    (cutoff, datetime.utcnow().isoformat()),
                )
                return cur.rowcount

    def stats(self) -> Dict[str, Any]:
        """Queue statistics for this bot."""
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM messages WHERE recipient = ?", (self.bot_name,)).fetchone()[0]
            unread = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE recipient = ? AND read_at IS NULL", (self.bot_name,)
            ).fetchone()[0]
            sent = conn.execute("SELECT COUNT(*) FROM messages WHERE sender = ?", (self.bot_name,)).fetchone()[0]
        return {"bot": self.bot_name, "total_received": total, "unread": unread, "total_sent": sent}
