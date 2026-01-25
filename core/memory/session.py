"""Session context persistence for conversation continuity.

Manages per-user conversation state across bot restarts.
"""
import json
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from .database import get_db

logger = logging.getLogger(__name__)


def save_session_context(
    user_id: str,
    platform: str,
    context: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Save or update session context for a user.

    Args:
        user_id: User identifier (telegram ID, twitter handle, etc.).
        platform: Platform name ('telegram', 'x', 'system').
        context: Current conversation state (dict serialized to JSON).
        metadata: Optional metadata (dict serialized to JSON).

    Returns:
        Session ID (string from sessions table).

    Example:
        session_id = save_session_context(
            user_id="123456",
            platform="telegram",
            context={"current_topic": "trading", "last_token": "KR8TIV"},
            metadata={"bot_version": "1.0"}
        )
    """
    db = get_db()

    # Generate session ID (platform:user_id)
    session_id = f"{platform}:{user_id}"

    # Serialize context and metadata to JSON
    context_json = json.dumps(context)
    metadata_json = json.dumps(metadata) if metadata else None

    # Check if session exists
    existing = db.execute(
        "SELECT id FROM sessions WHERE id = ?",
        (session_id,)
    ).fetchone()

    # Ensure user_identity exists if user_id is numeric
    user_id_int = None
    if user_id.isdigit():
        user_id_int = int(user_id)
        # Check if user identity exists, create if not
        existing_user = db.execute(
            "SELECT id FROM user_identities WHERE id = ?",
            (user_id_int,)
        ).fetchone()

        if not existing_user:
            # Create user identity
            db.execute(
                """
                INSERT INTO user_identities (id, canonical_name)
                VALUES (?, ?)
                """,
                (user_id_int, f"user_{user_id}")
            )
            db.commit()

    if existing:
        # Update existing session
        db.execute(
            """
            UPDATE sessions
            SET context = ?, last_active = ?
            WHERE id = ?
            """,
            (context_json, datetime.utcnow(), session_id)
        )
        logger.debug(f"Updated session context: {session_id}")
    else:
        # Create new session
        db.execute(
            """
            INSERT INTO sessions (id, user_id, platform, context, started_at, last_active)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                user_id_int,
                platform,
                context_json,
                datetime.utcnow(),
                datetime.utcnow(),
            )
        )
        logger.info(f"Created new session: {session_id}")

    db.commit()
    return session_id


def get_session_context(
    user_id: str,
    platform: str,
) -> Optional[Dict[str, Any]]:
    """
    Get session context for a user.

    Args:
        user_id: User identifier.
        platform: Platform name ('telegram', 'x', 'system').

    Returns:
        Session context dict, or None if no active session.

    Example:
        ctx = get_session_context("123456", "telegram")
        if ctx:
            last_token = ctx.get("last_token")
    """
    db = get_db()

    session_id = f"{platform}:{user_id}"

    row = db.execute(
        "SELECT context FROM sessions WHERE id = ?",
        (session_id,)
    ).fetchone()

    if row is None:
        logger.debug(f"No session found: {session_id}")
        return None

    # Deserialize JSON context
    context_json = row["context"]
    if context_json:
        try:
            context = json.loads(context_json)
            logger.debug(f"Retrieved session context: {session_id}")
            return context
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse session context JSON: {e}")
            return None

    return None


def clear_session_context(
    user_id: str,
    platform: str,
) -> bool:
    """
    Clear session context for a user.

    Deletes the session record from the database.

    Args:
        user_id: User identifier.
        platform: Platform name.

    Returns:
        True if session was deleted, False if no session existed.

    Example:
        cleared = clear_session_context("123456", "telegram")
    """
    db = get_db()

    session_id = f"{platform}:{user_id}"

    cursor = db.execute(
        "DELETE FROM sessions WHERE id = ?",
        (session_id,)
    )

    db.commit()

    deleted = cursor.rowcount > 0

    if deleted:
        logger.info(f"Cleared session context: {session_id}")
    else:
        logger.debug(f"No session to clear: {session_id}")

    return deleted


def get_or_create_session(
    user_id: str,
    platform: str,
) -> Tuple[str, Dict[str, Any]]:
    """
    Get existing session or create new one.

    Args:
        user_id: User identifier.
        platform: Platform name.

    Returns:
        Tuple of (session_id, context dict).
        Context dict is empty {} if new session.

    Example:
        session_id, ctx = get_or_create_session("123456", "telegram")
        ctx["current_topic"] = "trading"
        save_session_context("123456", "telegram", ctx)
    """
    session_id = f"{platform}:{user_id}"

    # Try to get existing context
    context = get_session_context(user_id, platform)

    if context is None:
        # Create new session with empty context
        context = {}
        save_session_context(user_id, platform, context)

    return session_id, context


def update_session_activity(
    user_id: str,
    platform: str,
) -> None:
    """
    Update last_active timestamp for a session.

    Call this on every user interaction to track session activity.

    Args:
        user_id: User identifier.
        platform: Platform name.

    Example:
        update_session_activity("123456", "telegram")
    """
    db = get_db()

    session_id = f"{platform}:{user_id}"

    db.execute(
        """
        UPDATE sessions
        SET last_active = ?
        WHERE id = ?
        """,
        (datetime.utcnow(), session_id)
    )

    db.commit()
    logger.debug(f"Updated session activity: {session_id}")


def get_active_sessions(
    platform: Optional[str] = None,
    min_age_minutes: int = 5,
) -> list[Dict[str, Any]]:
    """
    Get all active sessions (recently active).

    Args:
        platform: Filter by platform (optional).
        min_age_minutes: Sessions active within this many minutes.

    Returns:
        List of session dicts with keys: id, user_id, platform, last_active.

    Example:
        # Get all Telegram sessions active in last 5 minutes
        active = get_active_sessions(platform="telegram", min_age_minutes=5)
    """
    db = get_db()

    cutoff = datetime.utcnow()
    from datetime import timedelta
    cutoff = cutoff - timedelta(minutes=min_age_minutes)

    if platform:
        cursor = db.execute(
            """
            SELECT id, user_id, platform, last_active
            FROM sessions
            WHERE platform = ? AND last_active >= ?
            ORDER BY last_active DESC
            """,
            (platform, cutoff)
        )
    else:
        cursor = db.execute(
            """
            SELECT id, user_id, platform, last_active
            FROM sessions
            WHERE last_active >= ?
            ORDER BY last_active DESC
            """,
            (cutoff,)
        )

    results = []
    for row in cursor.fetchall():
        results.append({
            "id": row["id"],
            "user_id": row["user_id"],
            "platform": row["platform"],
            "last_active": row["last_active"],
        })

    return results
