"""
Persistent Conversation Memory for JARVIS Telegram Bot.

Features:
- SQLite-based persistent storage across sessions
- Conversation history with user tracking
- User relationship/context tracking
- Important facts and preferences storage
- Automatic history pruning

This maintains JARVIS's memory across restarts, enabling:
"Remember this conversation and all context. Maintain awareness of our
ongoing discussion, previous topics, and the group dynamic. Reference
past messages naturally when relevant. Keep track of who said what and when."
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# Database location
DB_DIR = Path(os.path.expanduser("~/.lifeos/jarvis"))
DB_PATH = DB_DIR / "conversation_memory.db"

# Configuration
MAX_HISTORY_ENTRIES = 1000  # Per chat
MAX_CONTEXT_WINDOW = 50  # Messages to load for context
USER_FACT_LIMIT = 20  # Facts per user


class ConversationMemory:
    """Persistent conversation memory using SQLite."""

    _instance: Optional["ConversationMemory"] = None

    def __new__(cls):
        """Singleton pattern to ensure single DB connection."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._conn: Optional[sqlite3.Connection] = None
        self._init_database()
        self._initialized = True
        logger.info(f"ConversationMemory initialized: {DB_PATH}")

    def _init_database(self):
        """Initialize the database schema."""
        try:
            DB_DIR.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row

            # Create tables
            self._conn.executescript("""
                -- Chat history table
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER,
                    username TEXT,
                    message TEXT NOT NULL,
                    is_jarvis BOOLEAN DEFAULT FALSE,
                    timestamp TEXT NOT NULL,
                    message_type TEXT DEFAULT 'text',
                    UNIQUE(chat_id, user_id, timestamp, message)
                );

                -- Index for fast lookups
                CREATE INDEX IF NOT EXISTS idx_chat_history_chat
                ON chat_history(chat_id, timestamp DESC);

                -- User facts/preferences table
                CREATE TABLE IF NOT EXISTS user_facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER,
                    fact_type TEXT NOT NULL,
                    fact_content TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id, chat_id, fact_type, fact_content)
                );

                -- Index for user facts
                CREATE INDEX IF NOT EXISTS idx_user_facts_user
                ON user_facts(user_id, chat_id);

                -- Chat state/topics table
                CREATE TABLE IF NOT EXISTS chat_state (
                    chat_id INTEGER PRIMARY KEY,
                    chat_name TEXT,
                    recent_topics TEXT,
                    mood TEXT DEFAULT 'neutral',
                    active_users TEXT,
                    last_jarvis_message TEXT,
                    last_active TEXT,
                    total_messages INTEGER DEFAULT 0
                );

                -- User relationships table
                CREATE TABLE IF NOT EXISTS user_relationships (
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    first_seen TEXT,
                    last_seen TEXT,
                    message_count INTEGER DEFAULT 0,
                    is_admin BOOLEAN DEFAULT FALSE,
                    is_friendly BOOLEAN DEFAULT TRUE,
                    nickname TEXT,
                    PRIMARY KEY (user_id, chat_id)
                );
            """)
            self._conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def save_message(
        self,
        chat_id: int,
        message: str,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        is_jarvis: bool = False,
        message_type: str = "text"
    ) -> bool:
        """Save a message to persistent history."""
        try:
            timestamp = datetime.now(timezone.utc).isoformat()

            # Insert message
            self._conn.execute("""
                INSERT OR IGNORE INTO chat_history
                (chat_id, user_id, username, message, is_jarvis, timestamp, message_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (chat_id, user_id, username, message[:2000], is_jarvis, timestamp, message_type))

            # Update chat state
            self._conn.execute("""
                INSERT INTO chat_state (chat_id, last_active, total_messages)
                VALUES (?, ?, 1)
                ON CONFLICT(chat_id) DO UPDATE SET
                    last_active = excluded.last_active,
                    total_messages = total_messages + 1
            """, (chat_id, timestamp))

            # Update user relationship
            if user_id:
                self._conn.execute("""
                    INSERT INTO user_relationships (user_id, chat_id, first_seen, last_seen, message_count)
                    VALUES (?, ?, ?, ?, 1)
                    ON CONFLICT(user_id, chat_id) DO UPDATE SET
                        last_seen = excluded.last_seen,
                        message_count = message_count + 1
                """, (user_id, chat_id, timestamp, timestamp))

            self._conn.commit()

            # Prune old entries periodically
            self._maybe_prune(chat_id)
            return True
        except Exception as e:
            logger.error(f"Failed to save message: {e}")
            return False

    def get_history(
        self,
        chat_id: int,
        limit: int = MAX_CONTEXT_WINDOW,
        hours_back: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Get conversation history for a chat."""
        try:
            if hours_back:
                cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).isoformat()
                cursor = self._conn.execute("""
                    SELECT * FROM chat_history
                    WHERE chat_id = ? AND timestamp > ?
                    ORDER BY timestamp DESC LIMIT ?
                """, (chat_id, cutoff, limit))
            else:
                cursor = self._conn.execute("""
                    SELECT * FROM chat_history
                    WHERE chat_id = ?
                    ORDER BY timestamp DESC LIMIT ?
                """, (chat_id, limit))

            rows = cursor.fetchall()
            # Reverse to get chronological order
            return [dict(row) for row in reversed(rows)]
        except Exception as e:
            logger.error(f"Failed to get history: {e}")
            return []

    def get_context_string(self, chat_id: int, limit: int = 20) -> str:
        """Get formatted conversation context for LLM prompt."""
        history = self.get_history(chat_id, limit)
        if not history:
            return ""

        lines = []
        for msg in history:
            speaker = "JARVIS" if msg.get("is_jarvis") else (msg.get("username") or "User")
            text = msg.get("message", "")[:200]
            lines.append(f"{speaker}: {text}")

        return "\n".join(lines)

    def save_user_fact(
        self,
        user_id: int,
        fact_type: str,
        fact_content: str,
        chat_id: Optional[int] = None,
        confidence: float = 1.0
    ) -> bool:
        """Save a fact about a user (preference, info, etc.)."""
        try:
            timestamp = datetime.now(timezone.utc).isoformat()
            self._conn.execute("""
                INSERT INTO user_facts (user_id, chat_id, fact_type, fact_content, confidence, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, chat_id, fact_type, fact_content) DO UPDATE SET
                    confidence = excluded.confidence,
                    updated_at = excluded.updated_at
            """, (user_id, chat_id, fact_type, fact_content, confidence, timestamp, timestamp))
            self._conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save user fact: {e}")
            return False

    def get_user_facts(self, user_id: int, chat_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all facts about a user."""
        try:
            if chat_id:
                cursor = self._conn.execute("""
                    SELECT * FROM user_facts
                    WHERE user_id = ? AND (chat_id = ? OR chat_id IS NULL)
                    ORDER BY confidence DESC, updated_at DESC
                    LIMIT ?
                """, (user_id, chat_id, USER_FACT_LIMIT))
            else:
                cursor = self._conn.execute("""
                    SELECT * FROM user_facts
                    WHERE user_id = ?
                    ORDER BY confidence DESC, updated_at DESC
                    LIMIT ?
                """, (user_id, USER_FACT_LIMIT))
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get user facts: {e}")
            return []

    def get_user_context(self, user_id: int, chat_id: int) -> str:
        """Get formatted user context for LLM."""
        try:
            # Get relationship
            cursor = self._conn.execute("""
                SELECT * FROM user_relationships
                WHERE user_id = ? AND chat_id = ?
            """, (user_id, chat_id))
            rel = cursor.fetchone()

            # Get facts
            facts = self.get_user_facts(user_id, chat_id)

            parts = []
            if rel:
                parts.append(f"Messages from this user: {rel['message_count']}")
                if rel['nickname']:
                    parts.append(f"Known as: {rel['nickname']}")
                if rel['is_admin']:
                    parts.append("Is admin/trusted")

            if facts:
                fact_strs = [f"{f['fact_type']}: {f['fact_content']}" for f in facts[:5]]
                parts.append(f"Known facts: {', '.join(fact_strs)}")

            return " | ".join(parts) if parts else ""
        except Exception as e:
            logger.error(f"Failed to get user context: {e}")
            return ""

    def set_user_admin(self, user_id: int, chat_id: int, is_admin: bool = True):
        """Mark user as admin for a chat."""
        try:
            timestamp = datetime.now(timezone.utc).isoformat()
            self._conn.execute("""
                INSERT INTO user_relationships (user_id, chat_id, first_seen, last_seen, is_admin)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, chat_id) DO UPDATE SET
                    is_admin = excluded.is_admin,
                    last_seen = excluded.last_seen
            """, (user_id, chat_id, timestamp, timestamp, is_admin))
            self._conn.commit()
        except Exception as e:
            logger.error(f"Failed to set user admin: {e}")

    def update_chat_topics(self, chat_id: int, topics: List[str]):
        """Update the recent topics for a chat."""
        try:
            timestamp = datetime.now(timezone.utc).isoformat()
            topics_json = json.dumps(topics[-10:])  # Keep last 10
            self._conn.execute("""
                INSERT INTO chat_state (chat_id, recent_topics, last_active)
                VALUES (?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    recent_topics = excluded.recent_topics,
                    last_active = excluded.last_active
            """, (chat_id, topics_json, timestamp))
            self._conn.commit()
        except Exception as e:
            logger.error(f"Failed to update chat topics: {e}")

    def get_chat_topics(self, chat_id: int) -> List[str]:
        """Get recent topics for a chat."""
        try:
            cursor = self._conn.execute("""
                SELECT recent_topics FROM chat_state WHERE chat_id = ?
            """, (chat_id,))
            row = cursor.fetchone()
            if row and row['recent_topics']:
                return json.loads(row['recent_topics'])
        except Exception as e:
            logger.error(f"Failed to get chat topics: {e}")
        return []

    def save_jarvis_response(self, chat_id: int, response: str):
        """Save JARVIS's own response for continuity."""
        self.save_message(chat_id, response, is_jarvis=True, username="JARVIS")

        # Also store as last response
        try:
            self._conn.execute("""
                UPDATE chat_state SET last_jarvis_message = ?
                WHERE chat_id = ?
            """, (response[:500], chat_id))
            self._conn.commit()
        except Exception as e:
            logger.error(f"Failed to save last jarvis message: {e}")

    def get_last_jarvis_response(self, chat_id: int) -> Optional[str]:
        """Get JARVIS's last response in this chat."""
        try:
            cursor = self._conn.execute("""
                SELECT last_jarvis_message FROM chat_state WHERE chat_id = ?
            """, (chat_id,))
            row = cursor.fetchone()
            if row:
                return row['last_jarvis_message']
        except Exception as e:
            logger.error(f"Failed to get last jarvis message: {e}")
        return None

    def _maybe_prune(self, chat_id: int):
        """Prune old entries if over limit."""
        try:
            cursor = self._conn.execute("""
                SELECT COUNT(*) as cnt FROM chat_history WHERE chat_id = ?
            """, (chat_id,))
            row = cursor.fetchone()

            if row and row['cnt'] > MAX_HISTORY_ENTRIES:
                # Delete oldest entries
                excess = row['cnt'] - MAX_HISTORY_ENTRIES + 100  # Delete 100 extra
                self._conn.execute("""
                    DELETE FROM chat_history WHERE id IN (
                        SELECT id FROM chat_history
                        WHERE chat_id = ?
                        ORDER BY timestamp ASC
                        LIMIT ?
                    )
                """, (chat_id, excess))
                self._conn.commit()
                logger.info(f"Pruned {excess} old messages from chat {chat_id}")
        except Exception as e:
            logger.error(f"Failed to prune: {e}")

    def extract_facts_from_message(self, user_id: int, chat_id: int, message: str, username: str = ""):
        """Extract and save potential facts from a message."""
        # Simple fact extraction (can be enhanced with LLM later)
        message_lower = message.lower()

        # Detect preferences
        if "i prefer" in message_lower or "i like" in message_lower:
            self.save_user_fact(user_id, "preference", message[:100], chat_id)

        # Detect portfolio mentions
        if any(w in message_lower for w in ["holding", "my bag", "i bought", "i own"]):
            self.save_user_fact(user_id, "holdings", message[:100], chat_id)

        # Detect trading style
        if any(w in message_lower for w in ["degen", "conservative", "scalp", "swing"]):
            self.save_user_fact(user_id, "trading_style", message[:100], chat_id)

        # Save username if provided
        if username and username != str(user_id):
            self.save_user_fact(user_id, "username", username, chat_id)

    def get_conversation_summary(self, chat_id: int) -> str:
        """Get a brief summary of the conversation for context injection."""
        try:
            # Get chat state
            cursor = self._conn.execute("""
                SELECT * FROM chat_state WHERE chat_id = ?
            """, (chat_id,))
            state = cursor.fetchone()

            # Get recent participant count
            cursor = self._conn.execute("""
                SELECT COUNT(DISTINCT user_id) as participants
                FROM chat_history
                WHERE chat_id = ? AND timestamp > ?
            """, (chat_id, (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()))
            part_row = cursor.fetchone()

            parts = []
            if state:
                if state['total_messages']:
                    parts.append(f"{state['total_messages']} total messages")
                if state['recent_topics']:
                    topics = json.loads(state['recent_topics'])
                    if topics:
                        parts.append(f"Recent topics: {', '.join(topics[-3:])}")
                if state['mood'] and state['mood'] != 'neutral':
                    parts.append(f"Mood: {state['mood']}")

            if part_row and part_row['participants']:
                parts.append(f"{part_row['participants']} active users (24h)")

            return " | ".join(parts) if parts else "New conversation"
        except Exception as e:
            logger.error(f"Failed to get conversation summary: {e}")
            return ""

    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None


# Singleton accessor
_memory_instance: Optional[ConversationMemory] = None


def get_conversation_memory() -> ConversationMemory:
    """Get the singleton ConversationMemory instance."""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = ConversationMemory()
    return _memory_instance
