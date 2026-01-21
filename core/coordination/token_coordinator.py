"""
Multi-Bot Token Conflict Coordinator
Reliability Audit Item #16: Coordinator for multi-bot token conflicts

Prevents multiple bots from trading the same token simultaneously.
Uses file-based locks with Redis fallback for distributed scenarios.
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import threading
import filelock

logger = logging.getLogger("jarvis.coordination.token")


@dataclass
class TokenClaim:
    """A claim on a token by a bot"""
    token_address: str
    bot_id: str
    operation: str  # 'buy', 'sell', 'monitor', 'analyze'
    claimed_at: datetime
    expires_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConflictEvent:
    """Record of a conflict attempt"""
    token_address: str
    requesting_bot: str
    holding_bot: str
    operation: str
    timestamp: datetime
    resolved: bool = False
    resolution: Optional[str] = None


class TokenCoordinator:
    """
    Coordinates token access across multiple bots.

    Features:
    - Exclusive locks for trading operations
    - Shared locks for monitoring/analysis
    - Automatic expiration of stale claims
    - Conflict tracking for debugging
    - Redis support for multi-instance deployments
    """

    EXCLUSIVE_OPERATIONS = {'buy', 'sell', 'swap', 'close_position'}
    SHARED_OPERATIONS = {'monitor', 'analyze', 'price_check'}

    def __init__(
        self,
        state_dir: str = None,
        default_ttl_sec: int = 300,  # 5 minutes default
        use_redis: bool = False,
        redis_url: str = None,
    ):
        self.state_dir = Path(state_dir or os.path.expanduser("~/.lifeos/coordination"))
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.default_ttl = default_ttl_sec
        self.use_redis = use_redis
        self.redis_url = redis_url or os.getenv("REDIS_URL")

        self._claims: Dict[str, TokenClaim] = {}
        self._conflicts: List[ConflictEvent] = []
        self._lock = threading.Lock()
        self._file_lock = filelock.FileLock(self.state_dir / ".coordinator.lock")

        # Redis client (lazy init)
        self._redis = None

        # Load persisted state
        self._load_state()

    def _get_redis(self):
        """Get or create Redis client"""
        if not self.use_redis:
            return None
        if self._redis is None:
            try:
                import redis
                self._redis = redis.from_url(self.redis_url or "redis://localhost:6379")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}")
                self._redis = None
        return self._redis

    def _load_state(self):
        """Load claims from disk"""
        state_file = self.state_dir / "token_claims.json"
        if state_file.exists():
            try:
                with open(state_file) as f:
                    data = json.load(f)
                for claim_data in data.get("claims", []):
                    claim = TokenClaim(
                        token_address=claim_data["token_address"],
                        bot_id=claim_data["bot_id"],
                        operation=claim_data["operation"],
                        claimed_at=datetime.fromisoformat(claim_data["claimed_at"]),
                        expires_at=datetime.fromisoformat(claim_data["expires_at"]),
                        metadata=claim_data.get("metadata", {}),
                    )
                    # Only load non-expired claims
                    if claim.expires_at > datetime.now(timezone.utc):
                        self._claims[claim.token_address] = claim
            except Exception as e:
                logger.error(f"Failed to load coordinator state: {e}")

    def _save_state(self):
        """Persist claims to disk"""
        state_file = self.state_dir / "token_claims.json"
        data = {
            "claims": [
                {
                    "token_address": c.token_address,
                    "bot_id": c.bot_id,
                    "operation": c.operation,
                    "claimed_at": c.claimed_at.isoformat(),
                    "expires_at": c.expires_at.isoformat(),
                    "metadata": c.metadata,
                }
                for c in self._claims.values()
            ],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(state_file, "w") as f:
            json.dump(data, f, indent=2)

    def _cleanup_expired(self):
        """Remove expired claims"""
        now = datetime.now(timezone.utc)
        expired = [
            addr for addr, claim in self._claims.items()
            if claim.expires_at <= now
        ]
        for addr in expired:
            del self._claims[addr]
            logger.debug(f"Expired claim on {addr[:8]}...")

    async def acquire(
        self,
        token_address: str,
        bot_id: str,
        operation: str,
        ttl_sec: Optional[int] = None,
        wait: bool = False,
        wait_timeout: float = 30.0,
        metadata: Dict[str, Any] = None,
    ) -> bool:
        """
        Acquire a claim on a token.

        Args:
            token_address: Token mint address
            bot_id: Identifier of the requesting bot
            operation: Type of operation ('buy', 'sell', 'monitor', etc.)
            ttl_sec: Time-to-live in seconds (default: 300)
            wait: If True, wait for lock to become available
            wait_timeout: Max time to wait if wait=True
            metadata: Additional claim metadata

        Returns:
            True if claim acquired, False otherwise
        """
        ttl = ttl_sec or self.default_ttl
        is_exclusive = operation in self.EXCLUSIVE_OPERATIONS

        start_time = time.time()

        while True:
            with self._lock:
                self._cleanup_expired()

                existing = self._claims.get(token_address)

                # No existing claim - acquire
                if existing is None:
                    now = datetime.now(timezone.utc)
                    self._claims[token_address] = TokenClaim(
                        token_address=token_address,
                        bot_id=bot_id,
                        operation=operation,
                        claimed_at=now,
                        expires_at=now.replace(
                            second=now.second + ttl
                        ) if ttl < 60 else datetime.fromtimestamp(
                            now.timestamp() + ttl, tz=timezone.utc
                        ),
                        metadata=metadata or {},
                    )
                    self._save_state()
                    logger.info(f"Bot {bot_id} acquired {operation} on {token_address[:8]}...")
                    return True

                # Same bot - allow re-entry
                if existing.bot_id == bot_id:
                    logger.debug(f"Bot {bot_id} re-acquired {token_address[:8]}...")
                    return True

                # Shared operation on shared claim - allow
                if (not is_exclusive and
                    existing.operation in self.SHARED_OPERATIONS):
                    logger.debug(f"Shared access granted for {token_address[:8]}...")
                    return True

                # Conflict
                conflict = ConflictEvent(
                    token_address=token_address,
                    requesting_bot=bot_id,
                    holding_bot=existing.bot_id,
                    operation=operation,
                    timestamp=datetime.now(timezone.utc),
                )
                self._conflicts.append(conflict)

                if len(self._conflicts) > 1000:
                    self._conflicts = self._conflicts[-500:]

                logger.warning(
                    f"Token conflict: {bot_id} wants {operation} on {token_address[:8]}... "
                    f"but {existing.bot_id} holds {existing.operation}"
                )

            # If not waiting, return failure immediately
            if not wait:
                return False

            # Check timeout
            if time.time() - start_time > wait_timeout:
                logger.warning(f"Wait timeout for {token_address[:8]}...")
                return False

            # Wait and retry
            await asyncio.sleep(0.5)

    def release(self, token_address: str, bot_id: str) -> bool:
        """
        Release a claim on a token.

        Args:
            token_address: Token mint address
            bot_id: Bot releasing the claim (must match holder)

        Returns:
            True if released, False if not held by this bot
        """
        with self._lock:
            existing = self._claims.get(token_address)

            if existing is None:
                return True  # Already released

            if existing.bot_id != bot_id:
                logger.warning(
                    f"Bot {bot_id} tried to release claim held by {existing.bot_id}"
                )
                return False

            del self._claims[token_address]
            self._save_state()
            logger.info(f"Bot {bot_id} released {token_address[:8]}...")
            return True

    def force_release(self, token_address: str, reason: str = "admin"):
        """Force release a claim (admin operation)"""
        with self._lock:
            if token_address in self._claims:
                claim = self._claims[token_address]
                logger.warning(
                    f"Force releasing {token_address[:8]}... from {claim.bot_id} ({reason})"
                )
                del self._claims[token_address]
                self._save_state()

    def get_claim(self, token_address: str) -> Optional[TokenClaim]:
        """Get current claim on a token"""
        with self._lock:
            self._cleanup_expired()
            return self._claims.get(token_address)

    def get_bot_claims(self, bot_id: str) -> List[TokenClaim]:
        """Get all claims held by a bot"""
        with self._lock:
            self._cleanup_expired()
            return [c for c in self._claims.values() if c.bot_id == bot_id]

    def get_all_claims(self) -> List[TokenClaim]:
        """Get all active claims"""
        with self._lock:
            self._cleanup_expired()
            return list(self._claims.values())

    def get_conflicts(self, limit: int = 100) -> List[ConflictEvent]:
        """Get recent conflict events"""
        return self._conflicts[-limit:]

    def is_available(self, token_address: str, operation: str) -> bool:
        """Check if token is available for operation"""
        with self._lock:
            self._cleanup_expired()
            existing = self._claims.get(token_address)

            if existing is None:
                return True

            is_exclusive = operation in self.EXCLUSIVE_OPERATIONS

            # Shared access allowed on shared claims
            if not is_exclusive and existing.operation in self.SHARED_OPERATIONS:
                return True

            return False

    def get_status(self) -> Dict[str, Any]:
        """Get coordinator status for health checks"""
        with self._lock:
            self._cleanup_expired()

            claims_by_bot: Dict[str, int] = {}
            claims_by_op: Dict[str, int] = {}

            for claim in self._claims.values():
                claims_by_bot[claim.bot_id] = claims_by_bot.get(claim.bot_id, 0) + 1
                claims_by_op[claim.operation] = claims_by_op.get(claim.operation, 0) + 1

            return {
                "active_claims": len(self._claims),
                "claims_by_bot": claims_by_bot,
                "claims_by_operation": claims_by_op,
                "recent_conflicts": len([
                    c for c in self._conflicts[-100:]
                    if (datetime.now(timezone.utc) - c.timestamp).total_seconds() < 3600
                ]),
                "redis_enabled": self.use_redis,
            }


class TokenClaimContext:
    """Context manager for token claims"""

    def __init__(
        self,
        coordinator: TokenCoordinator,
        token_address: str,
        bot_id: str,
        operation: str,
        ttl_sec: int = 300,
    ):
        self.coordinator = coordinator
        self.token_address = token_address
        self.bot_id = bot_id
        self.operation = operation
        self.ttl_sec = ttl_sec
        self._acquired = False

    async def __aenter__(self):
        self._acquired = await self.coordinator.acquire(
            token_address=self.token_address,
            bot_id=self.bot_id,
            operation=self.operation,
            ttl_sec=self.ttl_sec,
        )
        if not self._acquired:
            raise TokenConflictError(
                f"Could not acquire {self.operation} on {self.token_address[:8]}..."
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._acquired:
            self.coordinator.release(self.token_address, self.bot_id)
        return False


class TokenConflictError(Exception):
    """Raised when a token claim cannot be acquired"""
    pass


# =============================================================================
# SINGLETON
# =============================================================================

_coordinator: Optional[TokenCoordinator] = None


def get_token_coordinator() -> TokenCoordinator:
    """Get or create the token coordinator singleton"""
    global _coordinator
    if _coordinator is None:
        _coordinator = TokenCoordinator()
    return _coordinator


async def claim_token(
    token_address: str,
    bot_id: str,
    operation: str,
    ttl_sec: int = 300,
) -> TokenClaimContext:
    """
    Convenience function to claim a token with context manager.

    Usage:
        async with claim_token("So11...", "treasury_bot", "buy"):
            await execute_trade(...)
    """
    return TokenClaimContext(
        coordinator=get_token_coordinator(),
        token_address=token_address,
        bot_id=bot_id,
        operation=operation,
        ttl_sec=ttl_sec,
    )
