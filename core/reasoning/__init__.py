"""
Advanced Reasoning Modes for JARVIS

Provides:
- Thinking levels (off, minimal, low, medium, high, xhigh)
- Reasoning modes (on, off, stream)
- Verbose modes (on, off, full)
- State persistence per user/session
"""

from core.reasoning.engine import ReasoningEngine
from core.reasoning.state import ReasoningState, StateManager, get_state_manager

__all__ = [
    "ReasoningEngine",
    "ReasoningState",
    "StateManager",
    "get_state_manager",
]
