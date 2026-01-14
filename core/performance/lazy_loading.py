"""
JARVIS Lazy Loading Patterns

Provides lazy loading utilities for deferred initialization,
on-demand resource loading, and memory-efficient data access.
"""

from typing import TypeVar, Generic, Callable, Optional, Any, Dict, List
from dataclasses import dataclass, field
from functools import wraps
from datetime import datetime, timedelta
import asyncio
import threading
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


class LazyValue(Generic[T]):
    """
    Lazy value that is computed on first access.

    Usage:
        expensive_data = LazyValue(lambda: load_expensive_data())

        # Data is not loaded until accessed
        print(expensive_data.value)  # Loads now
        print(expensive_data.value)  # Returns cached
    """

    def __init__(self, factory: Callable[[], T]):
        self._factory = factory
        self._value: Optional[T] = None
        self._initialized = False
        self._lock = threading.Lock()

    @property
    def value(self) -> T:
        """Get the value, computing it if necessary."""
        if not self._initialized:
            with self._lock:
                if not self._initialized:  # Double-check
                    self._value = self._factory()
                    self._initialized = True
        return self._value  # type: ignore

    @property
    def is_initialized(self) -> bool:
        """Check if value has been computed."""
        return self._initialized

    def reset(self) -> None:
        """Reset the lazy value to be recomputed."""
        with self._lock:
            self._value = None
            self._initialized = False


class AsyncLazyValue(Generic[T]):
    """
    Async lazy value for async factory functions.

    Usage:
        async_data = AsyncLazyValue(async_load_data)

        # Data is not loaded until awaited
        data = await async_data.value
    """

    def __init__(self, factory: Callable[[], Any]):  # Returns Awaitable[T]
        self._factory = factory
        self._value: Optional[T] = None
        self._initialized = False
        self._lock = asyncio.Lock()

    @property
    async def value(self) -> T:
        """Get the value, computing it if necessary."""
        if not self._initialized:
            async with self._lock:
                if not self._initialized:
                    self._value = await self._factory()
                    self._initialized = True
        return self._value  # type: ignore

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    async def reset(self) -> None:
        async with self._lock:
            self._value = None
            self._initialized = False


class LazyDict(Dict[str, Any]):
    """
    Dictionary with lazy-loaded values.

    Values are only computed when accessed.

    Usage:
        config = LazyDict()
        config.register('database', lambda: connect_to_database())
        config.register('cache', lambda: connect_to_cache())

        # Neither connection made yet
        db = config['database']  # Now connects
    """

    def __init__(self):
        super().__init__()
        self._factories: Dict[str, Callable] = {}
        self._computed: Dict[str, bool] = {}

    def register(self, key: str, factory: Callable[[], Any]) -> None:
        """Register a lazy value."""
        self._factories[key] = factory
        self._computed[key] = False

    def __getitem__(self, key: str) -> Any:
        if key in self._factories and not self._computed.get(key):
            self[key] = self._factories[key]()
            self._computed[key] = True
        return super().__getitem__(key)

    def is_computed(self, key: str) -> bool:
        """Check if a value has been computed."""
        return self._computed.get(key, key in self)


@dataclass
class LazyProperty:
    """
    Descriptor for lazy property evaluation.

    Usage:
        class MyClass:
            @lazy_property
            def expensive_data(self):
                return load_expensive_data()
    """
    _func: Callable
    _attr_name: str = ""

    def __set_name__(self, owner, name):
        self._attr_name = f"_lazy_{name}"

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        if not hasattr(obj, self._attr_name):
            setattr(obj, self._attr_name, self._func(obj))
        return getattr(obj, self._attr_name)


def lazy_property(func: Callable) -> property:
    """
    Decorator for lazy property evaluation.

    Usage:
        class Config:
            @lazy_property
            def database_connection(self):
                return create_connection()
    """
    attr_name = f"_lazy_{func.__name__}"

    @property
    @wraps(func)
    def wrapper(self):
        if not hasattr(self, attr_name):
            setattr(self, attr_name, func(self))
        return getattr(self, attr_name)

    return wrapper


def async_lazy_property(func: Callable) -> property:
    """
    Decorator for async lazy property.

    Usage:
        class Service:
            @async_lazy_property
            async def client(self):
                return await create_async_client()
    """
    attr_name = f"_lazy_{func.__name__}"
    lock_name = f"_lazy_lock_{func.__name__}"

    @property
    @wraps(func)
    async def wrapper(self):
        if not hasattr(self, lock_name):
            setattr(self, lock_name, asyncio.Lock())

        lock = getattr(self, lock_name)

        if not hasattr(self, attr_name):
            async with lock:
                if not hasattr(self, attr_name):
                    result = await func(self)
                    setattr(self, attr_name, result)

        return getattr(self, attr_name)

    return wrapper


