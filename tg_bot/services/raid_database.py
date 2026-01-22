"""
Raid Bot Database - SQLite storage for raid tracking, users, and leaderboards.

Following pattern from bots/buy_tracker/database.py
"""

import sqlite3
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent.parent / "data" / "raid_bot.db"


@dataclass
class RaidUser:
    """A verified raid participant."""
    id: Optional[int] = None
    telegram_id: int = 0
    telegram_username: str = ""
    twitter_handle: str = ""
    twitter_id: str = ""
    is_verified: bool = False
    is_blue: bool = False
    weekly_points: int = 0
    total_points: int = 0
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Raid:
    """A raid campaign on a tweet."""
    id: Optional[int] = None
    tweet_id: str = ""
    tweet_url: str = ""
    tweet_author: str = ""
    tweet_text: str = ""
    started_at: str = ""
    ended_at: Optional[str] = None
    status: str = "active"  # active, ended, cancelled
    announcement_message_id: Optional[int] = None
    announcement_chat_id: Optional[int] = None
    total_participants: int = 0
    total_points_awarded: int = 0


@dataclass
class RaidParticipation:
    """User participation in a raid."""
    id: Optional[int] = None
    raid_id: int = 0
    user_id: int = 0
    liked: bool = False
    retweeted: bool = False
    commented: bool = False
    points_earned: int = 0
    verified_at: str = ""


