"""
User Profile System for Jarvis Community.

Features:
- Public/private profile settings
- Trading stats display
- Bio and customization
- Achievement badges display
- Trading history (optional)
- Privacy controls per field

Privacy settings:
- is_public: Whether profile is visible
- show_pnl: Show profit/loss
- show_trades: Show trading history
- show_badges: Show earned badges
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("jarvis.community.user_profile")


def init_profile_db(db_path: str) -> sqlite3.Connection:
    """Initialize the user profile database schema."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # User profiles table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            bio TEXT DEFAULT '',
            avatar_url TEXT,

            -- Privacy settings
            is_public INTEGER DEFAULT 0,
            show_pnl INTEGER DEFAULT 0,
            show_trades INTEGER DEFAULT 0,
            show_badges INTEGER DEFAULT 1,

            -- Trading stats (cached)
            total_pnl REAL DEFAULT 0,
            win_rate REAL DEFAULT 0,
            total_trades INTEGER DEFAULT 0,

            -- Timestamps
            created_at TEXT,
            updated_at TEXT
        )
    """)

    # Trading history table (for public display)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trade_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            trade_id TEXT UNIQUE,
            token TEXT,
            trade_type TEXT,
            entry_price REAL,
            exit_price REAL,
            pnl REAL,
            timestamp TEXT,
            FOREIGN KEY(user_id) REFERENCES user_profiles(user_id)
        )
    """)

    conn.commit()
    return conn


