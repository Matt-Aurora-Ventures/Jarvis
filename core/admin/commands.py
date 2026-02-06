"""
Admin Command Handlers.

Provides the AdminCommands class that handles all admin slash commands:
- /admin status - Get system status
- /admin restart [bot] - Restart a bot
- /admin logs [bot] - Get recent logs
- /admin cost - Get API costs today
- /admin health - Run health check

Usage:
    from core.admin.commands import AdminCommands

    cmds = AdminCommands()

    # Handle a command
    result = await cmds.dispatch(user_id=123456789, command="status")

    # Or call handlers directly
    status = await cmds.handle_status(user_id=123456789)
"""

import logging
from typing import Any, Dict, Optional, Union

from core.admin.auth import is_admin, require_admin, UnauthorizedError
from core.admin.actions import (
    get_status,
    get_logs,
    restart_bot,
    clear_cache,
    reload_config,
    health_check,
)

logger = logging.getLogger(__name__)


# Import cost tracker lazily to avoid circular imports
def get_cost_tracker():
    """Get the cost tracker instance."""
    from core.economics.costs import get_cost_tracker as _get_tracker
    return _get_tracker()


class AdminCommands:
    """
    Admin command handler class.

    Provides handlers for all admin commands with authorization checks.
    """

    # Valid bot names for restart/logs commands
    VALID_BOTS = [
        "telegram_bot",
        "treasury_bot",
        "twitter_poster",
        "sentiment_reporter",
        "autonomous_x",
        "bags_intel",
        "buy_bot",
        "ai_supervisor",
        "public_trading_bot",
        "autonomous_manager",
    ]

    def __init__(self):
        """Initialize admin commands."""
        self._command_map = {
            "status": self.handle_status,
            "restart": self.handle_restart,
            "logs": self.handle_logs,
            "cost": self.handle_cost,
            "costs": self.handle_cost,  # Alias
            "health": self.handle_health,
            "cache": self.handle_clear_cache,
            "reload": self.handle_reload_config,
        }
        logger.debug("AdminCommands initialized")

    async def dispatch(
        self,
        user_id: int,
        command: str,
        **kwargs
    ) -> Union[str, Dict[str, Any]]:
        """
        Dispatch a command to the appropriate handler.

        Args:
            user_id: The user ID making the request
            command: The command name (e.g., "status", "restart")
            **kwargs: Additional arguments for the command

        Returns:
            Command result (string or dict)
        """
        command = command.lower().strip()

        if command not in self._command_map:
            available = ", ".join(sorted(self._command_map.keys()))
            return f"Unknown command: {command}. Available: {available}"

        handler = self._command_map[command]

        try:
            return await handler(user_id=user_id, **kwargs)
        except UnauthorizedError as e:
            logger.warning(f"Unauthorized command {command} by user {user_id}")
            return f"Unauthorized: {e}"
        except Exception as e:
            logger.error(f"Error executing command {command}: {e}", exc_info=True)
            return f"Error: {e}"

    @require_admin
    async def handle_status(self, user_id: int) -> str:
        """
        Handle /admin status command.

        Returns formatted system status.
        """
        status = get_status()

        # Format as readable text
        lines = [
            "=== System Status ===",
            f"Timestamp: {status.get('timestamp', 'N/A')}",
            "",
            "** System **",
        ]

        system = status.get("system", {})
        lines.append(f"  Platform: {system.get('platform', 'N/A')}")
        lines.append(f"  Python: {system.get('python_version', 'N/A')}")
        lines.append(f"  Host: {system.get('hostname', 'N/A')}")

        if status.get("uptime"):
            lines.append(f"  Uptime: {status['uptime']}")

        lines.append("")
        lines.append("** Resources **")
        resources = status.get("resources", {})
        lines.append(f"  CPU: {resources.get('cpu_percent', 0):.1f}%")
        lines.append(f"  Memory: {resources.get('memory_percent', 0):.1f}%")
        lines.append(f"  Disk: {resources.get('disk_percent', 0):.1f}%")

        lines.append("")
        lines.append("** Bots **")
        bots = status.get("bots", {})
        for bot_name, bot_status in sorted(bots.items()):
            icon = "+" if bot_status == "running" else "-"
            lines.append(f"  {icon} {bot_name}: {bot_status}")

        return "\n".join(lines)

    @require_admin
    async def handle_restart(
        self,
        user_id: int,
        bot_name: str = ""
    ) -> str:
        """
        Handle /admin restart [bot] command.

        Args:
            user_id: The admin user ID
            bot_name: Name of the bot to restart

        Returns:
            Restart status message
        """
        if not bot_name:
            bots_list = ", ".join(self.VALID_BOTS)
            return f"Error: Bot name required. Available bots: {bots_list}"

        bot_name = bot_name.lower().strip()

        # Validate bot name
        if bot_name not in self.VALID_BOTS:
            bots_list = ", ".join(self.VALID_BOTS)
            return f"Error: Unknown bot '{bot_name}'. Available: {bots_list}"

        result = await restart_bot(bot_name)

        if result.get("success"):
            return f"Restart initiated for {bot_name}: {result.get('message', 'OK')}"
        else:
            return f"Restart failed for {bot_name}: {result.get('error', 'Unknown error')}"

    @require_admin
    async def handle_logs(
        self,
        user_id: int,
        bot_name: str = "",
        lines: int = 50
    ) -> str:
        """
        Handle /admin logs [bot] command.

        Args:
            user_id: The admin user ID
            bot_name: Name of the bot (default: supervisor)
            lines: Number of lines to return

        Returns:
            Log content
        """
        if not bot_name:
            bot_name = "supervisor"

        bot_name = bot_name.lower().strip()
        lines = min(max(1, lines), 500)  # Clamp to 1-500

        log_content = get_logs(bot_name, lines=lines)

        if not log_content or log_content.startswith("No logs"):
            return f"No logs found for {bot_name}"

        # Truncate if too long for Telegram
        max_length = 4000
        if len(log_content) > max_length:
            log_content = "...(truncated)\n" + log_content[-(max_length - 20):]

        return f"=== Logs for {bot_name} (last {lines} lines) ===\n\n{log_content}"

    @require_admin
    async def handle_cost(self, user_id: int, days: int = 1) -> str:
        """
        Handle /admin cost command.

        Args:
            user_id: The admin user ID
            days: Number of days to summarize (default: 1)

        Returns:
            Cost summary
        """
        tracker = get_cost_tracker()
        summary = tracker.get_summary(days=days)

        lines = [
            f"=== API Costs ({days} day{'s' if days > 1 else ''}) ===",
            "",
            f"Total: ${summary.total_usd:.4f} USD",
            f"API Calls: {summary.api_calls}",
            f"Total Tokens: {summary.total_tokens:,}",
            "",
            "** By Provider **",
        ]

        for provider, cost in sorted(
            summary.by_provider.items(),
            key=lambda x: x[1],
            reverse=True
        ):
            lines.append(f"  {provider}: ${cost:.4f}")

        if summary.by_category:
            lines.append("")
            lines.append("** By Category **")
            for category, cost in sorted(
                summary.by_category.items(),
                key=lambda x: x[1],
                reverse=True
            ):
                lines.append(f"  {category}: ${cost:.4f}")

        return "\n".join(lines)

    @require_admin
    async def handle_health(self, user_id: int) -> str:
        """
        Handle /admin health command.

        Returns:
            Health check results
        """
        result = await health_check()

        overall = "HEALTHY" if result.get("healthy") else "UNHEALTHY"
        icon = "+" if result.get("healthy") else "!"

        lines = [
            f"=== Health Check: {overall} ===",
            f"Timestamp: {result.get('timestamp', 'N/A')}",
            "",
            "** Components **",
        ]

        components = result.get("components", {})
        for component, status in sorted(components.items()):
            if status == "ok":
                comp_icon = "+"
            elif status == "degraded":
                comp_icon = "~"
            else:
                comp_icon = "!"
            lines.append(f"  {comp_icon} {component}: {status}")

        return "\n".join(lines)

    @require_admin
    async def handle_clear_cache(self, user_id: int) -> str:
        """
        Handle /admin cache command to clear caches.

        Returns:
            Cache clearing results
        """
        result = clear_cache()

        if result.get("success"):
            return (
                f"Cache cleared successfully.\n"
                f"Files removed: {result.get('cleared_files', 0)}\n"
                f"Space freed: {result.get('cleared_mb', 0):.2f} MB"
            )
        else:
            errors = result.get("errors", [])
            return f"Cache clearing completed with errors:\n" + "\n".join(errors[:5])

    @require_admin
    async def handle_reload_config(self, user_id: int) -> str:
        """
        Handle /admin reload command to reload configs.

        Returns:
            Config reload results
        """
        result = reload_config()

        if result.get("success"):
            reloaded = result.get("reloaded", [])
            return f"Config reloaded successfully:\n" + "\n".join(f"  - {r}" for r in reloaded)
        else:
            errors = result.get("errors", [])
            return f"Config reload completed with errors:\n" + "\n".join(errors[:5])
