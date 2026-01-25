"""Daily reflection orchestration for memory consolidation."""
import gzip
import json
import logging
import re
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional

from .database import get_db
from .config import get_config
from .summarize import synthesize_daily_facts, synthesize_entity_insights
from .retain import retain_fact
from .entity_profiles import get_entity_facts, update_entity_profile
from .patterns import detect_contradictions

logger = logging.getLogger(__name__)


def reflect_daily() -> Dict[str, Any]:
    """
    Run daily reflection to synthesize yesterday's facts into durable knowledge.

    This is the main entry point for daily memory consolidation.

    Process:
    1. Calculate yesterday's time boundaries (00:00:00 to 23:59:59 UTC)
    2. Query all facts from yesterday
    3. If no facts, return early with skip status
    4. Call synthesize_daily_facts() to get LLM synthesis
    5. Append synthesis to memory.md with dated section
    6. Store synthesis as a meta-fact
    7. Update reflect_state.json with execution metadata

    Returns:
        Dict with execution stats:
        - status: "completed" | "skipped"
        - facts_processed: count of facts synthesized
        - duration_seconds: execution time
        - reason: skip reason (if skipped)

    Example:
        result = reflect_daily()
        # {"status": "completed", "facts_processed": 42, "duration_seconds": 3.2}
    """
    start_time = time.time()
    logger.info("Starting daily reflection...")

    # Calculate yesterday's time boundaries (UTC)
    now = datetime.utcnow()
    yesterday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_end = (now - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)

    logger.info(f"Reflecting on facts from {yesterday_start} to {yesterday_end}")

    # Query facts from yesterday
    db = get_db()
    with db.get_cursor() as cursor:
        cursor.execute(
            """
            SELECT
                f.id,
                f.content,
                f.context,
                f.source,
                f.timestamp,
                f.confidence,
                GROUP_CONCAT(e.name, ', ') as entities
            FROM facts f
            LEFT JOIN entity_mentions em ON f.id = em.fact_id
            LEFT JOIN entities e ON em.entity_id = e.id
            WHERE f.timestamp >= ? AND f.timestamp <= ?
            GROUP BY f.id
            ORDER BY f.timestamp ASC
            """,
            (yesterday_start, yesterday_end)
        )

        rows = cursor.fetchall()

    # Convert rows to fact dicts
    facts = []
    for row in rows:
        entities_str = row["entities"] if hasattr(row, "keys") else row[6]
        entities = entities_str.split(", ") if entities_str else []

        facts.append({
            "id": row["id"] if hasattr(row, "keys") else row[0],
            "content": row["content"] if hasattr(row, "keys") else row[1],
            "context": row["context"] if hasattr(row, "keys") else row[2],
            "source": row["source"] if hasattr(row, "keys") else row[3],
            "timestamp": row["timestamp"] if hasattr(row, "keys") else row[4],
            "confidence": row["confidence"] if hasattr(row, "keys") else row[5],
            "entities": entities,
        })

    # Check if we have facts to process
    if not facts:
        duration = time.time() - start_time
        logger.info(f"No facts from yesterday. Skipping reflection. ({duration:.2f}s)")

        # Update state even for skips
        state = get_reflect_state()
        state["last_reflect_time"] = datetime.utcnow().isoformat()
        state["last_status"] = "skipped"
        state["last_reason"] = "no facts"
        save_reflect_state(state)

        return {
            "status": "skipped",
            "reason": "no facts",
            "duration_seconds": duration,
        }

    logger.info(f"Processing {len(facts)} facts from yesterday...")

    # Synthesize facts using Claude
    synthesis = synthesize_daily_facts(facts)

    # Append synthesis to memory.md
    config = get_config()
    memory_path = config.daily_logs_dir / "memory.md"

    # Ensure memory.md exists
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    if not memory_path.exists():
        with open(memory_path, "w", encoding="utf-8") as f:
            f.write("# Jarvis Memory\n\n")
            f.write("This file contains daily reflections and synthesized insights.\n\n")
            f.write("---\n\n")

    # Append reflection section
    yesterday_date = yesterday_start.strftime("%Y-%m-%d")
    reflection_section = f"\n## Reflection: {yesterday_date}\n\n{synthesis}\n\n"
    reflection_section += f"_Synthesized from {len(facts)} facts_\n\n---\n\n"

    with open(memory_path, "a", encoding="utf-8") as f:
        f.write(reflection_section)

    logger.info(f"Appended reflection to {memory_path}")

    # Store synthesis as a meta-fact for future recall
    try:
        retain_fact(
            content=f"Daily reflection for {yesterday_date}: {synthesis[:200]}...",  # First 200 chars
            context="daily_reflection",
            source="reflect_engine",
            confidence=0.9,
            auto_extract_entities=False,  # Don't auto-extract from synthesis
        )
        logger.info("Stored synthesis as meta-fact")
    except Exception as e:
        logger.warning(f"Failed to store synthesis as meta-fact: {e}")

    # Calculate duration
    duration = time.time() - start_time

    # Update reflect state
    state = get_reflect_state()
    state["last_reflect_time"] = datetime.utcnow().isoformat()
    state["last_status"] = "completed"
    state["facts_processed"] = len(facts)
    state["duration_seconds"] = duration
    state["last_date_reflected"] = yesterday_date

    # Track cumulative stats
    state["total_reflections"] = state.get("total_reflections", 0) + 1
    state["total_facts_processed"] = state.get("total_facts_processed", 0) + len(facts)

    save_reflect_state(state)

    logger.info(f"Daily reflection completed. Processed {len(facts)} facts in {duration:.2f}s")

    return {
        "status": "completed",
        "facts_processed": len(facts),
        "duration_seconds": duration,
    }


