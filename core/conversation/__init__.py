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
