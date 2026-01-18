"""
Achievement/Badge System for Jarvis Community.

Badge Types:
- Milestone: Profit thresholds ($100, $1000, $10K+)
- Streak: Consecutive winning trades (5, 10, 20+)
- Explorer: Analyze 50+ different tokens
- Perfectionist: 100% win rate on 10 trades
- Alpha Hunter: Discovered token before 10x
- Community Helper: Referred 5+ users

Features:
- Automatic badge detection based on events
- No duplicate badges
- Telegram notifications for new badges
- Badge display on profiles and leaderboard
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("jarvis.community.achievements")


class BadgeType(Enum):
    """Types of achievement badges."""
    MILESTONE = "milestone"
    STREAK = "streak"
    EXPLORER = "explorer"
    SKILL = "skill"
    COMMUNITY = "community"
    SPECIAL = "special"


# Badge definitions with requirements
BADGE_DEFINITIONS = {
    # Milestone badges
    "FIRST_TRADE": {
        "name": "First Trade",
        "description": "Completed your first trade",
        "type": BadgeType.MILESTONE,
        "icon": "rocket",
        "requirement": {"trade_count": 1},
    },
    "PROFIT_100": {
        "name": "Century",
        "description": "Earned $100 in profit",
        "type": BadgeType.MILESTONE,
        "icon": "money_bag",
        "requirement": {"total_pnl": 100},
    },
    "PROFIT_1K": {
        "name": "Grand Trader",
        "description": "Earned $1,000 in profit",
        "type": BadgeType.MILESTONE,
        "icon": "trophy",
        "requirement": {"total_pnl": 1000},
    },
    "PROFIT_10K": {
        "name": "Elite Trader",
        "description": "Earned $10,000 in profit",
        "type": BadgeType.MILESTONE,
        "icon": "crown",
        "requirement": {"total_pnl": 10000},
    },
    "PROFIT_100K": {
        "name": "Whale Status",
        "description": "Earned $100,000 in profit",
        "type": BadgeType.MILESTONE,
        "icon": "whale",
        "requirement": {"total_pnl": 100000},
    },

    # Streak badges
    "WIN_STREAK_5": {
        "name": "Hot Streak",
        "description": "5 consecutive winning trades",
        "type": BadgeType.STREAK,
        "icon": "fire",
        "requirement": {"win_streak": 5},
    },
    "WIN_STREAK_10": {
        "name": "On Fire",
        "description": "10 consecutive winning trades",
        "type": BadgeType.STREAK,
        "icon": "flame",
        "requirement": {"win_streak": 10},
    },
    "WIN_STREAK_20": {
        "name": "Unstoppable",
        "description": "20 consecutive winning trades",
        "type": BadgeType.STREAK,
        "icon": "star",
        "requirement": {"win_streak": 20},
    },

    # Skill badges
    "10X_GAIN": {
        "name": "10x Hunter",
        "description": "Achieved 10x gain on a single trade",
        "type": BadgeType.SKILL,
        "icon": "rocket",
        "requirement": {"trade_multiplier": 10},
    },
    "PERFECT_TRADER": {
        "name": "Perfectionist",
        "description": "100% win rate with 5+ trades",
        "type": BadgeType.SKILL,
        "icon": "target",
        "requirement": {"win_rate": 1.0, "trade_count": 5},
    },
    "CONSISTENT_TRADER": {
        "name": "Consistent Trader",
        "description": "Completed 20+ trades",
        "type": BadgeType.SKILL,
        "icon": "chart",
        "requirement": {"trade_count": 20},
    },

    # Explorer badges
    "EXPLORER": {
        "name": "Explorer",
        "description": "Analyzed 50+ different tokens",
        "type": BadgeType.EXPLORER,
        "icon": "compass",
        "requirement": {"unique_tokens_analyzed": 50},
    },
    "ALPHA_HUNTER": {
        "name": "Alpha Hunter",
        "description": "Discovered a token before 10x",
        "type": BadgeType.EXPLORER,
        "icon": "diamond",
        "requirement": {"alpha_discovery": True},
    },

    # Community badges
    "REFERRER_5": {
        "name": "Community Builder",
        "description": "Referred 5+ new users",
        "type": BadgeType.COMMUNITY,
        "icon": "people",
        "requirement": {"referral_count": 5},
    },
    "REFERRER_20": {
        "name": "Ambassador",
        "description": "Referred 20+ new users",
        "type": BadgeType.COMMUNITY,
        "icon": "megaphone",
        "requirement": {"referral_count": 20},
    },
    "VOTER": {
        "name": "Active Voter",
        "description": "Participated in 10+ community votes",
        "type": BadgeType.COMMUNITY,
        "icon": "ballot",
        "requirement": {"vote_count": 10},
    },
}


def init_achievements_db(db_path: str) -> sqlite3.Connection:
    """Initialize the achievements database schema."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # User badges table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            badge_id TEXT,
            earned_at TEXT,
            notified INTEGER DEFAULT 0,
            UNIQUE(user_id, badge_id)
        )
    """)

    # User stats for badge tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS badge_progress (
            user_id TEXT PRIMARY KEY,
            trade_count INTEGER DEFAULT 0,
            win_streak INTEGER DEFAULT 0,
            best_win_streak INTEGER DEFAULT 0,
            total_pnl REAL DEFAULT 0,
            win_rate REAL DEFAULT 0,
            unique_tokens_analyzed INTEGER DEFAULT 0,
            referral_count INTEGER DEFAULT 0,
            vote_count INTEGER DEFAULT 0,
            has_10x_trade INTEGER DEFAULT 0,
            has_alpha_discovery INTEGER DEFAULT 0,
            updated_at TEXT
        )
    """)

    conn.commit()
    return conn