class LazyLoader(Generic[T]):
    """
    Lazy loader with TTL and refresh capability.

    Usage:
        loader = LazyLoader(
            factory=load_config,
            ttl_seconds=300  # Refresh every 5 minutes
        )

        config = loader.get()  # Loads if needed
    """

    def __init__(
        self,
        factory: Callable[[], T],
        ttl_seconds: Optional[int] = None,
        on_load: Optional[Callable[[T], None]] = None
    ):
        self._factory = factory
        self._ttl = timedelta(seconds=ttl_seconds) if ttl_seconds else None
        self._on_load = on_load
        self._value: Optional[T] = None
        self._loaded_at: Optional[datetime] = None
        self._lock = threading.Lock()

    def get(self) -> T:
        """Get the value, loading if necessary."""
        if self._should_reload():
            with self._lock:
                if self._should_reload():  # Double-check
                    self._value = self._factory()
                    self._loaded_at = datetime.utcnow()
                    if self._on_load:
                        self._on_load(self._value)
                    logger.debug(f"Lazy loaded value at {self._loaded_at}")

        return self._value  # type: ignore

    def _should_reload(self) -> bool:
        """Check if value should be reloaded."""
        if self._value is None:
            return True
        if self._ttl and self._loaded_at:
            return datetime.utcnow() - self._loaded_at > self._ttl
        return False

    def invalidate(self) -> None:
        """Invalidate cached value."""
        with self._lock:
            self._value = None
            self._loaded_at = None

    @property
    def is_loaded(self) -> bool:
        return self._value is not None

    @property
    def age_seconds(self) -> Optional[float]:
        if self._loaded_at:
            return (datetime.utcnow() - self._loaded_at).total_seconds()
        return None


class AsyncLazyLoader(Generic[T]):
    """
    Async version of LazyLoader.

    Usage:
        loader = AsyncLazyLoader(async_load_data, ttl_seconds=60)
        data = await loader.get()
    """

    def __init__(
        self,
        factory: Callable[[], Any],  # Returns Awaitable[T]
        ttl_seconds: Optional[int] = None,
        on_load: Optional[Callable[[T], None]] = None
    ):
        self._factory = factory
        self._ttl = timedelta(seconds=ttl_seconds) if ttl_seconds else None
        self._on_load = on_load
        self._value: Optional[T] = None
        self._loaded_at: Optional[datetime] = None
        self._lock = asyncio.Lock()

    async def get(self) -> T:
        """Get the value, loading if necessary."""
        if self._should_reload():
            async with self._lock:
                if self._should_reload():
                    self._value = await self._factory()
                    self._loaded_at = datetime.utcnow()
                    if self._on_load:
                        self._on_load(self._value)

        return self._value  # type: ignore

    def _should_reload(self) -> bool:
        if self._value is None:
            return True
        if self._ttl and self._loaded_at:
            return datetime.utcnow() - self._loaded_at > self._ttl
        return False

    async def invalidate(self) -> None:
        async with self._lock:
            self._value = None
            self._loaded_at = None


class LazySequence(Generic[T]):
    """
    Lazy sequence that loads items on demand.

    Useful for large datasets where you don't want to load everything.

    Usage:
        users = LazySequence(
            count_func=lambda: db.count_users(),
            fetch_func=lambda offset, limit: db.get_users(offset, limit),
            page_size=100
        )

        # Only loads page containing index 50
        user = users[50]
    """

    def __init__(
        self,
        count_func: Callable[[], int],
        fetch_func: Callable[[int, int], List[T]],
        page_size: int = 100
    ):
        self._count_func = count_func
        self._fetch_func = fetch_func
        self._page_size = page_size
        self._pages: Dict[int, List[T]] = {}
        self._count: Optional[int] = None

    def __len__(self) -> int:
        if self._count is None:
            self._count = self._count_func()
        return self._count

    def __getitem__(self, index: int) -> T:
        if index < 0:
            index = len(self) + index

        if index < 0 or index >= len(self):
            raise IndexError("Index out of range")

        page_num = index // self._page_size
        page_offset = index % self._page_size

        if page_num not in self._pages:
            offset = page_num * self._page_size
            self._pages[page_num] = self._fetch_func(offset, self._page_size)
            logger.debug(f"Loaded page {page_num} of lazy sequence")

        return self._pages[page_num][page_offset]

    def __iter__(self):
        for i in range(len(self)):
            yield self[i]

    def clear_cache(self) -> None:
        """Clear loaded pages."""
        self._pages.clear()
        self._count = None


# Module-level lazy loaders for common resources
_lazy_resources: Dict[str, LazyLoader] = {}


def register_lazy_resource(name: str, factory: Callable, ttl_seconds: Optional[int] = None) -> None:
    """Register a lazy-loaded resource."""
    _lazy_resources[name] = LazyLoader(factory, ttl_seconds)


def get_lazy_resource(name: str) -> Any:
    """Get a lazy-loaded resource."""
    if name not in _lazy_resources:
        raise KeyError(f"Unknown lazy resource: {name}")
    return _lazy_resources[name].get()


def invalidate_lazy_resource(name: str) -> None:
    """Invalidate a lazy resource cache."""
    if name in _lazy_resources:
        _lazy_resources[name].invalidate()
