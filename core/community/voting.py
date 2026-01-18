"""
Community Voting System for Jarvis.

Features:
- Create polls for feature/token voting
- One vote per user per week
- Results publication
- Winning vote execution tracking

Vote types:
- Token to analyze next
- Strategy to promote
- Feature to build
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("jarvis.community.voting")


def init_voting_db(db_path: str) -> sqlite3.Connection:
    """Initialize the voting database schema."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Polls table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS polls (
            poll_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            options TEXT NOT NULL,
            poll_type TEXT DEFAULT 'feature',
            status TEXT DEFAULT 'active',
            duration_days INTEGER DEFAULT 7,
            start_date TEXT,
            end_date TEXT,
            created_at TEXT
        )
    """)

    # Votes table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            poll_id TEXT,
            user_id TEXT,
            option TEXT,
            voted_at TEXT,
            UNIQUE(poll_id, user_id),
            FOREIGN KEY(poll_id) REFERENCES polls(poll_id)
        )
    """)

    # User vote tracking (for weekly limit)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_vote_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            week_start TEXT,
            vote_count INTEGER DEFAULT 0,
            last_vote_at TEXT,
            UNIQUE(user_id, week_start)
        )
    """)

    # Poll results table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS poll_results (
            poll_id TEXT PRIMARY KEY,
            winner TEXT,
            results TEXT,
            total_votes INTEGER,
            finalized_at TEXT,
            action_taken INTEGER DEFAULT 0,
            FOREIGN KEY(poll_id) REFERENCES polls(poll_id)
        )
    """)

    conn.commit()
    return conn


