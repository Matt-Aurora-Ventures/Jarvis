"""
AI Runtime Integration

Provides an easy way to start the comprehensive AI runtime from the supervisor.
"""
import asyncio
import logging
import os
from typing import Optional

from .config import AIRuntimeConfig, AgentConfig
from .bus.socket_bus import SecureMessageBus
from .memory.store import MemoryStore
from .supervisor.ai_supervisor import AISupervisor
from .agents.telegram_agent import TelegramAgent
from .constants import NAMESPACE_TELEGRAM, NAMESPACE_API, NAMESPACE_WEB

logger = logging.getLogger("jarvis.ai_runtime.integration")


class AIRuntimeManager:
    """
    Manages the optional AI runtime layer.

    Fail-open design: If AI fails to start or crashes,
    the supervisor and all bots continue normally.
    """

    def __init__(self):
        self._ai_supervisor: Optional[AISupervisor] = None
        self._bus: Optional[SecureMessageBus] = None
        self._memory: Optional[MemoryStore] = None
        self._agents = {}
        self._running = False
        self._config: Optional[AIRuntimeConfig] = None

    async def start(self, *, use_arena: bool = False) -> bool:
        """
        Attempt to start AI runtime.

        Returns True if started, False if unavailable.
        Failure here is NOT an error - system continues without AI.
        """
        try:
            # Pass arena mode through runtime startup.
            if use_arena:
                os.environ["JARVIS_USE_ARENA"] = "1"
            else:
                os.environ.setdefault("JARVIS_USE_ARENA", "0")

            # Load configuration
            self._config = AIRuntimeConfig.from_env()

            if not self._config.enabled:
                logger.info("AI Runtime disabled by config")
                return False

            # Initialize memory store
            self._memory = MemoryStore(self._config.memory_db_path)

            # Initialize message bus
            self._bus = SecureMessageBus(
                self._config.bus.socket_path, self._config.bus.hmac_key
            )

            # Start bus
            await self._bus.start_server()
            logger.info("Message bus started: %s", self._config.bus.socket_path)

            # Start supervisor
            self._ai_supervisor = AISupervisor(self._config, self._bus, self._memory)
            await self._ai_supervisor.start()
            logger.info("AI Supervisor started")

            # Initialize Telegram agent
            telegram_config = AgentConfig(
                name="telegram_agent",
                namespace=NAMESPACE_TELEGRAM,
                capabilities={
                    "can_observe": True,
                    "can_suggest": True,
                    "can_write_code": False,
                    "can_execute_shell": False,
                    "can_access_secrets": False,
                    "can_modify_files": False,
                    "can_send_messages": False,
                },
            )

            self._agents["telegram"] = TelegramAgent(
                telegram_config, self._config.ollama, self._bus, self._memory
            )

            # Try to initialize agent (may fail if Ollama unavailable)
            agent_available = await self._agents["telegram"].initialize()
            if agent_available:
                self._ai_supervisor.register_agent("telegram_agent")
                logger.info("Telegram agent initialized")
            else:
                logger.info("Telegram agent unavailable (Ollama not accessible)")

            self._running = True
            logger.info("AI Runtime started successfully (use_arena=%s)", use_arena)
            return True

        except ImportError as e:
            logger.info("AI Runtime dependencies not available: %s", e)
            return False
        except Exception as e:
            logger.warning(
                "AI Runtime failed to start (continuing without AI): %s",
                e,
                exc_info=True,
            )
            return False

    async def stop(self):
        """Gracefully stop AI runtime."""
        if not self._running:
            return

        try:
            # Stop agents
            for agent in self._agents.values():
                await agent.shutdown()

            # Stop supervisor
            if self._ai_supervisor:
                await self._ai_supervisor.stop()

            # Stop bus
            if self._bus:
                await self._bus.stop()

            # Close memory
            if self._memory:
                self._memory.close()

            self._running = False
            logger.info("AI Runtime stopped")

        except Exception as e:
            logger.error("Error stopping AI Runtime: %s", e)

    def get_telegram_agent(self):
        """Get Telegram agent if available."""
        return self._agents.get("telegram") if self._running else None

    def get_supervisor(self) -> Optional[AISupervisor]:
        """Get the AI supervisor if available."""
        return self._ai_supervisor if self._running else None

    @property
    def is_running(self) -> bool:
        return self._running


# Global instance for easy access
_runtime_manager: Optional[AIRuntimeManager] = None


def get_ai_runtime_manager() -> AIRuntimeManager:
    """Get the global AI runtime manager instance."""
    global _runtime_manager
    if _runtime_manager is None:
        _runtime_manager = AIRuntimeManager()
    return _runtime_manager
