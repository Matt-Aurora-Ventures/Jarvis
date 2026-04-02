"""
Staking API Routes.

FastAPI endpoints for KR8TIV staking operations:
- User stake information
- Pool statistics
- Stake/Unstake/Claim transaction building
- Rewards history
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

logger = logging.getLogger("jarvis.api.staking")

router = APIRouter(prefix="/api/staking", tags=["Staking"])


# =============================================================================
# Request/Response Models
# =============================================================================


class StakeRequest(BaseModel):
    """Request to stake tokens."""
    wallet: str = Field(..., description="User's wallet address")
    amount: int = Field(..., gt=0, description="Amount to stake in lamports")


class UnstakeRequest(BaseModel):
    """Request to unstake tokens."""
    wallet: str = Field(..., description="User's wallet address")
    amount: Optional[int] = Field(None, description="Amount to unstake (None = all)")


class ClaimRequest(BaseModel):
    """Request to claim rewards."""
    wallet: str = Field(..., description="User's wallet address")


class UserStakeResponse(BaseModel):
    """User's stake information."""
    amount: int = Field(default=0, description="Staked amount in lamports")
    pendingRewards: int = Field(default=0, description="Pending rewards in lamports")
    multiplier: float = Field(default=1.0, description="Current time-weighted multiplier")
    stakeStartTime: Optional[str] = Field(None, description="ISO timestamp of stake start")
    cooldownEnd: Optional[str] = Field(None, description="ISO timestamp when cooldown ends")
    cooldownAmount: int = Field(default=0, description="Amount in cooldown")


class PoolStatsResponse(BaseModel):
    """Pool statistics."""
    totalStaked: int = Field(default=0, description="Total staked in pool (lamports)")
    stakerCount: int = Field(default=0, description="Number of active stakers")
    rewardRate: float = Field(default=0, description="Current reward rate per second")
    apy: float = Field(default=0, description="Estimated APY as decimal (0.15 = 15%)")
    rewardsPoolBalance: int = Field(default=0, description="SOL in rewards pool (lamports)")


class TransactionResponse(BaseModel):
    """Transaction ready for signing."""
    transaction: str = Field(..., description="Base64 encoded transaction")
    message: str = Field(default="", description="Human-readable description")


class ClaimHistoryItem(BaseModel):
    """Single claim record."""
    amount: int = Field(..., description="Amount claimed in lamports")
    timestamp: str = Field(..., description="ISO timestamp")
    signature: str = Field(..., description="Transaction signature")


class ClaimHistoryResponse(BaseModel):
    """User's claim history."""
    claims: List[ClaimHistoryItem] = Field(default_factory=list)


# =============================================================================
# Staking Service (Mock - would connect to on-chain program)
# =============================================================================


