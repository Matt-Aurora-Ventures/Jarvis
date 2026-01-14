"""
JARVIS Lifecycle Module

Handles application lifecycle management including:
- Graceful shutdown
- Signal handling
- Component coordination
"""

from .shutdown import (
    ShutdownManager,
    ShutdownPhase,
    ShutdownCallback,
    ShutdownResult,
    ShutdownStatus,
    ShutdownMiddleware,
    LifecycleContext,
    get_shutdown_manager,
)

__all__ = [
    "ShutdownManager",
    "ShutdownPhase",
    "ShutdownCallback",
    "ShutdownResult",
    "ShutdownStatus",
    "ShutdownMiddleware",
    "LifecycleContext",
    "get_shutdown_manager",
]
