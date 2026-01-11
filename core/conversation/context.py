"""
Context Manager - Manage conversation context windows efficiently.

Handles:
- Context window optimization
- Old context summarization
- Fresh context injection
- Token budget management
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import hashlib


class ContextPriority(Enum):
    """Priority levels for context entries."""
    CRITICAL = 1    # Must include (user preferences, safety)
    HIGH = 2        # Should include (recent messages, active trades)
    MEDIUM = 3      # Include if space (conversation history)
    LOW = 4         # Include last (general knowledge)


@dataclass
class ContextEntry:
    """A single context entry."""
    id: str
    content: str
    priority: ContextPriority = ContextPriority.MEDIUM
    token_count: int = 0  # Estimated tokens
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: str = "conversation"  # conversation, system, portfolio, etc.
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "content": self.content,
            "priority": self.priority.value,
            "token_count": self.token_count,
            "metadata": self.metadata,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }

    def estimate_tokens(self) -> int:
        """Estimate token count (rough approximation)."""
        # Rough estimate: 1 token ≈ 4 characters
        self.token_count = len(self.content) // 4
        return self.token_count


@dataclass
class ContextWindow:
    """A context window for a conversation."""
    max_tokens: int = 8000  # Max context window tokens
    entries: List[ContextEntry] = field(default_factory=list)
    summary: Optional[str] = None
    summary_token_count: int = 0

    def add(self, entry: ContextEntry) -> bool:
        """Add entry to context window."""
        entry.estimate_tokens()

        # Check if we have space
        current_tokens = self.get_token_count()
        if current_tokens + entry.token_count > self.max_tokens:
            # Try to make space by summarizing
            if not self._make_space(entry.token_count):
                return False

        self.entries.append(entry)
        return True

    def get_token_count(self) -> int:
        """Get total token count."""
        return sum(e.token_count for e in self.entries) + self.summary_token_count

    def _make_space(self, needed_tokens: int) -> bool:
        """Try to make space by removing low-priority entries."""
        # Sort by priority (highest priority = lowest number)
        self.entries.sort(key=lambda e: (e.priority.value, e.created_at))

        # Remove low-priority entries until we have space
        while self.entries and self.get_token_count() + needed_tokens > self.max_tokens:
            # Remove the lowest priority, oldest entry
            if self.entries[-1].priority.value >= ContextPriority.MEDIUM.value:
                self.entries.pop()
            else:
                break

        return self.get_token_count() + needed_tokens <= self.max_tokens

    def get_context_string(self) -> str:
        """Get the full context as a string."""
        parts = []

        if self.summary:
            parts.append(f"[Previous conversation summary]\n{self.summary}")

        # Sort entries by priority and time
        sorted_entries = sorted(
            self.entries,
            key=lambda e: (e.priority.value, e.created_at)
        )

        for entry in sorted_entries:
            if entry.source == "system":
                parts.append(f"[System: {entry.metadata.get('type', 'info')}]\n{entry.content}")
            elif entry.source == "portfolio":
                parts.append(f"[Portfolio Context]\n{entry.content}")
            else:
                parts.append(entry.content)

        return "\n\n".join(parts)

    def clear(self) -> None:
        """Clear all entries."""
        self.entries = []
        self.summary = None
        self.summary_token_count = 0


class ContextManager:
    """Manager for conversation context across users."""

    def __init__(self, default_max_tokens: int = 8000):
        self.default_max_tokens = default_max_tokens
        self.windows: Dict[str, ContextWindow] = {}
        self.system_context: List[ContextEntry] = []  # Global system context

    def get_window(self, user_id: str) -> ContextWindow:
        """Get or create context window for user."""
        if user_id not in self.windows:
            self.windows[user_id] = ContextWindow(max_tokens=self.default_max_tokens)
        return self.windows[user_id]

    def add_message(
        self,
        user_id: str,
        content: str,
        role: str = "user",
        priority: ContextPriority = ContextPriority.MEDIUM,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Add a message to user's context window."""
        window = self.get_window(user_id)

        entry = ContextEntry(
            id=self._generate_id(content),
            content=f"{role}: {content}",
            priority=priority,
            metadata=metadata or {"role": role},
            source="conversation",
        )

        return window.add(entry)

    def add_system_context(
        self,
        user_id: str,
        content: str,
        context_type: str = "info",
        priority: ContextPriority = ContextPriority.HIGH,
    ) -> bool:
        """Add system context (portfolio, preferences, etc.)."""
        window = self.get_window(user_id)

        entry = ContextEntry(
            id=self._generate_id(content),
            content=content,
            priority=priority,
            metadata={"type": context_type},
            source="system",
        )

        return window.add(entry)

    def add_portfolio_context(
        self,
        user_id: str,
        portfolio_summary: str,
    ) -> bool:
        """Add portfolio context."""
        window = self.get_window(user_id)

        entry = ContextEntry(
            id=self._generate_id(f"portfolio:{user_id}"),
            content=portfolio_summary,
            priority=ContextPriority.HIGH,
            metadata={"type": "portfolio"},
            source="portfolio",
        )

        return window.add(entry)

    def get_context(self, user_id: str) -> str:
        """Get full context string for user."""
        window = self.get_window(user_id)

        # Add any global system context
        context_parts = []

        for system_entry in self.system_context:
            context_parts.append(f"[System]\n{system_entry.content}")

        context_parts.append(window.get_context_string())

        return "\n\n".join(context_parts)

    def summarize_old_context(self, user_id: str, summary: str) -> None:
        """Set summary for old context."""
        window = self.get_window(user_id)
        window.summary = summary
        window.summary_token_count = len(summary) // 4

    def clear_context(self, user_id: str) -> None:
        """Clear user's context window."""
        if user_id in self.windows:
            self.windows[user_id].clear()

    def add_global_system_context(self, content: str, context_type: str = "info") -> None:
        """Add context that applies to all users."""
        entry = ContextEntry(
            id=self._generate_id(content),
            content=content,
            priority=ContextPriority.CRITICAL,
            metadata={"type": context_type},
            source="system",
        )
        self.system_context.append(entry)

    def _generate_id(self, content: str) -> str:
        """Generate unique ID for context entry."""
        data = f"{content}:{datetime.utcnow().isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def get_stats(self) -> Dict[str, Any]:
        """Get context manager statistics."""
        return {
            "total_users": len(self.windows),
            "global_context_entries": len(self.system_context),
            "windows": {
                user_id: {
                    "entries": len(window.entries),
                    "tokens": window.get_token_count(),
                    "has_summary": window.summary is not None,
                }
                for user_id, window in self.windows.items()
            }
        }


# Singleton instance
_context_manager: Optional[ContextManager] = None


def get_context_manager() -> ContextManager:
    """Get the global context manager instance."""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager
