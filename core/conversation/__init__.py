"""
Conversation Engine - Natural, context-aware conversations across all platforms.

This module provides:
- ConversationEngine: Main engine for managing conversations
- ConversationMemory: Memory types (session, user, relationship, global)
- IntentClassifier: Classify user intents
- ContextManager: Manage context windows
"""

from .engine import (
    ConversationEngine,
    ConversationConfig,
    Personality,
    get_conversation_engine,
)
from .memory import (
    ConversationMemory,
    MemoryType,
    MemoryEntry,
    MemoryManager,
    get_memory_manager,
)
from .intent import (
    IntentClassifier,
    Intent,
    IntentType,
    get_intent_classifier,
)
from .context import (
    ContextManager,
    ContextWindow,
    ContextEntry,
    get_context_manager,
)

# Re-export utility functions from the legacy conversation module
def _truncate(text: str, limit: int = 800) -> str:
    """Truncate text to limit with ellipsis."""
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _format_history(entries: list) -> str:
    """Format chat history entries."""
    lines = []
    for entry in entries:
        role = "User" if entry.get("source") == "voice_chat_user" else "Assistant"
        text = _truncate(entry.get("text", ""), 400)
        if text:
            lines.append(f"{role}: {text}")
    return "\n".join(lines).strip()


def _extract_entities(user_text: str) -> dict:
    """Extract key entities from user input."""
    import re
    entities = {
        "people": [],
        "tools": [],
        "projects": [],
        "actions": [],
        "topics": [],
    }
    lowered = user_text.lower()
    
    # Tool mentions
    tools = ["python", "git", "docker", "npm", "ollama", "cursor", "windsurf", 
             "vscode", "terminal", "browser", "firefox", "chrome", "notion", "obsidian"]
    entities["tools"] = [t for t in tools if t in lowered]
    
    # Action verbs
    action_patterns = [
        (r"\b(create|make|build|generate)\b", "create"),
        (r"\b(fix|repair|debug|solve)\b", "fix"),
        (r"\b(improve|enhance|optimize|upgrade)\b", "improve"),
        (r"\b(analyze|research|investigate|study)\b", "analyze"),
        (r"\b(delete|remove|clear|clean)\b", "delete"),
        (r"\b(open|launch|start|run)\b", "open"),
        (r"\b(send|share|post|publish)\b", "send"),
        (r"\b(find|search|look for|locate)\b", "find"),
    ]
    for pattern, action in action_patterns:
        if re.search(pattern, lowered):
            entities["actions"].append(action)
    
    # Topic detection
    topic_keywords = {
        "crypto": ["trading", "crypto", "bitcoin", "ethereum", "solana", "defi", "wallet"],
        "development": ["code", "programming", "development", "api", "function", "module"],
        "business": ["revenue", "sales", "marketing", "client", "customer", "project"],
        "personal": ["health", "fitness", "habits", "goals", "schedule", "calendar"],
    }
    for topic, keywords in topic_keywords.items():
        if any(kw in lowered for kw in keywords):
            entities["topics"].append(topic)
    
    return entities


def _is_research_request(user_text: str) -> bool:
    """Detect if user is requesting research."""
    lowered = user_text.lower()
    triggers = [
        "research", "deep dive", "investigate", "look up", "find sources",
        "summarize sources", "analyze sources", "what is", "who is",
    ]
    return any(t in lowered for t in triggers)


__all__ = [
    # Engine
    "ConversationEngine",
    "ConversationConfig",
    "Personality",
    "get_conversation_engine",
    # Memory
    "ConversationMemory",
    "MemoryType",
    "MemoryEntry",
    "MemoryManager",
    "get_memory_manager",
    # Intent
    "IntentClassifier",
    "Intent",
    "IntentType",
    "get_intent_classifier",
    # Context
    "ContextManager",
    "ContextWindow",
    "ContextEntry",
    "get_context_manager",
]
