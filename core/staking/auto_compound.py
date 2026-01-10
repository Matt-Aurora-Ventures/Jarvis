"""
Auto-Compound Feature for Staking.

Allows stakers to automatically reinvest their rewards:
1. User opts in to auto-compound
2. When rewards exceed threshold, automatically:
   - Claim rewards
   - Swap SOL to KR8TIV via Bags
   - Stake the new tokens
3. Track compound events for analytics
4. Calculate compound APY vs simple APY
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("jarvis.staking.auto_compound")


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class AutoCompoundConfig:
    """Configuration for auto-compound feature."""
    # Minimum SOL to trigger compound (default 0.01 SOL)
    min_compound_sol: float = 0.01

    # Check interval (seconds)
    check_interval: int = 3600  # 1 hour

    # Slippage for swap (basis points)
    swap_slippage_bps: int = 100  # 1%

    # Token mints
    sol_mint: str = "So11111111111111111111111111111111111111112"
    kr8tiv_mint: str = os.getenv("KR8TIV_MINT", "")


@dataclass
class CompoundEvent:
    """Record of an auto-compound execution."""
    id: str
    user_id: str
    timestamp: datetime
    rewards_claimed_sol: float
    tokens_received: int
    tokens_staked: int
    claim_signature: str
    swap_signature: str
    stake_signature: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat(),
            "rewards_claimed_sol": self.rewards_claimed_sol,
            "tokens_received": self.tokens_received,
            "tokens_staked": self.tokens_staked,
            "claim_signature": self.claim_signature,
            "swap_signature": self.swap_signature,
            "stake_signature": self.stake_signature,
        }


@dataclass
class CompoundSettings:
    """User's auto-compound settings."""
    enabled: bool = False
    min_compound_sol: float = 0.01
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_compound: Optional[datetime] = None
    total_compounded_sol: float = 0.0
    total_compounded_tokens: int = 0
    compound_count: int = 0


# =============================================================================
# APY Calculator
# =============================================================================


class APYCalculator:
    """Calculate and compare simple vs compound APY."""

    LAMPORTS_PER_SOL = 1_000_000_000
    SECONDS_PER_YEAR = 365.25 * 24 * 3600

    @staticmethod
    def simple_apy(
        base_rate: float,
        multiplier: float = 1.0,
    ) -> float:
        """
        Calculate simple APY (no compounding).

        Args:
            base_rate: Base reward rate per second per staked token
            multiplier: Time-weighted multiplier (1.0 - 2.5)

        Returns:
            APY as decimal (e.g., 0.15 = 15%)
        """
        return base_rate * APYCalculator.SECONDS_PER_YEAR * multiplier

    @staticmethod
    def compound_apy(
        base_rate: float,
        multiplier: float = 1.0,
        compounds_per_year: int = 365,
    ) -> float:
        """
        Calculate compound APY.

        Args:
            base_rate: Base reward rate per second per staked token
            multiplier: Time-weighted multiplier
            compounds_per_year: Number of compounding events per year

        Returns:
            APY as decimal
        """
        simple_rate = base_rate * APYCalculator.SECONDS_PER_YEAR * multiplier

        # Compound interest formula: (1 + r/n)^n - 1
        rate_per_compound = simple_rate / compounds_per_year
        compound_apy = (1 + rate_per_compound) ** compounds_per_year - 1

        return compound_apy

    @staticmethod
    def compare(
        base_rate: float,
        multiplier: float = 1.0,
        compounds_per_year: int = 365,
    ) -> Dict[str, float]:
        """Compare simple vs compound APY."""
        simple = APYCalculator.simple_apy(base_rate, multiplier)
        compound = APYCalculator.compound_apy(base_rate, multiplier, compounds_per_year)

        return {
            "simple_apy": simple,
            "compound_apy": compound,
            "additional_yield": compound - simple,
            "yield_boost_pct": ((compound / simple) - 1) * 100 if simple > 0 else 0,
        }


# =============================================================================
# Auto-Compound Service
# =============================================================================


