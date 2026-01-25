"""Retain functions for storing facts and preferences in memory."""
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any

from .database import get_db
from .markdown_sync import sync_fact_to_markdown, extract_entities_from_text


def get_or_create_entity(
    cursor: sqlite3.Cursor,
    name: str,
    entity_type: Optional[str] = None,
) -> int:
    """
    Get existing entity ID or create new entity.

    Args:
        cursor: Database cursor.
        name: Entity name (e.g., '@KR8TIV', 'lucid').
        entity_type: Type hint ('token', 'user', 'strategy', 'platform').

    Returns:
        Entity ID.
    """
    # Try to get existing entity
    result = cursor.execute(
        "SELECT id, type FROM entities WHERE name = ?",
        (name,)
    ).fetchone()

    if result:
        return result["id"] if hasattr(result, "keys") else result[0]

    # Infer entity type if not provided
    if entity_type is None:
        entity_type = _infer_entity_type(name)

    # Create new entity
    cursor.execute(
        """
        INSERT INTO entities (name, type, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (name, entity_type, datetime.utcnow(), datetime.utcnow())
    )

    return cursor.lastrowid


def _infer_entity_type(name: str) -> str:
    """
    Infer entity type from name patterns.

    Args:
        name: Entity name.

    Returns:
        Inferred type string.
    """
    name_lower = name.lower()

    # @mentions are usually users
    if name.startswith("@"):
        # But some @mentions are tokens
        inner = name[1:]
        if inner.isupper() and len(inner) <= 6:
            return "token"
        return "user"

    # All uppercase 3-6 chars = token
    if name.isupper() and 3 <= len(name) <= 6:
        return "token"

    # Known platforms (but schema only has 'other' for non-token/user/strategy)
    # Just return 'other' for everything else
    return "other"


def retain_fact(
    content: str,
    context: Optional[str] = None,
    entities: Optional[List[str]] = None,
    source: Optional[str] = None,
    confidence: float = 1.0,
    auto_extract_entities: bool = True,
) -> int:
    """
    Store a fact in both SQLite and daily Markdown log.

    This is the primary entry point for storing memory.

    Args:
        content: The fact content (required).
        context: Situational context (e.g., 'bags.fm graduation').
        entities: Explicit entity mentions. If None and auto_extract_entities=True,
                  entities are extracted from content.
        source: Source system ('telegram', 'treasury', 'x', 'bags_intel', 'buy_tracker').
        confidence: Confidence score 0.0-1.0 (default 1.0).
        auto_extract_entities: Auto-extract entities from content if none provided.

    Returns:
        The fact ID.

    Example:
        fact_id = retain_fact(
            content="KR8TIV bought at $0.05, sold at $0.12 (+140%)",
            context="bags.fm graduation within 2h, sentiment: 0.85",
            entities=["@KR8TIV", "@bags.fm", "@lucid"],
            source="treasury"
        )
    """
    db = get_db()
    timestamp = datetime.utcnow()

    # Auto-extract entities if not provided
    if entities is None and auto_extract_entities:
        entities = extract_entities_from_text(content)
        if context:
            entities.extend(extract_entities_from_text(context))
        entities = list(set(entities))  # Dedupe

    # Use transaction via get_cursor()
    with db.get_cursor() as cursor:
        # 1. Insert into facts table
        cursor.execute(
            """
            INSERT INTO facts (content, context, timestamp, source, confidence)
            VALUES (?, ?, ?, ?, ?)
            """,
            (content, context, timestamp, source, confidence)
        )
        fact_id = cursor.lastrowid

        # 2. Link entities
        if entities:
            for entity_name in entities:
                entity_id = get_or_create_entity(cursor, entity_name)
                try:
                    cursor.execute(
                        """
                        INSERT INTO entity_mentions (fact_id, entity_id, mention_text)
                        VALUES (?, ?, ?)
                        """,
                        (fact_id, entity_id, entity_name)
                    )
                except sqlite3.IntegrityError:
                    # Duplicate mention, skip
                    pass

    # 3. Sync to Markdown (outside transaction - file I/O)
    sync_fact_to_markdown(
        fact_id=fact_id,
        content=content,
        context=context,
        source=source,
        entities=entities,
        confidence=confidence,
        timestamp=timestamp,
    )

    return fact_id


def retain_preference(
    user: str,
    key: str,
    value: str,
    evidence: Optional[str] = None,
    confirmed: bool = True,
) -> Dict[str, Any]:
    """
    Store or update a user preference with confidence evolution.

    Confidence increases with confirmations, decreases with contradictions.

    Args:
        user: User identifier (e.g., 'lucid').
        key: Preference key (e.g., 'risk_tolerance').
        value: Preference value.
        evidence: Evidence for this preference update.
        confirmed: True if this confirms the preference, False if contradicts.

    Returns:
        Dict with preference state: {id, confidence, evidence_count}.

    Example:
        pref = retain_preference(
            user="lucid",
            key="risk_tolerance",
            value="aggressive",
            evidence="User said 'I want max gains'",
            confirmed=True
        )
    """
    db = get_db()
    timestamp = datetime.utcnow()

    # First, get or create user_identity
    with db.get_cursor() as cursor:
        # Get user_id from user_identities
        user_row = cursor.execute(
            "SELECT id FROM user_identities WHERE canonical_name = ?",
            (user,)
        ).fetchone()

        if user_row:
            user_id = user_row["id"] if hasattr(user_row, "keys") else user_row[0]
        else:
            # Create user identity
            cursor.execute(
                """
                INSERT INTO user_identities (canonical_name, created_at, updated_at)
                VALUES (?, ?, ?)
                """,
                (user, timestamp, timestamp)
            )
            user_id = cursor.lastrowid

        # Get current preference state
        current = cursor.execute(
            "SELECT id, confidence, evidence_count FROM preferences WHERE user_id = ? AND preference_key = ?",
            (user_id, key)
        ).fetchone()

        if current:
            pref_id = current["id"] if hasattr(current, "keys") else current[0]
            old_confidence = current["confidence"] if hasattr(current, "keys") else current[1]
            evidence_count = current["evidence_count"] if hasattr(current, "keys") else current[2]

            # Confidence evolution:
            # - Confirmation: +0.1 (max 0.95)
            # - Contradiction: -0.15 (min 0.1)
            if confirmed:
                new_confidence = min(0.95, old_confidence + 0.1)
            else:
                new_confidence = max(0.1, old_confidence - 0.15)

            # Update preference
            cursor.execute(
                """
                UPDATE preferences
                SET preference_value = ?, confidence = ?, evidence_count = ?, updated_at = ?
                WHERE id = ?
                """,
                (value, new_confidence, evidence_count + 1, timestamp, pref_id)
            )

            result = {
                "id": pref_id,
                "confidence": new_confidence,
                "evidence_count": evidence_count + 1,
                "updated": True,
            }
        else:
            # Create new preference (start at 0.5 confidence)
            cursor.execute(
                """
                INSERT INTO preferences (user_id, category, preference_key, preference_value, confidence, evidence_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, 0.5, 1, ?, ?)
                """,
                (user_id, "general", key, value, timestamp, timestamp)
            )

            result = {
                "id": cursor.lastrowid,
                "confidence": 0.5,
                "evidence_count": 1,
                "updated": False,
            }

    # Store evidence as fact (outside transaction to avoid nesting)
    if evidence:
        action = "confirmed" if confirmed else "contradicted"
        retain_fact(
            content=f"User {user} preference: {key}={value} ({action})",
            context=evidence,
            source="preference_tracking",
            entities=[f"@{user}"],
            confidence=result["confidence"],
        )

    return result


def get_user_preferences(user: str) -> List[Dict[str, Any]]:
    """
    Get all preferences for a user.

    Args:
        user: User identifier.

    Returns:
        List of preference dicts with key, value, confidence, evidence_count.
    """
    db = get_db()

    with db.get_cursor() as cursor:
        # Get user_id
        user_row = cursor.execute(
            "SELECT id FROM user_identities WHERE canonical_name = ?",
            (user,)
        ).fetchone()

        if not user_row:
            return []

        user_id = user_row["id"] if hasattr(user_row, "keys") else user_row[0]

        rows = cursor.execute(
            """
            SELECT preference_key, preference_value, confidence, evidence_count, updated_at
            FROM preferences
            WHERE user_id = ?
            ORDER BY updated_at DESC
            """,
            (user_id,)
        ).fetchall()

        return [
            {
                "key": row["preference_key"] if hasattr(row, "keys") else row[0],
                "value": row["preference_value"] if hasattr(row, "keys") else row[1],
                "confidence": row["confidence"] if hasattr(row, "keys") else row[2],
                "evidence_count": row["evidence_count"] if hasattr(row, "keys") else row[3],
                "last_updated": row["updated_at"] if hasattr(row, "keys") else row[4],
            }
            for row in rows
        ]
