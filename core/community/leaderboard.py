"""
Leaderboard System for Jarvis Community.

Tracks and ranks users by:
- Profit: total PnL across all trades
- Win rate: % of winning trades
- Consistency: Sharpe ratio, max drawdown
- Trades: total number of trades executed

Rankings:
- Overall: ranked by profit (all-time)
- Monthly: monthly winners
- Weekly: weekly hot traders

Features:
- Referral code generation and tracking
- Commission calculation for referrals
- Privacy-aware (optional public profiles)
"""

import hashlib
import json
import logging
import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("jarvis.community.leaderboard")


def init_leaderboard_db(db_path: str) -> sqlite3.Connection:
    """Initialize the leaderboard database schema."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # User stats table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_stats (
            user_id TEXT PRIMARY KEY,
            username TEXT,
            total_pnl REAL DEFAULT 0,
            win_rate REAL DEFAULT 0,
            total_trades INTEGER DEFAULT 0,
            sharpe_ratio REAL DEFAULT 0,
            max_drawdown REAL DEFAULT 0,
            unique_tokens_analyzed INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    # Weekly stats table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS weekly_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            username TEXT,
            week_start TEXT,
            total_pnl REAL DEFAULT 0,
            win_rate REAL DEFAULT 0,
            total_trades INTEGER DEFAULT 0,
            created_at TEXT,
            UNIQUE(user_id, week_start)
        )
    """)

    # Monthly stats table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS monthly_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            username TEXT,
            month_start TEXT,
            total_pnl REAL DEFAULT 0,
            win_rate REAL DEFAULT 0,
            total_trades INTEGER DEFAULT 0,
            created_at TEXT,
            UNIQUE(user_id, month_start)
        )
    """)

    # Referral codes table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS referral_codes (
            code TEXT PRIMARY KEY,
            user_id TEXT UNIQUE,
            created_at TEXT
        )
    """)

    # Referrals tracking table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id TEXT,
            referred_id TEXT UNIQUE,
            referral_code TEXT,
            created_at TEXT,
            FOREIGN KEY(referral_code) REFERENCES referral_codes(code)
        )
    """)

    # Referral commissions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS referral_commissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id TEXT,
            referred_id TEXT,
            trade_pnl REAL,
            commission REAL,
            is_ambassador INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)

    conn.commit()
    return conn


class Leaderboard:
    """
    Manages community leaderboard rankings and referrals.

    Usage:
        lb = Leaderboard()

        # Update user stats after trade
        lb.update_user_stats(
            user_id="user1",
            username="trader_pro",
            total_pnl=1500.0,
            win_rate=0.75,
            total_trades=10
        )

        # Get rankings
        top_traders = lb.get_rankings(by="profit", limit=10)

        # Referral tracking
        code = lb.generate_referral_code("user1")
        lb.track_referral("user1", "new_user", code)
    """

    def __init__(self, db_path: str = None):
        """Initialize leaderboard manager."""
        if db_path is None:
            data_dir = Path(os.getenv("DATA_DIR", "data"))
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "community" / "leaderboard.db")
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self.db_path = db_path
        self._conn = init_leaderboard_db(db_path)
        logger.info(f"Leaderboard initialized: {db_path}")

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_week_start(self) -> str:
        """Get the start of the current week (Monday)."""
        now = datetime.now(timezone.utc)
        week_start = now - timedelta(days=now.weekday())
        return week_start.strftime("%Y-%m-%d")

    def _get_month_start(self) -> str:
        """Get the start of the current month."""
        now = datetime.now(timezone.utc)
        return now.strftime("%Y-%m-01")

    # =========================================================================
    # User Stats Management
    # =========================================================================

    def update_user_stats(
        self,
        user_id: str,
        username: str,
        total_pnl: float = 0,
        win_rate: float = 0,
        total_trades: int = 0,
        sharpe_ratio: float = 0,
        max_drawdown: float = 0,
        unique_tokens_analyzed: int = 0,
        period: str = "overall",
    ) -> Dict[str, Any]:
        """
        Update user statistics.

        Args:
            user_id: Unique user identifier
            username: Display name
            total_pnl: Total profit/loss
            win_rate: Win rate (0-1)
            total_trades: Number of trades
            sharpe_ratio: Sharpe ratio for consistency
            max_drawdown: Maximum drawdown percentage
            unique_tokens_analyzed: Number of unique tokens analyzed
            period: "overall", "weekly", or "monthly"

        Returns:
            Updated stats dict
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        if period == "overall":
            # Upsert overall stats
            cursor.execute("""
                INSERT INTO user_stats (
                    user_id, username, total_pnl, win_rate, total_trades,
                    sharpe_ratio, max_drawdown, unique_tokens_analyzed,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    total_pnl = excluded.total_pnl,
                    win_rate = excluded.win_rate,
                    total_trades = excluded.total_trades,
                    sharpe_ratio = excluded.sharpe_ratio,
                    max_drawdown = excluded.max_drawdown,
                    unique_tokens_analyzed = excluded.unique_tokens_analyzed,
                    updated_at = excluded.updated_at
            """, (
                user_id, username, total_pnl, win_rate, total_trades,
                sharpe_ratio, max_drawdown, unique_tokens_analyzed,
                now, now
            ))

        elif period == "weekly":
            week_start = self._get_week_start()
            cursor.execute("""
                INSERT INTO weekly_stats (
                    user_id, username, week_start, total_pnl, win_rate,
                    total_trades, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, week_start) DO UPDATE SET
                    username = excluded.username,
                    total_pnl = excluded.total_pnl,
                    win_rate = excluded.win_rate,
                    total_trades = excluded.total_trades
            """, (
                user_id, username, week_start, total_pnl, win_rate,
                total_trades, now
            ))

        elif period == "monthly":
            month_start = self._get_month_start()
            cursor.execute("""
                INSERT INTO monthly_stats (
                    user_id, username, month_start, total_pnl, win_rate,
                    total_trades, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, month_start) DO UPDATE SET
                    username = excluded.username,
                    total_pnl = excluded.total_pnl,
                    win_rate = excluded.win_rate,
                    total_trades = excluded.total_trades
            """, (
                user_id, username, month_start, total_pnl, win_rate,
                total_trades, now
            ))

        conn.commit()
        conn.close()

        return self.get_user_stats(user_id)

    def get_user_stats(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get stats for a specific user."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM user_stats WHERE user_id = ?
        """, (user_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    # =========================================================================
    # Rankings
    # =========================================================================

    def get_rankings(
        self,
        by: str = "profit",
        period: str = "overall",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get leaderboard rankings.

        Args:
            by: Ranking metric - "profit", "win_rate", "trades", "consistency"
            period: "overall", "weekly", or "monthly"
            limit: Maximum number of results

        Returns:
            List of ranked users with stats
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        # Map ranking metric to column
        column_map = {
            "profit": "total_pnl",
            "win_rate": "win_rate",
            "trades": "total_trades",
            "consistency": "sharpe_ratio",
        }
        order_column = column_map.get(by, "total_pnl")

        if period == "overall":
            cursor.execute(f"""
                SELECT * FROM user_stats
                ORDER BY {order_column} DESC
                LIMIT ?
            """, (limit,))

        elif period == "weekly":
            week_start = self._get_week_start()
            cursor.execute(f"""
                SELECT * FROM weekly_stats
                WHERE week_start = ?
                ORDER BY {order_column} DESC
                LIMIT ?
            """, (week_start, limit))

        elif period == "monthly":
            month_start = self._get_month_start()
            cursor.execute(f"""
                SELECT * FROM monthly_stats
                WHERE month_start = ?
                ORDER BY {order_column} DESC
                LIMIT ?
            """, (month_start, limit))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    # =========================================================================
    # Referral System
    # =========================================================================

    def generate_referral_code(self, user_id: str) -> str:
        """
        Generate a unique referral code for a user.

        Args:
            user_id: User's unique identifier

        Returns:
            Unique referral code (6-8 characters)
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        # Check if user already has a code
        cursor.execute("""
            SELECT code FROM referral_codes WHERE user_id = ?
        """, (user_id,))

        existing = cursor.fetchone()
        if existing:
            conn.close()
            return existing["code"]

        # Generate new code
        # Use hash of user_id + random bytes for uniqueness
        random_part = secrets.token_hex(3)  # 6 hex chars
        hash_part = hashlib.sha256(f"{user_id}{random_part}".encode()).hexdigest()[:2]
        code = f"{random_part}{hash_part}".upper()

        now = datetime.now(timezone.utc).isoformat()

        cursor.execute("""
            INSERT INTO referral_codes (code, user_id, created_at)
            VALUES (?, ?, ?)
        """, (code, user_id, now))

        conn.commit()
        conn.close()

        logger.info(f"Generated referral code {code} for user {user_id}")
        return code

    def track_referral(
        self,
        referrer_id: str,
        referred_id: str,
        referral_code: str,
    ) -> Dict[str, Any]:
        """
        Track a new referral.

        Args:
            referrer_id: User who made the referral
            referred_id: New user who was referred
            referral_code: The referral code used

        Returns:
            Result dict with success status
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        # Verify referral code belongs to referrer
        cursor.execute("""
            SELECT user_id FROM referral_codes WHERE code = ?
        """, (referral_code,))

        code_owner = cursor.fetchone()
        if not code_owner or code_owner["user_id"] != referrer_id:
            conn.close()
            return {"success": False, "message": "Invalid referral code"}

        # Check if referred user already exists
        cursor.execute("""
            SELECT id FROM referrals WHERE referred_id = ?
        """, (referred_id,))

        if cursor.fetchone():
            conn.close()
            return {"success": False, "message": "User already referred"}

        now = datetime.now(timezone.utc).isoformat()

        cursor.execute("""
            INSERT INTO referrals (referrer_id, referred_id, referral_code, created_at)
            VALUES (?, ?, ?, ?)
        """, (referrer_id, referred_id, referral_code, now))

        conn.commit()
        conn.close()

        logger.info(f"Tracked referral: {referrer_id} -> {referred_id}")
        return {"success": True, "message": "Referral tracked successfully"}

    def get_referral_count(self, user_id: str) -> int:
        """Get the number of referrals for a user."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) as count FROM referrals WHERE referrer_id = ?
        """, (user_id,))

        result = cursor.fetchone()
        conn.close()

        return result["count"] if result else 0

    def calculate_referral_commission(
        self,
        referrer_id: str,
        referred_trade_pnl: float,
        is_ambassador: bool = False,
    ) -> float:
        """
        Calculate referral commission.

        Args:
            referrer_id: User who made the referral
            referred_trade_pnl: PnL from referred user's trade
            is_ambassador: Whether referrer is an ambassador (15% vs 10%)

        Returns:
            Commission amount
        """
        # Only positive trades generate commission
        if referred_trade_pnl <= 0:
            return 0.0

        commission_rate = 0.15 if is_ambassador else 0.10
        commission = referred_trade_pnl * commission_rate

        # Log commission (optional: store in database)
        logger.debug(f"Commission for {referrer_id}: {commission} ({commission_rate*100}%)")

        return commission

    def get_referral_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get comprehensive referral statistics for a user.

        Returns:
            Dict with referral count, total commission earned, etc.
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        # Get referral count
        cursor.execute("""
            SELECT COUNT(*) as count FROM referrals WHERE referrer_id = ?
        """, (user_id,))
        count_row = cursor.fetchone()
        referral_count = count_row["count"] if count_row else 0

        # Get total commissions
        cursor.execute("""
            SELECT SUM(commission) as total FROM referral_commissions
            WHERE referrer_id = ?
        """, (user_id,))
        comm_row = cursor.fetchone()
        total_commission = comm_row["total"] if comm_row and comm_row["total"] else 0.0

        # Get referral code
        cursor.execute("""
            SELECT code FROM referral_codes WHERE user_id = ?
        """, (user_id,))
        code_row = cursor.fetchone()
        referral_code = code_row["code"] if code_row else None

        conn.close()

        return {
            "referral_code": referral_code,
            "referral_count": referral_count,
            "total_commission": total_commission,
        }

    def export_leaderboard_json(self, filepath: str = None) -> str:
        """
        Export leaderboard data to JSON file.

        Args:
            filepath: Output path (defaults to data/community/leaderboard.json)

        Returns:
            Path to exported file
        """
        if filepath is None:
            data_dir = Path(os.getenv("DATA_DIR", "data"))
            filepath = str(data_dir / "community" / "leaderboard.json")

        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        # Get all rankings
        overall = self.get_rankings(by="profit", period="overall", limit=100)
        weekly = self.get_rankings(by="profit", period="weekly", limit=10)
        monthly = self.get_rankings(by="profit", period="monthly", limit=10)

        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "overall_top_100": overall,
            "weekly_top_10": weekly,
            "monthly_top_10": monthly,
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Exported leaderboard to {filepath}")
        return filepath
