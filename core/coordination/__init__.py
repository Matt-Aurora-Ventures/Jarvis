"""
Coordination module for multi-bot synchronization.

Provides:
- Token conflict coordination (prevents duplicate trades)
- Distributed locking mechanisms
- Cross-bot communication
"""

from core.coordination.token_coordinator import (
    TokenCoordinator,
    TokenClaim,
    TokenClaimContext,
    TokenConflictError,
    ConflictEvent,
    get_token_coordinator,
    claim_token,
)

__all__ = [
    "TokenCoordinator",
    "TokenClaim",
    "TokenClaimContext",
    "TokenConflictError",
    "ConflictEvent",
    "get_token_coordinator",
    "claim_token",
]
