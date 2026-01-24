"""
Legacy conversation API shim.

Provides generate_response() and sanitize_for_voice() so older modules
can continue to work after the new conversation package refactor.
"""

from __future__ import annotations

from core.conversation import (
    generate_response,
    sanitize_for_voice,
    get_conversation_engine,
)

__all__ = [
    "generate_response",
    "sanitize_for_voice",
    "get_conversation_engine",
]
