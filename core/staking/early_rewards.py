"""
Early Holder Rewards Program.

Incentivizes early KR8TIV token stakers with bonus rewards:
- First 1000 stakers get bonus multiplier
- Early staker tiers based on stake timing
- Snapshot-based verification
- One-time bonus claim per wallet
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("jarvis.staking.early_rewards")


# =============================================================================
# Configuration
# =============================================================================


class EarlyHolderTier(Enum):
    """Early holder tier based on staking order."""
    DIAMOND = "diamond"     # First 100 stakers: 3x bonus
    GOLD = "gold"           # Stakers 101-500: 2x bonus
    SILVER = "silver"       # Stakers 501-1000: 1.5x bonus
    NONE = "none"           # After first 1000: no bonus


@dataclass
class EarlyRewardsConfig:
    """Configuration for early holder rewards."""

    # Program settings
    program_start: datetime = field(
        default_factory=lambda: datetime(2026, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
    )
    program_end: datetime = field(
        default_factory=lambda: datetime(2026, 4, 15, 0, 0, 0, tzinfo=timezone.utc)
    )

    # Tier thresholds
    diamond_limit: int = 100
    gold_limit: int = 500
    silver_limit: int = 1000

    # Bonus multipliers
    diamond_multiplier: float = 3.0
    gold_multiplier: float = 2.0
    silver_multiplier: float = 1.5

    # Minimum stake for eligibility
    min_stake_tokens: int = 1000  # Minimum tokens to qualify

    # Bonus pool
    bonus_pool_sol: float = 10.0  # Total SOL allocated for early rewards


@dataclass
class EarlyHolder:
    """Record of an early holder."""

    wallet: str
    tier: EarlyHolderTier
    position: int  # Order number (1-1000)
    stake_amount: int
    stake_time: datetime
    multiplier: float
    bonus_claimed: bool = False
    bonus_amount: float = 0.0
    claim_signature: Optional[str] = None
    claim_time: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "wallet": self.wallet,
            "tier": self.tier.value,
            "position": self.position,
            "stake_amount": self.stake_amount,
            "stake_time": self.stake_time.isoformat(),
            "multiplier": self.multiplier,
            "bonus_claimed": self.bonus_claimed,
            "bonus_amount": self.bonus_amount,
            "claim_signature": self.claim_signature,
            "claim_time": self.claim_time.isoformat() if self.claim_time else None,
        }


# =============================================================================
# Early Rewards Service
# =============================================================================


class EarlyRewardsService:
    """
    Manages early holder rewards program.

    Features:
    - Track first 1000 stakers
    - Assign tiers based on position
    - Calculate and distribute bonuses
    - One-time claim per wallet
    """

    LAMPORTS_PER_SOL = 1_000_000_000

    def __init__(
        self,
        config: EarlyRewardsConfig = None,
        staking_client: Any = None,
    ):
        self.config = config or EarlyRewardsConfig()
        self._staking = staking_client

        # Early holders registry
        self._early_holders: Dict[str, EarlyHolder] = {}
        self._holder_positions: List[str] = []  # Ordered list of wallets

        # Statistics
        self._total_bonus_distributed = 0.0
        self._claims_processed = 0

    # =========================================================================
    # Program Status
    # =========================================================================

    def is_program_active(self) -> bool:
        """Check if early rewards program is active."""
        now = datetime.now(timezone.utc)
        return self.config.program_start <= now <= self.config.program_end

    def get_program_status(self) -> Dict[str, Any]:
        """Get current program status."""
        now = datetime.now(timezone.utc)

        return {
            "active": self.is_program_active(),
            "program_start": self.config.program_start.isoformat(),
            "program_end": self.config.program_end.isoformat(),
            "time_remaining": str(self.config.program_end - now) if self.is_program_active() else None,
            "total_early_holders": len(self._early_holders),
            "spots_remaining": max(0, self.config.silver_limit - len(self._holder_positions)),
            "diamond_spots": max(0, self.config.diamond_limit - len([
                h for h in self._early_holders.values()
                if h.tier == EarlyHolderTier.DIAMOND
            ])),
            "gold_spots": max(0, self.config.gold_limit - self.config.diamond_limit - len([
                h for h in self._early_holders.values()
                if h.tier == EarlyHolderTier.GOLD
            ])),
            "silver_spots": max(0, self.config.silver_limit - self.config.gold_limit - len([
                h for h in self._early_holders.values()
                if h.tier == EarlyHolderTier.SILVER
            ])),
            "total_bonus_pool_sol": self.config.bonus_pool_sol,
            "bonus_distributed_sol": self._total_bonus_distributed,
        }

    # =========================================================================
    # Registration
    # =========================================================================

    def register_early_holder(
        self,
        wallet: str,
        stake_amount: int,
        stake_time: datetime = None,
    ) -> Optional[EarlyHolder]:
        """
        Register a new early holder.

        Args:
            wallet: Wallet address
            stake_amount: Amount staked in tokens
            stake_time: Time of stake

        Returns:
            EarlyHolder record if eligible
        """
        # Check if program is active
        if not self.is_program_active():
            logger.info(f"Early rewards program not active, skipping {wallet[:16]}...")
            return None

        # Check if already registered
        if wallet in self._early_holders:
            logger.debug(f"Wallet {wallet[:16]}... already registered")
            return self._early_holders[wallet]

        # Check minimum stake
        if stake_amount < self.config.min_stake_tokens:
            logger.debug(f"Stake {stake_amount} below minimum {self.config.min_stake_tokens}")
            return None

        # Check if spots available
        position = len(self._holder_positions) + 1
        if position > self.config.silver_limit:
            logger.info(f"No early holder spots remaining (position would be {position})")
            return None

        # Determine tier
        tier = self._get_tier_for_position(position)
        multiplier = self._get_multiplier_for_tier(tier)

        # Create holder record
        holder = EarlyHolder(
            wallet=wallet,
            tier=tier,
            position=position,
            stake_amount=stake_amount,
            stake_time=stake_time or datetime.now(timezone.utc),
            multiplier=multiplier,
        )

        # Register
        self._early_holders[wallet] = holder
        self._holder_positions.append(wallet)

        logger.info(
            f"Registered early holder #{position} ({tier.value}): "
            f"{wallet[:16]}... with {stake_amount} tokens"
        )

        return holder

    def _get_tier_for_position(self, position: int) -> EarlyHolderTier:
        """Get tier based on position in line."""
        if position <= self.config.diamond_limit:
            return EarlyHolderTier.DIAMOND
        elif position <= self.config.gold_limit:
            return EarlyHolderTier.GOLD
        elif position <= self.config.silver_limit:
            return EarlyHolderTier.SILVER
        return EarlyHolderTier.NONE

    def _get_multiplier_for_tier(self, tier: EarlyHolderTier) -> float:
        """Get multiplier for tier."""
        multipliers = {
            EarlyHolderTier.DIAMOND: self.config.diamond_multiplier,
            EarlyHolderTier.GOLD: self.config.gold_multiplier,
            EarlyHolderTier.SILVER: self.config.silver_multiplier,
            EarlyHolderTier.NONE: 1.0,
        }
        return multipliers.get(tier, 1.0)

    # =========================================================================
    # Bonus Calculation & Claims
    # =========================================================================

    def calculate_bonus(self, wallet: str) -> Dict[str, Any]:
        """
        Calculate bonus for a wallet.

        Bonus = (stake_amount / total_tier_stakes) * tier_share_of_pool * multiplier
        """
        holder = self._early_holders.get(wallet)
        if not holder:
            return {"eligible": False, "reason": "Not an early holder"}

        if holder.bonus_claimed:
            return {
                "eligible": False,
                "reason": "Bonus already claimed",
                "claimed_amount": holder.bonus_amount,
            }

        # Calculate tier's share of bonus pool
        tier_shares = {
            EarlyHolderTier.DIAMOND: 0.5,   # 50% of pool
            EarlyHolderTier.GOLD: 0.35,      # 35% of pool
            EarlyHolderTier.SILVER: 0.15,    # 15% of pool
        }

        tier_share = tier_shares.get(holder.tier, 0)
        tier_pool = self.config.bonus_pool_sol * tier_share

        # Get all holders in same tier
        tier_holders = [
            h for h in self._early_holders.values()
            if h.tier == holder.tier
        ]
        total_tier_stakes = sum(h.stake_amount for h in tier_holders)

        if total_tier_stakes == 0:
            return {"eligible": False, "reason": "No stakes in tier"}

        # Calculate proportional bonus
        stake_proportion = holder.stake_amount / total_tier_stakes
        base_bonus = tier_pool * stake_proportion
        final_bonus = base_bonus * holder.multiplier

        return {
            "eligible": True,
            "wallet": wallet,
            "tier": holder.tier.value,
            "position": holder.position,
            "stake_amount": holder.stake_amount,
            "multiplier": holder.multiplier,
            "tier_pool_sol": tier_pool,
            "stake_proportion": stake_proportion,
            "base_bonus_sol": base_bonus,
            "final_bonus_sol": final_bonus,
            "final_bonus_lamports": int(final_bonus * self.LAMPORTS_PER_SOL),
        }

    async def claim_bonus(self, wallet: str) -> Dict[str, Any]:
        """
        Claim early holder bonus.

        Args:
            wallet: Wallet address to receive bonus

        Returns:
            Claim result with signature
        """
        holder = self._early_holders.get(wallet)
        if not holder:
            return {"success": False, "error": "Not an early holder"}

        if holder.bonus_claimed:
            return {
                "success": False,
                "error": "Bonus already claimed",
                "claimed_at": holder.claim_time.isoformat() if holder.claim_time else None,
            }

        # Calculate bonus
        bonus_info = self.calculate_bonus(wallet)
        if not bonus_info.get("eligible"):
            return {"success": False, "error": bonus_info.get("reason")}

        bonus_lamports = bonus_info["final_bonus_lamports"]
        bonus_sol = bonus_info["final_bonus_sol"]

        # Transfer bonus (mock for now)
        try:
            import hashlib
            signature = hashlib.sha256(
                f"early_bonus_{wallet}_{datetime.now()}".encode()
            ).hexdigest()[:88]

            # Update holder record
            holder.bonus_claimed = True
            holder.bonus_amount = bonus_sol
            holder.claim_signature = signature
            holder.claim_time = datetime.now(timezone.utc)

            # Update statistics
            self._total_bonus_distributed += bonus_sol
            self._claims_processed += 1

            logger.info(
                f"Early holder bonus claimed: {wallet[:16]}... "
                f"received {bonus_sol:.6f} SOL"
            )

            return {
                "success": True,
                "wallet": wallet,
                "tier": holder.tier.value,
                "bonus_sol": bonus_sol,
                "bonus_lamports": bonus_lamports,
                "signature": signature,
            }

        except Exception as e:
            logger.error(f"Bonus claim failed for {wallet[:16]}...: {e}")
            return {"success": False, "error": str(e)}

    # =========================================================================
    # Queries
    # =========================================================================

    def get_holder(self, wallet: str) -> Optional[Dict[str, Any]]:
        """Get early holder info for a wallet."""
        holder = self._early_holders.get(wallet)
        if holder:
            info = holder.to_dict()
            info["bonus_info"] = self.calculate_bonus(wallet)
            return info
        return None

    def get_leaderboard(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get early holder leaderboard."""
        sorted_holders = sorted(
            self._early_holders.values(),
            key=lambda h: h.position,
        )

        return [h.to_dict() for h in sorted_holders[:limit]]

    def get_tier_stats(self) -> Dict[str, Any]:
        """Get statistics per tier."""
        stats = {}
        for tier in [EarlyHolderTier.DIAMOND, EarlyHolderTier.GOLD, EarlyHolderTier.SILVER]:
            holders = [h for h in self._early_holders.values() if h.tier == tier]
            stats[tier.value] = {
                "count": len(holders),
                "total_staked": sum(h.stake_amount for h in holders),
                "claims_made": sum(1 for h in holders if h.bonus_claimed),
                "bonus_distributed": sum(h.bonus_amount for h in holders if h.bonus_claimed),
            }
        return stats


