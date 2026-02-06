"""
Admin module for Jarvis system administration.

Provides:
- Authentication and authorization (auth)
- Admin actions (actions)
- Command handlers (commands)
- Broadcast messaging (broadcast)
"""

from core.admin.auth import (
    is_admin,
    require_admin,
    get_admin_user_ids,
    UnauthorizedError,
)

from core.admin.actions import (
    get_status,
    get_logs,
    restart_bot,
    clear_cache,
    reload_config,
    health_check,
)

from core.admin.commands import AdminCommands

from core.admin.broadcast import (
    broadcast,
    broadcast_to_all,
)

__all__ = [
    # Auth
    "is_admin",
    "require_admin",
    "get_admin_user_ids",
    "UnauthorizedError",
    # Actions
    "get_status",
    "get_logs",
    "restart_bot",
    "clear_cache",
    "reload_config",
    "health_check",
    # Commands
    "AdminCommands",
    # Broadcast
    "broadcast",
    "broadcast_to_all",
]
