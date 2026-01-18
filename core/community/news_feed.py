"""
Community News Feed for Jarvis.

Aggregates news from:
- User achievements (badges, records)
- Community events (challenges, votes)
- Team updates (new features, posts)
- Market alpha (signal detections)

Features:
- Daily digest via Telegram
- Personalized based on followed users/tokens
- Configurable notification preferences
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("jarvis.community.news_feed")


def init_news_feed_db(db_path: str) -> sqlite3.Connection:
    """Initialize the news feed database schema."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # News items table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS news_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_type TEXT NOT NULL,
            content TEXT NOT NULL,
            user_id TEXT,
            metadata TEXT,
            priority INTEGER DEFAULT 1,
            created_at TEXT,
            expires_at TEXT
        )
    """)

    # User feed preferences table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feed_preferences (
            user_id TEXT PRIMARY KEY,
            show_achievements INTEGER DEFAULT 1,
            show_challenges INTEGER DEFAULT 1,
            show_team_updates INTEGER DEFAULT 1,
            show_market_alpha INTEGER DEFAULT 1,
            daily_digest INTEGER DEFAULT 1,
            digest_time TEXT DEFAULT '09:00'
        )
    """)

    # User follows (for personalization)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_follows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            follower_id TEXT,
            following_id TEXT,
            follow_type TEXT DEFAULT 'user',
            created_at TEXT,
            UNIQUE(follower_id, following_id, follow_type)
        )
    """)

    # Digest history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS digest_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            digest_date TEXT,
            items_count INTEGER,
            sent_at TEXT,
            UNIQUE(user_id, digest_date)
        )
    """)

    conn.commit()
    return conn


