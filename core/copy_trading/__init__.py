"""
JARVIS Copy Trading System

Follow successful traders and mirror their positions.
Includes leader verification, risk-adjusted copying, and performance tracking.

WARNING: Copy trading feature is DISABLED by default until full security audit.
"""

from .leader import (
    Leader,
    LeaderStats,
    LeaderTier,
    LeaderManager,
    get_leader_manager,
)
from .follower import (
    Follower,
    FollowConfig,
    FollowerManager,
    get_follower_manager,
)
from .copier import (
    CopyTrade,
    CopyTradeStatus,
    TradeCopier,
    get_trade_copier,
)

__all__ = [
    # Leaders
    "Leader",
    "LeaderStats",
    "LeaderTier",
    "LeaderManager",
    "get_leader_manager",
    # Followers
    "Follower",
    "FollowConfig",
    "FollowerManager",
    "get_follower_manager",
    # Copier
    "CopyTrade",
    "CopyTradeStatus",
    "TradeCopier",
    "get_trade_copier",
]

# SAFETY FLAG - Set to True only after security audit
COPY_TRADING_ENABLED = False
