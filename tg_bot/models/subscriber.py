"""
Subscriber model for digest subscriptions.

Uses SQLite for persistence.
"""

import sqlite3
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Subscriber:
    """Subscriber to hourly digests."""

    user_id: int
    chat_id: int
    username: Optional[str]
    risk_profile: str  # aggressive, conservative, neutral
    subscribed_at: datetime
    active: bool = True


class SubscriberDB:
    """SQLite database for subscribers."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database tables."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS subscribers (
                    user_id INTEGER PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    username TEXT,
                    risk_profile TEXT DEFAULT 'neutral',
                    subscribed_at TEXT NOT NULL,
                    active INTEGER DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS paper_wallets (
                    user_id INTEGER PRIMARY KEY,
                    balance_sol REAL DEFAULT 100.0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES subscribers (user_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS paper_positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token TEXT NOT NULL,
                    side TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    amount REAL NOT NULL,
                    opened_at TEXT NOT NULL,
                    closed_at TEXT,
                    exit_price REAL,
                    pnl REAL,
                    FOREIGN KEY (user_id) REFERENCES subscribers (user_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    condition TEXT NOT NULL,
                    threshold REAL,
                    active INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    triggered_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES subscribers (user_id)
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def subscribe(self, user_id: int, chat_id: int, username: Optional[str] = None) -> Subscriber:
        """Add or reactivate a subscriber."""
        conn = sqlite3.connect(self.db_path)
        try:
            now = datetime.utcnow().isoformat()
            conn.execute(
                """
                INSERT INTO subscribers (user_id, chat_id, username, subscribed_at, active)
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(user_id) DO UPDATE SET
                    chat_id = excluded.chat_id,
                    username = excluded.username,
                    active = 1
                """,
                (user_id, chat_id, username, now),
            )
            conn.commit()

            return Subscriber(
                user_id=user_id,
                chat_id=chat_id,
                username=username,
                risk_profile="neutral",
                subscribed_at=datetime.fromisoformat(now),
                active=True,
            )
        finally:
            conn.close()

    def unsubscribe(self, user_id: int) -> bool:
        """Deactivate a subscriber."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "UPDATE subscribers SET active = 0 WHERE user_id = ?",
                (user_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_active_subscribers(self) -> List[Subscriber]:
        """Get all active subscribers."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM subscribers WHERE active = 1"
            )
            rows = cursor.fetchall()
            return [
                Subscriber(
                    user_id=row["user_id"],
                    chat_id=row["chat_id"],
                    username=row["username"],
                    risk_profile=row["risk_profile"],
                    subscribed_at=datetime.fromisoformat(row["subscribed_at"]),
                    active=bool(row["active"]),
                )
                for row in rows
            ]
        finally:
            conn.close()

    def set_risk_profile(self, user_id: int, profile: str) -> bool:
        """Set user's risk profile."""
        if profile not in ("aggressive", "conservative", "neutral"):
            return False

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "UPDATE subscribers SET risk_profile = ? WHERE user_id = ?",
                (profile, user_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_subscriber(self, user_id: int) -> Optional[Subscriber]:
        """Get a specific subscriber."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM subscribers WHERE user_id = ?",
                (user_id,),
            )
            row = cursor.fetchone()
            if row:
                return Subscriber(
                    user_id=row["user_id"],
                    chat_id=row["chat_id"],
                    username=row["username"],
                    risk_profile=row["risk_profile"],
                    subscribed_at=datetime.fromisoformat(row["subscribed_at"]),
                    active=bool(row["active"]),
                )
            return None
        finally:
            conn.close()

    # Paper trading methods
    def get_paper_balance(self, user_id: int) -> float:
        """Get user's paper trading balance."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT balance_sol FROM paper_wallets WHERE user_id = ?",
                (user_id,),
            )
            row = cursor.fetchone()
            if row:
                return row[0]

            # Create new wallet
            now = datetime.utcnow().isoformat()
            conn.execute(
                "INSERT INTO paper_wallets (user_id, balance_sol, created_at) VALUES (?, 100.0, ?)",
                (user_id, now),
            )
            conn.commit()
            return 100.0
        finally:
            conn.close()

    def update_paper_balance(self, user_id: int, new_balance: float) -> bool:
        """Update user's paper trading balance."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "UPDATE paper_wallets SET balance_sol = ? WHERE user_id = ?",
                (new_balance, user_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
