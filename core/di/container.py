"""Dependency injection container implementation."""
from typing import Type, TypeVar, Dict, Callable, Optional, Any
from enum import Enum
from functools import wraps
import inspect
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


class Scope(str, Enum):
    SINGLETON = "singleton"
    TRANSIENT = "transient"
    REQUEST = "request"


class Container:
    """Simple dependency injection container."""
    
    _instance: Optional["Container"] = None
    
    def __init__(self):
        self._factories: Dict[Type, Callable] = {}
        self._instances: Dict[Type, object] = {}
        self._scopes: Dict[Type, Scope] = {}
    
    @classmethod
    def get_instance(cls) -> "Container":
        if cls._instance is None:
            cls._instance = Container()
        return cls._instance
    
    def register(
        self, 
        interface: Type[T], 
        factory: Callable[[], T],
        scope: Scope = Scope.SINGLETON
    ):
        """Register a factory for an interface."""
        self._factories[interface] = factory
        self._scopes[interface] = scope
        logger.debug(f"Registered {interface.__name__} with scope {scope.value}")
    
    def register_instance(self, interface: Type[T], instance: T):
        """Register an existing instance."""
        self._instances[interface] = instance
        self._scopes[interface] = Scope.SINGLETON
    
    def resolve(self, interface: Type[T]) -> T:
        """Resolve an interface to its implementation."""
        # Check for existing singleton instance
        if interface in self._instances:
            return self._instances[interface]
        
        # Check for registered factory
        if interface not in self._factories:
            raise ValueError(f"No factory registered for {interface.__name__}")
        
        # Create instance
        instance = self._factories[interface]()
        
        # Cache if singleton
        if self._scopes.get(interface) == Scope.SINGLETON:
            self._instances[interface] = instance
        
        return instance
    
    def reset(self):
        """Reset all instances (useful for testing)."""
        self._instances.clear()
    
    def __contains__(self, interface: Type) -> bool:
        return interface in self._factories or interface in self._instances


def inject(*dependencies: Type):
    """Decorator to inject dependencies into a function."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            container = Container.get_instance()
            injected = {
                dep.__name__.lower(): container.resolve(dep)
                for dep in dependencies
            }
            return func(*args, **{**injected, **kwargs})
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            container = Container.get_instance()
            injected = {
                dep.__name__.lower(): container.resolve(dep)
                for dep in dependencies
            }
            return await func(*args, **{**injected, **kwargs})
        
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return wrapper
    return decorator


# Global container instance
container = Container.get_instance()


def configure_dependencies():
    """Configure default dependencies."""
    from core.cache.redis_cache import RedisCache
    from core.database.pool import ConnectionPool
    
    container.register(RedisCache, lambda: RedisCache())
    container.register(ConnectionPool, lambda: ConnectionPool("data/jarvis.db"))
