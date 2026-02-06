"""
State Storage Backends

Provides various storage backends for persisting conversation contexts:
- InMemoryStorage: Fast, single-instance storage
- JSONFileStorage: File-based persistence
- RedisStorage: Distributed storage (stub for future implementation)

Example:
    from core.state.storage import InMemoryStorage
    from core.state.context import ConversationContext

    storage = InMemoryStorage()
    ctx = ConversationContext(user_id="123", chat_id="456")
    storage.save(ctx)

    retrieved = storage.get(ctx.key)
"""

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional

from core.state.context import ConversationContext

logger = logging.getLogger(__name__)


class StateStorage(ABC):
    """
    Abstract base class for state storage backends.

    All storage implementations must provide these methods.
    """

    @abstractmethod
    def save(self, context: ConversationContext) -> None:
        """
        Save a conversation context.

        Args:
            context: The context to save
        """
        pass

    @abstractmethod
    def get(self, key: str) -> Optional[ConversationContext]:
        """
        Retrieve a conversation context by key.

        Args:
            key: The context key (usually "user_id:chat_id")

        Returns:
            The context if found, None otherwise
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        """
        Delete a conversation context.

        Args:
            key: The context key to delete
        """
        pass

    @abstractmethod
    def get_by_user_id(self, user_id: str) -> List[ConversationContext]:
        """
        Get all contexts for a specific user.

        Args:
            user_id: The user identifier

        Returns:
            List of contexts for the user
        """
        pass

    @abstractmethod
    def clear_expired(self) -> int:
        """
        Remove all expired contexts.

        Returns:
            Number of contexts removed
        """
        pass


class InMemoryStorage(StateStorage):
    """
    In-memory storage for conversation contexts.

    Fast but not persistent - data is lost when the process ends.
    Best for single-instance deployments or testing.
    """

    def __init__(self):
        self._data: Dict[str, ConversationContext] = {}

    def save(self, context: ConversationContext) -> None:
        """Save context to memory."""
        self._data[context.key] = context

    def get(self, key: str) -> Optional[ConversationContext]:
        """Get context from memory."""
        return self._data.get(key)

    def delete(self, key: str) -> None:
        """Delete context from memory."""
        self._data.pop(key, None)

    def get_by_user_id(self, user_id: str) -> List[ConversationContext]:
        """Get all contexts for a user."""
        return [ctx for ctx in self._data.values() if ctx.user_id == user_id]

    def clear_expired(self) -> int:
        """Remove expired contexts."""
        expired_keys = [key for key, ctx in self._data.items() if ctx.is_expired()]
        for key in expired_keys:
            del self._data[key]
        return len(expired_keys)


class JSONFileStorage(StateStorage):
    """
    JSON file-based storage for conversation contexts.

    Persists data to a JSON file. Suitable for small deployments
    where persistence is needed but a database is overkill.

    Note: Not suitable for high-concurrency scenarios.
    """

    def __init__(self, file_path: str):
        """
        Initialize file storage.

        Args:
            file_path: Path to the JSON storage file
        """
        self._file_path = Path(file_path)
        self._data: Dict[str, Dict] = {}
        self._load()

    def _load(self) -> None:
        """Load data from file."""
        if self._file_path.exists():
            try:
                with open(self._file_path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load state file: {e}")
                self._data = {}

    def _save_to_file(self) -> None:
        """Save data to file."""
        try:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._file_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save state file: {e}")

    def save(self, context: ConversationContext) -> None:
        """Save context to file."""
        self._data[context.key] = context.to_dict()
        self._save_to_file()

    def get(self, key: str) -> Optional[ConversationContext]:
        """Get context from file storage."""
        data = self._data.get(key)
        if data is None:
            return None
        return ConversationContext.from_dict(data)

    def delete(self, key: str) -> None:
        """Delete context from file storage."""
        if key in self._data:
            del self._data[key]
            self._save_to_file()

    def get_by_user_id(self, user_id: str) -> List[ConversationContext]:
        """Get all contexts for a user."""
        contexts = []
        for data in self._data.values():
            if data.get("user_id") == user_id:
                contexts.append(ConversationContext.from_dict(data))
        return contexts

    def clear_expired(self) -> int:
        """Remove expired contexts."""
        expired_keys = []
        for key, data in self._data.items():
            ctx = ConversationContext.from_dict(data)
            if ctx.is_expired():
                expired_keys.append(key)

        for key in expired_keys:
            del self._data[key]

        if expired_keys:
            self._save_to_file()

        return len(expired_keys)


class RedisStorage(StateStorage):
    """
    Redis-based storage for conversation contexts.

    Stub implementation for future distributed deployments.
    Currently returns None/empty for all operations when not connected.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        prefix: str = "conv_ctx:",
    ):
        """
        Initialize Redis storage.

        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            prefix: Key prefix for all contexts
        """
        self._host = host
        self._port = port
        self._db = db
        self._prefix = prefix
        self._client = None
        self._connected = False

        # Try to connect (will fail gracefully if Redis not available)
        self._try_connect()

    def _try_connect(self) -> None:
        """Attempt to connect to Redis."""
        try:
            import redis

            self._client = redis.Redis(
                host=self._host,
                port=self._port,
                db=self._db,
                decode_responses=True,
            )
            # Test connection
            self._client.ping()
            self._connected = True
            logger.info("Connected to Redis")
        except ImportError:
            logger.warning("redis package not installed - using stub")
            self._connected = False
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}")
            self._connected = False

    def is_connected(self) -> bool:
        """Check if connected to Redis."""
        return self._connected

    def save(self, context: ConversationContext) -> None:
        """Save context to Redis."""
        if not self._connected:
            return

        key = f"{self._prefix}{context.key}"
        try:
            self._client.setex(
                key,
                context.ttl_seconds,
                json.dumps(context.to_dict()),
            )
        except Exception as e:
            logger.error(f"Redis save failed: {e}")

    def get(self, key: str) -> Optional[ConversationContext]:
        """Get context from Redis."""
        if not self._connected:
            return None

        redis_key = f"{self._prefix}{key}"
        try:
            data = self._client.get(redis_key)
            if data is None:
                return None
            return ConversationContext.from_dict(json.loads(data))
        except Exception as e:
            logger.error(f"Redis get failed: {e}")
            return None

    def delete(self, key: str) -> None:
        """Delete context from Redis."""
        if not self._connected:
            return

        redis_key = f"{self._prefix}{key}"
        try:
            self._client.delete(redis_key)
        except Exception as e:
            logger.error(f"Redis delete failed: {e}")

    def get_by_user_id(self, user_id: str) -> List[ConversationContext]:
        """Get all contexts for a user."""
        if not self._connected:
            return []

        try:
            # Scan for keys matching pattern
            pattern = f"{self._prefix}{user_id}:*"
            contexts = []
            for key in self._client.scan_iter(match=pattern):
                data = self._client.get(key)
                if data:
                    contexts.append(ConversationContext.from_dict(json.loads(data)))
            return contexts
        except Exception as e:
            logger.error(f"Redis scan failed: {e}")
            return []

    def clear_expired(self) -> int:
        """
        Clear expired contexts.

        Redis handles expiration automatically via SETEX,
        so this is a no-op.
        """
        return 0