class StakingService:
    """
    Service for interacting with the staking program.

    In production, this would use Solana RPC to read program state
    and build transactions for the Anchor staking program.
    """

    LAMPORTS_PER_SOL = 1_000_000_000
    STAKING_PROGRAM_ID = os.getenv("STAKING_PROGRAM_ID", "11111111111111111111111111111111")
    KR8TIV_MINT = os.getenv("KR8TIV_MINT", "11111111111111111111111111111111")

    # Multiplier tiers (days -> multiplier)
    MULTIPLIER_TIERS = [
        (0, 1.0),
        (7, 1.5),
        (30, 2.0),
        (90, 2.5),
    ]

    def __init__(self):
        self._user_stakes: Dict[str, Dict[str, Any]] = {}
        self._pool_stats = {
            "total_staked": 0,
            "staker_count": 0,
            "reward_rate": 0.0001,  # SOL per second per staked token
            "rewards_pool": 100 * self.LAMPORTS_PER_SOL,  # 100 SOL
        }
        self._claim_history: Dict[str, List[Dict]] = {}

    def get_user_stake(self, wallet: str) -> UserStakeResponse:
        """Get user's stake information."""
        stake = self._user_stakes.get(wallet, {})

        if not stake:
            return UserStakeResponse()

        # Calculate multiplier based on stake duration
        multiplier = 1.0
        if stake.get("stake_start"):
            days_staked = (datetime.now(timezone.utc) - stake["stake_start"]).days
            for days, mult in reversed(self.MULTIPLIER_TIERS):
                if days_staked >= days:
                    multiplier = mult
                    break

        # Calculate pending rewards
        pending_rewards = self._calculate_rewards(wallet, multiplier)

        return UserStakeResponse(
            amount=stake.get("amount", 0),
            pendingRewards=pending_rewards,
            multiplier=multiplier,
            stakeStartTime=stake.get("stake_start", datetime.now(timezone.utc)).isoformat() if stake.get("stake_start") else None,
            cooldownEnd=stake.get("cooldown_end").isoformat() if stake.get("cooldown_end") else None,
            cooldownAmount=stake.get("cooldown_amount", 0),
        )

    def get_pool_stats(self) -> PoolStatsResponse:
        """Get pool statistics."""
        total_staked = self._pool_stats["total_staked"]

        # Calculate APY based on reward rate and total staked
        if total_staked > 0:
            annual_rewards = self._pool_stats["reward_rate"] * 365 * 24 * 3600
            apy = annual_rewards / (total_staked / self.LAMPORTS_PER_SOL)
        else:
            apy = 0.15  # Default 15% APY when pool is empty

        return PoolStatsResponse(
            totalStaked=total_staked,
            stakerCount=self._pool_stats["staker_count"],
            rewardRate=self._pool_stats["reward_rate"],
            apy=apy,
            rewardsPoolBalance=self._pool_stats["rewards_pool"],
        )

    def build_stake_transaction(self, wallet: str, amount: int) -> TransactionResponse:
        """Build a stake transaction."""
        # In production, this would:
        # 1. Create Anchor instruction for stake
        # 2. Build transaction with recent blockhash
        # 3. Return serialized transaction for wallet signing

        # Mock transaction (base64 placeholder)
        mock_tx = "AAAA" + "B" * 100  # Placeholder

        return TransactionResponse(
            transaction=mock_tx,
            message=f"Stake {amount / self.LAMPORTS_PER_SOL:.4f} KR8TIV tokens",
        )

    def build_unstake_transaction(self, wallet: str, amount: Optional[int] = None) -> TransactionResponse:
        """Build an unstake transaction (initiates cooldown)."""
        stake = self._user_stakes.get(wallet, {})

        if not stake or stake.get("amount", 0) == 0:
            raise HTTPException(400, "No tokens staked")

        unstake_amount = amount or stake["amount"]
        if unstake_amount > stake["amount"]:
            raise HTTPException(400, "Unstake amount exceeds staked balance")

        mock_tx = "AAAA" + "C" * 100

        return TransactionResponse(
            transaction=mock_tx,
            message=f"Initiate unstake of {unstake_amount / self.LAMPORTS_PER_SOL:.4f} KR8TIV (3-day cooldown)",
        )

    def build_complete_unstake_transaction(self, wallet: str) -> TransactionResponse:
        """Build transaction to complete unstake after cooldown."""
        stake = self._user_stakes.get(wallet, {})

        if not stake.get("cooldown_end"):
            raise HTTPException(400, "No pending unstake")

        if datetime.now(timezone.utc) < stake["cooldown_end"]:
            raise HTTPException(400, "Cooldown period not complete")

        mock_tx = "AAAA" + "D" * 100

        return TransactionResponse(
            transaction=mock_tx,
            message=f"Withdraw {stake.get('cooldown_amount', 0) / self.LAMPORTS_PER_SOL:.4f} KR8TIV tokens",
        )

    def build_claim_transaction(self, wallet: str) -> TransactionResponse:
        """Build a claim rewards transaction."""
        stake = self._user_stakes.get(wallet, {})

        if not stake or stake.get("amount", 0) == 0:
            raise HTTPException(400, "No tokens staked")

        multiplier = 1.0
        if stake.get("stake_start"):
            days_staked = (datetime.now(timezone.utc) - stake["stake_start"]).days
            for days, mult in reversed(self.MULTIPLIER_TIERS):
                if days_staked >= days:
                    multiplier = mult
                    break

        pending = self._calculate_rewards(wallet, multiplier)

        if pending <= 0:
            raise HTTPException(400, "No rewards to claim")

        mock_tx = "AAAA" + "E" * 100

        return TransactionResponse(
            transaction=mock_tx,
            message=f"Claim {pending / self.LAMPORTS_PER_SOL:.6f} SOL rewards ({multiplier}x multiplier)",
        )

    def get_claim_history(self, wallet: str) -> ClaimHistoryResponse:
        """Get user's claim history."""
        history = self._claim_history.get(wallet, [])

        return ClaimHistoryResponse(
            claims=[
                ClaimHistoryItem(
                    amount=claim["amount"],
                    timestamp=claim["timestamp"].isoformat(),
                    signature=claim["signature"],
                )
                for claim in history
            ]
        )

    def _calculate_rewards(self, wallet: str, multiplier: float) -> int:
        """Calculate pending rewards for a user."""
        stake = self._user_stakes.get(wallet, {})

        if not stake or stake.get("amount", 0) == 0:
            return 0

        # Simple reward calculation (would be on-chain in production)
        stake_start = stake.get("stake_start", datetime.now(timezone.utc))
        seconds_staked = (datetime.now(timezone.utc) - stake_start).total_seconds()

        base_rewards = stake["amount"] * self._pool_stats["reward_rate"] * seconds_staked / self.LAMPORTS_PER_SOL
        multiplied_rewards = base_rewards * multiplier

        return int(multiplied_rewards * self.LAMPORTS_PER_SOL)


