"""
Rewards Calculator API Routes.

FastAPI endpoints for reward calculations and projections:
- Reward calculations by wallet
- Reward projections
- APY information
- Tier distribution
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from core.staking.rewards_calculator import (
    StakerRewardsCalculator,
    StakeTier,
    get_rewards_calculator,
)

logger = logging.getLogger("jarvis.api.rewards")

router = APIRouter(prefix="/api/rewards", tags=["Rewards Calculator"])


# =============================================================================
# Request/Response Models
# =============================================================================


class RewardCalculationResponse(BaseModel):
    """Calculated rewards for a period."""
    wallet: str
    period_start: str
    period_end: str
    base_reward: float = Field(..., description="Base reward before multipliers")
    tier_bonus: float = Field(..., description="Bonus from staking tier")
    lock_bonus: float = Field(..., description="Bonus from lock duration")
    total_reward: float = Field(..., description="Total reward amount")
    apy: float = Field(..., description="Effective APY as decimal")


class RewardProjectionResponse(BaseModel):
    """Projected future rewards."""
    wallet: str
    staked_amount: float
    daily_reward: float
    weekly_reward: float
    monthly_reward: float
    yearly_reward: float
    projected_apy: float
    projections: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Milestone projections (1w, 1m, 3m, 6m, 1y)"
    )


class StakeInfoResponse(BaseModel):
    """Stake information for a wallet."""
    wallet: str
    staked_amount: float
    stake_start: str
    lock_duration_days: int
    tier: str
    tier_multiplier: float
    lock_multiplier: float
    total_multiplier: float


class APYRangeResponse(BaseModel):
    """APY range information."""
    base_apy: float = Field(..., description="Base APY before multipliers")
    min_apy: float = Field(..., description="Minimum possible APY")
    max_apy: float = Field(..., description="Maximum possible APY")
    average_apy: float = Field(..., description="Average APY")


class TierDistributionResponse(BaseModel):
    """Distribution of stakers by tier."""
    bronze: int = 0
    silver: int = 0
    gold: int = 0
    platinum: int = 0
    total_stakers: int = 0


class PoolSummaryResponse(BaseModel):
    """Staking pool summary."""
    total_staked: float
    staker_count: int
    reward_pool: Dict[str, float]
    tier_distribution: TierDistributionResponse
    apy_range: APYRangeResponse


class RewardHistoryItem(BaseModel):
    """Single reward claim record."""
    period_start: str
    period_end: str
    base_reward: float
    tier_bonus: float
    lock_bonus: float
    total_reward: float
    claimed_at: str
    tx_signature: Optional[str] = None


class RewardHistoryResponse(BaseModel):
    """Reward claim history."""
    wallet: str
    history: List[RewardHistoryItem]


# =============================================================================
# Dependency
# =============================================================================


def get_calculator() -> StakerRewardsCalculator:
    """Get rewards calculator dependency."""
    return get_rewards_calculator()


# =============================================================================
# API Endpoints
# =============================================================================


@router.get("/calculate/{wallet}", response_model=RewardCalculationResponse)
async def calculate_rewards(
    wallet: str,
    calculator: StakerRewardsCalculator = Depends(get_calculator),
):
    """
    Calculate current rewards for a wallet.

    Returns the reward calculation breakdown including base reward,
    tier bonus, lock bonus, and effective APY.
    """
    try:
        result = await calculator.calculate_rewards(wallet)

        return RewardCalculationResponse(
            wallet=result.wallet,
            period_start=result.period_start.isoformat(),
            period_end=result.period_end.isoformat(),
            base_reward=result.base_reward,
            tier_bonus=result.tier_bonus,
            lock_bonus=result.lock_bonus,
            total_reward=result.total_reward,
            apy=result.apy,
        )
    except Exception as e:
        logger.error(f"Error calculating rewards for {wallet}: {e}")
        raise HTTPException(500, f"Failed to calculate rewards: {str(e)}")


@router.get("/project/{wallet}", response_model=RewardProjectionResponse)
async def project_rewards(
    wallet: str,
    days: int = Query(365, ge=1, le=1825, description="Days to project"),
    calculator: StakerRewardsCalculator = Depends(get_calculator),
):
    """
    Project future rewards for a wallet.

    Returns daily, weekly, monthly, and yearly reward projections
    along with milestone estimates.
    """
    try:
        result = await calculator.project_rewards(wallet, days)

        return RewardProjectionResponse(
            wallet=result.wallet,
            staked_amount=result.staked_amount,
            daily_reward=result.daily_reward,
            weekly_reward=result.weekly_reward,
            monthly_reward=result.monthly_reward,
            yearly_reward=result.yearly_reward,
            projected_apy=result.projected_apy,
            projections=result.projections,
        )
    except Exception as e:
        logger.error(f"Error projecting rewards for {wallet}: {e}")
        raise HTTPException(500, f"Failed to project rewards: {str(e)}")


@router.get("/stake/{wallet}", response_model=StakeInfoResponse)
async def get_stake_info(
    wallet: str,
    calculator: StakerRewardsCalculator = Depends(get_calculator),
):
    """
    Get stake information for a wallet.

    Returns staked amount, lock duration, tier, and multipliers.
    """
    try:
        stake = await calculator.get_stake(wallet)

        if stake is None:
            raise HTTPException(404, f"No stake found for wallet {wallet}")

        return StakeInfoResponse(
            wallet=stake.wallet,
            staked_amount=stake.staked_amount,
            stake_start=stake.stake_start.isoformat(),
            lock_duration_days=stake.lock_duration_days,
            tier=stake.tier.value,
            tier_multiplier=calculator.get_tier_multiplier(stake.tier),
            lock_multiplier=calculator.get_lock_multiplier(stake.lock_duration_days),
            total_multiplier=stake.bonus_multiplier,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting stake info for {wallet}: {e}")
        raise HTTPException(500, f"Failed to get stake info: {str(e)}")


@router.get("/apy", response_model=APYRangeResponse)
async def get_apy_range(
    calculator: StakerRewardsCalculator = Depends(get_calculator),
):
    """
    Get APY range information.

    Returns base, minimum, maximum, and average APY values
    based on all tier and lock duration combinations.
    """
    try:
        apy_range = await calculator.get_apy_range()

        return APYRangeResponse(
            base_apy=apy_range["base"],
            min_apy=apy_range["min"],
            max_apy=apy_range["max"],
            average_apy=apy_range["average"],
        )
    except Exception as e:
        logger.error(f"Error getting APY range: {e}")
        raise HTTPException(500, f"Failed to get APY range: {str(e)}")


@router.get("/pool/summary", response_model=PoolSummaryResponse)
async def get_pool_summary(
    calculator: StakerRewardsCalculator = Depends(get_calculator),
):
    """
    Get staking pool summary.

    Returns total staked, staker count, reward pool status,
    tier distribution, and APY range.
    """
    try:
        total_staked = await calculator.get_total_staked()
        staker_count = await calculator.get_staker_count()
        reward_pool = await calculator.get_reward_pool_status()
        tier_dist = await calculator.get_tier_distribution()
        apy_range = await calculator.get_apy_range()

        return PoolSummaryResponse(
            total_staked=total_staked,
            staker_count=staker_count,
            reward_pool=reward_pool,
            tier_distribution=TierDistributionResponse(
                bronze=tier_dist.get(StakeTier.BRONZE.value, 0),
                silver=tier_dist.get(StakeTier.SILVER.value, 0),
                gold=tier_dist.get(StakeTier.GOLD.value, 0),
                platinum=tier_dist.get(StakeTier.PLATINUM.value, 0),
                total_stakers=staker_count,
            ),
            apy_range=APYRangeResponse(
                base_apy=apy_range["base"],
                min_apy=apy_range["min"],
                max_apy=apy_range["max"],
                average_apy=apy_range["average"],
            ),
        )
    except Exception as e:
        logger.error(f"Error getting pool summary: {e}")
        raise HTTPException(500, f"Failed to get pool summary: {str(e)}")


@router.get("/history/{wallet}", response_model=RewardHistoryResponse)
async def get_reward_history(
    wallet: str,
    days: int = Query(30, ge=1, le=365, description="Days of history"),
    calculator: StakerRewardsCalculator = Depends(get_calculator),
):
    """
    Get reward claim history for a wallet.

    Returns list of past reward claims with full breakdown.
    """
    try:
        history = await calculator.get_reward_history(wallet, days)

        return RewardHistoryResponse(
            wallet=wallet,
            history=[
                RewardHistoryItem(
                    period_start=item.get("period_start", ""),
                    period_end=item.get("period_end", ""),
                    base_reward=item.get("base_reward", 0),
                    tier_bonus=item.get("tier_bonus", 0),
                    lock_bonus=item.get("lock_bonus", 0),
                    total_reward=item.get("total_reward", 0),
                    claimed_at=item.get("claimed_at", ""),
                    tx_signature=item.get("tx_signature"),
                )
                for item in history
            ],
        )
    except Exception as e:
        logger.error(f"Error getting reward history for {wallet}: {e}")
        raise HTTPException(500, f"Failed to get reward history: {str(e)}")


@router.get("/tiers", response_model=Dict[str, Any])
async def get_tier_info():
    """
    Get staking tier information.

    Returns tier thresholds and multipliers for each tier.
    """
    from core.staking.rewards_calculator import TIER_CONFIG, LOCK_BONUSES

    return {
        "tiers": {
            tier.value: {
                "min_stake": config["min_stake"],
                "max_stake": config["max_stake"] if config["max_stake"] != float('inf') else None,
                "multiplier": config["base_multiplier"],
            }
            for tier, config in TIER_CONFIG.items()
        },
        "lock_bonuses": LOCK_BONUSES,
    }


@router.get("/estimate")
async def estimate_rewards(
    amount: float = Query(..., gt=0, description="Amount to stake"),
    lock_days: int = Query(0, ge=0, le=365, description="Lock duration in days"),
    calculator: StakerRewardsCalculator = Depends(get_calculator),
):
    """
    Estimate rewards for a hypothetical stake.

    Useful for users to preview rewards before staking.
    """
    try:
        # Get tier for amount
        tier = calculator.get_tier(amount)
        tier_mult = calculator.get_tier_multiplier(tier)
        lock_mult = calculator.get_lock_multiplier(lock_days)
        total_mult = tier_mult * lock_mult

        # Calculate projected rewards
        daily_rate = calculator.base_apy / 365
        daily_reward = amount * daily_rate * total_mult
        effective_apy = calculator.base_apy * total_mult

        return {
            "amount": amount,
            "lock_days": lock_days,
            "tier": tier.value,
            "tier_multiplier": tier_mult,
            "lock_multiplier": lock_mult,
            "total_multiplier": total_mult,
            "effective_apy": effective_apy,
            "estimated_daily": daily_reward,
            "estimated_weekly": daily_reward * 7,
            "estimated_monthly": daily_reward * 30,
            "estimated_yearly": daily_reward * 365,
        }
    except Exception as e:
        logger.error(f"Error estimating rewards: {e}")
        raise HTTPException(500, f"Failed to estimate rewards: {str(e)}")
