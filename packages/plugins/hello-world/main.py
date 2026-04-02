"""
Hello World Plugin

Example plugin demonstrating the Jarvis plugin system.
Shows how to:
- Use lifecycle hooks
- Access configuration
- Create background tasks
- Use services (when available)
"""

import asyncio
from typing import Any, Dict

from lifeos.plugins import Plugin


class HelloWorldPlugin(Plugin):
    """
    Example plugin that demonstrates plugin capabilities.

    This plugin:
    - Logs a greeting on enable
    - Optionally runs a periodic background task
    - Demonstrates configuration usage
    """

    async def on_load(self) -> None:
        """Called once when plugin is loaded."""
        self.logger.info(
            f"HelloWorld plugin loaded! Version: {self.version}"
        )
        self._greeting_count = 0

    async def on_enable(self) -> None:
        """Called when plugin is enabled."""
        greeting = self.config.get("greeting", "Hello!")
        self.logger.info(f"Plugin enabled: {greeting}")

        # Start background task if configured
        interval = self.config.get("interval_seconds", 0)
        if interval > 0:
            self.create_task(self._periodic_greeting(interval))

    async def on_disable(self) -> None:
        """Called when plugin is disabled."""
        self.logger.info(
            f"Plugin disabled. Sent {self._greeting_count} greetings."
        )

    async def on_unload(self) -> None:
        """Called before plugin is unloaded."""
        self.logger.info("HelloWorld plugin unloading. Goodbye!")

    async def on_config_change(self, new_config: Dict[str, Any]) -> None:
        """Called when configuration changes."""
        self.logger.info(f"Config changed: {new_config}")

    async def _periodic_greeting(self, interval: int) -> None:
        """Background task that sends periodic greetings."""
        self.logger.info(f"Starting periodic greetings every {interval}s")

        while True:
            await asyncio.sleep(interval)
            self._greeting_count += 1
            greeting = self.config.get("greeting", "Hello!")
            self.logger.info(f"[{self._greeting_count}] {greeting}")

            # Try to send notification if we have permission
            notifications = self.get_service("notifications")
            if notifications:
                try:
                    await notifications.send(
                        message=greeting,
                        title="Jarvis Hello World",
                    )
                except Exception as e:
                    self.logger.debug(f"Could not send notification: {e}")

    # =========================================================================
    # Public API (for other plugins to use)
    # =========================================================================

    def greet(self, name: str = "World") -> str:
        """
        Generate a greeting.

        Args:
            name: Name to greet

        Returns:
            Greeting string
        """
        base = self.config.get("greeting", "Hello")
        return f"{base}, {name}!"

    def get_greeting_count(self) -> int:
        """Get the number of greetings sent."""
        return self._greeting_count