class AutoCompoundService:
    """
    Service for managing auto-compound functionality.

    Features:
    - User opt-in/out
    - Automatic compounding when threshold met
    - Event tracking and analytics
    """

    LAMPORTS_PER_SOL = 1_000_000_000

    def __init__(
        self,
        config: AutoCompoundConfig = None,
        trade_executor: Callable = None,
        staking_client: Any = None,
    ):
        self.config = config or AutoCompoundConfig()
        self._trade_executor = trade_executor
        self._staking = staking_client

        # User settings
        self._user_settings: Dict[str, CompoundSettings] = {}

        # Event history
        self._events: List[CompoundEvent] = []

        # Running state
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None

    # =========================================================================
    # User Settings
    # =========================================================================

    def enable_auto_compound(
        self,
        user_id: str,
        min_compound_sol: float = None,
    ) -> CompoundSettings:
        """
        Enable auto-compound for a user.

        Args:
            user_id: User's wallet address
            min_compound_sol: Minimum SOL to trigger compound

        Returns:
            User's compound settings
        """
        settings = self._user_settings.get(user_id, CompoundSettings())
        settings.enabled = True
        settings.min_compound_sol = min_compound_sol or self.config.min_compound_sol
        settings.created_at = datetime.now(timezone.utc)

        self._user_settings[user_id] = settings

        logger.info(f"Auto-compound enabled for {user_id[:16]}... (min: {settings.min_compound_sol} SOL)")

        return settings

    def disable_auto_compound(self, user_id: str) -> bool:
        """
        Disable auto-compound for a user.

        Args:
            user_id: User's wallet address

        Returns:
            True if disabled successfully
        """
        if user_id in self._user_settings:
            self._user_settings[user_id].enabled = False
            logger.info(f"Auto-compound disabled for {user_id[:16]}...")
            return True
        return False

    def get_settings(self, user_id: str) -> Optional[CompoundSettings]:
        """Get user's auto-compound settings."""
        return self._user_settings.get(user_id)

    def is_enabled(self, user_id: str) -> bool:
        """Check if auto-compound is enabled for a user."""
        settings = self._user_settings.get(user_id)
        return settings.enabled if settings else False

    def get_enabled_users(self) -> List[str]:
        """Get list of users with auto-compound enabled."""
        return [
            user_id for user_id, settings in self._user_settings.items()
            if settings.enabled
        ]

    # =========================================================================
    # Compound Execution
    # =========================================================================

    async def check_and_compound(self, user_id: str) -> Optional[CompoundEvent]:
        """
        Check if user should compound and execute if so.

        Args:
            user_id: User's wallet address

        Returns:
            CompoundEvent if compound was executed
        """
        settings = self._user_settings.get(user_id)
        if not settings or not settings.enabled:
            return None

        # Get pending rewards
        pending_rewards = await self._get_pending_rewards(user_id)
        pending_sol = pending_rewards / self.LAMPORTS_PER_SOL

        if pending_sol < settings.min_compound_sol:
            logger.debug(
                f"User {user_id[:16]}: pending {pending_sol:.6f} SOL < "
                f"min {settings.min_compound_sol} SOL, skipping"
            )
            return None

        logger.info(f"Compounding for {user_id[:16]}: {pending_sol:.6f} SOL")

        try:
            # 1. Claim rewards
            claim_sig = await self._claim_rewards(user_id)

            # 2. Swap SOL to KR8TIV
            swap_sig, tokens_received = await self._swap_to_tokens(pending_rewards)

            # 3. Stake tokens
            stake_sig = await self._stake_tokens(user_id, tokens_received)

            # Record event
            import uuid
            event = CompoundEvent(
                id=f"cmp_{uuid.uuid4().hex[:12]}",
                user_id=user_id,
                timestamp=datetime.now(timezone.utc),
                rewards_claimed_sol=pending_sol,
                tokens_received=tokens_received,
                tokens_staked=tokens_received,
                claim_signature=claim_sig,
                swap_signature=swap_sig,
                stake_signature=stake_sig,
            )

            self._events.append(event)

            # Update settings
            settings.last_compound = event.timestamp
            settings.total_compounded_sol += pending_sol
            settings.total_compounded_tokens += tokens_received
            settings.compound_count += 1

            logger.info(
                f"Compound complete for {user_id[:16]}: "
                f"{pending_sol:.6f} SOL -> {tokens_received} tokens"
            )

            return event

        except Exception as e:
            logger.error(f"Compound failed for {user_id[:16]}: {e}")
            raise

    async def _get_pending_rewards(self, user_id: str) -> int:
        """Get pending rewards in lamports."""
        if self._staking:
            stake = await self._staking.get_user_stake(user_id)
            return stake.get("pending_rewards", 0)

        # Mock for development
        return int(0.02 * self.LAMPORTS_PER_SOL)

    async def _claim_rewards(self, user_id: str) -> str:
        """Claim pending rewards."""
        if self._staking:
            result = await self._staking.claim_rewards(user_id)
            return result.get("signature", "")

        # Mock signature
        import hashlib
        return hashlib.sha256(f"claim_{user_id}_{datetime.now()}".encode()).hexdigest()[:88]

    async def _swap_to_tokens(self, amount_lamports: int) -> tuple[str, int]:
        """Swap SOL to KR8TIV tokens."""
        if self._trade_executor:
            signature, tokens = await self._trade_executor(
                input_mint=self.config.sol_mint,
                output_mint=self.config.kr8tiv_mint,
                amount=amount_lamports,
                slippage=self.config.swap_slippage_bps / 10000,
            )
            return signature, tokens

        # Mock for development
        import hashlib
        mock_sig = hashlib.sha256(f"swap_{amount_lamports}_{datetime.now()}".encode()).hexdigest()[:88]
        mock_tokens = int(amount_lamports * 100)  # Assume 100 tokens per SOL
        return mock_sig, mock_tokens

    async def _stake_tokens(self, user_id: str, amount: int) -> str:
        """Stake tokens."""
        if self._staking:
            result = await self._staking.stake(user_id, amount)
            return result.get("signature", "")

        # Mock signature
        import hashlib
        return hashlib.sha256(f"stake_{user_id}_{amount}_{datetime.now()}".encode()).hexdigest()[:88]

    # =========================================================================
    # Monitoring Service
    # =========================================================================

    async def start(self):
        """Start the auto-compound monitoring service."""
        if self._running:
            return

        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Auto-compound service started")

    async def stop(self):
        """Stop the auto-compound monitoring service."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Auto-compound service stopped")

    async def _monitor_loop(self):
        """Background loop to check and execute compounds."""
        while self._running:
            try:
                enabled_users = self.get_enabled_users()

                for user_id in enabled_users:
                    try:
                        await self.check_and_compound(user_id)
                    except Exception as e:
                        logger.error(f"Error compounding for {user_id[:16]}: {e}")

                    # Small delay between users
                    await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Monitor loop error: {e}")

            await asyncio.sleep(self.config.check_interval)

    # =========================================================================
    # Analytics
    # =========================================================================

    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get compound statistics for a user."""
        settings = self._user_settings.get(user_id)
        if not settings:
            return {"enabled": False}

        user_events = [e for e in self._events if e.user_id == user_id]

        return {
            "enabled": settings.enabled,
            "min_compound_sol": settings.min_compound_sol,
            "total_compounded_sol": settings.total_compounded_sol,
            "total_compounded_tokens": settings.total_compounded_tokens,
            "compound_count": settings.compound_count,
            "last_compound": settings.last_compound.isoformat() if settings.last_compound else None,
            "recent_events": [e.to_dict() for e in user_events[-5:]],
        }

    def get_global_stats(self) -> Dict[str, Any]:
        """Get global auto-compound statistics."""
        enabled_count = len(self.get_enabled_users())
        total_events = len(self._events)
        total_compounded = sum(e.rewards_claimed_sol for e in self._events)

        return {
            "enabled_users": enabled_count,
            "total_compounds": total_events,
            "total_sol_compounded": total_compounded,
            "avg_compound_sol": total_compounded / max(1, total_events),
        }

    def get_compound_history(
        self,
        user_id: str = None,
        limit: int = 50,
    ) -> List[Dict]:
        """Get compound event history."""
        events = self._events
        if user_id:
            events = [e for e in events if e.user_id == user_id]

        return [e.to_dict() for e in events[-limit:]]


