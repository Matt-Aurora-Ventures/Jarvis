"""
Jarvis Treasury Trading Module

Refactored from the original 3,754-line trading.py into logical submodules:
- types.py: Enums, dataclasses (Position, TradeReport, etc.)
- constants.py: Configuration, token lists, spending caps
- logging_utils.py: Structured logging helpers
- trading_risk.py: Token safety, spending limits, TP/SL calculations
- trading_positions.py: Position state persistence and management
- trading_analytics.py: P&L calculations, performance reporting
- trading_execution.py: Swap execution, signal analysis
- trading_operations.py: Core trading operations (open/close position)
- trading_core.py: Main TradingEngine orchestrator class + TreasuryTrader interface
"""

# Re-export all public interfaces for backward compatibility

# Import wallet and Jupiter for backward compatibility (used by tests)
try:
    from ..wallet import SecureWallet, WalletInfo
except ImportError:
    SecureWallet = None
    WalletInfo = None

try:
    from ..jupiter import JupiterClient
except ImportError:
    JupiterClient = None

# Types and enums
from .types import (
    TradeDirection,
    TradeStatus,
    RiskLevel,
    Position,
    TradeReport,
)

# Main engine and trader classes
from .trading_core import TradingEngine, TreasuryTrader, _SimpleWallet

# Risk management utilities
from .trading_risk import RiskChecker

# Position management
from .trading_positions import PositionManager

# Analytics
from .trading_analytics import TradingAnalytics

# Execution utilities
from .trading_execution import SwapExecutor, SignalAnalyzer

# Constants (commonly needed)
from .constants import (
    ESTABLISHED_TOKENS,
    BLOCKED_TOKENS,
    BLOCKED_SYMBOLS,
    TP_SL_CONFIG,
    POSITION_SIZE,
    MAX_TRADE_USD,
    MAX_DAILY_USD,
    ADMIN_USER_ID,
)


__all__ = [
    # Types
    'TradeDirection',
    'TradeStatus',
    'RiskLevel',
    'Position',
    'TradeReport',
    # Main classes
    'TradingEngine',
    'TreasuryTrader',
    '_SimpleWallet',
    # Utilities
    'RiskChecker',
    'PositionManager',
    'TradingAnalytics',
    'SwapExecutor',
    'SignalAnalyzer',
    # Constants
    'ESTABLISHED_TOKENS',
    'BLOCKED_TOKENS',
    'BLOCKED_SYMBOLS',
    'TP_SL_CONFIG',
    'POSITION_SIZE',
    'MAX_TRADE_USD',
    'MAX_DAILY_USD',
    'ADMIN_USER_ID',
    # Backward compatibility (for test patches)
    'SecureWallet',
    'WalletInfo',
    'JupiterClient',
]
