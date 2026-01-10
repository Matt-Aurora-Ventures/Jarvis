"""
Liquidity Mining Program
Prompt #43: LP token staking for additional rewards
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
import json

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# Reward distribution settings
BLOCKS_PER_DAY = 216000  # ~0.4s per slot on Solana
REWARD_PRECISION = 10**18
MIN_STAKE_DURATION = 3600  # 1 hour minimum


# =============================================================================
# MODELS
# =============================================================================

class PoolStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"
    PENDING = "pending"


class RewardType(str, Enum):
    SINGLE = "single"  # Single reward token
    DUAL = "dual"      # Two reward tokens
    MULTI = "multi"    # Multiple reward tokens


@dataclass
class RewardToken:
    """Configuration for a reward token"""
    mint: str
    symbol: str
    decimals: int = 9
    rewards_per_second: int = 0
    total_distributed: int = 0
    remaining_rewards: int = 0


@dataclass
class LiquidityPool:
    """A liquidity mining pool"""
    id: str
    name: str
    lp_token_mint: str
    lp_token_symbol: str
    lp_token_decimals: int = 9
    reward_tokens: List[RewardToken] = field(default_factory=list)
    total_staked: int = 0
    total_stakers: int = 0
    acc_reward_per_share: Dict[str, int] = field(default_factory=dict)  # Per reward token
    last_reward_time: datetime = field(default_factory=datetime.utcnow)
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    status: PoolStatus = PoolStatus.PENDING
    boost_multiplier: int = 100  # 100 = 1x, 150 = 1.5x
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        now = datetime.utcnow()
        return (
            self.status == PoolStatus.ACTIVE and
            now >= self.start_time and
            (self.end_time is None or now < self.end_time)
        )

    @property
    def duration_remaining(self) -> Optional[timedelta]:
        if self.end_time is None:
            return None
        return max(self.end_time - datetime.utcnow(), timedelta(0))


@dataclass
class UserLPStake:
    """User's LP token stake in a pool"""
    user_id: str
    pool_id: str
    amount: int = 0
    reward_debt: Dict[str, int] = field(default_factory=dict)  # Per reward token
    pending_rewards: Dict[str, int] = field(default_factory=dict)
    staked_at: datetime = field(default_factory=datetime.utcnow)
    last_claim: Optional[datetime] = None
    boost_nft: Optional[str] = None  # NFT providing boost
    boost_multiplier: int = 100  # User-specific boost
    total_claimed: Dict[str, int] = field(default_factory=dict)


@dataclass
class StakeEvent:
    """Record of a stake/unstake event"""
    id: str
    user_id: str
    pool_id: str
    event_type: str  # "stake", "unstake", "claim"
    amount: int
    rewards_claimed: Dict[str, int] = field(default_factory=dict)
    signature: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


# =============================================================================
# LIQUIDITY MINING MANAGER
# =============================================================================

