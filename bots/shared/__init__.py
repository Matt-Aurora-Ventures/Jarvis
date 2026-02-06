"""
Shared modules for ClawdBots.

Provides common capabilities that all bots can use:
- Computer control (browser automation, system control)
- Inter-bot coordination (task handoff, messaging, status)
- Command registry (unified command management)
- Self-healing, observability, heartbeat monitoring
- Cost tracking, rate limiting, scheduling
- Conversation memory, state management, analytics
- General utilities (time, text, data, network, file helpers)
"""

# Core modules (always available)
from .computer_capabilities import (
    browse_web,
    control_computer,
    send_telegram_web,
    read_telegram_web,
    check_remote_status,
    get_capabilities_prompt,
    COMPUTER_CAPABILITIES_PROMPT,
)

from .coordination import (
    BotCoordinator,
    BotRole,
    TaskPriority,
    TaskStatus,
    CoordinationTask,
    BotMessage,
    BotStatus,
    CoordinationError,
    get_coordinator,
)

from .campaign_orchestrator import CampaignOrchestrator

from .command_registry import (
    CommandRegistry,
    CommandInfo,
    CommandNotFoundError,
    CommandDisabledError,
    DuplicateCommandError,
    CommandRegistryError,
    get_global_registry,
    set_global_registry,
    create_bot_registry,
)

# Lazy imports for optional modules - each can be imported directly
# e.g. from bots.shared.self_healing import SelfHealingManager

_LAZY_MODULES = [
    "analytics",
    "cache",
    "config_loader",
    "conversation_memory",
    "cost_tracker",
    "error_handler",
    "heartbeat",
    "life_control_commands",
    "logging_utils",
    "observability",
    "personality",
    "rate_limiter",
    "scheduler",
    "security",
    "self_healing",
    "sleep_compute",
    "state_manager",
    "user_preferences",
    "webhook_handler",
]

__all__ = [
    # Computer capabilities
    "browse_web",
    "control_computer",
    "send_telegram_web",
    "read_telegram_web",
    "check_remote_status",
    "get_capabilities_prompt",
    "COMPUTER_CAPABILITIES_PROMPT",
    # Coordination
    "BotCoordinator",
    "BotRole",
    "TaskPriority",
    "TaskStatus",
    "CoordinationTask",
    "BotMessage",
    "BotStatus",
    "CoordinationError",
    "get_coordinator",
    # Campaign
    "CampaignOrchestrator",
    # Command Registry
    "CommandRegistry",
    "CommandInfo",
    "CommandNotFoundError",
    "CommandDisabledError",
    "DuplicateCommandError",
    "CommandRegistryError",
    "get_global_registry",
    "set_global_registry",
    "create_bot_registry",
] + _LAZY_MODULES
