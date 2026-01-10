"""
Referral System
Prompts #76-78: Referral rewards, conversion optimization, and growth
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import hashlib
import secrets

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# Referral rewards (basis points)
REFERRER_REWARD_BPS = 1000  # 10% of referee's fees
REFEREE_BONUS_BPS = 500     # 5% bonus for using referral

# Tier multipliers for referral rewards
TIER_MULTIPLIERS = {
    "free": 1.0,
    "starter": 1.2,
    "pro": 1.5,
    "enterprise": 2.0,
    "whale": 2.5
}

# Referral tiers based on total referrals
REFERRAL_TIERS = {
    0: {"name": "Bronze", "multiplier": 1.0, "bonus": 0},
    10: {"name": "Silver", "multiplier": 1.1, "bonus": 500},
    50: {"name": "Gold", "multiplier": 1.25, "bonus": 2000},
    100: {"name": "Platinum", "multiplier": 1.5, "bonus": 5000},
    500: {"name": "Diamond", "multiplier": 2.0, "bonus": 25000}
}


# =============================================================================
# MODELS
# =============================================================================

class ReferralStatus(str, Enum):
    PENDING = "pending"      # Code used but not verified
    ACTIVE = "active"        # User is active
    CONVERTED = "converted"  # User completed first trade/stake
    CHURNED = "churned"      # User inactive for 30+ days


@dataclass
class ReferralCode:
    """A referral code"""
    code: str
    owner: str  # Wallet address
    created_at: datetime = field(default_factory=datetime.utcnow)
    is_active: bool = True
    custom_reward_bps: Optional[int] = None
    max_uses: Optional[int] = None
    uses: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Referral:
    """A referral relationship"""
    id: str
    referrer: str  # Wallet of referrer
    referee: str   # Wallet of referred user
    code_used: str
    status: ReferralStatus = ReferralStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    converted_at: Optional[datetime] = None
    total_fees_generated: int = 0  # Total fees from referee
    rewards_paid: int = 0          # Total rewards paid to referrer
    last_activity: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ReferrerStats:
    """Statistics for a referrer"""
    wallet: str
    total_referrals: int = 0
    active_referrals: int = 0
    converted_referrals: int = 0
    total_rewards_earned: int = 0
    pending_rewards: int = 0
    referral_tier: str = "Bronze"
    tier_multiplier: float = 1.0


# =============================================================================
# REFERRAL MANAGER
# =============================================================================

class ReferralManager:
    """Manages referral codes, rewards, and tracking"""

    def __init__(self, db_url: str, token_mint: str):
        self.db_url = db_url
        self.token_mint = token_mint

        self.codes: Dict[str, ReferralCode] = {}
        self.referrals: Dict[str, Referral] = {}
        self.user_codes: Dict[str, str] = {}  # wallet -> code
        self.referrer_stats: Dict[str, ReferrerStats] = {}

    # =========================================================================
    # REFERRAL CODES
    # =========================================================================

    async def create_referral_code(
        self,
        owner: str,
        custom_code: Optional[str] = None
    ) -> ReferralCode:
        """Create a new referral code for a user"""
        # Check if user already has a code
        if owner in self.user_codes:
            return self.codes[self.user_codes[owner]]

        # Generate or validate code
        if custom_code:
            if custom_code in self.codes:
                raise ValueError("Code already exists")
            code = custom_code.upper()
        else:
            code = self._generate_code(owner)

        referral_code = ReferralCode(
            code=code,
            owner=owner
        )

        self.codes[code] = referral_code
        self.user_codes[owner] = code

        logger.info(f"Created referral code {code} for {owner[:8]}...")
        return referral_code

    async def get_referral_code(self, code: str) -> Optional[ReferralCode]:
        """Get a referral code"""
        return self.codes.get(code.upper())

    async def get_user_code(self, wallet: str) -> Optional[ReferralCode]:
        """Get user's referral code"""
        code = self.user_codes.get(wallet)
        if code:
            return self.codes.get(code)
        return None

    async def validate_code(self, code: str) -> bool:
        """Validate a referral code"""
        referral_code = self.codes.get(code.upper())
        if not referral_code:
            return False
        if not referral_code.is_active:
            return False
        if referral_code.max_uses and referral_code.uses >= referral_code.max_uses:
            return False
        return True

    def _generate_code(self, owner: str) -> str:
        """Generate a unique referral code"""
        # Use first 4 chars of wallet + random suffix
        prefix = owner[:4].upper()
        suffix = secrets.token_hex(3).upper()
        return f"{prefix}{suffix}"

    # =========================================================================
    # REFERRAL TRACKING
    # =========================================================================

    async def apply_referral(
        self,
        referee: str,
        code: str
    ) -> Referral:
        """Apply a referral code for a new user"""
        import uuid

        # Validate code
        referral_code = await self.get_referral_code(code)
        if not referral_code:
            raise ValueError("Invalid referral code")

        if not await self.validate_code(code):
            raise ValueError("Referral code is not valid")

        # Can't refer yourself
        if referral_code.owner == referee:
            raise ValueError("Cannot use your own referral code")

        # Check if already referred
        existing = await self.get_referral_by_referee(referee)
        if existing:
            raise ValueError("User already has a referrer")

        referral = Referral(
            id=str(uuid.uuid4()),
            referrer=referral_code.owner,
            referee=referee,
            code_used=code.upper()
        )

        self.referrals[referral.id] = referral
        referral_code.uses += 1

        # Update stats
        await self._update_referrer_stats(referral_code.owner)

        logger.info(f"Applied referral: {referee[:8]}... referred by {referral_code.owner[:8]}...")
        return referral

    async def mark_converted(self, referee: str) -> Optional[Referral]:
        """Mark a referral as converted (first trade/stake)"""
        referral = await self.get_referral_by_referee(referee)
        if not referral:
            return None

        if referral.status == ReferralStatus.CONVERTED:
            return referral

        referral.status = ReferralStatus.CONVERTED
        referral.converted_at = datetime.utcnow()

        # Award conversion bonus
        await self._award_conversion_bonus(referral)

        logger.info(f"Referral converted: {referee[:8]}...")
        return referral

    async def record_fee_contribution(
        self,
        referee: str,
        fee_amount: int
    ) -> int:
        """Record fee contribution and calculate referrer reward"""
        referral = await self.get_referral_by_referee(referee)
        if not referral:
            return 0

        if referral.status not in [ReferralStatus.ACTIVE, ReferralStatus.CONVERTED]:
            return 0

        # Update totals
        referral.total_fees_generated += fee_amount
        referral.last_activity = datetime.utcnow()

        # Calculate reward
        stats = await self.get_referrer_stats(referral.referrer)
        base_reward = fee_amount * REFERRER_REWARD_BPS // 10000
        reward = int(base_reward * stats.tier_multiplier)

        # Add to pending
        stats.pending_rewards += reward

        return reward

    async def get_referral_by_referee(self, referee: str) -> Optional[Referral]:
        """Get referral by referee wallet"""
        for referral in self.referrals.values():
            if referral.referee == referee:
                return referral
        return None

    async def get_referrals_by_referrer(
        self,
        referrer: str
    ) -> List[Referral]:
        """Get all referrals for a referrer"""
        return [
            r for r in self.referrals.values()
            if r.referrer == referrer
        ]

    # =========================================================================
    # REWARDS
    # =========================================================================

    async def claim_rewards(
        self,
        wallet: str
    ) -> Dict[str, Any]:
        """Claim pending referral rewards"""
        stats = await self.get_referrer_stats(wallet)

        if stats.pending_rewards <= 0:
            raise ValueError("No rewards to claim")

        amount = stats.pending_rewards

        # Transfer tokens
        signature = await self._transfer_rewards(wallet, amount)

        # Update stats
        stats.total_rewards_earned += amount
        stats.pending_rewards = 0

        # Update individual referrals
        for referral in await self.get_referrals_by_referrer(wallet):
            referral.rewards_paid += referral.total_fees_generated * REFERRER_REWARD_BPS // 10000

        logger.info(f"Claimed {amount} rewards for {wallet[:8]}...")

        return {
            "amount": amount,
            "signature": signature
        }

    async def _award_conversion_bonus(self, referral: Referral):
        """Award bonus for conversion"""
        stats = await self.get_referrer_stats(referral.referrer)

        # Get tier bonus
        tier_info = self._get_referral_tier(stats.total_referrals)
        bonus = tier_info["bonus"]

        if bonus > 0:
            stats.pending_rewards += bonus
            logger.info(f"Awarded {bonus} conversion bonus to {referral.referrer[:8]}...")

    async def _transfer_rewards(self, wallet: str, amount: int) -> str:
        """Transfer reward tokens"""
        # In production, execute token transfer
        return "mock_reward_signature"

    # =========================================================================
    # STATISTICS
    # =========================================================================

    async def get_referrer_stats(self, wallet: str) -> ReferrerStats:
        """Get statistics for a referrer"""
        if wallet not in self.referrer_stats:
            self.referrer_stats[wallet] = ReferrerStats(wallet=wallet)
            await self._update_referrer_stats(wallet)

        return self.referrer_stats[wallet]

    async def _update_referrer_stats(self, wallet: str):
        """Update referrer statistics"""
        referrals = await self.get_referrals_by_referrer(wallet)

        stats = self.referrer_stats.get(wallet, ReferrerStats(wallet=wallet))
        stats.total_referrals = len(referrals)
        stats.active_referrals = len([
            r for r in referrals
            if r.status in [ReferralStatus.ACTIVE, ReferralStatus.CONVERTED]
        ])
        stats.converted_referrals = len([
            r for r in referrals if r.status == ReferralStatus.CONVERTED
        ])

        # Update tier
        tier_info = self._get_referral_tier(stats.total_referrals)
        stats.referral_tier = tier_info["name"]
        stats.tier_multiplier = tier_info["multiplier"]

        self.referrer_stats[wallet] = stats

    def _get_referral_tier(self, total_referrals: int) -> Dict[str, Any]:
        """Get referral tier based on total referrals"""
        tier_info = REFERRAL_TIERS[0]
        for threshold, info in sorted(REFERRAL_TIERS.items()):
            if total_referrals >= threshold:
                tier_info = info
        return tier_info

    async def get_leaderboard(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get referral leaderboard"""
        stats_list = list(self.referrer_stats.values())
        stats_list.sort(key=lambda x: x.total_referrals, reverse=True)

        return [
            {
                "wallet": s.wallet,
                "total_referrals": s.total_referrals,
                "converted": s.converted_referrals,
                "total_earned": s.total_rewards_earned,
                "tier": s.referral_tier
            }
            for s in stats_list[:limit]
        ]

    async def get_global_stats(self) -> Dict[str, Any]:
        """Get global referral statistics"""
        total_referrals = len(self.referrals)
        converted = len([
            r for r in self.referrals.values()
            if r.status == ReferralStatus.CONVERTED
        ])
        total_rewards = sum(s.total_rewards_earned for s in self.referrer_stats.values())

        return {
            "total_referrals": total_referrals,
            "converted_referrals": converted,
            "conversion_rate": (converted / total_referrals * 100) if total_referrals > 0 else 0,
            "total_rewards_paid": total_rewards,
            "active_referrers": len(self.referrer_stats)
        }


# =============================================================================
# API ENDPOINTS
# =============================================================================

def create_referral_endpoints(manager: ReferralManager):
    """Create API endpoints for referrals"""
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel

    router = APIRouter(prefix="/api/referrals", tags=["Referrals"])

    class CreateCodeRequest(BaseModel):
        custom_code: Optional[str] = None

    class ApplyCodeRequest(BaseModel):
        code: str

    @router.post("/code")
    async def create_code(wallet: str, request: CreateCodeRequest):
        """Create a referral code"""
        try:
            code = await manager.create_referral_code(
                wallet, request.custom_code
            )
            return {"code": code.code}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("/code/{wallet}")
    async def get_code(wallet: str):
        """Get user's referral code"""
        code = await manager.get_user_code(wallet)
        if not code:
            raise HTTPException(status_code=404, detail="No code found")
        return {
            "code": code.code,
            "uses": code.uses,
            "is_active": code.is_active
        }

    @router.post("/apply")
    async def apply_code(wallet: str, request: ApplyCodeRequest):
        """Apply a referral code"""
        try:
            referral = await manager.apply_referral(wallet, request.code)
            return {"status": "applied", "referral_id": referral.id}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("/stats/{wallet}")
    async def get_stats(wallet: str):
        """Get referrer statistics"""
        stats = await manager.get_referrer_stats(wallet)
        return {
            "total_referrals": stats.total_referrals,
            "active_referrals": stats.active_referrals,
            "converted": stats.converted_referrals,
            "total_earned": stats.total_rewards_earned,
            "pending_rewards": stats.pending_rewards,
            "tier": stats.referral_tier,
            "multiplier": stats.tier_multiplier
        }

    @router.post("/claim")
    async def claim_rewards(wallet: str):
        """Claim pending rewards"""
        try:
            result = await manager.claim_rewards(wallet)
            return result
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("/referrals/{wallet}")
    async def get_referrals(wallet: str):
        """Get user's referrals"""
        referrals = await manager.get_referrals_by_referrer(wallet)
        return [
            {
                "id": r.id,
                "referee": r.referee[:8] + "..." + r.referee[-4:],
                "status": r.status.value,
                "fees_generated": r.total_fees_generated,
                "created_at": r.created_at.isoformat()
            }
            for r in referrals
        ]

    @router.get("/leaderboard")
    async def get_leaderboard(limit: int = 20):
        """Get referral leaderboard"""
        return await manager.get_leaderboard(limit)

    @router.get("/global-stats")
    async def get_global_stats():
        """Get global referral statistics"""
        return await manager.get_global_stats()

    return router
