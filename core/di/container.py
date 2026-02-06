"""Dependency injection container implementation."""
from typing import (
    Type, TypeVar, Dict, Callable, Optional, Any, Union,
    get_type_hints, Tuple
)
from enum import Enum
from functools import wraps
import inspect
import logging
import threading
from contextlib import contextmanager

logger = logging.getLogger(__name__)

T = TypeVar('T')


class Scope(str, Enum):
    """Service lifecycle scopes."""
    SINGLETON = "singleton"
    TRANSIENT = "transient"
    REQUEST = "request"


class ScopedContainer:
    """
    A scoped container for request-scoped dependencies.

    Shares singletons with parent container but maintains
    its own cache for request-scoped services.
    """

    def __init__(self, parent: "Container"):
        self._parent = parent
        self._instances: Dict[Type, object] = {}
        self._disposed = False

    def resolve(self, interface: Type[T]) -> T:
        """Resolve a dependency within this scope."""
        if self._disposed:
            raise RuntimeError("Cannot resolve from disposed scope")

        scope = self._parent._scopes.get(interface)

        # Singletons come from parent
        if scope == Scope.SINGLETON:
            return self._parent.resolve(interface)

        # Request-scoped: check local cache first
        if scope == Scope.REQUEST:
            if interface in self._instances:
                return self._instances[interface]

            # Create and cache
            instance = self._parent._create_instance(interface)
            self._instances[interface] = instance
            return instance

        # Transient: always create new
        return self._parent._create_instance(interface)

    def dispose(self):
        """Dispose this scope, clearing all cached instances."""
        self._instances.clear()
        self._disposed = True

    def __enter__(self) -> "ScopedContainer":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.dispose()
        return False

    def __contains__(self, interface: Type) -> bool:
        return interface in self._parent


