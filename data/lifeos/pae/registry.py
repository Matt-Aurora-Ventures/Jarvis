"""
PAE Registry

Central registry for managing Provider, Action, and Evaluator components.

Features:
- Registration via decorators or direct calls
- Dependency injection
- Component discovery
- Lifecycle management
- Health monitoring
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Type,
    TypeVar,
    Union,
)

from lifeos.pae.base import (
    PAEComponent,
    Provider,
    Action,
    Evaluator,
    ComponentStatus,
    ComponentHealth,
    PAEError,
)

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=PAEComponent)


@dataclass
class RegistryEntry:
    """Entry in the registry."""
    name: str
    component_type: str  # "provider", "action", "evaluator"
    component: PAEComponent
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: Set[str] = field(default_factory=set)
    enabled: bool = True


class PAERegistry:
    """
    Central registry for PAE components.

    Manages the lifecycle of providers, actions, and evaluators.
    Supports dependency injection and component discovery.

    Usage:
        registry = PAERegistry()

        # Register via decorator
        @registry.provider("weather")
        class WeatherProvider(Provider):
            ...

        # Register directly
        registry.register_provider("time", TimeProvider())

        # Get component
        weather = registry.get_provider("weather")
        data = await weather({"city": "NYC"})
    """

    def __init__(self, services: Optional[Dict[str, Any]] = None):
        """
        Initialize registry.

        Args:
            services: Shared services to inject into components
        """
        self._services = services or {}
        self._providers: Dict[str, RegistryEntry] = {}
        self._actions: Dict[str, RegistryEntry] = {}
        self._evaluators: Dict[str, RegistryEntry] = {}
        self._initialized = False

    # =========================================================================
    # Registration Methods
    # =========================================================================

    def provider(
        self,
        name: str,
        tags: Optional[Set[str]] = None,
        dependencies: Optional[Dict[str, Any]] = None,
    ) -> Callable[[Type[Provider]], Type[Provider]]:
        """
        Decorator to register a Provider class.

        Args:
            name: Provider name
            tags: Optional tags for discovery
            dependencies: Additional dependencies to inject

        Returns:
            Decorator function
        """
        def decorator(cls: Type[Provider]) -> Type[Provider]:
            deps = {**self._services, **(dependencies or {})}
            instance = cls(name, deps)
            self.register_provider(name, instance, tags)
            return cls
        return decorator

    def action(
        self,
        name: str,
        tags: Optional[Set[str]] = None,
        dependencies: Optional[Dict[str, Any]] = None,
    ) -> Callable[[Type[Action]], Type[Action]]:
        """
        Decorator to register an Action class.

        Args:
            name: Action name
            tags: Optional tags for discovery
            dependencies: Additional dependencies to inject

        Returns:
            Decorator function
        """
        def decorator(cls: Type[Action]) -> Type[Action]:
            deps = {**self._services, **(dependencies or {})}
            instance = cls(name, deps)
            self.register_action(name, instance, tags)
            return cls
        return decorator

    def evaluator(
        self,
        name: str,
        tags: Optional[Set[str]] = None,
        dependencies: Optional[Dict[str, Any]] = None,
    ) -> Callable[[Type[Evaluator]], Type[Evaluator]]:
        """
        Decorator to register an Evaluator class.

        Args:
            name: Evaluator name
            tags: Optional tags for discovery
            dependencies: Additional dependencies to inject

        Returns:
            Decorator function
        """
        def decorator(cls: Type[Evaluator]) -> Type[Evaluator]:
            deps = {**self._services, **(dependencies or {})}
            instance = cls(name, deps)
            self.register_evaluator(name, instance, tags)
            return cls
        return decorator

    def register_provider(
        self,
        name: str,
        provider: Provider,
        tags: Optional[Set[str]] = None,
    ) -> None:
        """Register a provider instance."""
        if name in self._providers:
            logger.warning(f"Overwriting existing provider: {name}")

        self._providers[name] = RegistryEntry(
            name=name,
            component_type="provider",
            component=provider,
            tags=tags or set(),
        )
        logger.debug(f"Registered provider: {name}")

    def register_action(
        self,
        name: str,
        action: Action,
        tags: Optional[Set[str]] = None,
    ) -> None:
        """Register an action instance."""
        if name in self._actions:
            logger.warning(f"Overwriting existing action: {name}")

        self._actions[name] = RegistryEntry(
            name=name,
            component_type="action",
            component=action,
            tags=tags or set(),
        )
        logger.debug(f"Registered action: {name}")

    def register_evaluator(
        self,
        name: str,
        evaluator: Evaluator,
        tags: Optional[Set[str]] = None,
    ) -> None:
        """Register an evaluator instance."""
        if name in self._evaluators:
            logger.warning(f"Overwriting existing evaluator: {name}")

        self._evaluators[name] = RegistryEntry(
            name=name,
            component_type="evaluator",
            component=evaluator,
            tags=tags or set(),
        )
        logger.debug(f"Registered evaluator: {name}")

    # =========================================================================
    # Retrieval Methods
    # =========================================================================

    def get_provider(self, name: str) -> Optional[Provider]:
        """Get a provider by name."""
        entry = self._providers.get(name)
        if entry and entry.enabled:
            return entry.component
        return None

    def get_action(self, name: str) -> Optional[Action]:
        """Get an action by name."""
        entry = self._actions.get(name)
        if entry and entry.enabled:
            return entry.component
        return None

    def get_evaluator(self, name: str) -> Optional[Evaluator]:
        """Get an evaluator by name."""
        entry = self._evaluators.get(name)
        if entry and entry.enabled:
            return entry.component
        return None

    def get_component(self, name: str) -> Optional[PAEComponent]:
        """Get any component by name."""
        return (
            self.get_provider(name) or
            self.get_action(name) or
            self.get_evaluator(name)
        )

    # =========================================================================
    # Discovery Methods
    # =========================================================================

    def list_providers(self, tag: Optional[str] = None) -> List[str]:
        """List all provider names, optionally filtered by tag."""
        return [
            name for name, entry in self._providers.items()
            if entry.enabled and (tag is None or tag in entry.tags)
        ]

    def list_actions(self, tag: Optional[str] = None) -> List[str]:
        """List all action names, optionally filtered by tag."""
        return [
            name for name, entry in self._actions.items()
            if entry.enabled and (tag is None or tag in entry.tags)
        ]

    def list_evaluators(self, tag: Optional[str] = None) -> List[str]:
        """List all evaluator names, optionally filtered by tag."""
        return [
            name for name, entry in self._evaluators.items()
            if entry.enabled and (tag is None or tag in entry.tags)
        ]

    def find_by_tag(self, tag: str) -> Dict[str, List[str]]:
        """Find all components with a given tag."""
        return {
            "providers": self.list_providers(tag),
            "actions": self.list_actions(tag),
            "evaluators": self.list_evaluators(tag),
        }

    # =========================================================================
    # Lifecycle Management
    # =========================================================================

    async def initialize(self) -> None:
        """Initialize all registered components."""
        if self._initialized:
            return

        all_entries = (
            list(self._providers.values()) +
            list(self._actions.values()) +
            list(self._evaluators.values())
        )

        for entry in all_entries:
            try:
                await entry.component.initialize()
                logger.debug(f"Initialized {entry.component_type}: {entry.name}")
            except Exception as e:
                logger.error(f"Failed to initialize {entry.name}: {e}")
                entry.enabled = False

        self._initialized = True
        logger.info(f"Initialized {len(all_entries)} PAE components")

    async def shutdown(self) -> None:
        """Shutdown all registered components."""
        all_entries = (
            list(self._providers.values()) +
            list(self._actions.values()) +
            list(self._evaluators.values())
        )

        for entry in reversed(all_entries):
            try:
                await entry.component.shutdown()
                logger.debug(f"Shutdown {entry.component_type}: {entry.name}")
            except Exception as e:
                logger.error(f"Failed to shutdown {entry.name}: {e}")

        self._initialized = False

    def enable(self, name: str) -> bool:
        """Enable a component."""
        for registry in [self._providers, self._actions, self._evaluators]:
            if name in registry:
                registry[name].enabled = True
                return True
        return False

    def disable(self, name: str) -> bool:
        """Disable a component."""
        for registry in [self._providers, self._actions, self._evaluators]:
            if name in registry:
                registry[name].enabled = False
                return True
        return False

    def unregister(self, name: str) -> bool:
        """Unregister a component."""
        for registry in [self._providers, self._actions, self._evaluators]:
            if name in registry:
                del registry[name]
                return True
        return False

    # =========================================================================
    # Health Monitoring
    # =========================================================================

    async def health_check(self) -> Dict[str, ComponentHealth]:
        """Check health of all components."""
        results = {}

        all_entries = (
            list(self._providers.values()) +
            list(self._actions.values()) +
            list(self._evaluators.values())
        )

        for entry in all_entries:
            try:
                health = await entry.component.health_check()
                results[entry.name] = health
            except Exception as e:
                results[entry.name] = ComponentHealth(
                    status=ComponentStatus.ERROR,
                    message=str(e),
                )

        return results

    async def health_check_component(self, name: str) -> Optional[ComponentHealth]:
        """Check health of a specific component."""
        component = self.get_component(name)
        if component:
            return await component.health_check()
        return None

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        all_entries = (
            list(self._providers.values()) +
            list(self._actions.values()) +
            list(self._evaluators.values())
        )

        return {
            "providers": {
                "total": len(self._providers),
                "enabled": len([e for e in self._providers.values() if e.enabled]),
            },
            "actions": {
                "total": len(self._actions),
                "enabled": len([e for e in self._actions.values() if e.enabled]),
            },
            "evaluators": {
                "total": len(self._evaluators),
                "enabled": len([e for e in self._evaluators.values() if e.enabled]),
            },
            "components": {
                entry.name: entry.component.stats
                for entry in all_entries
            },
            "initialized": self._initialized,
        }

    # =========================================================================
    # Service Management
    # =========================================================================

    def add_service(self, name: str, service: Any) -> None:
        """Add a service for dependency injection."""
        self._services[name] = service

    def get_service(self, name: str) -> Optional[Any]:
        """Get a service by name."""
        return self._services.get(name)

    def set_services(self, services: Dict[str, Any]) -> None:
        """Set all services."""
        self._services = services


# Global registry instance
_global_registry: Optional[PAERegistry] = None


def get_registry() -> PAERegistry:
    """Get the global PAE registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = PAERegistry()
    return _global_registry


def set_registry(registry: PAERegistry) -> None:
    """Set the global PAE registry."""
    global _global_registry
    _global_registry = registry
