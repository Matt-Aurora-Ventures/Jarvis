"""
Trading Configuration - Centralized configuration for trading engine.

All hardcoded trading parameters are now configurable via environment variables
or this configuration file. This allows tuning without code changes.

Environment Variables (override defaults):
    JARVIS_MAX_TRADE_USD         - Maximum single trade size (default: 100)
    JARVIS_MAX_DAILY_USD         - Maximum daily volume (default: 500)
    JARVIS_MAX_POSITION_PCT      - Max % of portfolio per position (default: 0.20)
    JARVIS_MAX_POSITIONS         - Maximum concurrent positions (default: 50)
    JARVIS_DRY_RUN               - Enable dry run mode (default: true)
    JARVIS_RISK_LEVEL            - Default risk level (default: MODERATE)

Usage:
    from core.trading_config import TradingConfig, get_trading_config

    config = get_trading_config()
    max_trade = config.max_trade_usd
"""

import os
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk levels for position sizing."""
    CONSERVATIVE = "CONSERVATIVE"  # 1% position size
    MODERATE = "MODERATE"          # 2% position size
    AGGRESSIVE = "AGGRESSIVE"      # 5% position size
    DEGEN = "DEGEN"                # 10% position size


@dataclass
class TradingConfig:
    """
    Centralized trading configuration.

    All values can be overridden via environment variables prefixed with JARVIS_.
    """

    # === SPENDING LIMITS ===
    max_trade_usd: float = 100.0          # Maximum single trade size
    max_daily_usd: float = 500.0          # Maximum daily trading volume
    max_position_pct: float = 0.20        # Max 20% of portfolio per position
    max_allocation_per_token: float = 0.20  # Max 20% per token (stacked)
    allow_stacking: bool = False          # Allow multiple positions in same token

    # === POSITION LIMITS ===
    max_positions: int = 50               # Maximum concurrent positions

    # === RISK MANAGEMENT ===
    default_risk_level: RiskLevel = RiskLevel.MODERATE
    position_size_pct: Dict[RiskLevel, float] = field(default_factory=lambda: {
        RiskLevel.CONSERVATIVE: 0.01,     # 1%
        RiskLevel.MODERATE: 0.02,         # 2%
        RiskLevel.AGGRESSIVE: 0.05,       # 5%
        RiskLevel.DEGEN: 0.10,            # 10%
    })

    # === HIGH RISK TOKEN SETTINGS ===
    min_liquidity_usd: float = 5000.0     # Minimum liquidity for any trade
    min_volume_24h_usd: float = 2500.0    # Minimum 24h volume
    min_token_age_hours: float = 1.0      # Minimum token age
    max_high_risk_position_pct: float = 0.15   # 15% of normal for high-risk
    max_unvetted_position_pct: float = 0.25    # 25% of normal for unvetted

    # === TAKE PROFIT / STOP LOSS ===
    tp_sl_config: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
        'A+': {'take_profit': 0.30, 'stop_loss': 0.08},
        'A': {'take_profit': 0.30, 'stop_loss': 0.08},
        'A-': {'take_profit': 0.25, 'stop_loss': 0.10},
        'B+': {'take_profit': 0.20, 'stop_loss': 0.10},
        'B': {'take_profit': 0.18, 'stop_loss': 0.12},
        'B-': {'take_profit': 0.15, 'stop_loss': 0.12},
        'C+': {'take_profit': 0.12, 'stop_loss': 0.15},
        'C': {'take_profit': 0.10, 'stop_loss': 0.15},
        'C-': {'take_profit': 0.08, 'stop_loss': 0.15},
        'D': {'take_profit': 0.05, 'stop_loss': 0.20},
        'F': {'take_profit': 0.05, 'stop_loss': 0.20},
    })

    # === EXECUTION SETTINGS ===
    dry_run: bool = True                  # Simulate trades without execution
    enable_signals: bool = True           # Enable advanced signal analysis
    slippage_bps: int = 100               # Default slippage in basis points (1%)

    # === CIRCUIT BREAKER ===
    circuit_breaker_enabled: bool = True
    max_consecutive_losses: int = 5       # Pause after N consecutive losses
    loss_cooldown_hours: float = 24.0     # Hours to pause after max losses
    max_drawdown_pct: float = 0.15        # Pause if drawdown exceeds 15%

    # === ADMIN ===
    admin_user_id: int = 8527368699       # Primary admin Telegram ID

    @classmethod
    def from_env(cls) -> "TradingConfig":
        """
        Create config from environment variables.

        Environment variables override defaults.
        """
        config = cls()

        # Load from environment with JARVIS_ prefix
        env_mappings = {
            "JARVIS_MAX_TRADE_USD": ("max_trade_usd", float),
            "JARVIS_MAX_DAILY_USD": ("max_daily_usd", float),
            "JARVIS_MAX_POSITION_PCT": ("max_position_pct", float),
            "JARVIS_MAX_POSITIONS": ("max_positions", int),
            "JARVIS_DRY_RUN": ("dry_run", lambda x: x.lower() in ("true", "1", "yes")),
            "JARVIS_RISK_LEVEL": ("default_risk_level", lambda x: RiskLevel[x.upper()]),
            "JARVIS_MIN_LIQUIDITY_USD": ("min_liquidity_usd", float),
            "JARVIS_SLIPPAGE_BPS": ("slippage_bps", int),
            "JARVIS_CIRCUIT_BREAKER": ("circuit_breaker_enabled", lambda x: x.lower() in ("true", "1", "yes")),
            "JARVIS_ADMIN_USER_ID": ("admin_user_id", int),
        }

        for env_var, (attr, converter) in env_mappings.items():
            value = os.environ.get(env_var)
            if value is not None:
                try:
                    setattr(config, attr, converter(value))
                    logger.info(f"Config override: {attr} = {getattr(config, attr)}")
                except (ValueError, KeyError) as e:
                    logger.warning(f"Invalid value for {env_var}: {value} ({e})")

        return config

    def get_position_size_pct(self, risk_level: Optional[RiskLevel] = None) -> float:
        """Get position size percentage for given risk level."""
        level = risk_level or self.default_risk_level
        return self.position_size_pct.get(level, 0.02)

    def get_tp_sl(self, grade: str) -> Dict[str, float]:
        """Get take profit and stop loss levels for sentiment grade."""
        return self.tp_sl_config.get(grade, {'take_profit': 0.10, 'stop_loss': 0.15})

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for serialization."""
        return {
            "max_trade_usd": self.max_trade_usd,
            "max_daily_usd": self.max_daily_usd,
            "max_position_pct": self.max_position_pct,
            "max_positions": self.max_positions,
            "dry_run": self.dry_run,
            "default_risk_level": self.default_risk_level.value,
            "min_liquidity_usd": self.min_liquidity_usd,
            "slippage_bps": self.slippage_bps,
            "circuit_breaker_enabled": self.circuit_breaker_enabled,
        }


# Singleton instance
_config_instance: Optional[TradingConfig] = None


def get_trading_config() -> TradingConfig:
    """Get the global trading configuration (singleton)."""
    global _config_instance
    if _config_instance is None:
        _config_instance = TradingConfig.from_env()
    return _config_instance


def reload_trading_config() -> TradingConfig:
    """Reload configuration from environment (useful for hot-reload)."""
    global _config_instance
    _config_instance = TradingConfig.from_env()
    return _config_instance


# Export for convenience
__all__ = [
    "TradingConfig",
    "RiskLevel",
    "get_trading_config",
    "reload_trading_config",
]
