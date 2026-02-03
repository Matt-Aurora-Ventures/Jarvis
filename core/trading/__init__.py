"""
Jarvis Trading Module
=====================
Autonomous trading with trust-based position sizing.

Components:
  - TrustAwareTrader: Position sizing based on trust ladder
  - PositionParameters: Trade parameters with risk adjustment
"""

from core.trading.trust_integration import (
    TrustAwareTrader,
    TrustLevel,
    PositionParameters,
    get_trust_trader,
    TRUST_LEVELS,
)

__all__ = [
    "TrustAwareTrader",
    "TrustLevel",
    "PositionParameters",
    "get_trust_trader",
    "TRUST_LEVELS",
]
