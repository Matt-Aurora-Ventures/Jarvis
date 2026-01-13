"""
JARVIS Core - Unified Service Registry & Capability Discovery

The central nervous system that enables JARVIS to understand itself.
All modules register their capabilities here, enabling:
- Self-awareness: JARVIS knows what it can do
- Service discovery: Components can find and use each other
- Event propagation: Unified event bus across all modules
- Health monitoring: Track status of all subsystems
- Dependency injection: Services can declare and receive dependencies

Usage:
    from core.jarvis_core import jarvis, Capability, ServiceStatus

    # Register a capability
    @jarvis.capability(
        name="sentiment_analysis",
        category="analytics",
        description="Analyze market sentiment from social media"
    )
    class SentimentAnalyzer:
        async def analyze(self, text: str) -> float:
            ...

    # Discover and use capabilities
    analyzer = await jarvis.get("sentiment_analysis")
    score = await analyzer.analyze("BTC to the moon!")

    # Subscribe to events
    @jarvis.on("trade.executed")
    async def handle_trade(event):
        ...

    # Emit events
    await jarvis.emit("trade.executed", {"symbol": "SOL", "amount": 100})
"""

import os
import json
import time
import asyncio
import logging
import inspect
from enum import Enum
from pathlib import Path
from datetime import datetime, timezone
from typing import (
    Any, Callable, Dict, List, Optional, Set, Type, TypeVar, Union,
    Protocol, runtime_checkable
)
from dataclasses import dataclass, field
from functools import wraps
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# Type variables
T = TypeVar('T')
HandlerType = Callable[..., Any]


class ServiceStatus(Enum):
    """Status of a registered service."""
    UNKNOWN = "unknown"
    INITIALIZING = "initializing"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    STOPPED = "stopped"


class Category(Enum):
    """Categories for organizing capabilities."""
    ANALYTICS = "analytics"
    TRADING = "trading"
    DATA = "data"
    SOCIAL = "social"
    MESSAGING = "messaging"
    STORAGE = "storage"
    AI = "ai"
    SECURITY = "security"
    INFRASTRUCTURE = "infrastructure"
    MONITORING = "monitoring"


@dataclass
class CapabilityMetadata:
    """Metadata describing a capability."""
    name: str
    category: Category
    description: str
    version: str = "1.0.0"
    dependencies: List[str] = field(default_factory=list)
    provides: List[str] = field(default_factory=list)
    tags: Set[str] = field(default_factory=set)
    config_keys: List[str] = field(default_factory=list)
    async_only: bool = False
    singleton: bool = True


@dataclass
class ServiceInfo:
    """Information about a registered service."""
    metadata: CapabilityMetadata
    instance: Any
    factory: Optional[Callable] = None
    status: ServiceStatus = ServiceStatus.UNKNOWN
    registered_at: float = field(default_factory=time.time)
    last_health_check: Optional[float] = None
    health_check_fn: Optional[Callable] = None
    error_count: int = 0
    last_error: Optional[str] = None


@dataclass
class Event:
    """Event data structure."""
    topic: str
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    source: Optional[str] = None
    correlation_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "data": self.data,
            "timestamp": self.timestamp,
            "source": self.source,
            "correlation_id": self.correlation_id,
        }


@runtime_checkable
class HealthCheckable(Protocol):
    """Protocol for services that support health checks."""
    async def health_check(self) -> bool: ...


@runtime_checkable
class Initializable(Protocol):
    """Protocol for services that need async initialization."""
    async def initialize(self) -> None: ...


@runtime_checkable
class Closeable(Protocol):
    """Protocol for services that need cleanup."""
    async def close(self) -> None: ...