class RaidDatabase:
    """SQLite database for raid tracking."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Raid users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS raid_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    telegram_username TEXT,
                    twitter_handle TEXT NOT NULL,
                    twitter_id TEXT,
                    is_verified INTEGER DEFAULT 0,
                    is_blue INTEGER DEFAULT 0,
                    weekly_points INTEGER DEFAULT 0,
                    total_points INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Raids table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS raids (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tweet_id TEXT UNIQUE NOT NULL,
                    tweet_url TEXT NOT NULL,
                    tweet_author TEXT,
                    tweet_text TEXT,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    status TEXT DEFAULT 'active',
                    announcement_message_id INTEGER,
                    announcement_chat_id INTEGER,
                    total_participants INTEGER DEFAULT 0,
                    total_points_awarded INTEGER DEFAULT 0
                )
            """)

            # Raid participations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS raid_participations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    raid_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    liked INTEGER DEFAULT 0,
                    retweeted INTEGER DEFAULT 0,
                    commented INTEGER DEFAULT 0,
                    points_earned INTEGER DEFAULT 0,
                    verified_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (raid_id) REFERENCES raids(id),
                    FOREIGN KEY (user_id) REFERENCES raid_users(id),
                    UNIQUE(raid_id, user_id)
                )
            """)

            # Raid config table (key-value)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS raid_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Weekly winners history
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS weekly_winners (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    week_start TEXT NOT NULL,
                    week_end TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    rank INTEGER NOT NULL,
                    points INTEGER NOT NULL,
                    reward_amount REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES raid_users(id)
                )
            """)

            # Indexes for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_telegram ON raid_users(telegram_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_twitter ON raid_users(twitter_handle)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_weekly_points ON raid_users(weekly_points DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_total_points ON raid_users(total_points DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_raids_status ON raids(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_raids_tweet ON raids(tweet_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_participations_raid ON raid_participations(raid_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_participations_user ON raid_participations(user_id)")

            # Insert default config values
            default_config = {
                "points_like": "1",
                "points_retweet": "1",
                "points_comment": "2",
                "blue_bonus": "1",
                "weekly_reward_amount": "100000",
                "weekly_reward_token": "KR8TIV",
            }
            for key, value in default_config.items():
                cursor.execute(
                    "INSERT OR IGNORE INTO raid_config (key, value) VALUES (?, ?)",
                    (key, value)
                )

            conn.commit()
            logger.info(f"Raid database initialized at {self.db_path}")

    @contextmanager
    def _get_connection(self):
        """Get database connection with context manager."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    # =========================================================================
    # USER METHODS
    # =========================================================================

    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict]:
        """Get user by Telegram ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM raid_users WHERE telegram_id = ?", (telegram_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Get user by internal ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM raid_users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_user_by_twitter_handle(self, handle: str) -> Optional[Dict]:
        """Get user by Twitter handle."""
        handle = handle.lower().lstrip("@")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM raid_users WHERE LOWER(twitter_handle) = ?",
                (handle,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def register_user(
        self,
        telegram_id: int,
        telegram_username: str,
        twitter_handle: str,
        twitter_id: str = "",
        is_blue: bool = False
    ) -> int:
        """Register a new raid user. Returns user ID."""
        twitter_handle = twitter_handle.lstrip("@")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Use INSERT OR REPLACE to handle re-registration
            cursor.execute("""
                INSERT INTO raid_users
                (telegram_id, telegram_username, twitter_handle, twitter_id, is_verified, is_blue, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    telegram_username = excluded.telegram_username,
                    twitter_handle = excluded.twitter_handle,
                    twitter_id = excluded.twitter_id,
                    is_verified = 1,
                    is_blue = excluded.is_blue,
                    updated_at = CURRENT_TIMESTAMP
            """, (telegram_id, telegram_username, twitter_handle, twitter_id, 1 if is_blue else 0))
            conn.commit()

            # Get the user ID
            cursor.execute("SELECT id FROM raid_users WHERE telegram_id = ?", (telegram_id,))
            row = cursor.fetchone()
            return row["id"] if row else cursor.lastrowid

    def update_user_blue_status(self, user_id: int, is_blue: bool) -> None:
        """Update user's blue verification status."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE raid_users
                SET is_blue = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (1 if is_blue else 0, user_id))
            conn.commit()

    def update_user_points(self, user_id: int, points_delta: int) -> None:
        """Add points to a user (both weekly and total)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE raid_users
                SET weekly_points = weekly_points + ?,
                    total_points = total_points + ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (points_delta, points_delta, user_id))
            conn.commit()

    def get_leaderboard(self, limit: int = 10, weekly: bool = True) -> List[Dict]:
        """Get top raiders by points."""
        points_col = "weekly_points" if weekly else "total_points"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT id, telegram_id, telegram_username, twitter_handle, is_blue,
                       weekly_points, total_points
                FROM raid_users
                WHERE is_verified = 1 AND {points_col} > 0
                ORDER BY {points_col} DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_user_rank(self, user_id: int, weekly: bool = True) -> int:
        """Get user's rank on leaderboard."""
        points_col = "weekly_points" if weekly else "total_points"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT COUNT(*) + 1 as rank
                FROM raid_users
                WHERE is_verified = 1 AND {points_col} > (
                    SELECT {points_col} FROM raid_users WHERE id = ?
                )
            """, (user_id,))
            row = cursor.fetchone()
            return row["rank"] if row else 0

    def get_total_verified_users(self) -> int:
        """Get total count of verified users."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM raid_users WHERE is_verified = 1")
            row = cursor.fetchone()
            return row["count"] if row else 0

    def reset_weekly_points(self) -> List[Dict]:
        """Reset all weekly points. Returns top 10 before reset."""
        top_10 = self.get_leaderboard(limit=10, weekly=True)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE raid_users SET weekly_points = 0")
            conn.commit()
        return top_10

    # =========================================================================
    # RAID METHODS
    # =========================================================================

    def create_raid(
        self,
        tweet_id: str,
        tweet_url: str,
        tweet_author: str = "",
        tweet_text: str = "",
        announcement_message_id: int = None,
        announcement_chat_id: int = None
    ) -> int:
        """Create a new raid. Returns raid ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO raids
                (tweet_id, tweet_url, tweet_author, tweet_text, started_at, status,
                 announcement_message_id, announcement_chat_id)
                VALUES (?, ?, ?, ?, ?, 'active', ?, ?)
            """, (tweet_id, tweet_url, tweet_author, tweet_text,
                  datetime.now(timezone.utc).isoformat(),
                  announcement_message_id, announcement_chat_id))
            conn.commit()
            return cursor.lastrowid

    def get_active_raid(self) -> Optional[Dict]:
        """Get the currently active raid."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM raids WHERE status = 'active' ORDER BY started_at DESC LIMIT 1")
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_raid_by_id(self, raid_id: int) -> Optional[Dict]:
        """Get raid by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM raids WHERE id = ?", (raid_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_raid_by_tweet_id(self, tweet_id: str) -> Optional[Dict]:
        """Get raid by tweet ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM raids WHERE tweet_id = ?", (tweet_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def end_raid(self, raid_id: int) -> None:
        """End a raid."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Calculate totals
            cursor.execute("""
                SELECT COUNT(DISTINCT user_id) as participants, COALESCE(SUM(points_earned), 0) as points
                FROM raid_participations WHERE raid_id = ?
            """, (raid_id,))
            row = cursor.fetchone()
            participants = row["participants"] if row else 0
            points = row["points"] if row else 0

            cursor.execute("""
                UPDATE raids
                SET status = 'ended',
                    ended_at = ?,
                    total_participants = ?,
                    total_points_awarded = ?
                WHERE id = ?
            """, (datetime.now(timezone.utc).isoformat(), participants, points, raid_id))
            conn.commit()

    def cancel_raid(self, raid_id: int) -> None:
        """Cancel a raid without awarding points."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE raids
                SET status = 'cancelled',
                    ended_at = ?
                WHERE id = ?
            """, (datetime.now(timezone.utc).isoformat(), raid_id))
            conn.commit()

    def get_recent_raids(self, limit: int = 10) -> List[Dict]:
        """Get recent raids."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM raids
                ORDER BY started_at DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def update_raid_announcement(self, raid_id: int, message_id: int, chat_id: int) -> None:
        """Update raid with announcement message details."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE raids
                SET announcement_message_id = ?, announcement_chat_id = ?
                WHERE id = ?
            """, (message_id, chat_id, raid_id))
            conn.commit()

    # =========================================================================
    # PARTICIPATION METHODS
    # =========================================================================

    def record_participation(
        self,
        raid_id: int,
        user_id: int,
        liked: bool,
        retweeted: bool,
        commented: bool,
        points: int
    ) -> int:
        """Record user participation in a raid. Returns participation ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO raid_participations
                (raid_id, user_id, liked, retweeted, commented, points_earned, verified_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(raid_id, user_id) DO UPDATE SET
                    liked = excluded.liked,
                    retweeted = excluded.retweeted,
                    commented = excluded.commented,
                    points_earned = excluded.points_earned,
                    verified_at = CURRENT_TIMESTAMP
            """, (raid_id, user_id, 1 if liked else 0, 1 if retweeted else 0,
                  1 if commented else 0, points))
            conn.commit()
            return cursor.lastrowid

    def get_participation(self, raid_id: int, user_id: int) -> Optional[Dict]:
        """Get user's participation in a specific raid."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM raid_participations
                WHERE raid_id = ? AND user_id = ?
            """, (raid_id, user_id))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_raid_participants(self, raid_id: int) -> List[Dict]:
        """Get all participants in a raid with their details."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.*, u.telegram_username, u.twitter_handle, u.is_blue
                FROM raid_participations p
                JOIN raid_users u ON p.user_id = u.id
                WHERE p.raid_id = ?
                ORDER BY p.points_earned DESC
            """, (raid_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_user_raid_history(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Get a user's raid participation history."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.*, r.tweet_url, r.tweet_author, r.started_at as raid_started
                FROM raid_participations p
                JOIN raids r ON p.raid_id = r.id
                WHERE p.user_id = ?
                ORDER BY p.verified_at DESC
                LIMIT ?
            """, (user_id, limit))
            return [dict(row) for row in cursor.fetchall()]

    # =========================================================================
    # CONFIG METHODS
    # =========================================================================

    def get_config(self, key: str) -> Optional[str]:
        """Get config value."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM raid_config WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else None

    def set_config(self, key: str, value: str) -> None:
        """Set config value."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO raid_config (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
            """, (key, value))
            conn.commit()

    def get_all_config(self) -> Dict[str, str]:
        """Get all config values."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM raid_config")
            return {row["key"]: row["value"] for row in cursor.fetchall()}

    def get_point_values(self) -> Dict[str, int]:
        """Get current point values for actions."""
        return {
            "like": int(self.get_config("points_like") or 1),
            "retweet": int(self.get_config("points_retweet") or 1),
            "comment": int(self.get_config("points_comment") or 2),
            "blue_bonus": int(self.get_config("blue_bonus") or 1),
        }

    # =========================================================================
    # WEEKLY WINNERS
    # =========================================================================

    def record_weekly_winners(
        self,
        week_start: str,
        week_end: str,
        winners: List[Dict],
        reward_per_winner: float
    ) -> None:
        """Record weekly winners for history."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for i, winner in enumerate(winners, 1):
                cursor.execute("""
                    INSERT INTO weekly_winners
                    (week_start, week_end, user_id, rank, points, reward_amount)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (week_start, week_end, winner["id"], i,
                      winner["weekly_points"], reward_per_winner if i <= 10 else 0))
            conn.commit()

    def get_weekly_winners_history(self, limit: int = 5) -> List[Dict]:
        """Get recent weekly winners."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT w.*, u.telegram_username, u.twitter_handle
                FROM weekly_winners w
                JOIN raid_users u ON w.user_id = u.id
                ORDER BY w.created_at DESC
                LIMIT ?
            """, (limit * 10,))  # 10 winners per week
            return [dict(row) for row in cursor.fetchall()]


# Singleton instance
_raid_db: Optional[RaidDatabase] = None


def get_raid_db() -> RaidDatabase:
    """Get or create raid database singleton."""
    global _raid_db
    if _raid_db is None:
        _raid_db = RaidDatabase()
    return _raid_db
