"""
Memory System - Short-term and long-term memory management.

Provides:
- LongTermMemory: Persistent memories with semantic retrieval
- MemoryStore: SQLite-backed storage with embeddings
- Memory consolidation and archival
"""

from core.memory.persistence import (
    LongTermMemory,
    MemoryStore,
    MemoryType,
    MemoryPriority,
    MemorySearchResult,
    ConsolidationResult,
    get_memory_store,
)

__all__ = [
    "LongTermMemory",
    "MemoryStore",
    "MemoryType",
    "MemoryPriority",
    "MemorySearchResult",
    "ConsolidationResult",
    "get_memory_store",
]
