"""
Staking Module.

Provides staking functionality:
- Auto-compound service
- APY calculations
- Staking analytics
- Rewards calculation
"""

from .auto_compound import (
    AutoCompoundConfig,
    AutoCompoundService,
    APYCalculator,
    CompoundEvent,
    CompoundSettings,
    get_auto_compound_service,
    create_auto_compound_router,
)
from .rewards_calculator import (
    StakerRewardsCalculator,
    RewardCalculation,
    RewardProjection,
    StakeTier,
    get_rewards_calculator,
)

__all__ = [
    # Auto-compound
    "AutoCompoundConfig",
    "AutoCompoundService",
    "APYCalculator",
    "CompoundEvent",
    "CompoundSettings",
    "get_auto_compound_service",
    "create_auto_compound_router",
    # Rewards calculator
    "StakerRewardsCalculator",
    "RewardCalculation",
    "RewardProjection",
    "StakeTier",
    "get_rewards_calculator",
]
