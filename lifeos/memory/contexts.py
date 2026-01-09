"""
Memory Context Definitions

Defines memory contexts with isolation boundaries.
SECURITY CRITICAL: Trading data MUST NOT leak to other contexts.

Context Hierarchy:
    SYSTEM - Core system state, read-only for most
    TRADING - Trading-related data, strictly isolated
    PERSONAL - User personal information, protected
    PUBLIC - General conversation, shared

Each context has:
    - Read permissions (who can read)
    - Write permissions (who can write)
    - TTL defaults
    - Audit requirements
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import timedelta
from typing import FrozenSet, Set


class MemoryContext(Enum):
    """
    Memory context identifiers.

    Each context represents an isolation boundary.
    Data in one context cannot be accessed from another
    without explicit permission.
    """
    # System-level state (plugins, config, health)
    SYSTEM = "system"

    # Trading-related data (positions, strategies, keys)
    # CRITICAL: Must be completely isolated
    TRADING = "trading"

    # Personal user information (preferences, notes)
    PERSONAL = "personal"

    # General conversation and public data
    PUBLIC = "public"

    # Temporary scratch space (auto-expires quickly)
    SCRATCH = "scratch"


@dataclass(frozen=True)
class ContextPermissions:
    """
    Permission set for a memory context.

    Defines which contexts can read from and write to this context.
    """
    # Contexts that can read from this context
    readable_by: FrozenSet[MemoryContext]

    # Contexts that can write to this context
    writable_by: FrozenSet[MemoryContext]

    # Whether access to this context requires audit logging
    audit_required: bool = False

    # Default TTL for entries in this context
    default_ttl: timedelta = field(default_factory=lambda: timedelta(hours=24))

    # Maximum TTL allowed
    max_ttl: timedelta = field(default_factory=lambda: timedelta(days=30))


# =============================================================================
# Context Permission Definitions
# SECURITY CRITICAL: These define the isolation boundaries
# =============================================================================

CONTEXT_PERMISSIONS = {
    MemoryContext.SYSTEM: ContextPermissions(
        # System can be read by all but only written by system
        readable_by=frozenset({
            MemoryContext.SYSTEM,
            MemoryContext.TRADING,
            MemoryContext.PERSONAL,
            MemoryContext.PUBLIC,
        }),
        writable_by=frozenset({MemoryContext.SYSTEM}),
        audit_required=True,
        default_ttl=timedelta(days=7),
        max_ttl=timedelta(days=365),
    ),

    MemoryContext.TRADING: ContextPermissions(
        # CRITICAL: Trading is completely isolated
        # Can ONLY be read and written by trading context
        readable_by=frozenset({MemoryContext.TRADING}),
        writable_by=frozenset({MemoryContext.TRADING}),
        audit_required=True,  # All trading access must be logged
        default_ttl=timedelta(hours=1),  # Short TTL for security
        max_ttl=timedelta(days=1),  # Max 24 hours
    ),

    MemoryContext.PERSONAL: ContextPermissions(
        # Personal data is readable by personal and system
        # Writable only by personal
        readable_by=frozenset({MemoryContext.PERSONAL, MemoryContext.SYSTEM}),
        writable_by=frozenset({MemoryContext.PERSONAL}),
        audit_required=True,
        default_ttl=timedelta(days=30),
        max_ttl=timedelta(days=365),
    ),

    MemoryContext.PUBLIC: ContextPermissions(
        # Public is readable and writable by all contexts
        readable_by=frozenset({
            MemoryContext.SYSTEM,
            MemoryContext.TRADING,
            MemoryContext.PERSONAL,
            MemoryContext.PUBLIC,
            MemoryContext.SCRATCH,
        }),
        writable_by=frozenset({
            MemoryContext.SYSTEM,
            MemoryContext.TRADING,
            MemoryContext.PERSONAL,
            MemoryContext.PUBLIC,
            MemoryContext.SCRATCH,
        }),
        audit_required=False,
        default_ttl=timedelta(hours=24),
        max_ttl=timedelta(days=30),
    ),

    MemoryContext.SCRATCH: ContextPermissions(
        # Scratch is temporary, readable/writable by all
        readable_by=frozenset({
            MemoryContext.SYSTEM,
            MemoryContext.TRADING,
            MemoryContext.PERSONAL,
            MemoryContext.PUBLIC,
            MemoryContext.SCRATCH,
        }),
        writable_by=frozenset({
            MemoryContext.SYSTEM,
            MemoryContext.TRADING,
            MemoryContext.PERSONAL,
            MemoryContext.PUBLIC,
            MemoryContext.SCRATCH,
        }),
        audit_required=False,
        default_ttl=timedelta(minutes=30),
        max_ttl=timedelta(hours=4),
    ),
}


def can_read(
    from_context: MemoryContext,
    target_context: MemoryContext,
) -> bool:
    """
    Check if from_context can read from target_context.

    Args:
        from_context: The context requesting read access
        target_context: The context being read from

    Returns:
        True if read is allowed
    """
    permissions = CONTEXT_PERMISSIONS.get(target_context)
    if permissions is None:
        return False
    return from_context in permissions.readable_by


def can_write(
    from_context: MemoryContext,
    target_context: MemoryContext,
) -> bool:
    """
    Check if from_context can write to target_context.

    Args:
        from_context: The context requesting write access
        target_context: The context being written to

    Returns:
        True if write is allowed
    """
    permissions = CONTEXT_PERMISSIONS.get(target_context)
    if permissions is None:
        return False
    return from_context in permissions.writable_by


def requires_audit(context: MemoryContext) -> bool:
    """Check if access to a context requires audit logging."""
    permissions = CONTEXT_PERMISSIONS.get(context)
    return permissions.audit_required if permissions else True


def get_default_ttl(context: MemoryContext) -> timedelta:
    """Get the default TTL for a context."""
    permissions = CONTEXT_PERMISSIONS.get(context)
    return permissions.default_ttl if permissions else timedelta(hours=1)


def get_max_ttl(context: MemoryContext) -> timedelta:
    """Get the maximum TTL for a context."""
    permissions = CONTEXT_PERMISSIONS.get(context)
    return permissions.max_ttl if permissions else timedelta(days=1)