class UserProfileManager:
    """
    Manages user profiles with privacy controls.

    Usage:
        manager = UserProfileManager()

        # Create profile
        profile = manager.create_profile(
            user_id="user1",
            username="trader_pro",
            bio="I trade memecoins"
        )

        # Update privacy
        manager.update_privacy(user_id="user1", is_public=True, show_pnl=True)

        # Get public profile (respects privacy)
        public = manager.get_public_profile("user1")
    """

    MAX_BIO_LENGTH = 200

    def __init__(self, db_path: str = None):
        """Initialize profile manager."""
        if db_path is None:
            data_dir = Path(os.getenv("DATA_DIR", "data"))
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "community" / "profiles.db")
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self.db_path = db_path
        self._conn = init_profile_db(db_path)
        logger.info(f"Profile manager initialized: {db_path}")

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # =========================================================================
    # Profile Management
    # =========================================================================

    def create_profile(
        self,
        user_id: str,
        username: str,
        bio: str = "",
        avatar_url: str = None,
    ) -> Dict[str, Any]:
        """
        Create a new user profile.

        Args:
            user_id: Unique user identifier
            username: Display name
            bio: Short bio (max 200 chars)
            avatar_url: URL to avatar image

        Returns:
            Created profile dict
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        # Truncate bio if too long
        if len(bio) > self.MAX_BIO_LENGTH:
            bio = bio[:self.MAX_BIO_LENGTH]

        cursor.execute("""
            INSERT INTO user_profiles (
                user_id, username, bio, avatar_url,
                is_public, show_pnl, show_trades, show_badges,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, 0, 0, 0, 1, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                bio = excluded.bio,
                avatar_url = excluded.avatar_url,
                updated_at = excluded.updated_at
        """, (user_id, username, bio, avatar_url, now, now))

        conn.commit()
        conn.close()

        return self.get_profile(user_id)

    def get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get full profile for a user (internal use)."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM user_profiles WHERE user_id = ?
        """, (user_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            profile = dict(row)
            # Convert integers to booleans
            profile["is_public"] = bool(profile["is_public"])
            profile["show_pnl"] = bool(profile["show_pnl"])
            profile["show_trades"] = bool(profile["show_trades"])
            profile["show_badges"] = bool(profile["show_badges"])
            return profile

        return None

    def update_profile(
        self,
        user_id: str,
        username: str = None,
        bio: str = None,
        avatar_url: str = None,
    ) -> Optional[Dict[str, Any]]:
        """Update profile fields."""
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        # Build dynamic update query
        updates = []
        params = []

        if username is not None:
            updates.append("username = ?")
            params.append(username)

        if bio is not None:
            if len(bio) > self.MAX_BIO_LENGTH:
                bio = bio[:self.MAX_BIO_LENGTH]
            updates.append("bio = ?")
            params.append(bio)

        if avatar_url is not None:
            updates.append("avatar_url = ?")
            params.append(avatar_url)

        if not updates:
            conn.close()
            return self.get_profile(user_id)

        updates.append("updated_at = ?")
        params.append(now)
        params.append(user_id)

        cursor.execute(f"""
            UPDATE user_profiles SET {', '.join(updates)}
            WHERE user_id = ?
        """, params)

        conn.commit()
        conn.close()

        return self.get_profile(user_id)

    # =========================================================================
    # Privacy Settings
    # =========================================================================

    def update_privacy(
        self,
        user_id: str,
        is_public: bool = None,
        show_pnl: bool = None,
        show_trades: bool = None,
        show_badges: bool = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Update privacy settings.

        Args:
            user_id: User identifier
            is_public: Make profile publicly visible
            show_pnl: Show profit/loss on public profile
            show_trades: Show trading history on public profile
            show_badges: Show badges on public profile

        Returns:
            Updated profile dict
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        updates = []
        params = []

        if is_public is not None:
            updates.append("is_public = ?")
            params.append(1 if is_public else 0)

        if show_pnl is not None:
            updates.append("show_pnl = ?")
            params.append(1 if show_pnl else 0)

        if show_trades is not None:
            updates.append("show_trades = ?")
            params.append(1 if show_trades else 0)

        if show_badges is not None:
            updates.append("show_badges = ?")
            params.append(1 if show_badges else 0)

        if not updates:
            conn.close()
            return self.get_profile(user_id)

        updates.append("updated_at = ?")
        params.append(now)
        params.append(user_id)

        cursor.execute(f"""
            UPDATE user_profiles SET {', '.join(updates)}
            WHERE user_id = ?
        """, params)

        conn.commit()
        conn.close()

        return self.get_profile(user_id)

    # =========================================================================
    # Stats Management
    # =========================================================================

    def update_stats(
        self,
        user_id: str,
        total_pnl: float = None,
        win_rate: float = None,
        total_trades: int = None,
    ) -> Optional[Dict[str, Any]]:
        """Update trading stats on profile."""
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        updates = []
        params = []

        if total_pnl is not None:
            updates.append("total_pnl = ?")
            params.append(total_pnl)

        if win_rate is not None:
            updates.append("win_rate = ?")
            params.append(win_rate)

        if total_trades is not None:
            updates.append("total_trades = ?")
            params.append(total_trades)

        if not updates:
            conn.close()
            return self.get_profile(user_id)

        updates.append("updated_at = ?")
        params.append(now)
        params.append(user_id)

        cursor.execute(f"""
            UPDATE user_profiles SET {', '.join(updates)}
            WHERE user_id = ?
        """, params)

        conn.commit()
        conn.close()

        return self.get_profile(user_id)

    # =========================================================================
    # Public Profile Access
    # =========================================================================

    def get_public_profile(self, user_id: str) -> Dict[str, Any]:
        """
        Get public-facing profile respecting privacy settings.

        Args:
            user_id: User identifier

        Returns:
            Public profile with only allowed fields
        """
        profile = self.get_profile(user_id)

        if not profile:
            return {"username": "Unknown", "error": "Profile not found"}

        # If not public, return minimal anonymous info
        if not profile["is_public"]:
            return {
                "username": "Anonymous",
                "bio": "",
                "badges": [] if profile["show_badges"] else None,
            }

        # Build public profile based on privacy settings
        public = {
            "username": profile["username"],
            "bio": profile["bio"],
            "avatar_url": profile.get("avatar_url"),
        }

        if profile["show_pnl"]:
            public["total_pnl"] = profile["total_pnl"]
            public["win_rate"] = profile["win_rate"]

        if profile["show_trades"]:
            public["total_trades"] = profile["total_trades"]
            public["recent_trades"] = self._get_recent_trades(user_id, limit=10)

        if profile["show_badges"]:
            public["badges"] = self._get_user_badges(user_id)

        return public

    def _get_recent_trades(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent trades for public display."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT token, trade_type, pnl, timestamp
            FROM trade_history
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (user_id, limit))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def _get_user_badges(self, user_id: str) -> List[str]:
        """
        Get user badges from achievements table.

        Note: This connects to the achievements database.
        """
        try:
            # Try to import and use achievements manager
            from core.community.achievements import AchievementManager
            achievements = AchievementManager()
            return achievements.get_user_badges(user_id)
        except Exception:
            return []

    # =========================================================================
    # Trading History
    # =========================================================================

    def add_trade(
        self,
        user_id: str,
        trade_id: str,
        token: str,
        trade_type: str,
        entry_price: float,
        exit_price: float,
        pnl: float,
        timestamp: str = None,
    ) -> bool:
        """Add a trade to user's history."""
        conn = self._get_conn()
        cursor = conn.cursor()

        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()

        try:
            cursor.execute("""
                INSERT INTO trade_history (
                    user_id, trade_id, token, trade_type,
                    entry_price, exit_price, pnl, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, trade_id, token, trade_type,
                entry_price, exit_price, pnl, timestamp
            ))

            conn.commit()
            conn.close()
            return True

        except sqlite3.IntegrityError:
            # Trade already exists
            conn.close()
            return False

    # =========================================================================
    # Bulk Operations
    # =========================================================================

    def get_all_public_profiles(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all public profiles."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT user_id FROM user_profiles
            WHERE is_public = 1
            ORDER BY total_pnl DESC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        return [self.get_public_profile(row["user_id"]) for row in rows]

    def export_profiles_json(self, filepath: str = None) -> str:
        """Export all public profiles to JSON."""
        if filepath is None:
            data_dir = Path(os.getenv("DATA_DIR", "data"))
            filepath = str(data_dir / "community" / "profiles" / "public_profiles.json")

        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        profiles = self.get_all_public_profiles()

        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "profile_count": len(profiles),
            "profiles": profiles,
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Exported {len(profiles)} profiles to {filepath}")
        return filepath
