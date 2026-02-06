"""
State Machine Framework for Bot Conversations

This module provides a flexible state machine implementation for managing
multi-turn conversations in bots (Telegram, Discord, etc.).

Components:
- StateMachine: Core state machine with transitions and callbacks
- ConversationContext: Context object for storing conversation state and data
- StateStorage: Storage backends (memory, file, Redis)
- StateHandler: Base class for state-specific message handlers

Example usage:
    from core.state import StateMachine, ConversationContext, InMemoryStorage

    # Create a state machine
    sm = StateMachine(initial_state="idle")
    sm.add_state("idle", on_enter=lambda ctx: print("Waiting..."))
    sm.add_state("processing", on_enter=lambda ctx: print("Processing..."))
    sm.add_transition("idle", "processing", "start")

    # Trigger transition
    sm.trigger("start")

    # Create conversation context
    ctx = ConversationContext(user_id="123", chat_id="456")
    ctx.data["token"] = "SOL"

    # Store in memory
    storage = InMemoryStorage()
    storage.save(ctx)
"""

from core.state.machine import StateMachine, StateError
from core.state.context import ConversationContext
from core.state.storage import StateStorage, InMemoryStorage, JSONFileStorage, RedisStorage
from core.state.handlers import StateHandler, Response, HandlerRegistry

__all__ = [
    "StateMachine",
    "StateError",
    "ConversationContext",
    "StateStorage",
    "InMemoryStorage",
    "JSONFileStorage",
    "RedisStorage",
    "StateHandler",
    "Response",
    "HandlerRegistry",
]
