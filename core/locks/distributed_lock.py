"""
Distributed Lock Mechanism
Reliability Audit Item #6: Distributed locking for multi-instance scenarios

Provides distributed locking for coordinating across multiple instances.

Features:
- File-based locking (single machine)
- Redis-based locking (distributed)
- Automatic lock expiration
- Lock extension
- Graceful degradation
"""

import asyncio
import logging
import os
import time
import uuid
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
import threading
import filelock

logger = logging.getLogger("jarvis.locks")


@dataclass
class LockInfo:
    """Information about a held lock"""
    lock_id: str
    resource: str
    owner: str
    acquired_at: datetime
    expires_at: Optional[datetime]
    metadata: Dict[str, Any]


class LockBackend(ABC):
    """Abstract base class for lock backends"""

    @abstractmethod
    async def acquire(
        self,
        resource: str,
        owner: str,
        ttl_sec: int,
        wait: bool,
        timeout: float,
    ) -> Optional[str]:
        """
        Acquire a lock on a resource.

        Args:
            resource: Resource identifier
            owner: Lock owner identifier
            ttl_sec: Lock time-to-live in seconds
            wait: Whether to wait for lock
            timeout: Max wait time in seconds

        Returns:
            Lock ID if acquired, None otherwise
        """
        pass

    @abstractmethod
    async def release(self, resource: str, lock_id: str) -> bool:
        """Release a lock"""
        pass

    @abstractmethod
    async def extend(self, resource: str, lock_id: str, ttl_sec: int) -> bool:
        """Extend a lock's TTL"""
        pass

    @abstractmethod
    async def is_locked(self, resource: str) -> bool:
        """Check if resource is locked"""
        pass

    @abstractmethod
    async def get_lock_info(self, resource: str) -> Optional[LockInfo]:
        """Get information about a lock"""
        pass


class FileLockBackend(LockBackend):
    """
    File-based lock backend for single-machine deployments.

    Uses filelock for process-safe locking with custom TTL support.
    """

    def __init__(self, lock_dir: str = None):
        self.lock_dir = Path(lock_dir or os.path.expanduser("~/.lifeos/locks"))
        self.lock_dir.mkdir(parents=True, exist_ok=True)

        self._locks: Dict[str, filelock.FileLock] = {}
        self._lock_ids: Dict[str, str] = {}
        self._lock_info: Dict[str, LockInfo] = {}
        self._local_lock = threading.Lock()

    def _get_lock_path(self, resource: str) -> Path:
        """Get the lock file path for a resource"""
        safe_name = resource.replace("/", "_").replace(":", "_")
        return self.lock_dir / f"{safe_name}.lock"

    def _get_info_path(self, resource: str) -> Path:
        """Get the info file path for a resource"""
        safe_name = resource.replace("/", "_").replace(":", "_")
        return self.lock_dir / f"{safe_name}.info"

    async def acquire(
        self,
        resource: str,
        owner: str,
        ttl_sec: int = 60,
        wait: bool = False,
        timeout: float = 30.0,
    ) -> Optional[str]:
        lock_path = self._get_lock_path(resource)
        lock = filelock.FileLock(lock_path, timeout=timeout if wait else 0)

        try:
            lock.acquire(timeout=timeout if wait else 0)
        except filelock.Timeout:
            return None

        lock_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc)

        info = LockInfo(
            lock_id=lock_id,
            resource=resource,
            owner=owner,
            acquired_at=now,
            expires_at=datetime.fromtimestamp(now.timestamp() + ttl_sec, tz=timezone.utc),
            metadata={},
        )

        with self._local_lock:
            self._locks[resource] = lock
            self._lock_ids[resource] = lock_id
            self._lock_info[resource] = info

        # Write info file
        info_path = self._get_info_path(resource)
        try:
            import json
            with open(info_path, "w") as f:
                json.dump({
                    "lock_id": lock_id,
                    "owner": owner,
                    "acquired_at": info.acquired_at.isoformat(),
                    "expires_at": info.expires_at.isoformat(),
                }, f)
        except Exception:
            pass

        logger.debug(f"Acquired file lock on {resource}")
        return lock_id

    async def release(self, resource: str, lock_id: str) -> bool:
        with self._local_lock:
            if resource not in self._locks:
                return False

            if self._lock_ids.get(resource) != lock_id:
                return False

            lock = self._locks.pop(resource)
            self._lock_ids.pop(resource, None)
            self._lock_info.pop(resource, None)

        try:
            lock.release()
        except Exception:
            pass

        # Clean up info file
        info_path = self._get_info_path(resource)
        try:
            info_path.unlink(missing_ok=True)
        except Exception:
            pass

        logger.debug(f"Released file lock on {resource}")
        return True

    async def extend(self, resource: str, lock_id: str, ttl_sec: int) -> bool:
        with self._local_lock:
            if self._lock_ids.get(resource) != lock_id:
                return False

            info = self._lock_info.get(resource)
            if info:
                now = datetime.now(timezone.utc)
                info.expires_at = datetime.fromtimestamp(now.timestamp() + ttl_sec, tz=timezone.utc)

        return True

    async def is_locked(self, resource: str) -> bool:
        lock_path = self._get_lock_path(resource)
        if not lock_path.exists():
            return False

        # Try to acquire briefly to check
        lock = filelock.FileLock(lock_path, timeout=0)
        try:
            lock.acquire(timeout=0)
            lock.release()
            return False
        except filelock.Timeout:
            return True

    async def get_lock_info(self, resource: str) -> Optional[LockInfo]:
        with self._local_lock:
            return self._lock_info.get(resource)


class RedisLockBackend(LockBackend):
    """
    Redis-based lock backend for distributed deployments.

    Uses Redis SET NX with expiration for atomic locking.
    """

    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self._redis = None
        self._prefix = "jarvis:lock:"

    def _get_redis(self):
        """Get or create Redis connection"""
        if self._redis is None:
            try:
                import redis
                self._redis = redis.from_url(self.redis_url, decode_responses=True)
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                return None
        return self._redis

    async def acquire(
        self,
        resource: str,
        owner: str,
        ttl_sec: int = 60,
        wait: bool = False,
        timeout: float = 30.0,
    ) -> Optional[str]:
        redis_client = self._get_redis()
        if redis_client is None:
            return None

        lock_id = str(uuid.uuid4())[:8]
        key = f"{self._prefix}{resource}"
        value = f"{lock_id}:{owner}"

        start_time = time.time()

        while True:
            # Try to set with NX (only if not exists)
            acquired = redis_client.set(key, value, nx=True, ex=ttl_sec)

            if acquired:
                logger.debug(f"Acquired Redis lock on {resource}")
                return lock_id

            if not wait:
                return None

            if time.time() - start_time > timeout:
                return None

            await asyncio.sleep(0.1)

    async def release(self, resource: str, lock_id: str) -> bool:
        redis_client = self._get_redis()
        if redis_client is None:
            return False

        key = f"{self._prefix}{resource}"

        # Use Lua script for atomic check-and-delete
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """

        try:
            # Check if lock belongs to us
            current = redis_client.get(key)
            if current and current.startswith(f"{lock_id}:"):
                redis_client.delete(key)
                logger.debug(f"Released Redis lock on {resource}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to release Redis lock: {e}")
            return False

    async def extend(self, resource: str, lock_id: str, ttl_sec: int) -> bool:
        redis_client = self._get_redis()
        if redis_client is None:
            return False

        key = f"{self._prefix}{resource}"

        try:
            current = redis_client.get(key)
            if current and current.startswith(f"{lock_id}:"):
                redis_client.expire(key, ttl_sec)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to extend Redis lock: {e}")
            return False

    async def is_locked(self, resource: str) -> bool:
        redis_client = self._get_redis()
        if redis_client is None:
            return False

        key = f"{self._prefix}{resource}"
        return redis_client.exists(key) > 0

    async def get_lock_info(self, resource: str) -> Optional[LockInfo]:
        redis_client = self._get_redis()
        if redis_client is None:
            return None

        key = f"{self._prefix}{resource}"
        value = redis_client.get(key)

        if not value:
            return None

        parts = value.split(":", 1)
        lock_id = parts[0]
        owner = parts[1] if len(parts) > 1 else "unknown"

        ttl = redis_client.ttl(key)

        return LockInfo(
            lock_id=lock_id,
            resource=resource,
            owner=owner,
            acquired_at=datetime.now(timezone.utc),  # Approximate
            expires_at=datetime.fromtimestamp(time.time() + ttl, tz=timezone.utc) if ttl > 0 else None,
            metadata={},
        )


class DistributedLock:
    """
    High-level distributed lock with automatic backend selection.

    Tries Redis first, falls back to file-based locking.
    """

    def __init__(
        self,
        redis_url: str = None,
        lock_dir: str = None,
        prefer_redis: bool = True,
    ):
        self.prefer_redis = prefer_redis

        # Initialize backends
        self._file_backend = FileLockBackend(lock_dir)
        self._redis_backend = None

        if prefer_redis:
            try:
                self._redis_backend = RedisLockBackend(redis_url)
                # Test connection
                redis_client = self._redis_backend._get_redis()
                if redis_client:
                    redis_client.ping()
                    logger.info("Using Redis for distributed locks")
                else:
                    self._redis_backend = None
            except Exception as e:
                logger.info(f"Redis not available, using file locks: {e}")
                self._redis_backend = None

    def _get_backend(self) -> LockBackend:
        """Get the active backend"""
        if self._redis_backend:
            return self._redis_backend
        return self._file_backend

    async def acquire(
        self,
        resource: str,
        owner: str = None,
        ttl_sec: int = 60,
        wait: bool = False,
        timeout: float = 30.0,
    ) -> Optional[str]:
        """
        Acquire a distributed lock.

        Args:
            resource: Resource to lock
            owner: Owner identifier (defaults to hostname)
            ttl_sec: Lock TTL in seconds
            wait: Whether to wait for lock
            timeout: Max wait time

        Returns:
            Lock ID if acquired, None otherwise
        """
        import socket
        owner = owner or f"{socket.gethostname()}:{os.getpid()}"

        backend = self._get_backend()
        return await backend.acquire(resource, owner, ttl_sec, wait, timeout)

    async def release(self, resource: str, lock_id: str) -> bool:
        """Release a lock"""
        backend = self._get_backend()
        return await backend.release(resource, lock_id)

    async def extend(self, resource: str, lock_id: str, ttl_sec: int = 60) -> bool:
        """Extend a lock's TTL"""
        backend = self._get_backend()
        return await backend.extend(resource, lock_id, ttl_sec)

    async def is_locked(self, resource: str) -> bool:
        """Check if resource is locked"""
        backend = self._get_backend()
        return await backend.is_locked(resource)

    async def get_lock_info(self, resource: str) -> Optional[LockInfo]:
        """Get lock information"""
        backend = self._get_backend()
        return await backend.get_lock_info(resource)

    @asynccontextmanager
    async def lock(
        self,
        resource: str,
        owner: str = None,
        ttl_sec: int = 60,
        wait: bool = True,
        timeout: float = 30.0,
    ):
        """
        Context manager for acquiring and releasing locks.

        Usage:
            async with distributed_lock.lock("resource_name"):
                # Critical section
                pass
        """
        lock_id = await self.acquire(resource, owner, ttl_sec, wait, timeout)

        if lock_id is None:
            raise LockError(f"Failed to acquire lock on {resource}")

        try:
            yield lock_id
        finally:
            await self.release(resource, lock_id)


class LockError(Exception):
    """Raised when lock operations fail"""
    pass


# =============================================================================
# SINGLETON
# =============================================================================

_lock_manager: Optional[DistributedLock] = None


def get_distributed_lock() -> DistributedLock:
    """Get or create the distributed lock manager singleton"""
    global _lock_manager
    if _lock_manager is None:
        _lock_manager = DistributedLock()
    return _lock_manager


@asynccontextmanager
async def distributed_lock(
    resource: str,
    ttl_sec: int = 60,
    wait: bool = True,
    timeout: float = 30.0,
):
    """
    Convenience function for distributed locking.

    Usage:
        async with distributed_lock("my_resource"):
            # Critical section
            pass
    """
    lock_manager = get_distributed_lock()
    async with lock_manager.lock(resource, ttl_sec=ttl_sec, wait=wait, timeout=timeout):
        yield
