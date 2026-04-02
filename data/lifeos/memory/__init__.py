"""
Jarvis Memory Sandboxing System

Provides isolated memory storage with strict access control.
SECURITY CRITICAL: Trading data is completely isolated.

Context Types:
- SYSTEM: Core system state (read-only for most)
- TRADING: Trading data (completely isolated)
- PERSONAL: User data (protected)
- PUBLIC: General data (shared)
- SCRATCH: Temporary data (auto-expires)

Usage:
    from lifeos.memory import MemoryStore, MemoryContext

    store = MemoryStore()

    # Store trading data (only trading context can read/write)
    await store.set(
        key="position",
        value={"symbol": "SOL"},
        context=MemoryContext.TRADING,
        caller_context=MemoryContext.TRADING,
    )

    # This will FAIL - trading is isolated
    await store.get(
        key="position",
        context=MemoryContext.TRADING,
        caller_context=MemoryContext.PUBLIC,  # ACCESS DENIED
    )
"""

from lifeos.memory.contexts import (
    MemoryContext,
    ContextPermissions,
    CONTEXT_PERMISSIONS,
    can_read,
    can_write,
    requires_audit,
    get_default_ttl,
    get_max_ttl,
)
from lifeos.memory.store import (
    MemoryStore,
    MemoryEntry,
    AuditLogEntry,
    MemoryAccessError,
    get_memory_store,
    set_memory_store,
)

__all__ = [
    # Contexts
    "MemoryContext",
    "ContextPermissions",
    "CONTEXT_PERMISSIONS",
    "can_read",
    "can_write",
    "requires_audit",
    "get_default_ttl",
    "get_max_ttl",
    # Store
    "MemoryStore",
    "MemoryEntry",
    "AuditLogEntry",
    "MemoryAccessError",
    "get_memory_store",
    "set_memory_store",
]