class JarvisCore:
    """
    The unified core that orchestrates all JARVIS capabilities.

    This is the "brain" that enables self-awareness and coordination
    across all modules and subsystems.
    """

    # Singleton instance
    _instance: Optional['JarvisCore'] = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Service registry
        self._services: Dict[str, ServiceInfo] = {}
        self._aliases: Dict[str, str] = {}  # alias -> canonical name

        # Event system
        self._handlers: Dict[str, List[tuple]] = {}  # topic -> [(handler, priority)]
        self._event_history: List[Event] = []
        self._max_history = 1000

        # Configuration
        self._config: Dict[str, Any] = {}
        self._config_sources: List[Path] = []

        # State
        self._started = False
        self._shutting_down = False

        # Metrics
        self._metrics = {
            "events_emitted": 0,
            "events_handled": 0,
            "service_calls": 0,
            "errors": 0,
        }

        self._initialized = True
        logger.info("JarvisCore initialized")

    # ==================== Service Registration ====================

    def capability(
        self,
        name: str,
        category: Union[Category, str],
        description: str,
        version: str = "1.0.0",
        dependencies: List[str] = None,
        provides: List[str] = None,
        tags: Set[str] = None,
        config_keys: List[str] = None,
        singleton: bool = True,
        aliases: List[str] = None,
    ) -> Callable[[Type[T]], Type[T]]:
        """
        Decorator to register a class as a JARVIS capability.

        Usage:
            @jarvis.capability(
                name="price_fetcher",
                category=Category.DATA,
                description="Fetches live prices from multiple sources"
            )
            class PriceFetcher:
                ...
        """
        if isinstance(category, str):
            category = Category(category)

        metadata = CapabilityMetadata(
            name=name,
            category=category,
            description=description,
            version=version,
            dependencies=dependencies or [],
            provides=provides or [name],
            tags=set(tags) if tags else set(),
            config_keys=config_keys or [],
            singleton=singleton,
        )

        def decorator(cls: Type[T]) -> Type[T]:
            # Check if async
            metadata.async_only = any(
                asyncio.iscoroutinefunction(getattr(cls, m, None))
                for m in dir(cls) if not m.startswith('_')
            )

            # Store metadata on class
            cls._jarvis_metadata = metadata

            # Register with factory
            self._register_factory(name, cls, metadata, aliases)

            logger.info(f"Registered capability: {name} ({category.value})")
            return cls

        return decorator

    def _register_factory(
        self,
        name: str,
        factory: Callable,
        metadata: CapabilityMetadata,
        aliases: List[str] = None
    ):
        """Register a factory function or class."""
        self._services[name] = ServiceInfo(
            metadata=metadata,
            instance=None,
            factory=factory,
            status=ServiceStatus.UNKNOWN,
        )

        # Register aliases
        if aliases:
            for alias in aliases:
                self._aliases[alias] = name

        # Auto-register provided capabilities
        for provided in metadata.provides:
            if provided != name:
                self._aliases[provided] = name

    def register(
        self,
        name: str,
        instance: Any,
        category: Union[Category, str] = Category.INFRASTRUCTURE,
        description: str = "",
        **kwargs
    ):
        """
        Register an existing instance as a capability.

        Usage:
            jarvis.register("my_service", my_instance, category="data")
        """
        if isinstance(category, str):
            category = Category(category)

        metadata = CapabilityMetadata(
            name=name,
            category=category,
            description=description or f"Instance of {type(instance).__name__}",
            **kwargs
        )

        self._services[name] = ServiceInfo(
            metadata=metadata,
            instance=instance,
            status=ServiceStatus.HEALTHY,
        )

        logger.info(f"Registered instance: {name}")

    def register_alias(self, alias: str, target: str):
        """Register an alias for a capability."""
        self._aliases[alias] = target

    # ==================== Service Discovery ====================

    async def get(self, name: str, default: Any = None) -> Any:
        """
        Get a capability by name.

        If singleton, returns cached instance. Otherwise creates new.
        Handles async initialization if needed.
        """
        # Resolve alias
        canonical = self._aliases.get(name, name)

        if canonical not in self._services:
            if default is not None:
                return default
            raise KeyError(f"Unknown capability: {name}")

        service = self._services[canonical]
        self._metrics["service_calls"] += 1

        # Return existing instance if available
        if service.instance is not None:
            return service.instance

        # Create instance
        if service.factory is None:
            raise RuntimeError(f"No factory for {name}")

        try:
            # Check dependencies first
            await self._resolve_dependencies(service.metadata.dependencies)

            # Create instance
            instance = service.factory()

            # Initialize if needed
            if isinstance(instance, Initializable):
                service.status = ServiceStatus.INITIALIZING
                await instance.initialize()

            service.instance = instance
            service.status = ServiceStatus.HEALTHY
            return instance

        except Exception as e:
            service.status = ServiceStatus.UNHEALTHY
            service.last_error = str(e)
            service.error_count += 1
            logger.error(f"Failed to create {name}: {e}")
            raise

    def get_sync(self, name: str, default: Any = None) -> Any:
        """Synchronous version of get() - only for already-instantiated services."""
        canonical = self._aliases.get(name, name)

        if canonical not in self._services:
            if default is not None:
                return default
            raise KeyError(f"Unknown capability: {name}")

        service = self._services[canonical]
        if service.instance is None:
            raise RuntimeError(f"Service {name} not yet instantiated. Use 'await jarvis.get()' first.")

        return service.instance

    async def _resolve_dependencies(self, deps: List[str]):
        """Resolve and initialize dependencies."""
        for dep in deps:
            await self.get(dep)

    def has(self, name: str) -> bool:
        """Check if a capability is registered."""
        canonical = self._aliases.get(name, name)
        return canonical in self._services

    def list_capabilities(
        self,
        category: Optional[Category] = None,
        tag: Optional[str] = None,
        status: Optional[ServiceStatus] = None
    ) -> List[str]:
        """List registered capabilities with optional filtering."""
        results = []

        for name, service in self._services.items():
            if category and service.metadata.category != category:
                continue
            if tag and tag not in service.metadata.tags:
                continue
            if status and service.status != status:
                continue
            results.append(name)

        return results

    def get_metadata(self, name: str) -> Optional[CapabilityMetadata]:
        """Get metadata for a capability."""
        canonical = self._aliases.get(name, name)
        if canonical in self._services:
            return self._services[canonical].metadata
        return None

    def get_status(self, name: str) -> ServiceStatus:
        """Get status of a capability."""
        canonical = self._aliases.get(name, name)
        if canonical in self._services:
            return self._services[canonical].status
        return ServiceStatus.UNKNOWN

    # ==================== Event System ====================

    def on(
        self,
        topic: str,
        priority: int = 0
    ) -> Callable[[HandlerType], HandlerType]:
        """
        Decorator to subscribe to events.

        Supports wildcards: "trade.*" matches "trade.executed", "trade.failed"

        Usage:
            @jarvis.on("trade.executed")
            async def handle_trade(event: Event):
                print(f"Trade: {event.data}")
        """
        def decorator(handler: HandlerType) -> HandlerType:
            self.subscribe(topic, handler, priority)
            return handler
        return decorator

    def subscribe(
        self,
        topic: str,
        handler: HandlerType,
        priority: int = 0
    ):
        """Subscribe a handler to a topic."""
        if topic not in self._handlers:
            self._handlers[topic] = []

        self._handlers[topic].append((handler, priority))
        # Sort by priority (higher first)
        self._handlers[topic].sort(key=lambda x: -x[1])

        logger.debug(f"Subscribed to {topic}: {handler.__name__}")

    def unsubscribe(self, topic: str, handler: HandlerType):
        """Unsubscribe a handler from a topic."""
        if topic in self._handlers:
            self._handlers[topic] = [
                (h, p) for h, p in self._handlers[topic] if h != handler
            ]

    async def emit(
        self,
        topic: str,
        data: Dict[str, Any] = None,
        source: str = None,
        correlation_id: str = None
    ) -> int:
        """
        Emit an event to all subscribers.

        Returns number of handlers that processed the event.
        """
        event = Event(
            topic=topic,
            data=data or {},
            source=source,
            correlation_id=correlation_id,
        )

        # Store in history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]

        self._metrics["events_emitted"] += 1

        # Find matching handlers
        handlers = self._get_matching_handlers(topic)
        handled = 0

        for handler, _ in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
                handled += 1
                self._metrics["events_handled"] += 1
            except Exception as e:
                self._metrics["errors"] += 1
                logger.error(f"Error in event handler {handler.__name__}: {e}")

        return handled

    def _get_matching_handlers(self, topic: str) -> List[tuple]:
        """Get handlers that match a topic (including wildcards)."""
        handlers = []

        for pattern, pattern_handlers in self._handlers.items():
            if self._topic_matches(pattern, topic):
                handlers.extend(pattern_handlers)

        # Sort by priority
        handlers.sort(key=lambda x: -x[1])
        return handlers

    def _topic_matches(self, pattern: str, topic: str) -> bool:
        """Check if a topic matches a pattern (supports wildcards)."""
        if pattern == topic:
            return True

        if '*' in pattern:
            pattern_parts = pattern.split('.')
            topic_parts = topic.split('.')

            if len(pattern_parts) > len(topic_parts):
                return False

            for i, part in enumerate(pattern_parts):
                if part == '*':
                    continue
                if part == '**':
                    return True  # Match rest
                if i >= len(topic_parts) or part != topic_parts[i]:
                    return False

            return len(pattern_parts) == len(topic_parts) or pattern_parts[-1] in ('*', '**')

        return False

    def get_event_history(
        self,
        topic: Optional[str] = None,
        limit: int = 100
    ) -> List[Event]:
        """Get recent events, optionally filtered by topic."""
        events = self._event_history
        if topic:
            events = [e for e in events if self._topic_matches(topic, e.topic)]
        return events[-limit:]

    # ==================== Configuration ====================

    def configure(self, config: Dict[str, Any]):
        """Update configuration."""
        self._config.update(config)

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def load_config_file(self, path: Path):
        """Load configuration from a JSON file."""
        if path.exists():
            with open(path) as f:
                config = json.load(f)
                self._config.update(config)
                self._config_sources.append(path)
                logger.info(f"Loaded config from {path}")

    # ==================== Health & Monitoring ====================

    async def health_check(self, name: str) -> bool:
        """Run health check for a specific service."""
        canonical = self._aliases.get(name, name)

        if canonical not in self._services:
            return False

        service = self._services[canonical]

        if service.instance is None:
            return False

        try:
            if isinstance(service.instance, HealthCheckable):
                healthy = await service.instance.health_check()
            elif service.health_check_fn:
                healthy = await service.health_check_fn()
            else:
                healthy = True  # Assume healthy if no check

            service.status = ServiceStatus.HEALTHY if healthy else ServiceStatus.UNHEALTHY
            service.last_health_check = time.time()
            return healthy

        except Exception as e:
            service.status = ServiceStatus.UNHEALTHY
            service.last_error = str(e)
            return False

    async def health_check_all(self) -> Dict[str, bool]:
        """Run health checks for all services."""
        results = {}
        for name in self._services:
            results[name] = await self.health_check(name)
        return results

    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        services_by_status = {}
        for status in ServiceStatus:
            services_by_status[status.value] = []

        for name, service in self._services.items():
            services_by_status[service.status.value].append(name)

        return {
            "started": self._started,
            "shutting_down": self._shutting_down,
            "total_services": len(self._services),
            "services_by_status": services_by_status,
            "services_by_category": self._group_by_category(),
            "metrics": self._metrics.copy(),
            "event_queue_size": len(self._event_history),
        }

    def _group_by_category(self) -> Dict[str, List[str]]:
        """Group services by category."""
        by_category = {}
        for name, service in self._services.items():
            cat = service.metadata.category.value
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(name)
        return by_category

    # ==================== Lifecycle ====================

    async def start(self):
        """Start JARVIS core and initialize essential services."""
        if self._started:
            return

        logger.info("Starting JARVIS Core...")

        # Emit startup event
        await self.emit("jarvis.starting", {"timestamp": time.time()})

        self._started = True

        await self.emit("jarvis.started", {"timestamp": time.time()})
        logger.info("JARVIS Core started")

    async def shutdown(self):
        """Gracefully shutdown all services."""
        if self._shutting_down:
            return

        self._shutting_down = True
        logger.info("Shutting down JARVIS Core...")

        await self.emit("jarvis.stopping", {"timestamp": time.time()})

        # Close all closeable services
        for name, service in self._services.items():
            if service.instance and isinstance(service.instance, Closeable):
                try:
                    await service.instance.close()
                    service.status = ServiceStatus.STOPPED
                except Exception as e:
                    logger.error(f"Error closing {name}: {e}")

        self._started = False
        logger.info("JARVIS Core shutdown complete")

    # ==================== Introspection ====================

    def describe(self) -> str:
        """Generate a human-readable description of JARVIS capabilities."""
        lines = [
            "=" * 60,
            "JARVIS CAPABILITY MANIFEST",
            "=" * 60,
            "",
        ]

        by_category = self._group_by_category()

        for category, services in sorted(by_category.items()):
            lines.append(f"\n## {category.upper()}")
            lines.append("-" * 40)

            for name in sorted(services):
                service = self._services[name]
                meta = service.metadata
                status_icon = {
                    ServiceStatus.HEALTHY: "[OK]",
                    ServiceStatus.DEGRADED: "[!!]",
                    ServiceStatus.UNHEALTHY: "[X]",
                    ServiceStatus.STOPPED: "[--]",
                }.get(service.status, "[?]")

                lines.append(f"  {status_icon} {name}")
                lines.append(f"      {meta.description}")
                if meta.dependencies:
                    lines.append(f"      Deps: {', '.join(meta.dependencies)}")

        lines.append("")
        lines.append("=" * 60)
        lines.append(f"Total capabilities: {len(self._services)}")
        lines.append("=" * 60)

        return "\n".join(lines)

    def to_manifest(self) -> Dict[str, Any]:
        """Export capability manifest as JSON-serializable dict."""
        manifest = {
            "version": "1.0.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "capabilities": {},
        }

        for name, service in self._services.items():
            meta = service.metadata
            manifest["capabilities"][name] = {
                "category": meta.category.value,
                "description": meta.description,
                "version": meta.version,
                "dependencies": meta.dependencies,
                "provides": list(meta.provides),
                "tags": list(meta.tags),
                "status": service.status.value,
                "async_only": meta.async_only,
            }

        return manifest


# ==================== Global Instance ====================

# The singleton instance
jarvis = JarvisCore()


# ==================== Convenience Functions ====================

def capability(
    name: str,
    category: Union[Category, str],
    description: str,
    **kwargs
) -> Callable[[Type[T]], Type[T]]:
    """Decorator shortcut for jarvis.capability()."""
    return jarvis.capability(name, category, description, **kwargs)


def on(topic: str, priority: int = 0) -> Callable[[HandlerType], HandlerType]:
    """Decorator shortcut for jarvis.on()."""
    return jarvis.on(topic, priority)


async def emit(topic: str, data: Dict[str, Any] = None, **kwargs) -> int:
    """Shortcut for jarvis.emit()."""
    return await jarvis.emit(topic, data, **kwargs)


async def get(name: str, default: Any = None) -> Any:
    """Shortcut for jarvis.get()."""
    return await jarvis.get(name, default)


def register(name: str, instance: Any, **kwargs):
    """Shortcut for jarvis.register()."""
    return jarvis.register(name, instance, **kwargs)