def get_reflect_state() -> Dict[str, Any]:
    """
    Load and return reflect_state.json from ~/.lifeos/memory/.

    Returns:
        Dict with state information, or empty dict if file doesn't exist.

    Example state:
        {
            "last_reflect_time": "2026-01-25T10:30:00Z",
            "last_status": "completed",
            "facts_processed": 42,
            "duration_seconds": 3.2,
            "last_date_reflected": "2026-01-24",
            "total_reflections": 15,
            "total_facts_processed": 523
        }
    """
    config = get_config()
    state_path = config.memory_root / "reflect_state.json"

    if not state_path.exists():
        logger.debug(f"reflect_state.json not found at {state_path}, returning empty state")
        return {}

    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
        logger.debug(f"Loaded reflect state from {state_path}")
        return state
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load reflect_state.json: {e}")
        return {}


def save_reflect_state(state: Dict[str, Any]) -> None:
    """
    Save reflect state to reflect_state.json.

    Creates parent directory if needed.

    Args:
        state: State dict to save.
    """
    config = get_config()
    state_path = config.memory_root / "reflect_state.json"

    # Ensure parent directory exists
    state_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        logger.debug(f"Saved reflect state to {state_path}")
    except OSError as e:
        logger.error(f"Failed to save reflect_state.json: {e}", exc_info=True)
        raise


