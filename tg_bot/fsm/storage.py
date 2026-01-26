"""
Redis-backed FSM Storage for Telegram Bot.

Provides persistent storage for FSM state and session data with:
- Redis backend for distributed persistence
- Automatic TTL-based session expiration (default 1 hour)
- Session recovery on bot restart
- In-memory fallback when Redis is unavailable
- Wallet-per-session isolation
"""

import asyncio
import json
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from tg_bot.fsm.states import FSMState, SessionData, parse_state_string

logger = logging.getLogger(__name__)

# Try to import redis
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None


@dataclass
class StoredState:
    """Wrapper for stored state with metadata."""
    state: Optional[FSMState]
    updated_at: str


class RedisFSMStorage:
    """
    Redis-backed storage for FSM state and session data.

    Features:
    - State persistence with TTL
    - Session data persistence
    - Automatic expiration (default 1 hour inactive)
    - Session recovery on restart
    - In-memory fallback when Redis unavailable
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        key_prefix: str = "jarvis:fsm:",
        session_ttl: int = 3600,  # 1 hour
        use_redis: bool = True,
    ):
        """
        Initialize FSM storage.

        Args:
            redis_url: Redis connection URL
            key_prefix: Prefix for all Redis keys
            session_ttl: Session timeout in seconds (default 1 hour)
            use_redis: Whether to attempt Redis connection
        """
        self.redis_url = redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        self.key_prefix = key_prefix
        self.session_ttl = session_ttl
        self.use_redis = use_redis and REDIS_AVAILABLE

        # Redis client (lazy initialized)
        self._redis: Optional[Any] = None
        self._redis_connected = False
        self._connection_attempted = False

        # In-memory fallback state
        self._memory_states: Dict[str, StoredState] = {}
        self._memory_data: Dict[str, SessionData] = {}
        self._memory_timestamps: Dict[str, float] = {}
        self._lock = asyncio.Lock()

        logger.info(
            f"RedisFSMStorage initialized (redis={self.use_redis}, "
            f"available={REDIS_AVAILABLE}, ttl={session_ttl}s)"
        )

    async def _get_redis(self) -> Optional[Any]:
        """Get Redis client, initializing if needed."""
        if not self.use_redis:
            return None

        # Don't retry failed connections too often
        if self._connection_attempted and not self._redis_connected:
            return None

        if self._redis is None:
            self._connection_attempted = True
            try:
                self._redis = redis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=2.0,
                    socket_timeout=2.0,
                )
                # Test connection
                await asyncio.wait_for(self._redis.ping(), timeout=2.0)
                self._redis_connected = True
                logger.info("FSM Redis connection established")
            except asyncio.TimeoutError:
                logger.warning("FSM Redis connection timed out, using memory fallback")
                self._redis_connected = False
                self._redis = None
            except Exception as e:
                logger.warning(f"FSM Redis connection failed: {e}, using memory fallback")
                self._redis_connected = False
                self._redis = None

        return self._redis if self._redis_connected else None

    def _make_state_key(self, user_id: int, chat_id: int) -> str:
        """Generate Redis key for state."""
        return f"{self.key_prefix}state:{user_id}:{chat_id}"

    def _make_data_key(self, user_id: int, chat_id: int) -> str:
        """Generate Redis key for session data."""
        return f"{self.key_prefix}data:{user_id}:{chat_id}"

    # =========================================================================
    # State Operations
    # =========================================================================

    async def set_state(
        self,
        user_id: int,
        chat_id: int,
        state: Optional[FSMState]
    ) -> bool:
        """
        Set FSM state for a user/chat.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            state: FSM state to set (None to clear)

        Returns:
            True if successful
        """
        state_str = str(state) if state else "None"
        stored = {
            "state": state_str,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

        redis_client = await self._get_redis()

        if redis_client:
            try:
                key = self._make_state_key(user_id, chat_id)
                await redis_client.setex(key, self.session_ttl, json.dumps(stored))
                return True
            except Exception as e:
                logger.warning(f"Redis set_state error: {e}, falling back to memory")

        # Memory fallback
        async with self._lock:
            key = self._make_state_key(user_id, chat_id)
            self._memory_states[key] = StoredState(state=state, updated_at=stored["updated_at"])
            self._memory_timestamps[key] = time.time()
            return True

    async def get_state(self, user_id: int, chat_id: int) -> Optional[FSMState]:
        """
        Get FSM state for a user/chat.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID

        Returns:
            Current FSM state or None
        """
        redis_client = await self._get_redis()

        if redis_client:
            try:
                key = self._make_state_key(user_id, chat_id)
                data = await redis_client.get(key)

                if data:
                    stored = json.loads(data)
                    return parse_state_string(stored.get("state", "None"))

                return None
            except Exception as e:
                logger.warning(f"Redis get_state error: {e}, falling back to memory")

        # Memory fallback
        async with self._lock:
            key = self._make_state_key(user_id, chat_id)
            stored = self._memory_states.get(key)

            if stored:
                # Check if expired
                timestamp = self._memory_timestamps.get(key, 0)
                if time.time() - timestamp > self.session_ttl:
                    del self._memory_states[key]
                    del self._memory_timestamps[key]
                    return None

                return stored.state

            return None

    # =========================================================================
    # Session Data Operations
    # =========================================================================

    async def set_data(
        self,
        user_id: int,
        chat_id: int,
        data: SessionData
    ) -> bool:
        """
        Set session data for a user/chat.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            data: Session data to store

        Returns:
            True if successful
        """
        redis_client = await self._get_redis()

        if redis_client:
            try:
                key = self._make_data_key(user_id, chat_id)
                await redis_client.setex(key, self.session_ttl, json.dumps(data.to_dict()))
                return True
            except Exception as e:
                logger.warning(f"Redis set_data error: {e}, falling back to memory")

        # Memory fallback
        async with self._lock:
            key = self._make_data_key(user_id, chat_id)
            self._memory_data[key] = data
            self._memory_timestamps[key] = time.time()
            return True

    async def get_data(self, user_id: int, chat_id: int) -> Optional[SessionData]:
        """
        Get session data for a user/chat.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID

        Returns:
            Session data or None
        """
        redis_client = await self._get_redis()

        if redis_client:
            try:
                key = self._make_data_key(user_id, chat_id)
                data = await redis_client.get(key)

                if data:
                    return SessionData.from_dict(json.loads(data))

                return None
            except Exception as e:
                logger.warning(f"Redis get_data error: {e}, falling back to memory")

        # Memory fallback
        async with self._lock:
            key = self._make_data_key(user_id, chat_id)
            data = self._memory_data.get(key)

            if data:
                # Check if expired
                timestamp = self._memory_timestamps.get(key, 0)
                if time.time() - timestamp > self.session_ttl:
                    del self._memory_data[key]
                    del self._memory_timestamps[key]
                    return None

                return data

            return None

    async def update_data(
        self,
        user_id: int,
        chat_id: int,
        **updates
    ) -> Optional[SessionData]:
        """
        Update specific fields in session data.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            **updates: Fields to update

        Returns:
            Updated session data or None if not found
        """
        data = await self.get_data(user_id, chat_id)

        if data is None:
            return None

        # Apply updates
        data.update(**updates)

        # Save back
        await self.set_data(user_id, chat_id, data)

        return data

    # =========================================================================
    # Session Management
    # =========================================================================

    async def clear(self, user_id: int, chat_id: int) -> bool:
        """
        Clear state and data for a user/chat.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID

        Returns:
            True if successful
        """
        state_key = self._make_state_key(user_id, chat_id)
        data_key = self._make_data_key(user_id, chat_id)

        redis_client = await self._get_redis()

        if redis_client:
            try:
                await redis_client.delete(state_key, data_key)
                return True
            except Exception as e:
                logger.warning(f"Redis clear error: {e}, falling back to memory")

        # Memory fallback
        async with self._lock:
            self._memory_states.pop(state_key, None)
            self._memory_data.pop(data_key, None)
            self._memory_timestamps.pop(state_key, None)
            self._memory_timestamps.pop(data_key, None)
            return True

    async def get_active_sessions(self) -> List[Tuple[int, int]]:
        """
        Get list of active sessions (user_id, chat_id tuples).

        Returns:
            List of (user_id, chat_id) tuples
        """
        sessions = []

        redis_client = await self._get_redis()

        if redis_client:
            try:
                cursor = 0
                pattern = f"{self.key_prefix}state:*"

                while True:
                    cursor, keys = await redis_client.scan(cursor, match=pattern, count=100)

                    for key in keys:
                        # Parse key: "jarvis:fsm:state:123:456"
                        parts = key.split(":")
                        if len(parts) >= 5:
                            try:
                                user_id = int(parts[-2])
                                chat_id = int(parts[-1])
                                sessions.append((user_id, chat_id))
                            except ValueError:
                                pass

                    if cursor == 0:
                        break

                return sessions
            except Exception as e:
                logger.warning(f"Redis get_active_sessions error: {e}, falling back to memory")

        # Memory fallback
        async with self._lock:
            for key in self._memory_states.keys():
                # Parse key: "jarvis:fsm:state:123:456"
                parts = key.split(":")
                if len(parts) >= 5:
                    try:
                        user_id = int(parts[-2])
                        chat_id = int(parts[-1])
                        sessions.append((user_id, chat_id))
                    except ValueError:
                        pass

            return sessions

    async def cleanup_expired(self) -> int:
        """
        Clean up expired sessions (memory fallback only - Redis uses TTL).

        Returns:
            Number of sessions cleaned up
        """
        cleaned = 0
        now = time.time()

        # Only needed for memory fallback
        async with self._lock:
            expired_keys = [
                key for key, ts in self._memory_timestamps.items()
                if now - ts > self.session_ttl
            ]

            for key in expired_keys:
                self._memory_states.pop(key, None)
                self._memory_data.pop(key, None)
                self._memory_timestamps.pop(key, None)
                cleaned += 1

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} expired FSM sessions")

        return cleaned

    async def touch(self, user_id: int, chat_id: int) -> bool:
        """
        Refresh TTL for a session (keep alive).

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID

        Returns:
            True if session exists and was refreshed
        """
        state_key = self._make_state_key(user_id, chat_id)
        data_key = self._make_data_key(user_id, chat_id)

        redis_client = await self._get_redis()

        if redis_client:
            try:
                # Refresh TTL on both keys
                await redis_client.expire(state_key, self.session_ttl)
                await redis_client.expire(data_key, self.session_ttl)
                return True
            except Exception as e:
                logger.warning(f"Redis touch error: {e}")

        # Memory fallback
        async with self._lock:
            now = time.time()
            if state_key in self._memory_timestamps:
                self._memory_timestamps[state_key] = now
                self._memory_timestamps[data_key] = now
                return True

        return False

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            try:
                await self._redis.close()
            except Exception:
                pass
            self._redis = None
            self._redis_connected = False

    async def health_check(self) -> Dict[str, Any]:
        """
        Check storage health status.

        Returns:
            Health status dict
        """
        status = {
            "redis_available": REDIS_AVAILABLE,
            "redis_connected": self._redis_connected,
            "memory_sessions": len(self._memory_states),
            "session_ttl": self.session_ttl,
        }

        redis_client = await self._get_redis()
        if redis_client:
            try:
                await redis_client.ping()
                status["redis_healthy"] = True
            except Exception:
                status["redis_healthy"] = False
        else:
            status["redis_healthy"] = False

        return status


# Singleton instance
_fsm_storage: Optional[RedisFSMStorage] = None


def get_fsm_storage(
    redis_url: Optional[str] = None,
    session_ttl: int = 3600,
) -> RedisFSMStorage:
    """
    Get the singleton FSM storage instance.

    Args:
        redis_url: Redis URL (only used on first call)
        session_ttl: Session TTL in seconds (only used on first call)

    Returns:
        RedisFSMStorage instance
    """
    global _fsm_storage

    if _fsm_storage is None:
        _fsm_storage = RedisFSMStorage(
            redis_url=redis_url,
            session_ttl=session_ttl,
        )

    return _fsm_storage


def reset_fsm_storage() -> None:
    """Reset the singleton instance (for testing)."""
    global _fsm_storage
    _fsm_storage = None


__all__ = [
    "RedisFSMStorage",
    "get_fsm_storage",
    "reset_fsm_storage",
]
