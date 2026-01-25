"""
Memory System - Short-term and long-term memory management.

Provides:
- LongTermMemory: Persistent memories with semantic retrieval
- MemoryStore: SQLite-backed storage with embeddings
- Memory consolidation and archival
- Clawdbot-inspired dual-layer memory workspace (NEW)
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

# New workspace-based memory system (Clawdbot architecture)
from core.memory.config import MemoryConfig, get_config
from core.memory.workspace import init_workspace, get_memory_path, MEMORY_ROOT
from core.memory.database import get_db, DatabaseManager
from core.memory.retain import retain_fact, retain_preference, get_or_create_entity, get_user_preferences
from core.memory.markdown_sync import (
    append_to_daily_log,
    sync_fact_to_markdown,
    extract_entities_from_text,
    get_daily_log_path,
)
from core.memory.search import (
    search_facts,
    search_by_entity,
    search_by_source,
    get_recent_facts,
    get_entity_summary,
    get_facts_count,
    benchmark_search,
)

# New deduplication-focused memory store (M1 implementation)
try:
    from core.memory.dedup_store import (
        MemoryStore as DeduplicationMemoryStore,
        MemoryEntry,
        MemoryType as DeduplicationMemoryType,
        SQLiteMemoryStore as SQLiteDeduplicationStore,
        get_memory_store as get_dedup_store,
    )
except ImportError:
    # dedup_store not yet available
    DeduplicationMemoryStore = None
    MemoryEntry = None
    DeduplicationMemoryType = None
    SQLiteDeduplicationStore = None
    get_dedup_store = None


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
    # Existing memory system (persistence.py)
    "LongTermMemory",
    "MemoryStore",
    "MemoryType",
    "MemoryPriority",
    "MemorySearchResult",
    "ConsolidationResult",
    "get_memory_store",
    "get_recent_entries",
    "summarize_entries",
    # New deduplication memory store (dedup_store.py - M1)
    "DeduplicationMemoryStore",
    "MemoryEntry",
    "DeduplicationMemoryType",
    "SQLiteDeduplicationStore",
    "get_dedup_store",
    # New workspace-based memory system (config.py, workspace.py)
    "MemoryConfig",
    "get_config",
    "init_workspace",
    "get_memory_path",
    "MEMORY_ROOT",
    # Database (database.py)
    "get_db",
    "DatabaseManager",
    # Retain functions (retain.py)
    "retain_fact",
    "retain_preference",
    "get_or_create_entity",
    "get_user_preferences",
    # Markdown sync (markdown_sync.py)
    "append_to_daily_log",
    "sync_fact_to_markdown",
    "extract_entities_from_text",
    "get_daily_log_path",
    # Search functions (search.py)
    "search_facts",
    "search_by_entity",
    "search_by_source",
    "get_recent_facts",
    "get_entity_summary",
    "get_facts_count",
    "benchmark_search",
]