# =============================================================================
# Singleton
# =============================================================================

_service: Optional[AutoCompoundService] = None


def get_auto_compound_service() -> AutoCompoundService:
    """Get singleton auto-compound service."""
    global _service
    if _service is None:
        _service = AutoCompoundService()
    return _service


# =============================================================================
# FastAPI Routes
# =============================================================================


def create_auto_compound_router():
    """Create FastAPI router for auto-compound endpoints."""
    try:
        from fastapi import APIRouter, HTTPException
        from pydantic import BaseModel, Field
    except ImportError:
        return None

    router = APIRouter(prefix="/api/staking/compound", tags=["Auto-Compound"])
    service = get_auto_compound_service()
    calculator = APYCalculator()

    class EnableRequest(BaseModel):
        wallet: str = Field(..., description="Wallet address")
        min_sol: float = Field(default=0.01, description="Minimum SOL to trigger compound")

    class DisableRequest(BaseModel):
        wallet: str = Field(..., description="Wallet address")

    @router.post("/enable")
    async def enable_compound(request: EnableRequest):
        """Enable auto-compound for a wallet."""
        settings = service.enable_auto_compound(request.wallet, request.min_sol)
        return {
            "success": True,
            "enabled": settings.enabled,
            "min_compound_sol": settings.min_compound_sol,
        }

    @router.post("/disable")
    async def disable_compound(request: DisableRequest):
        """Disable auto-compound for a wallet."""
        success = service.disable_auto_compound(request.wallet)
        return {"success": success}

    @router.get("/settings/{wallet}")
    async def get_settings(wallet: str):
        """Get auto-compound settings for a wallet."""
        settings = service.get_settings(wallet)
        if not settings:
            return {"enabled": False}

        return {
            "enabled": settings.enabled,
            "min_compound_sol": settings.min_compound_sol,
            "total_compounded_sol": settings.total_compounded_sol,
            "compound_count": settings.compound_count,
        }

    @router.get("/stats/{wallet}")
    async def get_user_stats(wallet: str):
        """Get compound statistics for a wallet."""
        return service.get_user_stats(wallet)

    @router.get("/history/{wallet}")
    async def get_history(wallet: str, limit: int = 50):
        """Get compound history for a wallet."""
        return {"events": service.get_compound_history(wallet, limit)}

    @router.get("/apy-comparison")
    async def compare_apy(base_rate: float = 0.0001, multiplier: float = 1.0):
        """Compare simple vs compound APY."""
        return calculator.compare(base_rate, multiplier)

    @router.post("/trigger/{wallet}")
    async def trigger_compound(wallet: str):
        """Manually trigger a compound check."""
        event = await service.check_and_compound(wallet)
        if event:
            return {"success": True, "event": event.to_dict()}
        return {"success": False, "message": "No compound needed"}

    @router.get("/global-stats")
    async def get_global_stats():
        """Get global auto-compound statistics."""
        return service.get_global_stats()

    return router
