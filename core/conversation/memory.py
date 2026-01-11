"""
Conversation Memory System - Multi-tier memory for context persistence.

Memory Types:
- Working: Current session context
- Short-term: 24 hours of recent patterns
- Long-term: Permanent user preferences
- Episodic: Specific memorable events
- Semantic: Learned facts and relationships
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
import hashlib
import json


class MemoryType(Enum):
    """Types of memory storage."""
    WORKING = "working"       # Session-only, cleared on disconnect
    SHORT_TERM = "short_term" # 24 hours TTL
    LONG_TERM = "long_term"   # Permanent user preferences
    EPISODIC = "episodic"     # Specific memorable events
    SEMANTIC = "semantic"     # Learned facts and relationships


@dataclass
class MemoryEntry:
    """A single memory entry."""
    id: str
    memory_type: MemoryType
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    importance: float = 0.5  # 0.0 to 1.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    embeddings: Optional[List[float]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "memory_type": self.memory_type.value,
            "content": self.content,
            "metadata": self.metadata,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "importance": self.importance,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            memory_type=MemoryType(data["memory_type"]),
            content=data["content"],
            metadata=data.get("metadata", {}),
            user_id=data.get("user_id"),
            session_id=data.get("session_id"),
            importance=data.get("importance", 0.5),
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            access_count=data.get("access_count", 0),
            last_accessed=datetime.fromisoformat(data["last_accessed"]) if data.get("last_accessed") else None,
        )

    def is_expired(self) -> bool:
        """Check if memory has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def touch(self) -> None:
        """Update access time and count."""
        self.access_count += 1
        self.last_accessed = datetime.utcnow()


class ConversationMemory:
    """Memory storage for a single conversation/user."""

    def __init__(self, user_id: str, session_id: Optional[str] = None):
        self.user_id = user_id
        self.session_id = session_id or self._generate_session_id()
        self.memories: Dict[str, MemoryEntry] = {}
        self.created_at = datetime.utcnow()

    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        data = f"{self.user_id}:{datetime.utcnow().isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def _generate_memory_id(self, content: str) -> str:
        """Generate unique memory ID."""
        data = f"{self.user_id}:{content}:{datetime.utcnow().isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def add(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.WORKING,
        metadata: Optional[Dict[str, Any]] = None,
        importance: float = 0.5,
        ttl_hours: Optional[int] = None,
    ) -> MemoryEntry:
        """Add a new memory entry."""
        memory_id = self._generate_memory_id(content)

        # Set expiration based on memory type
        expires_at = None
        if ttl_hours:
            expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
        elif memory_type == MemoryType.SHORT_TERM:
            expires_at = datetime.utcnow() + timedelta(hours=24)
        elif memory_type == MemoryType.WORKING:
            expires_at = datetime.utcnow() + timedelta(hours=4)

        entry = MemoryEntry(
            id=memory_id,
            memory_type=memory_type,
            content=content,
            metadata=metadata or {},
            user_id=self.user_id,
            session_id=self.session_id,
            importance=importance,
            expires_at=expires_at,
        )

        self.memories[memory_id] = entry
        return entry

    def get(self, memory_id: str) -> Optional[MemoryEntry]:
        """Get a memory by ID."""
        entry = self.memories.get(memory_id)
        if entry and not entry.is_expired():
            entry.touch()
            return entry
        return None

    def search(
        self,
        query: str,
        memory_types: Optional[List[MemoryType]] = None,
        limit: int = 10,
        min_importance: float = 0.0,
    ) -> List[MemoryEntry]:
        """Search memories by content (simple substring match)."""
        results = []
        query_lower = query.lower()

        for entry in self.memories.values():
            if entry.is_expired():
                continue
            if memory_types and entry.memory_type not in memory_types:
                continue
            if entry.importance < min_importance:
                continue
            if query_lower in entry.content.lower():
                entry.touch()
                results.append(entry)

        # Sort by importance and recency
        results.sort(key=lambda e: (e.importance, e.created_at), reverse=True)
        return results[:limit]

    def get_by_type(
        self,
        memory_type: MemoryType,
        limit: int = 50,
    ) -> List[MemoryEntry]:
        """Get all memories of a specific type."""
        results = [
            e for e in self.memories.values()
            if e.memory_type == memory_type and not e.is_expired()
        ]
        results.sort(key=lambda e: e.created_at, reverse=True)
        return results[:limit]

    def get_recent(self, limit: int = 20) -> List[MemoryEntry]:
        """Get most recent non-expired memories."""
        results = [e for e in self.memories.values() if not e.is_expired()]
        results.sort(key=lambda e: e.created_at, reverse=True)
        return results[:limit]

    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        if memory_id in self.memories:
            del self.memories[memory_id]
            return True
        return False

    def cleanup_expired(self) -> int:
        """Remove all expired memories."""
        expired = [k for k, v in self.memories.items() if v.is_expired()]
        for key in expired:
            del self.memories[key]
        return len(expired)

    def clear_session(self) -> int:
        """Clear all working memory (session-only)."""
        session_memories = [
            k for k, v in self.memories.items()
            if v.memory_type == MemoryType.WORKING
        ]
        for key in session_memories:
            del self.memories[key]
        return len(session_memories)

    def summarize(self) -> Dict[str, Any]:
        """Get memory statistics."""
        self.cleanup_expired()
        type_counts = {}
        for memory_type in MemoryType:
            type_counts[memory_type.value] = len(self.get_by_type(memory_type))

        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "total_memories": len(self.memories),
            "by_type": type_counts,
            "created_at": self.created_at.isoformat(),
        }