class AchievementManager:
    """
    Manages achievement badges for users.

    Usage:
        manager = AchievementManager()

        # Check and award badges after trade
        badges = manager.check_and_award(
            user_id="user1",
            event="trade_complete",
            trade_count=1,
            total_pnl=150.0
        )

        # Get user's badges
        badges = manager.get_user_badges("user1")
    """

    def __init__(self, db_path: str = None):
        """Initialize achievement manager."""
        if db_path is None:
            data_dir = Path(os.getenv("DATA_DIR", "data"))
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "community" / "achievements.db")
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self.db_path = db_path
        self._conn = init_achievements_db(db_path)
        logger.info(f"Achievement manager initialized: {db_path}")

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # =========================================================================
    # Badge Checking and Awarding
    # =========================================================================

    def check_and_award(
        self,
        user_id: str,
        event: str,
        trade_count: int = None,
        total_pnl: float = None,
        win_rate: float = None,
        win_streak: int = None,
        trade_multiplier: float = None,
        unique_tokens_analyzed: int = None,
        referral_count: int = None,
        vote_count: int = None,
        token_multiplier_since_discovery: float = None,
    ) -> List[Dict[str, Any]]:
        """
        Check and award badges based on event and stats.

        Args:
            user_id: User identifier
            event: Event type (trade_complete, stats_update, alpha_discovery, etc.)
            trade_count: Total number of trades
            total_pnl: Total profit/loss
            win_rate: Win rate (0-1)
            win_streak: Current win streak
            trade_multiplier: Multiplier on a single trade (e.g., 10x)
            unique_tokens_analyzed: Number of unique tokens analyzed
            referral_count: Number of referrals
            vote_count: Number of votes cast
            token_multiplier_since_discovery: Token multiplier since user first analyzed it

        Returns:
            List of newly awarded badges
        """
        # Update progress tracking
        self._update_progress(
            user_id,
            trade_count=trade_count,
            total_pnl=total_pnl,
            win_rate=win_rate,
            win_streak=win_streak,
            trade_multiplier=trade_multiplier,
            unique_tokens_analyzed=unique_tokens_analyzed,
            referral_count=referral_count,
            vote_count=vote_count,
            token_multiplier_since_discovery=token_multiplier_since_discovery,
        )

        # Get user's current badges
        existing_badges = set(self.get_user_badges(user_id))

        # Check each badge definition
        new_badges = []

        for badge_id, definition in BADGE_DEFINITIONS.items():
            if badge_id in existing_badges:
                continue

            if self._check_badge_requirement(
                badge_id,
                definition["requirement"],
                trade_count=trade_count,
                total_pnl=total_pnl,
                win_rate=win_rate,
                win_streak=win_streak,
                trade_multiplier=trade_multiplier,
                unique_tokens_analyzed=unique_tokens_analyzed,
                referral_count=referral_count,
                vote_count=vote_count,
                token_multiplier_since_discovery=token_multiplier_since_discovery,
            ):
                # Award badge
                self._award_badge(user_id, badge_id)
                new_badges.append({
                    "badge_id": badge_id,
                    "name": definition["name"],
                    "description": definition["description"],
                    "icon": definition["icon"],
                })

        if new_badges:
            logger.info(f"Awarded {len(new_badges)} badges to {user_id}: {[b['badge_id'] for b in new_badges]}")

        return new_badges

    def _check_badge_requirement(
        self,
        badge_id: str,
        requirement: Dict[str, Any],
        **stats,
    ) -> bool:
        """Check if a badge requirement is met."""
        for key, threshold in requirement.items():
            # Special handling for specific requirements
            if key == "alpha_discovery":
                # Check if token multiplier is >= 10x
                multiplier = stats.get("token_multiplier_since_discovery")
                if multiplier is None or multiplier < 10:
                    return False
                continue  # Skip the normal check for this key

            if key == "trade_multiplier":
                # Check trade_multiplier for 10x badge
                multiplier = stats.get("trade_multiplier")
                if multiplier is None or multiplier < threshold:
                    return False
                continue

            value = stats.get(key)

            if value is None:
                return False

            if key == "win_rate" and "trade_count" in requirement:
                # For perfect trader, need both win_rate and trade_count
                if value < threshold:
                    return False
                trade_count = stats.get("trade_count", 0) or 0
                if trade_count < requirement["trade_count"]:
                    return False
            elif key == "trade_count" and badge_id == "PERFECT_TRADER":
                # Skip trade_count check here as it's part of win_rate check
                continue
            else:
                if value < threshold:
                    return False

        return True

    def _award_badge(self, user_id: str, badge_id: str) -> bool:
        """Award a badge to a user."""
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        try:
            cursor.execute("""
                INSERT INTO user_badges (user_id, badge_id, earned_at)
                VALUES (?, ?, ?)
            """, (user_id, badge_id, now))

            conn.commit()
            conn.close()
            return True

        except sqlite3.IntegrityError:
            # Badge already awarded
            conn.close()
            return False

    def _update_progress(
        self,
        user_id: str,
        **stats,
    ) -> None:
        """Update badge progress tracking."""
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        # Build update query dynamically
        # Track columns and values separately for proper SQL construction
        columns = []
        insert_values = []
        update_sets = []

        # Map stats to database columns
        col_map = {
            "trade_count": "trade_count",
            "total_pnl": "total_pnl",
            "win_rate": "win_rate",
            "win_streak": "win_streak",
            "unique_tokens_analyzed": "unique_tokens_analyzed",
            "referral_count": "referral_count",
            "vote_count": "vote_count",
        }

        for key, value in stats.items():
            if value is not None:
                if key in col_map:
                    col = col_map[key]
                    columns.append(col)
                    insert_values.append(value)
                    update_sets.append(f"{col} = excluded.{col}")

                elif key == "trade_multiplier" and value >= 10:
                    columns.append("has_10x_trade")
                    insert_values.append(1)
                    update_sets.append("has_10x_trade = 1")

                elif key == "token_multiplier_since_discovery" and value >= 10:
                    columns.append("has_alpha_discovery")
                    insert_values.append(1)
                    update_sets.append("has_alpha_discovery = 1")

        if not columns:
            conn.close()
            return

        # Add updated_at
        columns.append("updated_at")
        insert_values.append(now)
        update_sets.append("updated_at = excluded.updated_at")

        # Build SQL
        col_str = ", ".join(columns)
        placeholders = ", ".join("?" for _ in insert_values)
        update_str = ", ".join(update_sets)

        cursor.execute(f"""
            INSERT INTO badge_progress (user_id, {col_str})
            VALUES (?, {placeholders})
            ON CONFLICT(user_id) DO UPDATE SET {update_str}
        """, [user_id] + insert_values)

        conn.commit()
        conn.close()

    # =========================================================================
    # Badge Retrieval
    # =========================================================================

    def get_user_badges(self, user_id: str) -> List[str]:
        """Get list of badge IDs earned by user."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT badge_id FROM user_badges WHERE user_id = ?
        """, (user_id,))

        rows = cursor.fetchall()
        conn.close()

        return [row["badge_id"] for row in rows]

    def get_user_badges_detailed(self, user_id: str) -> List[Dict[str, Any]]:
        """Get detailed badge info for user."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT badge_id, earned_at FROM user_badges WHERE user_id = ?
        """, (user_id,))

        rows = cursor.fetchall()
        conn.close()

        badges = []
        for row in rows:
            badge_id = row["badge_id"]
            if badge_id in BADGE_DEFINITIONS:
                definition = BADGE_DEFINITIONS[badge_id]
                badges.append({
                    "badge_id": badge_id,
                    "name": definition["name"],
                    "description": definition["description"],
                    "icon": definition["icon"],
                    "type": definition["type"].value,
                    "earned_at": row["earned_at"],
                })

        return badges

    def get_badge_progress(self, user_id: str) -> Dict[str, Any]:
        """Get badge progress for a user."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM badge_progress WHERE user_id = ?
        """, (user_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return {}

    # =========================================================================
    # Notification Management
    # =========================================================================

    def get_unnotified_badges(self, user_id: str) -> List[Dict[str, Any]]:
        """Get badges that haven't been notified yet."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT badge_id, earned_at FROM user_badges
            WHERE user_id = ? AND notified = 0
        """, (user_id,))

        rows = cursor.fetchall()
        conn.close()

        badges = []
        for row in rows:
            badge_id = row["badge_id"]
            if badge_id in BADGE_DEFINITIONS:
                definition = BADGE_DEFINITIONS[badge_id]
                badges.append({
                    "badge_id": badge_id,
                    "name": definition["name"],
                    "description": definition["description"],
                    "icon": definition["icon"],
                    "earned_at": row["earned_at"],
                })

        return badges

    def mark_badge_notified(self, user_id: str, badge_id: str) -> bool:
        """Mark a badge as notified."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE user_badges SET notified = 1
            WHERE user_id = ? AND badge_id = ?
        """, (user_id, badge_id))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()

        return success

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_badge_stats(self) -> Dict[str, int]:
        """Get count of each badge awarded across all users."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT badge_id, COUNT(*) as count
            FROM user_badges
            GROUP BY badge_id
        """)

        rows = cursor.fetchall()
        conn.close()

        return {row["badge_id"]: row["count"] for row in rows}

    def get_rare_badges(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get the rarest badges (fewest users have them)."""
        stats = self.get_badge_stats()

        # Sort by count ascending
        sorted_badges = sorted(stats.items(), key=lambda x: x[1])[:limit]

        return [
            {
                "badge_id": badge_id,
                "name": BADGE_DEFINITIONS.get(badge_id, {}).get("name", badge_id),
                "count": count,
            }
            for badge_id, count in sorted_badges
        ]

    def export_achievements_json(self, filepath: str = None) -> str:
        """Export all achievements data to JSON."""
        if filepath is None:
            data_dir = Path(os.getenv("DATA_DIR", "data"))
            filepath = str(data_dir / "community" / "achievements" / "badges.json")

        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "badge_definitions": {
                k: {**v, "type": v["type"].value}
                for k, v in BADGE_DEFINITIONS.items()
            },
            "badge_stats": self.get_badge_stats(),
            "rare_badges": self.get_rare_badges(),
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Exported achievements to {filepath}")
        return filepath