class Container:
    """
    Dependency injection container.

    Supports three lifecycle scopes:
    - SINGLETON: One instance for the entire application
    - TRANSIENT: New instance on each resolve
    - REQUEST: One instance per scope (e.g., per HTTP request)

    Usage:
        container = Container()
        container.register_singleton(IService, lambda: ConcreteService())
        service = container.resolve(IService)
    """

    _instance: Optional["Container"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._factories: Dict[Type, Callable] = {}
        self._instances: Dict[Type, object] = {}
        self._scopes: Dict[Type, Scope] = {}
        self._named: Dict[str, Callable] = {}
        self._named_instances: Dict[str, object] = {}
        self._providers: Dict[Type, Any] = {}  # For Provider-based registration

    @classmethod
    def get_instance(cls) -> "Container":
        """Get the global singleton container instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = Container()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Reset the global singleton (for testing)."""
        with cls._lock:
            cls._instance = None

    def register(
        self,
        interface: Type[T],
        factory: Callable[[], T],
        scope: Scope = Scope.SINGLETON
    ):
        """
        Register a factory for an interface.

        Args:
            interface: The type/interface to register
            factory: A callable that returns an instance
            scope: Lifecycle scope (default: SINGLETON)
        """
        self._factories[interface] = factory
        self._scopes[interface] = scope
        logger.debug(f"Registered {interface.__name__} with scope {scope.value}")

    def register_singleton(
        self,
        interface: Type[T],
        factory: Callable[[], T]
    ):
        """
        Register a singleton service.

        Shorthand for register(interface, factory, Scope.SINGLETON)
        """
        self.register(interface, factory, Scope.SINGLETON)

    def register_transient(
        self,
        interface: Type[T],
        factory: Callable[[], T]
    ):
        """
        Register a transient service.

        Shorthand for register(interface, factory, Scope.TRANSIENT)
        """
        self.register(interface, factory, Scope.TRANSIENT)

    def register_instance(self, interface: Type[T], instance: T):
        """
        Register an existing instance.

        The instance will be returned for all resolves (singleton behavior).
        """
        self._instances[interface] = instance
        self._scopes[interface] = Scope.SINGLETON
        logger.debug(f"Registered instance for {interface.__name__}")

    def register_named(
        self,
        name: str,
        factory: Union[Callable, Any],
        scope: Scope = Scope.SINGLETON
    ):
        """
        Register a service by name.

        Useful for registering multiple implementations of the same interface.
        """
        if hasattr(factory, 'provide'):
            # It's a Provider
            self._named[name] = factory.provide
        elif callable(factory):
            self._named[name] = factory
        else:
            # It's a value
            self._named[name] = lambda: factory

    def resolve_named(self, name: str) -> Any:
        """Resolve a named service."""
        if name not in self._named:
            raise ValueError(f"No service registered with name '{name}'")

        # Check for cached instance
        if name in self._named_instances:
            return self._named_instances[name]

        # Create instance
        factory = self._named[name]
        instance = factory() if callable(factory) else factory

        # Cache it (treating named as singleton by default)
        self._named_instances[name] = instance
        return instance

    def register_provider(
        self,
        interface: Type[T],
        provider: "Provider",
        scope: Scope = Scope.TRANSIENT
    ):
        """
        Register a Provider for an interface.

        Provider must have a provide() method.
        """
        self._providers[interface] = provider
        self._scopes[interface] = scope
        self._factories[interface] = provider.provide

    def register_auto(self, cls: Type[T]):
        """
        Auto-register a class, resolving its dependencies from type hints.

        The class constructor parameters will be resolved automatically.
        """
        def factory():
            return self._auto_create(cls)

        scope = getattr(cls, '__scope__', Scope.SINGLETON)
        self.register(cls, factory, scope)

    def _auto_create(self, cls: Type[T]) -> T:
        """Create an instance by auto-resolving constructor dependencies."""
        try:
            hints = get_type_hints(cls.__init__)
        except Exception:
            hints = {}

        # Remove 'return' hint if present
        hints.pop('return', None)

        # Build kwargs from type hints
        kwargs = {}
        sig = inspect.signature(cls.__init__)
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue

            # Check if we have a type hint
            if param_name in hints:
                param_type = hints[param_name]
                if param_type in self:
                    kwargs[param_name] = self.resolve(param_type)

        return cls(**kwargs)

    def _create_instance(self, interface: Type[T]) -> T:
        """Create an instance using the registered factory."""
        if interface not in self._factories:
            raise ValueError(f"No factory registered for {interface.__name__}")

        return self._factories[interface]()

    def resolve(self, interface: Type[T]) -> T:
        """
        Resolve an interface to its implementation.

        Args:
            interface: The type/interface to resolve

        Returns:
            An instance of the registered implementation

        Raises:
            ValueError: If no factory is registered for the interface
        """
        # Check for existing singleton instance
        if interface in self._instances:
            return self._instances[interface]

        # Check for registered factory
        if interface not in self._factories:
            raise ValueError(f"No factory registered for {interface.__name__}")

        # Create instance
        instance = self._create_instance(interface)

        # Cache if singleton
        if self._scopes.get(interface) == Scope.SINGLETON:
            self._instances[interface] = instance

        return instance

    def create_scope(self) -> ScopedContainer:
        """
        Create a new dependency scope.

        Returns a ScopedContainer that shares singletons with this container
        but maintains its own cache for request-scoped services.

        Usage:
            with container.create_scope() as scope:
                service = scope.resolve(IService)
        """
        return ScopedContainer(self)

    def reset(self):
        """Reset all cached instances (useful for testing)."""
        self._instances.clear()
        self._named_instances.clear()

    def clear(self):
        """Clear all registrations and instances."""
        self._factories.clear()
        self._instances.clear()
        self._scopes.clear()
        self._named.clear()
        self._named_instances.clear()
        self._providers.clear()

    def __contains__(self, interface: Type) -> bool:
        """Check if an interface is registered."""
        return interface in self._factories or interface in self._instances


def inject(*dependencies: Type):
    """
    Decorator to inject dependencies into a function.

    Dependencies are resolved from the global container.

    Usage:
        @inject(ILogger, IDatabase)
        def my_function(logger: ILogger, database: IDatabase):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            container = Container.get_instance()
            injected = {}
            for dep in dependencies:
                # Use lowercase class name as parameter name
                param_name = dep.__name__.lower()
                if param_name not in kwargs:
                    injected[param_name] = container.resolve(dep)
            return func(*args, **{**injected, **kwargs})

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            container = Container.get_instance()
            injected = {}
            for dep in dependencies:
                param_name = dep.__name__.lower()
                if param_name not in kwargs:
                    injected[param_name] = container.resolve(dep)
            return await func(*args, **{**injected, **kwargs})

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return wrapper
    return decorator


# Global container instance
container = Container.get_instance()


def configure_dependencies():
    """Configure default dependencies."""
    # Lazy imports to avoid circular dependencies
    try:
        from core.cache.redis_cache import RedisCache
        container.register(RedisCache, lambda: RedisCache())
    except ImportError:
        pass

    try:
        from core.database.pool import ConnectionPool
        container.register(ConnectionPool, lambda: ConnectionPool("data/jarvis.db"))
    except ImportError:
        pass
