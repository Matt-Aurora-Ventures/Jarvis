"""
Treasury Management System.

Manages platform funds with secure multi-wallet architecture:

Wallet Structure:
- Reserve Vault (60%): Cold storage, multisig protected
- Active Trading (30%): Hot wallet for bot operations
- Profit Buffer (10%): Holds profits before distribution

Key Features:
- Autonomous trading with risk controls
- Automated profit distribution to stakers
- Transparency dashboard
- Circuit breakers and safety limits

Usage:
    from core.treasury import (
        get_treasury,
        TreasuryManager,
        WalletType,
    )

    treasury = get_treasury()
    balance = await treasury.get_total_balance()
    await treasury.rebalance()
"""

from core.treasury.manager import (
    TreasuryManager,
    get_treasury,
)
from core.treasury.wallet import (
    WalletType,
    TreasuryWallet,
    WalletAllocation,
)
from core.treasury.risk import (
    RiskManager,
    RiskLimits,
    CircuitBreaker,
)
from core.treasury.distribution import (
    ProfitDistributor,
    DistributionConfig,
)

__all__ = [
    # Manager
    "TreasuryManager",
    "get_treasury",
    # Wallet
    "WalletType",
    "TreasuryWallet",
    "WalletAllocation",
    # Risk
    "RiskManager",
    "RiskLimits",
    "CircuitBreaker",
    # Distribution
    "ProfitDistributor",
    "DistributionConfig",
]
