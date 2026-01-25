"""Daily reflection orchestration for memory consolidation."""
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional

from .database import get_db
from .config import get_config
from .summarize import synthesize_daily_facts
from .retain import retain_fact

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