class NewsFeed:
    """
    Manages the community news feed.

    Usage:
        feed = NewsFeed()

        # Add news item
        item = feed.add_item(
            item_type="achievement",
            content="user1 earned the '10x Gain' badge!",
            user_id="user1",
            metadata={"badge_id": "10X_GAIN"}
        )

        # Get personalized feed
        items = feed.get_feed(user_id="user1", limit=10)

        # Generate daily digest
        digest = feed.generate_daily_digest(user_id="user1")
    """

    # News item types
    ITEM_TYPES = [
        "achievement",     # Badge earned, record broken
        "challenge",       # Challenge started, ended, winner
        "team_update",     # New feature, announcement
        "market_alpha",    # Signal detection, trending token
        "community",       # Vote results, leaderboard changes
        "trade",           # Notable trades (if user allows)
    ]

    def __init__(self, db_path: str = None):
        """Initialize news feed."""
        if db_path is None:
            data_dir = Path(os.getenv("DATA_DIR", "data"))
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "community" / "news_feed.db")
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self.db_path = db_path
        self._conn = init_news_feed_db(db_path)
        logger.info(f"News feed initialized: {db_path}")

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # =========================================================================
    # Item Management
    # =========================================================================

    def add_item(
        self,
        item_type: str,
        content: str,
        user_id: str = None,
        metadata: Dict[str, Any] = None,
        priority: int = 1,
        expires_hours: int = 168,  # 1 week default
    ) -> Dict[str, Any]:
        """
        Add a news item to the feed.

        Args:
            item_type: Type of news (achievement, challenge, etc.)
            content: The news content/message
            user_id: Associated user (if any)
            metadata: Additional data
            priority: 1-5, higher = more important
            expires_hours: How long item stays in feed

        Returns:
            Created news item
        """
        if item_type not in self.ITEM_TYPES:
            item_type = "community"  # Default fallback

        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=expires_hours)

        cursor.execute("""
            INSERT INTO news_items (
                item_type, content, user_id, metadata, priority,
                created_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            item_type,
            content,
            user_id,
            json.dumps(metadata) if metadata else None,
            priority,
            now.isoformat(),
            expires.isoformat(),
        ))

        item_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.debug(f"Added news item: {item_type} - {content[:50]}...")

        return {
            "id": item_id,
            "item_type": item_type,
            "content": content,
            "user_id": user_id,
            "metadata": metadata,
            "priority": priority,
            "created_at": now.isoformat(),
        }

    def get_item(self, item_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific news item."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM news_items WHERE id = ?
        """, (item_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            item = dict(row)
            item["metadata"] = json.loads(item["metadata"]) if item["metadata"] else None
            return item

        return None

    # =========================================================================
    # Feed Retrieval
    # =========================================================================

    def get_feed(
        self,
        user_id: str = None,
        item_types: List[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get personalized feed for a user.

        Args:
            user_id: User to get feed for (for personalization)
            item_types: Filter by types (None = all)
            limit: Max items to return
            offset: Pagination offset

        Returns:
            List of news items
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        # Build query
        query = """
            SELECT * FROM news_items
            WHERE expires_at >= ?
        """
        params = [now]

        # Filter by type
        if item_types:
            placeholders = ",".join("?" * len(item_types))
            query += f" AND item_type IN ({placeholders})"
            params.extend(item_types)

        # Apply user preferences if user_id provided
        if user_id:
            prefs = self._get_preferences(user_id)
            hidden_types = []
            if not prefs.get("show_achievements", True):
                hidden_types.append("achievement")
            if not prefs.get("show_challenges", True):
                hidden_types.append("challenge")
            if not prefs.get("show_team_updates", True):
                hidden_types.append("team_update")
            if not prefs.get("show_market_alpha", True):
                hidden_types.append("market_alpha")

            if hidden_types:
                placeholders = ",".join("?" * len(hidden_types))
                query += f" AND item_type NOT IN ({placeholders})"
                params.extend(hidden_types)

        query += " ORDER BY priority DESC, created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        items = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item["metadata"]) if item["metadata"] else None
            items.append(item)

        return items

    def get_user_news(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get news items about a specific user."""
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        cursor.execute("""
            SELECT * FROM news_items
            WHERE user_id = ? AND expires_at >= ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (user_id, now, limit))

        rows = cursor.fetchall()
        conn.close()

        items = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item["metadata"]) if item["metadata"] else None
            items.append(item)

        return items

    # =========================================================================
    # User Preferences
    # =========================================================================

    def _get_preferences(self, user_id: str) -> Dict[str, Any]:
        """Get user's feed preferences."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM feed_preferences WHERE user_id = ?
        """, (user_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            prefs = dict(row)
            for key in ["show_achievements", "show_challenges", "show_team_updates",
                        "show_market_alpha", "daily_digest"]:
                prefs[key] = bool(prefs.get(key, 1))
            return prefs

        # Return defaults
        return {
            "user_id": user_id,
            "show_achievements": True,
            "show_challenges": True,
            "show_team_updates": True,
            "show_market_alpha": True,
            "daily_digest": True,
            "digest_time": "09:00",
        }

    def set_preferences(
        self,
        user_id: str,
        show_achievements: bool = None,
        show_challenges: bool = None,
        show_team_updates: bool = None,
        show_market_alpha: bool = None,
        daily_digest: bool = None,
        digest_time: str = None,
    ) -> Dict[str, Any]:
        """Update user's feed preferences."""
        conn = self._get_conn()
        cursor = conn.cursor()

        # Get current prefs
        current = self._get_preferences(user_id)

        # Apply updates
        updates = {}
        if show_achievements is not None:
            updates["show_achievements"] = 1 if show_achievements else 0
        if show_challenges is not None:
            updates["show_challenges"] = 1 if show_challenges else 0
        if show_team_updates is not None:
            updates["show_team_updates"] = 1 if show_team_updates else 0
        if show_market_alpha is not None:
            updates["show_market_alpha"] = 1 if show_market_alpha else 0
        if daily_digest is not None:
            updates["daily_digest"] = 1 if daily_digest else 0
        if digest_time is not None:
            updates["digest_time"] = digest_time

        if updates:
            columns = list(updates.keys())
            values = list(updates.values())

            cursor.execute(f"""
                INSERT INTO feed_preferences (user_id, {', '.join(columns)})
                VALUES (?, {', '.join('?' for _ in values)})
                ON CONFLICT(user_id) DO UPDATE SET
                    {', '.join(f'{c} = excluded.{c}' for c in columns)}
            """, [user_id] + values)

            conn.commit()

        conn.close()
        return self._get_preferences(user_id)

    # =========================================================================
    # Daily Digest
    # =========================================================================

    def generate_daily_digest(
        self,
        user_id: str,
        hours_back: int = 24,
    ) -> Dict[str, Any]:
        """
        Generate a daily digest for a user.

        Args:
            user_id: User to generate digest for
            hours_back: How many hours of news to include

        Returns:
            Digest with items and summary
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).isoformat()

        # Get items from last 24 hours
        items = self.get_feed(user_id=user_id, limit=50)
        recent_items = [i for i in items if i["created_at"] >= cutoff]

        # Group by type
        grouped = {}
        for item in recent_items:
            item_type = item["item_type"]
            if item_type not in grouped:
                grouped[item_type] = []
            grouped[item_type].append(item)

        # Build summary
        summary_parts = []
        if "achievement" in grouped:
            summary_parts.append(f"{len(grouped['achievement'])} new badges earned")
        if "challenge" in grouped:
            summary_parts.append(f"{len(grouped['challenge'])} challenge updates")
        if "market_alpha" in grouped:
            summary_parts.append(f"{len(grouped['market_alpha'])} market signals")
        if "team_update" in grouped:
            summary_parts.append(f"{len(grouped['team_update'])} team updates")

        # Record digest was generated
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        cursor.execute("""
            INSERT INTO digest_history (user_id, digest_date, items_count, sent_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, digest_date) DO UPDATE SET
                items_count = excluded.items_count,
                sent_at = excluded.sent_at
        """, (user_id, today, len(recent_items), datetime.now(timezone.utc).isoformat()))

        conn.commit()
        conn.close()

        return {
            "user_id": user_id,
            "date": today,
            "items": recent_items,
            "item_count": len(recent_items),
            "summary": ", ".join(summary_parts) if summary_parts else "No new updates",
            "grouped": grouped,
        }

    def get_users_for_digest(self) -> List[str]:
        """Get users who should receive daily digest now."""
        conn = self._get_conn()
        cursor = conn.cursor()

        # Get current hour
        current_hour = datetime.now(timezone.utc).strftime("%H:00")

        cursor.execute("""
            SELECT user_id FROM feed_preferences
            WHERE daily_digest = 1 AND digest_time = ?
        """, (current_hour,))

        rows = cursor.fetchall()
        conn.close()

        return [row["user_id"] for row in rows]

    # =========================================================================
    # Following
    # =========================================================================

    def follow_user(self, follower_id: str, following_id: str) -> bool:
        """Follow another user to see their achievements."""
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        try:
            cursor.execute("""
                INSERT INTO user_follows (follower_id, following_id, follow_type, created_at)
                VALUES (?, ?, 'user', ?)
            """, (follower_id, following_id, now))

            conn.commit()
            conn.close()
            return True

        except sqlite3.IntegrityError:
            conn.close()
            return False  # Already following

    def unfollow_user(self, follower_id: str, following_id: str) -> bool:
        """Unfollow a user."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM user_follows
            WHERE follower_id = ? AND following_id = ? AND follow_type = 'user'
        """, (follower_id, following_id))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()

        return success

    def get_following(self, user_id: str) -> List[str]:
        """Get list of user IDs that a user follows."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT following_id FROM user_follows
            WHERE follower_id = ? AND follow_type = 'user'
        """, (user_id,))

        rows = cursor.fetchall()
        conn.close()

        return [row["following_id"] for row in rows]

    # =========================================================================
    # Cleanup
    # =========================================================================

    def cleanup_expired(self) -> int:
        """Remove expired news items."""
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        cursor.execute("""
            DELETE FROM news_items WHERE expires_at < ?
        """, (now,))

        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        if deleted > 0:
            logger.info(f"Cleaned up {deleted} expired news items")

        return deleted
