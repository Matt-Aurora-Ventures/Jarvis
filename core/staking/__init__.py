"""
Staking Module.

Provides staking functionality:
- Auto-compound service
- APY calculations
- Staking analytics
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

__all__ = [
    "AutoCompoundConfig",
    "AutoCompoundService",
    "APYCalculator",
    "CompoundEvent",
    "CompoundSettings",
    "get_auto_compound_service",
    "create_auto_compound_router",
]
