"""
Bot Modes - Online/Offline mode management for JARVIS.

This module provides:
- BotMode: Mode enumeration (ONLINE, DEGRADED, OFFLINE, MAINTENANCE)
- BotModeManager: Mode state management
- Capability checking based on mode
"""

from .modes import (
    BotMode,
    BotModeManager,
    ModeCapability,
    get_current_mode,
    get_mode_manager,
    requires_online,
)

__all__ = [
    "BotMode",
    "BotModeManager",
    "ModeCapability",
    "get_current_mode",
    "get_mode_manager",
    "requires_online",
]
