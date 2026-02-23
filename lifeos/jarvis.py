"""
Jarvis - Main Orchestration Class

The central hub that connects all LifeOS systems:
- Configuration management
- Service registry (LLM, Market, Notifications)
- Plugin management
- Memory sandboxing
- PAE (Provider-Action-Evaluator) registry
- Persona management
- Event bus

Usage:
    from lifeos import Jarvis

    jarvis = Jarvis()
    await jarvis.start()

    response = await jarvis.chat("What's the SOL price?")
    print(response)

    await jarvis.stop()
"""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from lifeos.config import Config, get_config
from lifeos.events import EventBus, Event, EventPriority
from lifeos.memory import MemoryStore, MemoryContext
from lifeos.pae import PAERegistry
from lifeos.persona import PersonaManager, PersonaState
from lifeos.plugins import PluginManager

logger = logging.getLogger(__name__)

try:
    from bots.shared.supermemory_client import get_memory_client
except Exception:  # pragma: no cover - optional dependency
    get_memory_client = None  # type: ignore[assignment]


class Jarvis:
    """
    Main Jarvis orchestration class.

    Coordinates all subsystems and provides a unified interface
    for interacting with the AI assistant.
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        plugins_dir: Optional[Path] = None,
        personas_dir: Optional[Path] = None,
    ):
        """
        Initialize Jarvis.

        Args:
            config: Configuration (uses global if None)
            plugins_dir: Directory for plugins
            personas_dir: Directory for persona definitions
        """
        self._config = config or get_config()
        self._plugins_dir = plugins_dir or Path("plugins")
        self._personas_dir = personas_dir

        # Core systems
        self._event_bus: Optional[EventBus] = None
        self._memory: Optional[MemoryStore] = None
        self._pae: Optional[PAERegistry] = None
        self._persona: Optional[PersonaManager] = None
        self._plugins: Optional[PluginManager] = None

        # LLM service
        self._llm = None
        self._supermemory_client = None

        # State
        self._started = False
        self._start_time: Optional[datetime] = None
        self._shutdown_handlers: List[Callable] = []

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def start(self) -> "Jarvis":
        """
        Start Jarvis and all subsystems.

        Returns:
            Self for chaining
        """
        if self._started:
            logger.warning("Jarvis already started")
            return self

        logger.info("Starting Jarvis...")
        self._start_time = datetime.now(timezone.utc)

        # Initialize event bus first (others may emit events)
        self._event_bus = EventBus(
            max_history=self._config.get("events.max_history", 1000),
            max_dead_letters=self._config.get("events.max_dead_letters", 100),
        )

        # Initialize memory
        self._memory = MemoryStore()

        # Initialize PAE registry with services
        self._pae = PAERegistry(services=self._build_services())

        # Initialize persona manager
        self._persona = PersonaManager(
            personas_dir=self._personas_dir,
            default_persona=self._config.get("persona.default", "jarvis"),
        )

        # Initialize plugin manager
        if self._config.get("plugins.enabled", True):
            self._plugins = PluginManager(
                plugin_dirs=[self._plugins_dir],
                services=self._build_services(),
            )

            if self._config.get("plugins.auto_load", True):
                await self._plugins.start()

        # Initialize LLM service
        await self._init_llm()

        # Emit startup event
        await self._event_bus.emit(
            "jarvis.started",
            {"timestamp": self._start_time.isoformat()},
            priority=EventPriority.HIGH,
        )

        self._started = True
        logger.info("Jarvis started successfully")
        return self

    async def stop(self) -> None:
        """Stop Jarvis and all subsystems."""
        if not self._started:
            return

        logger.info("Stopping Jarvis...")

        # Emit shutdown event
        if self._event_bus:
            await self._event_bus.emit(
                "jarvis.stopping",
                priority=EventPriority.HIGH,
            )

        # Run shutdown handlers
        for handler in self._shutdown_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler()
                else:
                    handler()
            except Exception as e:
                logger.error(f"Shutdown handler failed: {e}")

        # Stop plugins
        if self._plugins:
            await self._plugins.stop()

        # Shutdown PAE
        if self._pae:
            await self._pae.shutdown()

        self._started = False
        logger.info("Jarvis stopped")

    def on_shutdown(self, handler: Callable) -> None:
        """Register a shutdown handler."""
        self._shutdown_handlers.append(handler)

    async def _init_llm(self) -> None:
        """Initialize LLM service based on config."""
        provider = self._config.get("llm.provider", "groq")

        try:
            if provider == "groq":
                from lifeos.services.llm import GroqLLMAdapter
                api_key = self._config.get("llm.api_key") or os.environ.get("GROQ_API_KEY")
                self._llm = GroqLLMAdapter(
                    api_key=api_key,
                    model=self._config.get("llm.model", "llama-3.3-70b-versatile"),
                )
            elif provider == "ollama":
                from lifeos.services.llm import OllamaLLMAdapter
                self._llm = OllamaLLMAdapter(
                    model=self._config.get("llm.model", "llama3.2"),
                    base_url=self._config.get("llm.base_url", "http://localhost:11434"),
                )
            elif provider == "openai":
                from lifeos.services.llm import OpenAILLMAdapter
                api_key = self._config.get("llm.api_key") or os.environ.get("OPENAI_API_KEY")
                self._llm = OpenAILLMAdapter(
                    api_key=api_key,
                    model=self._config.get("llm.model", "gpt-4o"),
                )
            else:
                logger.warning(f"Unknown LLM provider: {provider}")
        except ImportError as e:
            logger.warning(f"Failed to import LLM adapter: {e}")
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")

    def _get_supermemory_client(self, persona: Optional[str] = None):
        """
        Lazily initialize the optional supermemory client.
        """
        if self._supermemory_client is not None:
            return self._supermemory_client
        if get_memory_client is None:
            return None

        try:
            bot_name = (persona or self._config.get("persona.default", "jarvis") or "jarvis").lower()
            self._supermemory_client = get_memory_client(bot_name=bot_name)
            return self._supermemory_client
        except Exception as e:
            logger.debug(f"Supermemory client unavailable: {e}")
            return None

    def _build_services(self) -> Dict[str, Any]:
        """Build services dictionary for dependency injection."""
        return {
            "config": self._config,
            "event_bus": self._event_bus,
            "memory": self._memory,
            "llm": self._llm,
            "jarvis": self,
        }

    # =========================================================================
    # Chat Interface
    # =========================================================================

    async def chat(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        persona: Optional[str] = None,
    ) -> str:
        """
        Send a message and get a response.

        Args:
            message: User message
            context: Additional context
            persona: Override persona for this message

        Returns:
            Assistant response
        """
        if not self._started:
            await self.start()

        # Set persona if specified
        if persona and self._persona:
            self._persona.set_active(persona)

        # Emit chat event
        await self._event_bus.emit(
            "chat.message",
            {"message": message, "context": context},
        )

        # Get system prompt from persona
        system_prompt = ""
        if self._persona:
            context_type = context.get("context_type") if context else None
            system_prompt = self._persona.get_system_prompt(context_type)

        # preRecall hook: inject dual-profile memory context before LLM call.
        memory_client = self._get_supermemory_client(persona=persona)
        if memory_client is not None:
            try:
                pre_recall_payload = await memory_client.pre_recall(message)
                prompt_block = pre_recall_payload.get("prompt_block", "")
                if prompt_block:
                    system_prompt = f"{system_prompt}\n\n{prompt_block}".strip()
            except Exception as e:
                logger.debug(f"Supermemory pre_recall skipped: {e}")

        # Build messages
        from lifeos.services.interfaces import LLMMessage, LLMConfig

        messages = [LLMMessage(role="user", content=message)]

        # Call LLM
        if self._llm:
            try:
                config = LLMConfig(
                    temperature=self._config.get("llm.temperature", 0.7),
                    max_tokens=self._config.get("llm.max_tokens", 500),
                )
                response = await self._llm.chat(
                    messages=messages,
                    system_prompt=system_prompt,
                    config=config,
                )

                # Style response
                styled = response.content
                if self._persona:
                    styled = await self._persona.style_response(styled, context)

                # Emit response event
                await self._event_bus.emit(
                    "chat.response",
                    {"response": styled, "model": response.model},
                )

                # postResponse hook: async memory capture after response is ready.
                if memory_client is not None:
                    async def _post_response_capture():
                        try:
                            await memory_client.post_response(
                                user_message=message,
                                assistant_response=styled,
                                metadata={"source": "lifeos.jarvis.chat"},
                            )
                        except Exception as hook_error:
                            logger.debug(f"Supermemory post_response skipped: {hook_error}")

                    asyncio.create_task(_post_response_capture())

                return styled

            except Exception as e:
                logger.error(f"Chat failed: {e}")
                if self._persona:
                    return self._persona.format_error(str(e))
                return f"I encountered an error: {e}"
        else:
            return "LLM service not available"

    # =========================================================================
    # Memory Interface
    # =========================================================================

    async def remember(
        self,
        key: str,
        value: Any,
        context: MemoryContext = MemoryContext.PUBLIC,
    ) -> None:
        """Store a value in memory."""
        await self._memory.set(
            key=key,
            value=value,
            context=context,
            caller_context=context,
        )

    async def recall(
        self,
        key: str,
        context: MemoryContext = MemoryContext.PUBLIC,
        default: Any = None,
    ) -> Any:
        """Retrieve a value from memory."""
        return await self._memory.get(
            key=key,
            context=context,
            caller_context=context,
            default=default,
        )

    async def forget(
        self,
        key: str,
        context: MemoryContext = MemoryContext.PUBLIC,
    ) -> bool:
        """Delete a value from memory."""
        return await self._memory.delete(
            key=key,
            context=context,
            caller_context=context,
        )

    # =========================================================================
    # Event Interface
    # =========================================================================

    def on(
        self,
        pattern: str,
        priority: int = 0,
    ) -> Callable:
        """Subscribe to events."""
        return self._event_bus.on(pattern, priority=priority)

    async def emit(
        self,
        topic: str,
        data: Optional[Dict[str, Any]] = None,
        priority: EventPriority = EventPriority.NORMAL,
    ) -> Event:
        """Emit an event."""
        return await self._event_bus.emit(topic, data, priority=priority)

    # =========================================================================
    # Persona Interface
    # =========================================================================

    def set_persona(self, name: str) -> bool:
        """Switch to a different persona."""
        if self._persona:
            return self._persona.set_active(name)
        return False

    def set_state(self, state: PersonaState) -> None:
        """Set persona state."""
        if self._persona:
            self._persona.set_state(state)

    def get_greeting(self, context: Optional[Dict[str, Any]] = None) -> str:
        """Get a greeting from the current persona."""
        if self._persona:
            return self._persona.get_greeting(context)
        return "Hello!"

    # =========================================================================
    # Plugin Interface
    # =========================================================================

    async def load_plugin(self, name: str) -> bool:
        """Load a specific plugin."""
        if self._plugins:
            try:
                await self._plugins.enable(name)
                return True
            except Exception as e:
                logger.error(f"Failed to load plugin {name}: {e}")
        return False

    async def unload_plugin(self, name: str) -> bool:
        """Unload a plugin."""
        if self._plugins:
            try:
                await self._plugins.disable(name)
                return True
            except Exception:
                pass
        return False

    def list_plugins(self) -> List[str]:
        """List loaded plugins."""
        if self._plugins:
            return list(self._plugins._loader.get_all_plugins().keys())
        return []

    # =========================================================================
    # PAE Interface
    # =========================================================================

    async def provide(self, provider_name: str, query: Dict[str, Any]) -> Any:
        """Call a provider."""
        if self._pae:
            provider = self._pae.get_provider(provider_name)
            if provider:
                return await provider(query)
        raise ValueError(f"Provider not found: {provider_name}")

    async def execute(self, action_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an action."""
        if self._pae:
            action = self._pae.get_action(action_name)
            if action:
                return await action(params)
        raise ValueError(f"Action not found: {action_name}")

    async def evaluate(self, evaluator_name: str, context: Dict[str, Any]) -> Any:
        """Call an evaluator."""
        if self._pae:
            evaluator = self._pae.get_evaluator(evaluator_name)
            if evaluator:
                return await evaluator(context)
        raise ValueError(f"Evaluator not found: {evaluator_name}")

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def is_running(self) -> bool:
        """Check if Jarvis is running."""
        return self._started

    @property
    def config(self) -> Config:
        """Get configuration."""
        return self._config

    @property
    def event_bus(self) -> Optional[EventBus]:
        """Get event bus."""
        return self._event_bus

    @property
    def memory(self) -> Optional[MemoryStore]:
        """Get memory store."""
        return self._memory

    @property
    def pae(self) -> Optional[PAERegistry]:
        """Get PAE registry."""
        return self._pae

    @property
    def persona_manager(self) -> Optional[PersonaManager]:
        """Get persona manager."""
        return self._persona

    @property
    def plugin_manager(self) -> Optional[PluginManager]:
        """Get plugin manager."""
        return self._plugins

    @property
    def uptime(self) -> float:
        """Get uptime in seconds."""
        if self._start_time:
            return (datetime.now(timezone.utc) - self._start_time).total_seconds()
        return 0

    def get_stats(self) -> Dict[str, Any]:
        """Get system statistics."""
        stats = {
            "running": self._started,
            "uptime_seconds": self.uptime,
            "persona": self._persona.get_active_name() if self._persona else None,
        }

        if self._event_bus:
            stats["events"] = self._event_bus.get_stats()

        if self._memory:
            stats["memory"] = self._memory.get_stats()

        if self._pae:
            stats["pae"] = self._pae.get_stats()

        if self._plugins:
            stats["plugins"] = {
                "loaded": len(self.list_plugins()),
            }

        return stats


# Import for type hints
import os
