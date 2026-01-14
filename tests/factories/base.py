"""
Base Factory Classes

Provides base classes for all test factories with common functionality
like sequence generation, random data, and build strategies.
"""

from typing import TypeVar, Generic, Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
import random
import string
import uuid

T = TypeVar('T')


class SequenceGenerator:
    """Generates unique sequential values for factory fields."""

    _sequences: Dict[str, int] = {}

    @classmethod
    def next(cls, name: str = "default") -> int:
        """Get next value in sequence."""
        if name not in cls._sequences:
            cls._sequences[name] = 0
        cls._sequences[name] += 1
        return cls._sequences[name]

    @classmethod
    def reset(cls, name: Optional[str] = None) -> None:
        """Reset sequence(s) to zero."""
        if name:
            cls._sequences[name] = 0
        else:
            cls._sequences.clear()


class RandomData:
    """Generates random test data."""

    FIRST_NAMES = ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Henry"]
    LAST_NAMES = ["Smith", "Jones", "Williams", "Brown", "Davis", "Miller", "Wilson"]
    DOMAINS = ["example.com", "test.org", "mock.io", "demo.net"]
    SYMBOLS = ["SOL", "BTC", "ETH", "USDC", "BONK", "JUP", "RAY"]

    @classmethod
    def string(cls, length: int = 10) -> str:
        """Generate random string."""
        return ''.join(random.choices(string.ascii_letters, k=length))

    @classmethod
    def email(cls) -> str:
        """Generate random email."""
        name = cls.string(8).lower()
        domain = random.choice(cls.DOMAINS)
        return f"{name}@{domain}"

    @classmethod
    def username(cls) -> str:
        """Generate random username."""
        return f"user_{cls.string(6).lower()}"

    @classmethod
    def full_name(cls) -> str:
        """Generate random full name."""
        return f"{random.choice(cls.FIRST_NAMES)} {random.choice(cls.LAST_NAMES)}"

    @classmethod
    def uuid(cls) -> str:
        """Generate random UUID."""
        return str(uuid.uuid4())

    @classmethod
    def integer(cls, min_val: int = 0, max_val: int = 1000) -> int:
        """Generate random integer."""
        return random.randint(min_val, max_val)

    @classmethod
    def decimal(cls, min_val: float = 0.0, max_val: float = 100.0, precision: int = 2) -> float:
        """Generate random decimal."""
        return round(random.uniform(min_val, max_val), precision)

    @classmethod
    def boolean(cls) -> bool:
        """Generate random boolean."""
        return random.choice([True, False])

    @classmethod
    def datetime(
        cls,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> datetime:
        """Generate random datetime within range."""
        if not start:
            start = datetime.utcnow() - timedelta(days=30)
        if not end:
            end = datetime.utcnow()

        delta = end - start
        random_seconds = random.randint(0, int(delta.total_seconds()))
        return start + timedelta(seconds=random_seconds)

    @classmethod
    def choice(cls, options: List[Any]) -> Any:
        """Choose random item from list."""
        return random.choice(options)

    @classmethod
    def symbol(cls) -> str:
        """Generate random trading symbol."""
        return random.choice(cls.SYMBOLS)

    @classmethod
    def wallet_address(cls) -> str:
        """Generate random Solana-like wallet address."""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=44))

    @classmethod
    def telegram_id(cls) -> int:
        """Generate random Telegram user ID."""
        return random.randint(100000000, 999999999)

    @classmethod
    def twitter_id(cls) -> str:
        """Generate random Twitter user ID."""
        return str(random.randint(1000000000, 9999999999))


class BaseFactory(ABC, Generic[T]):
    """
    Base class for all test factories.

    Subclasses should implement _build() to define how objects are created.
    """

    _overrides: Dict[str, Any] = {}

    @classmethod
    @abstractmethod
    def _build(cls, **kwargs) -> T:
        """Build a single instance. Must be implemented by subclasses."""
        pass

    @classmethod
    def build(cls, **kwargs) -> T:
        """Build a single instance with optional overrides."""
        merged = {**cls._overrides, **kwargs}
        return cls._build(**merged)

    @classmethod
    def build_batch(cls, count: int, **kwargs) -> List[T]:
        """Build multiple instances."""
        return [cls.build(**kwargs) for _ in range(count)]

    @classmethod
    def create(cls, **kwargs) -> T:
        """Create an instance (alias for build, can be extended for DB persistence)."""
        return cls.build(**kwargs)

    @classmethod
    def create_batch(cls, count: int, **kwargs) -> List[T]:
        """Create multiple instances."""
        return cls.build_batch(count, **kwargs)

    @classmethod
    def with_overrides(cls, **overrides) -> type:
        """Create a factory subclass with default overrides."""
        class OverriddenFactory(cls):
            _overrides = overrides
        return OverriddenFactory


@dataclass
class FactoryContext:
    """Context for factory-generated data, useful for cleanup."""

    created_objects: List[Any] = field(default_factory=list)

    def register(self, obj: Any) -> Any:
        """Register an object for potential cleanup."""
        self.created_objects.append(obj)
        return obj

    def cleanup(self) -> None:
        """Clean up all registered objects."""
        self.created_objects.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        return False


# Lazy evaluation helper
class LazyAttribute:
    """Lazily evaluate attribute value."""

    def __init__(self, func: Callable[[], Any]):
        self.func = func

    def evaluate(self) -> Any:
        return self.func()


def lazy(func: Callable[[], Any]) -> LazyAttribute:
    """Decorator for lazy attribute evaluation."""
    return LazyAttribute(func)


def sequence(name: str = "default") -> int:
    """Get next value in a named sequence."""
    return SequenceGenerator.next(name)
