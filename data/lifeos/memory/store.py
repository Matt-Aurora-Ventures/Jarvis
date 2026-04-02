"""
Sandboxed Memory Store

Provides isolated memory storage with context-based access control.
SECURITY CRITICAL: Enforces isolation boundaries between contexts.

Features:
- Context-based isolation
- Permission enforcement
- TTL-based expiration
- Audit logging for sensitive access
- Thread-safe operations

Usage:
    store = MemoryStore()

    # Write to trading context
    await store.set(
        key="position",
        value={"symbol": "SOL", "amount": 100},
        context=MemoryContext.TRADING,
        caller_context=MemoryContext.TRADING,
    )

    # This will FAIL (trading is isolated)
    await store.get(
        key="position",
        context=MemoryContext.TRADING,
        caller_context=MemoryContext.PUBLIC,
    )
"""

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set
import threading

from lifeos.memory.contexts import (
    MemoryContext,
    CONTEXT_PERMISSIONS,
    can_read,
    can_write,
    requires_audit,
    get_default_ttl,
    get_max_ttl,
)

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """A single memory entry."""
    key: str
    value: Any
    context: MemoryContext
    created_at: datetime
    expires_at: datetime
    created_by: MemoryContext
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        return datetime.now(timezone.utc) > self.expires_at

    def touch(self) -> None:
        """Update access tracking."""
        self.access_count += 1
        self.last_accessed = datetime.now(timezone.utc)


@dataclass
class AuditLogEntry:
    """Audit log entry for sensitive access."""
    timestamp: datetime
    operation: str  # "read", "write", "delete"
    key: str
    context: MemoryContext
    caller_context: MemoryContext
    success: bool
    reason: Optional[str] = None  # Failure reason if not success

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "operation": self.operation,
            "key": self.key,
            "context": self.context.value,
            "caller_context": self.caller_context.value,
            "success": self.success,
            "reason": self.reason,
        }


class MemoryAccessError(Exception):
    """Raised when memory access is denied."""

    def __init__(
        self,
        operation: str,
        key: str,
        context: MemoryContext,
        caller_context: MemoryContext,
        reason: str,
    ):
        self.operation = operation
        self.key = key
        self.context = context
        self.caller_context = caller_context
        self.reason = reason
        super().__init__(
            f"Access denied: {caller_context.value} cannot {operation} "
            f"{context.value}/{key}: {reason}"
        )