class LiquidityMiningManager:
    """Manages liquidity mining pools and rewards"""

    def __init__(self, db_url: str, token_mint: str):
        self.db_url = db_url
        self.token_mint = token_mint  # $KR8TIV token
        self.pools: Dict[str, LiquidityPool] = {}
        self.user_stakes: Dict[str, Dict[str, UserLPStake]] = {}  # user_id -> pool_id -> stake
        self.events: List[StakeEvent] = []

    # =========================================================================
    # POOL MANAGEMENT
    # =========================================================================

    async def create_pool(
        self,
        name: str,
        lp_token_mint: str,
        lp_token_symbol: str,
        reward_tokens: List[Dict[str, Any]],
        start_time: Optional[datetime] = None,
        duration_days: Optional[int] = None,
        boost_multiplier: int = 100
    ) -> LiquidityPool:
        """Create a new liquidity mining pool"""
        import uuid

        pool = LiquidityPool(
            id=str(uuid.uuid4()),
            name=name,
            lp_token_mint=lp_token_mint,
            lp_token_symbol=lp_token_symbol,
            reward_tokens=[
                RewardToken(
                    mint=rt["mint"],
                    symbol=rt["symbol"],
                    decimals=rt.get("decimals", 9),
                    rewards_per_second=rt.get("rewards_per_second", 0),
                    remaining_rewards=rt.get("total_rewards", 0)
                )
                for rt in reward_tokens
            ],
            start_time=start_time or datetime.utcnow(),
            end_time=(start_time or datetime.utcnow()) + timedelta(days=duration_days) if duration_days else None,
            boost_multiplier=boost_multiplier,
            status=PoolStatus.PENDING if start_time and start_time > datetime.utcnow() else PoolStatus.ACTIVE
        )

        # Initialize acc_reward_per_share for each reward token
        for rt in pool.reward_tokens:
            pool.acc_reward_per_share[rt.mint] = 0

        self.pools[pool.id] = pool
        await self._save_pool(pool)

        logger.info(f"Created liquidity mining pool: {name} ({pool.id})")
        return pool

    async def update_pool_rewards(
        self,
        pool_id: str,
        reward_updates: Dict[str, int]  # mint -> new rewards_per_second
    ):
        """Update reward emission rates"""
        pool = self.pools.get(pool_id)
        if not pool:
            raise ValueError("Pool not found")

        # First update accumulated rewards
        await self._update_pool(pool)

        # Then update rates
        for rt in pool.reward_tokens:
            if rt.mint in reward_updates:
                rt.rewards_per_second = reward_updates[rt.mint]

        await self._save_pool(pool)
        logger.info(f"Updated pool {pool_id} reward rates: {reward_updates}")

    async def add_rewards(
        self,
        pool_id: str,
        reward_additions: Dict[str, int]  # mint -> amount to add
    ):
        """Add more rewards to a pool"""
        pool = self.pools.get(pool_id)
        if not pool:
            raise ValueError("Pool not found")

        for rt in pool.reward_tokens:
            if rt.mint in reward_additions:
                rt.remaining_rewards += reward_additions[rt.mint]

        await self._save_pool(pool)
        logger.info(f"Added rewards to pool {pool_id}: {reward_additions}")

    async def pause_pool(self, pool_id: str):
        """Pause a pool (stops new rewards)"""
        pool = self.pools.get(pool_id)
        if not pool:
            raise ValueError("Pool not found")

        await self._update_pool(pool)
        pool.status = PoolStatus.PAUSED
        await self._save_pool(pool)

    async def resume_pool(self, pool_id: str):
        """Resume a paused pool"""
        pool = self.pools.get(pool_id)
        if not pool:
            raise ValueError("Pool not found")

        pool.status = PoolStatus.ACTIVE
        pool.last_reward_time = datetime.utcnow()
        await self._save_pool(pool)

    async def end_pool(self, pool_id: str):
        """End a pool permanently"""
        pool = self.pools.get(pool_id)
        if not pool:
            raise ValueError("Pool not found")

        await self._update_pool(pool)
        pool.status = PoolStatus.ENDED
        pool.end_time = datetime.utcnow()
        await self._save_pool(pool)

    # =========================================================================
    # STAKING OPERATIONS
    # =========================================================================

    async def stake_lp(
        self,
        user_id: str,
        pool_id: str,
        amount: int
    ) -> Dict[str, Any]:
        """Stake LP tokens in a pool"""
        pool = self.pools.get(pool_id)
        if not pool:
            raise ValueError("Pool not found")

        if not pool.is_active:
            raise ValueError("Pool is not active")

        if amount <= 0:
            raise ValueError("Amount must be positive")

        # Update pool rewards first
        await self._update_pool(pool)

        # Get or create user stake
        user_stake = await self._get_or_create_stake(user_id, pool_id)

        # Claim any pending rewards first
        pending = await self._calculate_pending_rewards(user_stake, pool)

        # Update user stake
        user_stake.amount += amount
        user_stake.staked_at = datetime.utcnow()

        # Update reward debt for each token
        for rt in pool.reward_tokens:
            user_stake.reward_debt[rt.mint] = (
                user_stake.amount * pool.acc_reward_per_share[rt.mint] // REWARD_PRECISION
            )
            # Add any pending to pending_rewards for later claim
            if pending.get(rt.mint, 0) > 0:
                user_stake.pending_rewards[rt.mint] = (
                    user_stake.pending_rewards.get(rt.mint, 0) + pending[rt.mint]
                )

        # Update pool totals
        pool.total_staked += amount
        if user_stake.amount == amount:  # New staker
            pool.total_stakers += 1

        await self._save_stake(user_stake)
        await self._save_pool(pool)

        # Record event
        event = StakeEvent(
            id=f"stake-{user_id}-{pool_id}-{datetime.utcnow().timestamp()}",
            user_id=user_id,
            pool_id=pool_id,
            event_type="stake",
            amount=amount
        )
        self.events.append(event)

        logger.info(f"User {user_id} staked {amount} LP tokens in pool {pool_id}")

        return {
            "pool_id": pool_id,
            "amount_staked": amount,
            "total_staked": user_stake.amount,
            "pending_rewards": pending
        }

    async def unstake_lp(
        self,
        user_id: str,
        pool_id: str,
        amount: int
    ) -> Dict[str, Any]:
        """Unstake LP tokens from a pool"""
        pool = self.pools.get(pool_id)
        if not pool:
            raise ValueError("Pool not found")

        user_stake = await self._get_stake(user_id, pool_id)
        if not user_stake or user_stake.amount < amount:
            raise ValueError("Insufficient staked amount")

        # Update pool rewards
        await self._update_pool(pool)

        # Calculate and claim rewards
        pending = await self._calculate_pending_rewards(user_stake, pool)
        claimed = await self._claim_rewards(user_stake, pool, pending)

        # Update stake
        user_stake.amount -= amount

        # Update reward debt
        for rt in pool.reward_tokens:
            user_stake.reward_debt[rt.mint] = (
                user_stake.amount * pool.acc_reward_per_share[rt.mint] // REWARD_PRECISION
            )

        # Update pool totals
        pool.total_staked -= amount
        if user_stake.amount == 0:
            pool.total_stakers -= 1

        await self._save_stake(user_stake)
        await self._save_pool(pool)

        # Record event
        event = StakeEvent(
            id=f"unstake-{user_id}-{pool_id}-{datetime.utcnow().timestamp()}",
            user_id=user_id,
            pool_id=pool_id,
            event_type="unstake",
            amount=amount,
            rewards_claimed=claimed
        )
        self.events.append(event)

        logger.info(f"User {user_id} unstaked {amount} LP tokens from pool {pool_id}")

        return {
            "pool_id": pool_id,
            "amount_unstaked": amount,
            "remaining_staked": user_stake.amount,
            "rewards_claimed": claimed
        }

    async def claim_rewards(
        self,
        user_id: str,
        pool_id: str
    ) -> Dict[str, Any]:
        """Claim pending rewards without unstaking"""
        pool = self.pools.get(pool_id)
        if not pool:
            raise ValueError("Pool not found")

        user_stake = await self._get_stake(user_id, pool_id)
        if not user_stake or user_stake.amount == 0:
            raise ValueError("No stake found")

        # Update pool rewards
        await self._update_pool(pool)

        # Calculate pending
        pending = await self._calculate_pending_rewards(user_stake, pool)

        # Add stored pending rewards
        for mint, amount in user_stake.pending_rewards.items():
            pending[mint] = pending.get(mint, 0) + amount
        user_stake.pending_rewards = {}

        if sum(pending.values()) == 0:
            raise ValueError("No rewards to claim")

        # Claim
        claimed = await self._claim_rewards(user_stake, pool, pending)

        # Update reward debt
        for rt in pool.reward_tokens:
            user_stake.reward_debt[rt.mint] = (
                user_stake.amount * pool.acc_reward_per_share[rt.mint] // REWARD_PRECISION
            )

        await self._save_stake(user_stake)

        # Record event
        event = StakeEvent(
            id=f"claim-{user_id}-{pool_id}-{datetime.utcnow().timestamp()}",
            user_id=user_id,
            pool_id=pool_id,
            event_type="claim",
            amount=0,
            rewards_claimed=claimed
        )
        self.events.append(event)

        logger.info(f"User {user_id} claimed rewards from pool {pool_id}: {claimed}")

        return {
            "pool_id": pool_id,
            "rewards_claimed": claimed,
            "total_claimed": user_stake.total_claimed
        }

    # =========================================================================
    # BOOST SYSTEM
    # =========================================================================

    async def apply_boost(
        self,
        user_id: str,
        pool_id: str,
        nft_mint: str,
        boost_multiplier: int
    ):
        """Apply NFT boost to user's stake"""
        user_stake = await self._get_stake(user_id, pool_id)
        if not user_stake:
            raise ValueError("No stake found")

        # Verify NFT ownership (would check on-chain)
        if not await self._verify_nft_ownership(user_id, nft_mint):
            raise ValueError("NFT not owned")

        # Claim pending rewards at old rate first
        pool = self.pools[pool_id]
        await self._update_pool(pool)
        pending = await self._calculate_pending_rewards(user_stake, pool)
        if sum(pending.values()) > 0:
            for mint, amount in pending.items():
                user_stake.pending_rewards[mint] = (
                    user_stake.pending_rewards.get(mint, 0) + amount
                )

        # Apply boost
        user_stake.boost_nft = nft_mint
        user_stake.boost_multiplier = boost_multiplier

        # Update reward debt
        for rt in pool.reward_tokens:
            user_stake.reward_debt[rt.mint] = (
                user_stake.amount * pool.acc_reward_per_share[rt.mint] // REWARD_PRECISION
            )

        await self._save_stake(user_stake)
        logger.info(f"Applied {boost_multiplier}% boost to user {user_id} in pool {pool_id}")

    async def remove_boost(self, user_id: str, pool_id: str):
        """Remove NFT boost from user's stake"""
        user_stake = await self._get_stake(user_id, pool_id)
        if not user_stake:
            raise ValueError("No stake found")

        # Claim pending at boosted rate first
        pool = self.pools[pool_id]
        await self._update_pool(pool)
        pending = await self._calculate_pending_rewards(user_stake, pool)
        for mint, amount in pending.items():
            user_stake.pending_rewards[mint] = (
                user_stake.pending_rewards.get(mint, 0) + amount
            )

        # Remove boost
        user_stake.boost_nft = None
        user_stake.boost_multiplier = 100

        # Update reward debt
        for rt in pool.reward_tokens:
            user_stake.reward_debt[rt.mint] = (
                user_stake.amount * pool.acc_reward_per_share[rt.mint] // REWARD_PRECISION
            )

        await self._save_stake(user_stake)

    # =========================================================================
    # VIEW FUNCTIONS
    # =========================================================================

    async def get_pool(self, pool_id: str) -> Optional[LiquidityPool]:
        """Get pool details"""
        return self.pools.get(pool_id)

    async def get_all_pools(self, active_only: bool = False) -> List[LiquidityPool]:
        """Get all pools"""
        pools = list(self.pools.values())
        if active_only:
            pools = [p for p in pools if p.is_active]
        return pools

    async def get_user_stake(
        self,
        user_id: str,
        pool_id: str
    ) -> Optional[UserLPStake]:
        """Get user's stake in a pool"""
        return await self._get_stake(user_id, pool_id)

    async def get_user_all_stakes(
        self,
        user_id: str
    ) -> List[Dict[str, Any]]:
        """Get all stakes for a user across all pools"""
        stakes = []
        for pool_id, pool in self.pools.items():
            stake = await self._get_stake(user_id, pool_id)
            if stake and stake.amount > 0:
                await self._update_pool(pool)
                pending = await self._calculate_pending_rewards(stake, pool)
                stakes.append({
                    "pool_id": pool_id,
                    "pool_name": pool.name,
                    "amount": stake.amount,
                    "pending_rewards": pending,
                    "boost_multiplier": stake.boost_multiplier,
                    "staked_at": stake.staked_at.isoformat()
                })
        return stakes

    async def get_pending_rewards(
        self,
        user_id: str,
        pool_id: str
    ) -> Dict[str, int]:
        """Get pending rewards for a user in a pool"""
        pool = self.pools.get(pool_id)
        if not pool:
            return {}

        stake = await self._get_stake(user_id, pool_id)
        if not stake:
            return {}

        await self._update_pool(pool)
        pending = await self._calculate_pending_rewards(stake, pool)

        # Add stored pending
        for mint, amount in stake.pending_rewards.items():
            pending[mint] = pending.get(mint, 0) + amount

        return pending

    async def get_pool_apy(self, pool_id: str) -> Dict[str, Decimal]:
        """Calculate current APY for each reward token"""
        pool = self.pools.get(pool_id)
        if not pool or pool.total_staked == 0:
            return {}

        apys = {}
        for rt in pool.reward_tokens:
            yearly_rewards = rt.rewards_per_second * 86400 * 365
            # APY = (yearly_rewards / total_staked) * 100
            apy = Decimal(yearly_rewards) / Decimal(pool.total_staked) * 100
            apys[rt.symbol] = apy

        return apys

    async def get_global_stats(self) -> Dict[str, Any]:
        """Get global liquidity mining statistics"""
        total_value_locked = sum(p.total_staked for p in self.pools.values())
        total_stakers = sum(p.total_stakers for p in self.pools.values())
        active_pools = len([p for p in self.pools.values() if p.is_active])

        total_rewards_distributed = {}
        for pool in self.pools.values():
            for rt in pool.reward_tokens:
                total_rewards_distributed[rt.symbol] = (
                    total_rewards_distributed.get(rt.symbol, 0) +
                    rt.total_distributed
                )

        return {
            "total_pools": len(self.pools),
            "active_pools": active_pools,
            "total_value_locked": total_value_locked,
            "total_stakers": total_stakers,
            "total_rewards_distributed": total_rewards_distributed
        }

    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================

    async def _update_pool(self, pool: LiquidityPool):
        """Update pool's accumulated rewards per share"""
        if pool.total_staked == 0 or not pool.is_active:
            pool.last_reward_time = datetime.utcnow()
            return

        now = datetime.utcnow()
        time_elapsed = (now - pool.last_reward_time).total_seconds()

        if time_elapsed <= 0:
            return

        for rt in pool.reward_tokens:
            # Calculate rewards for this period
            rewards = int(rt.rewards_per_second * time_elapsed)

            # Cap at remaining rewards
            rewards = min(rewards, rt.remaining_rewards)

            if rewards > 0:
                # Update accumulated reward per share
                pool.acc_reward_per_share[rt.mint] += (
                    rewards * REWARD_PRECISION // pool.total_staked
                )
                rt.total_distributed += rewards
                rt.remaining_rewards -= rewards

        pool.last_reward_time = now

    async def _calculate_pending_rewards(
        self,
        stake: UserLPStake,
        pool: LiquidityPool
    ) -> Dict[str, int]:
        """Calculate pending rewards for a stake"""
        pending = {}

        for rt in pool.reward_tokens:
            acc_per_share = pool.acc_reward_per_share.get(rt.mint, 0)
            debt = stake.reward_debt.get(rt.mint, 0)

            # Apply user boost
            effective_amount = stake.amount * stake.boost_multiplier // 100

            reward = effective_amount * acc_per_share // REWARD_PRECISION - debt
            pending[rt.mint] = max(0, reward)

        return pending

    async def _claim_rewards(
        self,
        stake: UserLPStake,
        pool: LiquidityPool,
        rewards: Dict[str, int]
    ) -> Dict[str, int]:
        """Execute reward claim (transfers)"""
        claimed = {}

        for mint, amount in rewards.items():
            if amount > 0:
                # In production, execute on-chain transfer
                signature = await self._transfer_rewards(stake.user_id, mint, amount)
                claimed[mint] = amount
                stake.total_claimed[mint] = stake.total_claimed.get(mint, 0) + amount

        stake.last_claim = datetime.utcnow()
        return claimed

    async def _get_or_create_stake(
        self,
        user_id: str,
        pool_id: str
    ) -> UserLPStake:
        """Get existing stake or create new one"""
        if user_id not in self.user_stakes:
            self.user_stakes[user_id] = {}

        if pool_id not in self.user_stakes[user_id]:
            self.user_stakes[user_id][pool_id] = UserLPStake(
                user_id=user_id,
                pool_id=pool_id
            )

        return self.user_stakes[user_id][pool_id]

    async def _get_stake(
        self,
        user_id: str,
        pool_id: str
    ) -> Optional[UserLPStake]:
        """Get user stake if exists"""
        if user_id in self.user_stakes:
            return self.user_stakes[user_id].get(pool_id)
        return None

    async def _save_pool(self, pool: LiquidityPool):
        """Save pool to database"""
        # In production, save to PostgreSQL
        pass

    async def _save_stake(self, stake: UserLPStake):
        """Save stake to database"""
        # In production, save to PostgreSQL
        pass

    async def _transfer_rewards(
        self,
        user_id: str,
        token_mint: str,
        amount: int
    ) -> str:
        """Transfer reward tokens to user"""
        # In production, execute Solana transfer
        return "mock_signature"

    async def _verify_nft_ownership(
        self,
        user_id: str,
        nft_mint: str
    ) -> bool:
        """Verify user owns the NFT"""
        # In production, check on-chain
        return True


