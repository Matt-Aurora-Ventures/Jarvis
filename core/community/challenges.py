"""
Community Challenges System for Jarvis.

Monthly challenges:
- "Bull Run": Highest % gain
- "Stability": Lowest drawdown
- "Consistency": Highest number of winning trades

Features:
- Create and manage challenges
- User registration for challenges
- Score tracking and updates
- Challenge-specific leaderboards
- Prizes: featured profile, special badge, bonus credit
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("jarvis.community.challenges")


def init_challenges_db(db_path: str) -> sqlite3.Connection:
    """Initialize the challenges database schema."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Challenges table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS challenges (
            challenge_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            metric TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            prizes TEXT,
            rules TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT
        )
    """)

    # Challenge participants table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS challenge_participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            challenge_id TEXT,
            user_id TEXT,
            username TEXT,
            score REAL DEFAULT 0,
            rank INTEGER,
            registered_at TEXT,
            updated_at TEXT,
            UNIQUE(challenge_id, user_id),
            FOREIGN KEY(challenge_id) REFERENCES challenges(challenge_id)
        )
    """)

    # Challenge winners table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS challenge_winners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            challenge_id TEXT,
            user_id TEXT,
            rank INTEGER,
            score REAL,
            prize TEXT,
            awarded_at TEXT,
            FOREIGN KEY(challenge_id) REFERENCES challenges(challenge_id)
        )
    """)

    conn.commit()
    return conn


class ChallengeManager:
    """
    Manages community challenges.

    Usage:
        manager = ChallengeManager()

        # Create a challenge
        challenge = manager.create_challenge(
            title="Bull Run January",
            description="Highest % gain wins",
            metric="percent_gain",
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=30)
        )

        # Register user
        manager.register(challenge["challenge_id"], "user1")

        # Update score
        manager.update_score(challenge["challenge_id"], "user1", 150.5)

        # Get leaderboard
        lb = manager.get_challenge_leaderboard(challenge["challenge_id"])
    """

    def __init__(self, db_path: str = None):
        """Initialize challenge manager."""
        if db_path is None:
            data_dir = Path(os.getenv("DATA_DIR", "data"))
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "community" / "challenges.db")
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self.db_path = db_path
        self._conn = init_challenges_db(db_path)
        logger.info(f"Challenge manager initialized: {db_path}")

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _generate_challenge_id(self) -> str:
        """Generate unique challenge ID."""
        import uuid
        return f"ch_{uuid.uuid4().hex[:8]}"

    # =========================================================================
    # Challenge Management
    # =========================================================================

    def create_challenge(
        self,
        title: str,
        metric: str,
        start_date: datetime,
        end_date: datetime,
        description: str = None,
        prizes: List[str] = None,
        rules: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new challenge.

        Args:
            title: Challenge title
            metric: What metric to track (profit, percent_gain, win_count, drawdown)
            start_date: When challenge starts
            end_date: When challenge ends
            description: Challenge description
            prizes: List of prizes for top 3
            rules: List of rules

        Returns:
            Created challenge dict
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        challenge_id = self._generate_challenge_id()
        now = datetime.now(timezone.utc).isoformat()

        cursor.execute("""
            INSERT INTO challenges (
                challenge_id, title, description, metric,
                start_date, end_date, prizes, rules, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)
        """, (
            challenge_id,
            title,
            description,
            metric,
            start_date.isoformat(),
            end_date.isoformat(),
            json.dumps(prizes or ["Featured Profile", "Special Badge", "100 Credits"]),
            json.dumps(rules or []),
            now,
        ))

        conn.commit()
        conn.close()

        logger.info(f"Created challenge: {title} ({challenge_id})")
        return self.get_challenge(challenge_id)

    def get_challenge(self, challenge_id: str) -> Optional[Dict[str, Any]]:
        """Get challenge by ID."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM challenges WHERE challenge_id = ?
        """, (challenge_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            challenge = dict(row)
            challenge["prizes"] = json.loads(challenge["prizes"]) if challenge["prizes"] else []
            challenge["rules"] = json.loads(challenge["rules"]) if challenge["rules"] else []
            return challenge

        return None

    def get_active_challenges(self) -> List[Dict[str, Any]]:
        """Get all active challenges."""
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        cursor.execute("""
            SELECT * FROM challenges
            WHERE status = 'active' AND start_date <= ? AND end_date >= ?
        """, (now, now))

        rows = cursor.fetchall()
        conn.close()

        challenges = []
        for row in rows:
            challenge = dict(row)
            challenge["prizes"] = json.loads(challenge["prizes"]) if challenge["prizes"] else []
            challenge["rules"] = json.loads(challenge["rules"]) if challenge["rules"] else []
            challenges.append(challenge)

        return challenges

    # =========================================================================
    # Participant Management
    # =========================================================================

    def register(
        self,
        challenge_id: str,
        user_id: str,
        username: str = None,
    ) -> Dict[str, Any]:
        """
        Register a user for a challenge.

        Args:
            challenge_id: Challenge to register for
            user_id: User's ID
            username: Display name

        Returns:
            Registration result
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        # Check if challenge exists and is active
        cursor.execute("""
            SELECT status, start_date, end_date FROM challenges
            WHERE challenge_id = ?
        """, (challenge_id,))

        challenge = cursor.fetchone()
        if not challenge:
            conn.close()
            return {"success": False, "message": "Challenge not found"}

        if challenge["status"] != "active":
            conn.close()
            return {"success": False, "message": "Challenge is not active"}

        try:
            cursor.execute("""
                INSERT INTO challenge_participants (
                    challenge_id, user_id, username, score, registered_at, updated_at
                ) VALUES (?, ?, ?, 0, ?, ?)
            """, (challenge_id, user_id, username or "Anonymous", now, now))

            conn.commit()
            conn.close()

            logger.info(f"User {user_id} registered for challenge {challenge_id}")
            return {"success": True, "message": "Successfully registered"}

        except sqlite3.IntegrityError:
            conn.close()
            return {"success": False, "message": "Already registered for this challenge"}

    def update_score(
        self,
        challenge_id: str,
        user_id: str,
        score: float,
    ) -> bool:
        """
        Update a participant's score.

        Args:
            challenge_id: Challenge ID
            user_id: Participant's ID
            score: New score value

        Returns:
            True if updated successfully
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        cursor.execute("""
            UPDATE challenge_participants
            SET score = ?, updated_at = ?
            WHERE challenge_id = ? AND user_id = ?
        """, (score, now, challenge_id, user_id))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()

        if success:
            # Update ranks
            self._update_ranks(challenge_id)

        return success

    def _update_ranks(self, challenge_id: str) -> None:
        """Update participant ranks based on scores."""
        conn = self._get_conn()
        cursor = conn.cursor()

        # Get challenge metric to determine sort order
        cursor.execute("""
            SELECT metric FROM challenges WHERE challenge_id = ?
        """, (challenge_id,))

        challenge = cursor.fetchone()
        if not challenge:
            conn.close()
            return

        # For drawdown, lower is better; for everything else, higher is better
        order = "ASC" if challenge["metric"] == "drawdown" else "DESC"

        # Get participants ordered by score
        cursor.execute(f"""
            SELECT user_id FROM challenge_participants
            WHERE challenge_id = ?
            ORDER BY score {order}
        """, (challenge_id,))

        rows = cursor.fetchall()

        # Update ranks
        for rank, row in enumerate(rows, 1):
            cursor.execute("""
                UPDATE challenge_participants
                SET rank = ?
                WHERE challenge_id = ? AND user_id = ?
            """, (rank, challenge_id, row["user_id"]))

        conn.commit()
        conn.close()

    # =========================================================================
    # Leaderboard
    # =========================================================================

    def get_challenge_leaderboard(
        self,
        challenge_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get challenge leaderboard.

        Args:
            challenge_id: Challenge ID
            limit: Maximum number of results

        Returns:
            List of participants sorted by rank
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        # First update ranks
        self._update_ranks(challenge_id)

        cursor.execute("""
            SELECT user_id, username, score, rank
            FROM challenge_participants
            WHERE challenge_id = ?
            ORDER BY rank ASC
            LIMIT ?
        """, (challenge_id, limit))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_user_challenges(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all challenges a user is participating in."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT c.*, cp.score, cp.rank
            FROM challenges c
            JOIN challenge_participants cp ON c.challenge_id = cp.challenge_id
            WHERE cp.user_id = ?
        """, (user_id,))

        rows = cursor.fetchall()
        conn.close()

        challenges = []
        for row in rows:
            challenge = dict(row)
            challenge["prizes"] = json.loads(challenge["prizes"]) if challenge["prizes"] else []
            challenge["rules"] = json.loads(challenge["rules"]) if challenge["rules"] else []
            challenges.append(challenge)

        return challenges

    # =========================================================================
    # Challenge Completion
    # =========================================================================

    def finalize_challenge(self, challenge_id: str) -> List[Dict[str, Any]]:
        """
        Finalize a challenge and determine winners.

        Args:
            challenge_id: Challenge to finalize

        Returns:
            List of winners with prizes
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        # Get challenge info
        challenge = self.get_challenge(challenge_id)
        if not challenge:
            conn.close()
            return []

        # Update challenge status
        cursor.execute("""
            UPDATE challenges SET status = 'completed'
            WHERE challenge_id = ?
        """, (challenge_id,))

        # Get top 3 participants
        lb = self.get_challenge_leaderboard(challenge_id, limit=3)

        winners = []
        prizes = challenge.get("prizes", [])

        for i, participant in enumerate(lb):
            prize = prizes[i] if i < len(prizes) else None

            cursor.execute("""
                INSERT INTO challenge_winners (
                    challenge_id, user_id, rank, score, prize, awarded_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                challenge_id,
                participant["user_id"],
                participant["rank"],
                participant["score"],
                prize,
                now,
            ))

            winners.append({
                "user_id": participant["user_id"],
                "username": participant["username"],
                "rank": participant["rank"],
                "score": participant["score"],
                "prize": prize,
            })

        conn.commit()
        conn.close()

        logger.info(f"Challenge {challenge_id} finalized with {len(winners)} winners")
        return winners

    def get_challenge_winners(self, challenge_id: str) -> List[Dict[str, Any]]:
        """Get winners of a completed challenge."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM challenge_winners
            WHERE challenge_id = ?
            ORDER BY rank ASC
        """, (challenge_id,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    # =========================================================================
    # Templates
    # =========================================================================

    def create_monthly_challenges(self) -> List[Dict[str, Any]]:
        """Create standard monthly challenges."""
        now = datetime.now(timezone.utc)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Calculate end of month
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1) - timedelta(seconds=1)
        else:
            end = start.replace(month=start.month + 1) - timedelta(seconds=1)

        month_name = start.strftime("%B")

        challenges = []

        # Bull Run - highest % gain
        challenges.append(self.create_challenge(
            title=f"Bull Run {month_name}",
            description=f"Achieve the highest percentage gain in {month_name}",
            metric="percent_gain",
            start_date=start,
            end_date=end,
            prizes=["Featured Profile + Gold Badge", "Silver Badge", "Bronze Badge"],
            rules=[
                "Only trades made during the challenge period count",
                "Minimum 5 trades required to qualify",
                "Percentage gain calculated from starting portfolio value",
            ],
        ))

        # Stability - lowest drawdown
        challenges.append(self.create_challenge(
            title=f"Rock Solid {month_name}",
            description=f"Maintain the lowest drawdown in {month_name}",
            metric="drawdown",
            start_date=start,
            end_date=end,
            prizes=["Featured Profile + Stability Badge", "Silver Badge", "Bronze Badge"],
            rules=[
                "Minimum 10 trades required",
                "Drawdown measured from peak to trough",
            ],
        ))

        # Consistency - most winning trades
        challenges.append(self.create_challenge(
            title=f"Winning Machine {month_name}",
            description=f"Execute the most winning trades in {month_name}",
            metric="win_count",
            start_date=start,
            end_date=end,
            prizes=["Featured Profile + Consistency Badge", "Silver Badge", "Bronze Badge"],
            rules=[
                "Only winning trades (positive PnL) count",
                "No minimum trade size",
            ],
        ))

        return challenges
