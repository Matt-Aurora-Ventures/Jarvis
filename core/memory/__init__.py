"""
Memory System - Short-term and long-term memory management.

Provides:
- LongTermMemory: Persistent memories with semantic retrieval
- MemoryStore: SQLite-backed storage with embeddings
- Memory consolidation and archival
"""

import asyncio
from datetime import datetime, timedelta
from typing import List

from core.memory.persistence import (
    LongTermMemory,
    MemoryStore,
    MemoryType,
    MemoryPriority,
    MemorySearchResult,
    ConsolidationResult,
    get_memory_store,
)


def get_recent_entries(days: int = 7, limit: int = 50) -> List[LongTermMemory]:
    """
    Get recent memory entries from the store.

    Args:
        days: Number of days to look back (default 7)
        limit: Maximum number of entries to return (default 50)

    Returns:
        List of recent LongTermMemory objects
    """
    store = get_memory_store()

    # Initialize store synchronously if needed
    if store._conn is None:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_until_complete(store.initialize())

    # Query recent memories directly
    cutoff = datetime.utcnow() - timedelta(days=days)
    cursor = store._conn.execute(
        """
        SELECT * FROM memories
        WHERE created_at > ? AND is_archived = 0
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (cutoff.isoformat(), limit)
    )

    return [store._row_to_memory(row) for row in cursor.fetchall()]


def summarize_entries(entries: List[LongTermMemory]) -> str:
    """
    Create a text summary of memory entries.

    Args:
        entries: List of LongTermMemory objects

    Returns:
        Formatted string summary
    """
    if not entries:
        return "- No recent memory entries."

    lines = []
    for entry in entries:
        # Format: [type] content (priority)
        priority_str = entry.priority.name.lower()
        type_str = entry.memory_type.value
        content_preview = entry.content[:100] + "..." if len(entry.content) > 100 else entry.content
        lines.append(f"- [{type_str}] {content_preview} ({priority_str})")

    return "\n".join(lines)


__all__ = [
    "LongTermMemory",
    "MemoryStore",
    "MemoryType",
    "MemoryPriority",
    "MemorySearchResult",
    "ConsolidationResult",
    "get_memory_store",
    "get_recent_entries",
    "summarize_entries",
]