# =============================================================================
# API ENDPOINTS
# =============================================================================

def create_liquidity_mining_endpoints(manager: LiquidityMiningManager):
    """Create API endpoints for liquidity mining"""
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel

    router = APIRouter(prefix="/api/liquidity-mining", tags=["Liquidity Mining"])

    class StakeLPRequest(BaseModel):
        pool_id: str
        amount: int

    class UnstakeLPRequest(BaseModel):
        pool_id: str
        amount: int

    class ApplyBoostRequest(BaseModel):
        pool_id: str
        nft_mint: str
        boost_multiplier: int

    @router.get("/pools")
    async def get_pools(active_only: bool = False):
        """Get all liquidity mining pools"""
        pools = await manager.get_all_pools(active_only)
        return [
            {
                "id": p.id,
                "name": p.name,
                "lp_token": {
                    "mint": p.lp_token_mint,
                    "symbol": p.lp_token_symbol
                },
                "reward_tokens": [
                    {
                        "mint": rt.mint,
                        "symbol": rt.symbol,
                        "rewards_per_second": rt.rewards_per_second,
                        "remaining": rt.remaining_rewards
                    }
                    for rt in p.reward_tokens
                ],
                "total_staked": p.total_staked,
                "total_stakers": p.total_stakers,
                "status": p.status.value,
                "apy": await manager.get_pool_apy(p.id)
            }
            for p in pools
        ]

    @router.get("/pools/{pool_id}")
    async def get_pool(pool_id: str):
        """Get pool details"""
        pool = await manager.get_pool(pool_id)
        if not pool:
            raise HTTPException(status_code=404, detail="Pool not found")

        return {
            "id": pool.id,
            "name": pool.name,
            "lp_token": {
                "mint": pool.lp_token_mint,
                "symbol": pool.lp_token_symbol
            },
            "reward_tokens": [
                {
                    "mint": rt.mint,
                    "symbol": rt.symbol,
                    "rewards_per_second": rt.rewards_per_second,
                    "total_distributed": rt.total_distributed,
                    "remaining": rt.remaining_rewards
                }
                for rt in pool.reward_tokens
            ],
            "total_staked": pool.total_staked,
            "total_stakers": pool.total_stakers,
            "status": pool.status.value,
            "start_time": pool.start_time.isoformat(),
            "end_time": pool.end_time.isoformat() if pool.end_time else None,
            "boost_multiplier": pool.boost_multiplier,
            "apy": await manager.get_pool_apy(pool_id)
        }

    @router.post("/stake")
    async def stake_lp(user_id: str, request: StakeLPRequest):
        """Stake LP tokens"""
        try:
            result = await manager.stake_lp(
                user_id=user_id,
                pool_id=request.pool_id,
                amount=request.amount
            )
            return result
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/unstake")
    async def unstake_lp(user_id: str, request: UnstakeLPRequest):
        """Unstake LP tokens"""
        try:
            result = await manager.unstake_lp(
                user_id=user_id,
                pool_id=request.pool_id,
                amount=request.amount
            )
            return result
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/claim/{pool_id}")
    async def claim_rewards(pool_id: str, user_id: str):
        """Claim pending rewards"""
        try:
            result = await manager.claim_rewards(user_id, pool_id)
            return result
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("/user/{user_id}/stakes")
    async def get_user_stakes(user_id: str):
        """Get all stakes for a user"""
        stakes = await manager.get_user_all_stakes(user_id)
        return {"user_id": user_id, "stakes": stakes}

    @router.get("/user/{user_id}/pools/{pool_id}/pending")
    async def get_pending_rewards(user_id: str, pool_id: str):
        """Get pending rewards for a user in a pool"""
        pending = await manager.get_pending_rewards(user_id, pool_id)
        return {"pool_id": pool_id, "pending_rewards": pending}

    @router.post("/boost")
    async def apply_boost(user_id: str, request: ApplyBoostRequest):
        """Apply NFT boost to stake"""
        try:
            await manager.apply_boost(
                user_id=user_id,
                pool_id=request.pool_id,
                nft_mint=request.nft_mint,
                boost_multiplier=request.boost_multiplier
            )
            return {"status": "ok", "boost_applied": request.boost_multiplier}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("/stats")
    async def get_global_stats():
        """Get global liquidity mining statistics"""
        return await manager.get_global_stats()

    return router