# Singleton service instance
_staking_service: Optional[StakingService] = None


def get_staking_service() -> StakingService:
    """Get or create staking service."""
    global _staking_service
    if _staking_service is None:
        _staking_service = StakingService()
    return _staking_service


# =============================================================================
# API Endpoints
# =============================================================================


@router.get("/user/{wallet}", response_model=UserStakeResponse)
async def get_user_stake(
    wallet: str,
    service: StakingService = Depends(get_staking_service),
):
    """Get user's stake information."""
    try:
        return service.get_user_stake(wallet)
    except Exception as e:
        logger.error(f"Error fetching user stake: {e}")
        raise HTTPException(500, str(e))


@router.get("/pool", response_model=PoolStatsResponse)
async def get_pool_stats(
    service: StakingService = Depends(get_staking_service),
):
    """Get pool statistics."""
    try:
        return service.get_pool_stats()
    except Exception as e:
        logger.error(f"Error fetching pool stats: {e}")
        raise HTTPException(500, str(e))


@router.post("/stake", response_model=TransactionResponse)
async def create_stake_transaction(
    request: StakeRequest,
    service: StakingService = Depends(get_staking_service),
):
    """Create a stake transaction for signing."""
    try:
        return service.build_stake_transaction(request.wallet, request.amount)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error building stake transaction: {e}")
        raise HTTPException(500, str(e))


@router.post("/unstake/initiate", response_model=TransactionResponse)
async def create_unstake_transaction(
    request: UnstakeRequest,
    service: StakingService = Depends(get_staking_service),
):
    """Create an unstake transaction (initiates 3-day cooldown)."""
    try:
        return service.build_unstake_transaction(request.wallet, request.amount)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error building unstake transaction: {e}")
        raise HTTPException(500, str(e))


@router.post("/unstake/complete", response_model=TransactionResponse)
async def complete_unstake_transaction(
    request: ClaimRequest,
    service: StakingService = Depends(get_staking_service),
):
    """Complete unstake after cooldown period."""
    try:
        return service.build_complete_unstake_transaction(request.wallet)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error building complete unstake transaction: {e}")
        raise HTTPException(500, str(e))


@router.post("/rewards/claim", response_model=TransactionResponse)
async def create_claim_transaction(
    request: ClaimRequest,
    service: StakingService = Depends(get_staking_service),
):
    """Create a claim rewards transaction."""
    try:
        return service.build_claim_transaction(request.wallet)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error building claim transaction: {e}")
        raise HTTPException(500, str(e))


@router.get("/rewards/history/{wallet}", response_model=ClaimHistoryResponse)
async def get_rewards_history(
    wallet: str,
    service: StakingService = Depends(get_staking_service),
):
    """Get user's rewards claim history."""
    try:
        return service.get_claim_history(wallet)
    except Exception as e:
        logger.error(f"Error fetching claim history: {e}")
        raise HTTPException(500, str(e))