class MemoryManager:
    """Global memory manager for all users."""

    def __init__(self):
        self.user_memories: Dict[str, ConversationMemory] = {}
        self.global_memories: Dict[str, MemoryEntry] = {}  # Shared across all users

    def get_user_memory(
        self,
        user_id: str,
        session_id: Optional[str] = None,
    ) -> ConversationMemory:
        """Get or create memory for a user."""
        if user_id not in self.user_memories:
            self.user_memories[user_id] = ConversationMemory(user_id, session_id)
        return self.user_memories[user_id]

    def add_global_memory(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        importance: float = 0.5,
    ) -> MemoryEntry:
        """Add a global memory (shared across all users)."""
        memory_id = hashlib.sha256(content.encode()).hexdigest()[:16]
        entry = MemoryEntry(
            id=memory_id,
            memory_type=MemoryType.SEMANTIC,
            content=content,
            metadata=metadata or {},
            importance=importance,
        )
        self.global_memories[memory_id] = entry
        return entry

    def search_global(
        self,
        query: str,
        limit: int = 10,
    ) -> List[MemoryEntry]:
        """Search global memories."""
        results = []
        query_lower = query.lower()

        for entry in self.global_memories.values():
            if query_lower in entry.content.lower():
                entry.touch()
                results.append(entry)

        results.sort(key=lambda e: (e.importance, e.access_count), reverse=True)
        return results[:limit]

    def cleanup_all(self) -> Dict[str, int]:
        """Cleanup expired memories for all users."""
        stats = {"users_cleaned": 0, "memories_removed": 0}
        for memory in self.user_memories.values():
            removed = memory.cleanup_expired()
            if removed > 0:
                stats["users_cleaned"] += 1
                stats["memories_removed"] += removed
        return stats

    def get_stats(self) -> Dict[str, Any]:
        """Get global memory statistics."""
        total_memories = sum(
            len(m.memories) for m in self.user_memories.values()
        )
        return {
            "total_users": len(self.user_memories),
            "total_user_memories": total_memories,
            "total_global_memories": len(self.global_memories),
        }


# Singleton instance
_memory_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """Get the global memory manager instance."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager
