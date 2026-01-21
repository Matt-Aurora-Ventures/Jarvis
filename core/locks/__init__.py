"""
Distributed locking module.

Provides:
- File-based locks for single machine
- Redis-based locks for distributed deployments
- Automatic backend selection
"""

from core.locks.distributed_lock import (
    DistributedLock,
    FileLockBackend,
    RedisLockBackend,
    LockBackend,
    LockInfo,
    LockError,
    get_distributed_lock,
    distributed_lock,
)

__all__ = [
    "DistributedLock",
    "FileLockBackend",
    "RedisLockBackend",
    "LockBackend",
    "LockInfo",
    "LockError",
    "get_distributed_lock",
    "distributed_lock",
]