class MemoryStore:
    """
    Thread-safe, sandboxed memory store.

    Provides isolated storage with context-based access control.
    All operations are logged for audit purposes.
    """

    def __init__(self, max_audit_log_size: int = 10000):
        """
        Initialize memory store.

        Args:
            max_audit_log_size: Maximum audit log entries to keep
        """
        self._lock = threading.RLock()
        self._storage: Dict[MemoryContext, Dict[str, MemoryEntry]] = {
            ctx: {} for ctx in MemoryContext
        }
        self._audit_log: List[AuditLogEntry] = []
        self._max_audit_size = max_audit_log_size
        self._cleanup_interval = 60  # seconds
        self._cleanup_task: Optional[asyncio.Task] = None

    # =========================================================================
    # Core Operations
    # =========================================================================

    async def set(
        self,
        key: str,
        value: Any,
        context: MemoryContext,
        caller_context: MemoryContext,
        ttl: Optional[timedelta] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Store a value in memory.

        Args:
            key: Storage key
            value: Value to store (must be JSON-serializable)
            context: Target memory context
            caller_context: Context making the request
            ttl: Time-to-live (uses context default if None)
            metadata: Optional metadata to attach

        Raises:
            MemoryAccessError: If write access is denied
        """
        # Check permission
        if not can_write(caller_context, context):
            self._audit(
                operation="write",
                key=key,
                context=context,
                caller_context=caller_context,
                success=False,
                reason="Permission denied",
            )
            raise MemoryAccessError(
                operation="write",
                key=key,
                context=context,
                caller_context=caller_context,
                reason="Write permission denied",
            )

        # Calculate TTL
        if ttl is None:
            ttl = get_default_ttl(context)
        else:
            max_ttl = get_max_ttl(context)
            if ttl > max_ttl:
                ttl = max_ttl

        now = datetime.now(timezone.utc)
        entry = MemoryEntry(
            key=key,
            value=value,
            context=context,
            created_at=now,
            expires_at=now + ttl,
            created_by=caller_context,
            metadata=metadata or {},
        )

        with self._lock:
            self._storage[context][key] = entry

        self._audit(
            operation="write",
            key=key,
            context=context,
            caller_context=caller_context,
            success=True,
        )

        logger.debug(f"Memory set: {context.value}/{key}")

    async def get(
        self,
        key: str,
        context: MemoryContext,
        caller_context: MemoryContext,
        default: Any = None,
    ) -> Any:
        """
        Retrieve a value from memory.

        Args:
            key: Storage key
            context: Target memory context
            caller_context: Context making the request
            default: Default value if key not found

        Returns:
            Stored value or default

        Raises:
            MemoryAccessError: If read access is denied
        """
        # Check permission
        if not can_read(caller_context, context):
            self._audit(
                operation="read",
                key=key,
                context=context,
                caller_context=caller_context,
                success=False,
                reason="Permission denied",
            )
            raise MemoryAccessError(
                operation="read",
                key=key,
                context=context,
                caller_context=caller_context,
                reason="Read permission denied",
            )

        with self._lock:
            entry = self._storage[context].get(key)

            if entry is None:
                return default

            if entry.is_expired():
                del self._storage[context][key]
                return default

            entry.touch()

        self._audit(
            operation="read",
            key=key,
            context=context,
            caller_context=caller_context,
            success=True,
        )

        return entry.value

    async def delete(
        self,
        key: str,
        context: MemoryContext,
        caller_context: MemoryContext,
    ) -> bool:
        """
        Delete a value from memory.

        Args:
            key: Storage key
            context: Target memory context
            caller_context: Context making the request

        Returns:
            True if key existed and was deleted

        Raises:
            MemoryAccessError: If write access is denied
        """
        # Check permission (delete requires write)
        if not can_write(caller_context, context):
            self._audit(
                operation="delete",
                key=key,
                context=context,
                caller_context=caller_context,
                success=False,
                reason="Permission denied",
            )
            raise MemoryAccessError(
                operation="delete",
                key=key,
                context=context,
                caller_context=caller_context,
                reason="Write permission denied for delete",
            )

        with self._lock:
            existed = key in self._storage[context]
            if existed:
                del self._storage[context][key]

        self._audit(
            operation="delete",
            key=key,
            context=context,
            caller_context=caller_context,
            success=True,
        )

        return existed

    async def exists(
        self,
        key: str,
        context: MemoryContext,
        caller_context: MemoryContext,
    ) -> bool:
        """
        Check if a key exists in memory.

        Args:
            key: Storage key
            context: Target memory context
            caller_context: Context making the request

        Returns:
            True if key exists and is not expired

        Raises:
            MemoryAccessError: If read access is denied
        """
        if not can_read(caller_context, context):
            raise MemoryAccessError(
                operation="exists",
                key=key,
                context=context,
                caller_context=caller_context,
                reason="Read permission denied",
            )

        with self._lock:
            entry = self._storage[context].get(key)
            if entry is None:
                return False
            if entry.is_expired():
                del self._storage[context][key]
                return False
            return True

    async def keys(
        self,
        context: MemoryContext,
        caller_context: MemoryContext,
        pattern: Optional[str] = None,
    ) -> List[str]:
        """
        List keys in a context.

        Args:
            context: Target memory context
            caller_context: Context making the request
            pattern: Optional prefix filter

        Returns:
            List of keys

        Raises:
            MemoryAccessError: If read access is denied
        """
        if not can_read(caller_context, context):
            raise MemoryAccessError(
                operation="keys",
                key="*",
                context=context,
                caller_context=caller_context,
                reason="Read permission denied",
            )

        with self._lock:
            all_keys = list(self._storage[context].keys())

        # Filter expired entries and apply pattern
        result = []
        for key in all_keys:
            entry = self._storage[context].get(key)
            if entry and not entry.is_expired():
                if pattern is None or key.startswith(pattern):
                    result.append(key)

        return result

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def cleanup_expired(self) -> int:
        """
        Remove expired entries from all contexts.

        Returns:
            Number of entries removed
        """
        removed = 0
        now = datetime.now(timezone.utc)

        with self._lock:
            for context in MemoryContext:
                to_remove = []
                for key, entry in self._storage[context].items():
                    if entry.expires_at < now:
                        to_remove.append(key)

                for key in to_remove:
                    del self._storage[context][key]
                    removed += 1

        if removed > 0:
            logger.debug(f"Cleaned up {removed} expired memory entries")

        return removed

    async def clear_context(
        self,
        context: MemoryContext,
        caller_context: MemoryContext,
    ) -> int:
        """
        Clear all entries in a context.

        Args:
            context: Context to clear
            caller_context: Context making the request

        Returns:
            Number of entries removed

        Raises:
            MemoryAccessError: If write access is denied
        """
        if not can_write(caller_context, context):
            raise MemoryAccessError(
                operation="clear",
                key="*",
                context=context,
                caller_context=caller_context,
                reason="Write permission denied",
            )

        with self._lock:
            count = len(self._storage[context])
            self._storage[context].clear()

        self._audit(
            operation="clear",
            key="*",
            context=context,
            caller_context=caller_context,
            success=True,
        )

        return count

    def start_cleanup_task(self) -> None:
        """Start background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    def stop_cleanup_task(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()

    async def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        while True:
            await asyncio.sleep(self._cleanup_interval)
            await self.cleanup_expired()

    # =========================================================================
    # Audit
    # =========================================================================

    def _audit(
        self,
        operation: str,
        key: str,
        context: MemoryContext,
        caller_context: MemoryContext,
        success: bool,
        reason: Optional[str] = None,
    ) -> None:
        """Record an audit log entry."""
        # Only audit if required for the context
        if not requires_audit(context):
            return

        entry = AuditLogEntry(
            timestamp=datetime.now(timezone.utc),
            operation=operation,
            key=key,
            context=context,
            caller_context=caller_context,
            success=success,
            reason=reason,
        )

        with self._lock:
            self._audit_log.append(entry)
            # Trim log if too large
            if len(self._audit_log) > self._max_audit_size:
                self._audit_log = self._audit_log[-self._max_audit_size:]

        # Log security events
        if not success:
            logger.warning(
                f"SECURITY: Access denied - {caller_context.value} tried to "
                f"{operation} {context.value}/{key}: {reason}"
            )

    def get_audit_log(
        self,
        context: Optional[MemoryContext] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get audit log entries.

        Args:
            context: Filter by context (None for all)
            limit: Maximum entries to return

        Returns:
            List of audit log entries as dicts
        """
        with self._lock:
            entries = self._audit_log[-limit:]
            if context:
                entries = [e for e in entries if e.context == context]
            return [e.to_dict() for e in entries]

    # =========================================================================
    # Stats
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get memory store statistics."""
        with self._lock:
            stats = {
                "contexts": {},
                "total_entries": 0,
                "audit_log_size": len(self._audit_log),
            }

            for context in MemoryContext:
                entries = self._storage[context]
                expired = sum(1 for e in entries.values() if e.is_expired())
                stats["contexts"][context.value] = {
                    "entries": len(entries),
                    "expired": expired,
                    "active": len(entries) - expired,
                }
                stats["total_entries"] += len(entries)

            return stats


# Global store instance
_store: Optional[MemoryStore] = None


def get_memory_store() -> MemoryStore:
    """Get or create the global memory store."""
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store


def set_memory_store(store: MemoryStore) -> None:
    """Set the global memory store."""
    global _store
    _store = store