def evolve_preference_confidence(since_time: datetime) -> Dict[str, Any]:
    """
    Evolve preference confidence scores based on confirmations/contradictions.

    Process:
    1. Query preference-related facts from the period
    2. Parse each fact to extract user, key, and action (confirmed/contradicted)
    3. For confirmed preferences: increase confidence by +0.1 (max 0.95)
    4. For contradicted preferences: decrease confidence by -0.15 (min 0.1)
    5. If confidence drops below 0.3: flip preference to new value, reset to 0.5

    Args:
        since_time: Only process facts after this timestamp.

    Returns:
        Dict with stats:
        - preferences_evolved: count of preferences updated
        - flips: count of preferences that flipped
        - confirmations: count of confirmations processed
        - contradictions: count of contradictions processed

    Example fact format:
        "User daryl preference: response_style=concise (confirmed)"
        "User daryl preference: verbosity=high (contradicted)"
    """
    db = get_db()
    preferences_evolved = 0
    flips = 0
    confirmations = 0
    contradictions = 0

    logger.info(f"Evolving preference confidence since {since_time}")

    # Query preference-related facts
    with db.get_cursor() as cursor:
        cursor.execute(
            """
            SELECT id, content, context, timestamp
            FROM facts
            WHERE source = 'preference_tracking'
            AND timestamp >= ?
            ORDER BY timestamp ASC
            """,
            (since_time,)
        )
        facts = cursor.fetchall()

    logger.debug(f"Found {len(facts)} preference tracking facts")

    # Pattern: "User {user} preference: {key}={value} (confirmed|contradicted)"
    pattern = r"User (\w+) preference: (\w+)=(\w+) \((confirmed|contradicted)\)"

    for fact in facts:
        content = fact["content"] if hasattr(fact, "keys") else fact[1]
        match = re.search(pattern, content)

        if not match:
            logger.debug(f"Fact {fact['id']} doesn't match preference pattern, skipping")
            continue

        user, key, value, action = match.groups()

        # Get current preference from database
        with db.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT id, confidence, evidence_count, value
                FROM preferences
                WHERE user_id = ? AND key = ?
                """,
                (user, key)
            )
            pref_row = cursor.fetchone()

        if not pref_row:
            logger.warning(f"Preference {user}.{key} not found in database, skipping")
            continue

        pref_id = pref_row["id"] if hasattr(pref_row, "keys") else pref_row[0]
        old_confidence = pref_row["confidence"] if hasattr(pref_row, "keys") else pref_row[1]
        evidence_count = pref_row["evidence_count"] if hasattr(pref_row, "keys") else pref_row[2]
        current_value = pref_row["value"] if hasattr(pref_row, "keys") else pref_row[3]

        # Calculate new confidence
        if action == "confirmed":
            new_confidence = min(0.95, old_confidence + 0.1)
            confirmations += 1
        else:  # contradicted
            new_confidence = max(0.1, old_confidence - 0.15)
            contradictions += 1

        # Check if we need to flip the preference
        did_flip = False
        new_value = current_value

        if action == "contradicted" and new_confidence < 0.3:
            # Flip preference to the contradicted value
            new_value = value
            new_confidence = 0.5  # Reset to neutral
            did_flip = True
            flips += 1
            logger.info(f"Flipped preference {user}.{key}: {current_value} -> {new_value} (confidence dropped to {old_confidence:.2f})")

        # Check if already at bounds (skip update but still count)
        if not did_flip and new_confidence == old_confidence:
            logger.debug(f"Preference {user}.{key} already at confidence bound ({old_confidence}), skipping update")
            continue

        # Update database
        with db.get_cursor() as cursor:
            if did_flip:
                cursor.execute(
                    """
                    UPDATE preferences
                    SET confidence = ?, value = ?, evidence_count = evidence_count + 1, last_updated = ?
                    WHERE user_id = ? AND key = ?
                    """,
                    (new_confidence, new_value, datetime.utcnow(), user, key)
                )
            else:
                cursor.execute(
                    """
                    UPDATE preferences
                    SET confidence = ?, evidence_count = evidence_count + 1, last_updated = ?
                    WHERE user_id = ? AND key = ?
                    """,
                    (new_confidence, datetime.utcnow(), user, key)
                )

        preferences_evolved += 1
        logger.info(f"Evolved {user}.{key}: confidence {old_confidence:.2f} -> {new_confidence:.2f} ({action})")

    logger.info(f"Preference evolution complete: {preferences_evolved} evolved, {flips} flipped, {confirmations} confirmed, {contradictions} contradicted")

    return {
        "preferences_evolved": preferences_evolved,
        "flips": flips,
        "confirmations": confirmations,
        "contradictions": contradictions,
    }


def update_entity_summaries(since_time: datetime) -> Dict[str, int]:
    """
    Update entity summaries for entities with new facts since given time.

    Process:
    1. Query entities with new facts since since_time
    2. For each entity, get recent facts (last 100)
    3. Score facts by recency + importance (7-day half-life)
    4. Take top 20 facts
    5. Synthesize insights via LLM
    6. Update entity profile markdown with new summary

    Args:
        since_time: Only update entities with facts after this time

    Returns:
        Dict with update statistics:
        - entities_updated: count of entities that got new summaries
        - entities_skipped: count of entities with no new facts

    Example:
        from datetime import datetime, timedelta
        since_time = datetime.utcnow() - timedelta(hours=24)
        result = update_entity_summaries(since_time)
        # {"entities_updated": 5, "entities_skipped": 2}
    """
    logger.info(f"Updating entity summaries for facts since {since_time}")

    db = get_db()
    entities_updated = 0
    entities_skipped = 0

    # Context weights for fact scoring
    context_weights = {
        "trade_outcome": 1.0,
        "user_preference": 0.8,
        "graduation_pattern": 0.7,
        "market_observation": 0.6,
        "general": 0.5,
    }

    try:
        # Query entities with new facts since since_time
        with db.get_cursor() as cursor:
            rows = cursor.execute(
                """
                SELECT DISTINCT e.id, e.name, e.type
                FROM entities e
                JOIN entity_mentions em ON e.id = em.entity_id
                JOIN facts f ON em.fact_id = f.id
                WHERE f.timestamp > ? AND f.is_active = 1
                ORDER BY e.name
                """,
                (since_time,)
            ).fetchall()

        if not rows:
            logger.info("No entities with new facts to update")
            return {"entities_updated": 0, "entities_skipped": 0}

        logger.info(f"Found {len(rows)} entities with new facts")

        # Process each entity
        for row in rows:
            entity_id = row["id"] if hasattr(row, "keys") else row[0]
            entity_name = row["name"] if hasattr(row, "keys") else row[1]
            entity_type = row["type"] if hasattr(row, "keys") else row[2]

            # Default to "other" if no entity_type
            if not entity_type:
                entity_type = "other"

            logger.info(f"Processing entity: {entity_name} (type: {entity_type})")

            # Get recent facts for this entity (last 100)
            with db.get_cursor() as cursor:
                fact_rows = cursor.execute(
                    """
                    SELECT f.id, f.content, f.timestamp, f.source, f.context, f.confidence
                    FROM facts f
                    INNER JOIN entity_mentions em ON em.fact_id = f.id
                    WHERE em.entity_id = ? AND f.is_active = 1
                    ORDER BY f.timestamp DESC
                    LIMIT 100
                    """,
                    (entity_id,)
                ).fetchall()

            if not fact_rows:
                entities_skipped += 1
                continue

            # Score facts by recency + importance
            now = datetime.utcnow()
            scored_facts = []

            for fact_row in fact_rows:
                fact_id = fact_row["id"] if hasattr(fact_row, "keys") else fact_row[0]
                content = fact_row["content"] if hasattr(fact_row, "keys") else fact_row[1]
                timestamp_str = fact_row["timestamp"] if hasattr(fact_row, "keys") else fact_row[2]
                source = fact_row["source"] if hasattr(fact_row, "keys") else fact_row[3]
                context = fact_row["context"] if hasattr(fact_row, "keys") else fact_row[4]
                confidence = fact_row["confidence"] if hasattr(fact_row, "keys") else fact_row[5]

                # Parse timestamp
                if isinstance(timestamp_str, str):
                    fact_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00').replace('+00:00', ''))
                else:
                    fact_time = timestamp_str

                # Calculate recency score (7-day half-life)
                hours_ago = (now - fact_time).total_seconds() / 3600
                recency_score = 2 ** (-hours_ago / (7 * 24))

                # Calculate importance score
                context_weight = context_weights.get(context, 0.5)
                confidence_val = confidence if confidence is not None else 0.5
                importance = context_weight * confidence_val

                # Total score
                total_score = recency_score * importance

                scored_facts.append({
                    "id": fact_id,
                    "content": content,
                    "timestamp": fact_time,
                    "source": source,
                    "context": context,
                    "confidence": confidence_val,
                    "score": total_score,
                })

            # Sort by score and take top 20
            scored_facts.sort(key=lambda x: x["score"], reverse=True)
            top_facts = scored_facts[:20]

            logger.info(f"Selected {len(top_facts)} top-scored facts for {entity_name}")

            # Synthesize insights using LLM
            synthesis = synthesize_entity_insights(
                entity_name=entity_name,
                entity_type=entity_type,
                facts=top_facts
            )

            # Handle empty synthesis
            if not synthesis or synthesis.strip() == "":
                synthesis = "No significant activity"

            # Update entity profile with new summary
            success = update_entity_profile(
                entity_name=entity_name,
                new_fact="",  # Not adding a fact, just updating summary
                update_summary=True,
                new_summary=synthesis
            )

            if success:
                entities_updated += 1
                logger.info(f"Updated summary for {entity_name}")
            else:
                entities_skipped += 1
                logger.warning(f"Failed to update summary for {entity_name}")

        logger.info(f"Entity summary update complete: {entities_updated} updated, {entities_skipped} skipped")

        return {
            "entities_updated": entities_updated,
            "entities_skipped": entities_skipped,
        }

    except Exception as e:
        logger.error(f"Error updating entity summaries: {e}", exc_info=True)
        return {
            "entities_updated": entities_updated,
            "entities_skipped": entities_skipped,
        }