# =============================================================================
# Singleton
# =============================================================================

_service: Optional[EarlyRewardsService] = None


def get_early_rewards_service() -> EarlyRewardsService:
    """Get singleton early rewards service."""
    global _service
    if _service is None:
        _service = EarlyRewardsService()
    return _service


# =============================================================================
# FastAPI Routes
# =============================================================================


def create_early_rewards_router():
    """Create FastAPI router for early rewards endpoints."""
    try:
        from fastapi import APIRouter, HTTPException
        from pydantic import BaseModel, Field
    except ImportError:
        return None

    router = APIRouter(prefix="/api/staking/early-rewards", tags=["Early Rewards"])
    service = get_early_rewards_service()

    class RegisterRequest(BaseModel):
        wallet: str = Field(..., description="Wallet address")
        stake_amount: int = Field(..., description="Amount staked")

    @router.get("/status")
    async def get_status():
        """Get early rewards program status."""
        return service.get_program_status()

    @router.get("/holder/{wallet}")
    async def get_holder(wallet: str):
        """Get early holder info for a wallet."""
        info = service.get_holder(wallet)
        if not info:
            raise HTTPException(status_code=404, detail="Not an early holder")
        return info

    @router.get("/leaderboard")
    async def get_leaderboard(limit: int = 50):
        """Get early holder leaderboard."""
        return {"leaderboard": service.get_leaderboard(limit)}

    @router.get("/tier-stats")
    async def get_tier_stats():
        """Get statistics per tier."""
        return service.get_tier_stats()

    @router.post("/calculate-bonus")
    async def calculate_bonus(wallet: str):
        """Calculate bonus for a wallet."""
        return service.calculate_bonus(wallet)

    @router.post("/claim/{wallet}")
    async def claim_bonus(wallet: str):
        """Claim early holder bonus."""
        result = await service.claim_bonus(wallet)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result

    return router