class VotingManager:
    """
    Manages community voting polls.

    Usage:
        manager = VotingManager()

        # Create a poll
        poll = manager.create_poll(
            title="Which token to analyze?",
            options=["BONK", "WIF", "POPCAT"],
            duration_days=7
        )

        # Cast a vote
        result = manager.cast_vote(poll["poll_id"], "user1", "BONK")

        # Get results
        results = manager.get_results(poll["poll_id"])
    """

    def __init__(self, db_path: str = None):
        """Initialize voting manager."""
        if db_path is None:
            data_dir = Path(os.getenv("DATA_DIR", "data"))
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "community" / "voting.db")
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self.db_path = db_path
        self._conn = init_voting_db(db_path)
        self._bypass_weekly_limit = False  # For testing
        logger.info(f"Voting manager initialized: {db_path}")

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _generate_poll_id(self) -> str:
        """Generate unique poll ID."""
        import uuid
        return f"poll_{uuid.uuid4().hex[:8]}"

    def _get_week_start(self) -> str:
        """Get the start of the current week (Monday)."""
        now = datetime.now(timezone.utc)
        week_start = now - timedelta(days=now.weekday())
        return week_start.strftime("%Y-%m-%d")

    # =========================================================================
    # Poll Management
    # =========================================================================

    def create_poll(
        self,
        title: str,
        options: List[str],
        duration_days: int = 7,
        description: str = None,
        poll_type: str = "feature",
    ) -> Dict[str, Any]:
        """
        Create a new poll.

        Args:
            title: Poll question/title
            options: List of voting options
            duration_days: How long the poll runs
            description: Additional description
            poll_type: Type of poll (feature, token, strategy)

        Returns:
            Created poll dict
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        poll_id = self._generate_poll_id()
        now = datetime.now(timezone.utc)
        end_date = now + timedelta(days=duration_days)

        cursor.execute("""
            INSERT INTO polls (
                poll_id, title, description, options, poll_type,
                status, duration_days, start_date, end_date, created_at
            ) VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)
        """, (
            poll_id,
            title,
            description,
            json.dumps(options),
            poll_type,
            duration_days,
            now.isoformat(),
            end_date.isoformat(),
            now.isoformat(),
        ))

        conn.commit()
        conn.close()

        logger.info(f"Created poll: {title} ({poll_id})")
        return self.get_poll(poll_id)

    def get_poll(self, poll_id: str) -> Optional[Dict[str, Any]]:
        """Get poll by ID."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM polls WHERE poll_id = ?
        """, (poll_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            poll = dict(row)
            poll["options"] = json.loads(poll["options"])
            return poll

        return None

    def get_active_polls(self) -> List[Dict[str, Any]]:
        """Get all active polls."""
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        cursor.execute("""
            SELECT * FROM polls
            WHERE status = 'active' AND end_date >= ?
        """, (now,))

        rows = cursor.fetchall()
        conn.close()

        polls = []
        for row in rows:
            poll = dict(row)
            poll["options"] = json.loads(poll["options"])
            polls.append(poll)

        return polls

    # =========================================================================
    # Voting
    # =========================================================================

    def cast_vote(
        self,
        poll_id: str,
        user_id: str,
        option: str,
    ) -> Dict[str, Any]:
        """
        Cast a vote in a poll.

        Args:
            poll_id: Poll to vote in
            user_id: User casting the vote
            option: Option to vote for

        Returns:
            Result dict with success status
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc)

        # Check if poll exists and is active
        poll = self.get_poll(poll_id)
        if not poll:
            conn.close()
            return {"success": False, "message": "Poll not found"}

        if poll["status"] != "active":
            conn.close()
            return {"success": False, "message": "Poll is not active"}

        if option not in poll["options"]:
            conn.close()
            return {"success": False, "message": "Invalid option"}

        # Check weekly vote limit (unless bypassed for testing)
        if not self._bypass_weekly_limit:
            week_start = self._get_week_start()
            cursor.execute("""
                SELECT vote_count FROM user_vote_log
                WHERE user_id = ? AND week_start = ?
            """, (user_id, week_start))

            vote_log = cursor.fetchone()
            if vote_log and vote_log["vote_count"] >= 1:
                conn.close()
                return {"success": False, "message": "Weekly vote limit reached (1 vote per week)"}

        # Cast the vote
        try:
            cursor.execute("""
                INSERT INTO votes (poll_id, user_id, option, voted_at)
                VALUES (?, ?, ?, ?)
            """, (poll_id, user_id, option, now.isoformat()))

            # Update vote log
            if not self._bypass_weekly_limit:
                week_start = self._get_week_start()
                cursor.execute("""
                    INSERT INTO user_vote_log (user_id, week_start, vote_count, last_vote_at)
                    VALUES (?, ?, 1, ?)
                    ON CONFLICT(user_id, week_start) DO UPDATE SET
                        vote_count = vote_count + 1,
                        last_vote_at = excluded.last_vote_at
                """, (user_id, week_start, now.isoformat()))

            conn.commit()
            conn.close()

            logger.info(f"User {user_id} voted for '{option}' in poll {poll_id}")
            return {"success": True, "message": "Vote cast successfully"}

        except sqlite3.IntegrityError:
            conn.close()
            return {"success": False, "message": "Already voted in this poll"}

    def get_user_vote(self, poll_id: str, user_id: str) -> Optional[str]:
        """Get user's vote in a poll."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT option FROM votes WHERE poll_id = ? AND user_id = ?
        """, (poll_id, user_id))

        row = cursor.fetchone()
        conn.close()

        return row["option"] if row else None

    # =========================================================================
    # Results
    # =========================================================================

    def get_results(self, poll_id: str) -> Dict[str, int]:
        """
        Get voting results for a poll.

        Args:
            poll_id: Poll ID

        Returns:
            Dict mapping options to vote counts
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        # Get poll options
        poll = self.get_poll(poll_id)
        if not poll:
            conn.close()
            return {}

        # Initialize results with 0 for each option
        results = {option: 0 for option in poll["options"]}

        # Count votes
        cursor.execute("""
            SELECT option, COUNT(*) as count
            FROM votes
            WHERE poll_id = ?
            GROUP BY option
        """, (poll_id,))

        rows = cursor.fetchall()
        conn.close()

        for row in rows:
            results[row["option"]] = row["count"]

        return results

    def get_total_votes(self, poll_id: str) -> int:
        """Get total number of votes in a poll."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) as total FROM votes WHERE poll_id = ?
        """, (poll_id,))

        row = cursor.fetchone()
        conn.close()

        return row["total"] if row else 0

    def get_winner(self, poll_id: str) -> Optional[str]:
        """Get the winning option of a poll."""
        results = self.get_results(poll_id)
        if not results:
            return None

        return max(results, key=results.get)

    # =========================================================================
    # Poll Finalization
    # =========================================================================

    def finalize_poll(self, poll_id: str) -> Dict[str, Any]:
        """
        Finalize a poll and record results.

        Args:
            poll_id: Poll to finalize

        Returns:
            Final results
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        # Update poll status
        cursor.execute("""
            UPDATE polls SET status = 'closed' WHERE poll_id = ?
        """, (poll_id,))

        # Get results
        results = self.get_results(poll_id)
        winner = max(results, key=results.get) if results else None
        total_votes = sum(results.values())

        # Store results
        cursor.execute("""
            INSERT INTO poll_results (
                poll_id, winner, results, total_votes, finalized_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(poll_id) DO UPDATE SET
                winner = excluded.winner,
                results = excluded.results,
                total_votes = excluded.total_votes,
                finalized_at = excluded.finalized_at
        """, (poll_id, winner, json.dumps(results), total_votes, now))

        conn.commit()
        conn.close()

        logger.info(f"Poll {poll_id} finalized. Winner: {winner} with {total_votes} total votes")

        return {
            "poll_id": poll_id,
            "winner": winner,
            "results": results,
            "total_votes": total_votes,
        }

    def get_finalized_results(self, poll_id: str) -> Optional[Dict[str, Any]]:
        """Get finalized poll results."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM poll_results WHERE poll_id = ?
        """, (poll_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            result = dict(row)
            result["results"] = json.loads(result["results"])
            return result

        return None

    # =========================================================================
    # Weekly Results
    # =========================================================================

    def get_weekly_results(self) -> List[Dict[str, Any]]:
        """Get all polls finalized this week."""
        conn = self._get_conn()
        cursor = conn.cursor()

        week_start = self._get_week_start()

        cursor.execute("""
            SELECT pr.*, p.title, p.poll_type
            FROM poll_results pr
            JOIN polls p ON pr.poll_id = p.poll_id
            WHERE pr.finalized_at >= ?
        """, (week_start,))

        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            result = dict(row)
            result["results"] = json.loads(result["results"])
            results.append(result)

        return results

    def get_user_weekly_votes(self, user_id: str) -> int:
        """Get number of votes a user has cast this week."""
        conn = self._get_conn()
        cursor = conn.cursor()

        week_start = self._get_week_start()

        cursor.execute("""
            SELECT vote_count FROM user_vote_log
            WHERE user_id = ? AND week_start = ?
        """, (user_id, week_start))

        row = cursor.fetchone()
        conn.close()

        return row["vote_count"] if row else 0
