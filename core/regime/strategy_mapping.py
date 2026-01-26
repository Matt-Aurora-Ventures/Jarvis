"""
Strategy-to-Regime Mapping for Adaptive Trading.
=================================================

Maps trading strategies to their appropriate market regimes.
This is the core of regime-adaptive strategy orchestration.

5 Simplified Regimes:
- trending: Clear directional movement (up or down)
- ranging: Sideways, range-bound market
- high_vol: High volatility without clear direction
- quiet: Low activity, minimal volatility
- crash: Rapid decline with high volatility

Each regime has:
- Compatible strategies
- Position size multiplier
- Risk parameters
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any

logger = logging.getLogger(__name__)

# The 5 simplified regime names
REGIME_NAMES = ["trending", "ranging", "high_vol", "quiet", "crash"]


@dataclass
class StrategyConfig:
    """Configuration for a trading strategy."""
    name: str
    compatible_regimes: List[str]
    description: str
    default_position_mult: float = 1.0
    parameters: Dict[str, Any] = field(default_factory=dict)


# Default strategy configurations
DEFAULT_STRATEGIES: Dict[str, StrategyConfig] = {
    "momentum": StrategyConfig(
        name="momentum",
        compatible_regimes=["trending"],
        description="Follow momentum in trending markets",
        default_position_mult=1.2,
        parameters={
            "entry_type": "breakout",
            "stop_loss_type": "trailing",
            "trailing_pct": 0.05,
        }
    ),
    "trend_following": StrategyConfig(
        name="trend_following",
        compatible_regimes=["trending"],
        description="Ride established trends with tight risk management",
        default_position_mult=1.1,
        parameters={
            "entry_type": "pullback",
            "stop_loss_type": "atr_based",
            "atr_mult": 2.0,
        }
    ),
    "mean_reversion": StrategyConfig(
        name="mean_reversion",
        compatible_regimes=["ranging"],
        description="Buy support, sell resistance in range-bound markets",
        default_position_mult=1.0,
        parameters={
            "entry_type": "bb_bounce",
            "stop_loss_type": "fixed",
            "stop_pct": 0.03,
        }
    ),
    "grid_trading": StrategyConfig(
        name="grid_trading",
        compatible_regimes=["ranging"],
        description="Place grid of orders in defined range",
        default_position_mult=0.8,
        parameters={
            "grid_levels": 10,
            "range_pct": 0.10,
        }
    ),
    "vol_arb": StrategyConfig(
        name="vol_arb",
        compatible_regimes=["high_vol"],
        description="Exploit volatility spikes for quick profits",
        default_position_mult=0.6,
        parameters={
            "entry_type": "vol_spike",
            "stop_loss_type": "time_based",
            "max_hold_hours": 4,
        }
    ),
    "volatility_breakout": StrategyConfig(
        name="volatility_breakout",
        compatible_regimes=["high_vol"],
        description="Trade volatility breakouts with tight stops",
        default_position_mult=0.5,
        parameters={
            "entry_type": "vol_expansion",
            "stop_loss_type": "atr_based",
            "atr_mult": 3.0,
        }
    ),
    "reduced_exposure": StrategyConfig(
        name="reduced_exposure",
        compatible_regimes=["high_vol"],
        description="Minimal positions during high volatility",
        default_position_mult=0.3,
        parameters={
            "max_positions": 2,
            "tight_stops": True,
        }
    ),
    "accumulation": StrategyConfig(
        name="accumulation",
        compatible_regimes=["quiet"],
        description="Slowly accumulate positions during quiet periods",
        default_position_mult=0.7,
        parameters={
            "entry_type": "dca",
            "interval_hours": 24,
        }
    ),
    "dca": StrategyConfig(
        name="dca",
        compatible_regimes=["quiet"],
        description="Dollar cost averaging during low activity",
        default_position_mult=0.6,
        parameters={
            "entry_type": "scheduled",
            "amount_per_interval": 0.1,
        }
    ),
    "passive": StrategyConfig(
        name="passive",
        compatible_regimes=["quiet"],
        description="Hold existing positions, minimal new activity",
        default_position_mult=0.5,
        parameters={
            "no_new_positions": True,
        }
    ),
    "cash": StrategyConfig(
        name="cash",
        compatible_regimes=["crash"],
        description="Move to cash/stables during crash",
        default_position_mult=0.1,
        parameters={
            "exit_existing": True,
            "no_new_longs": True,
        }
    ),
    "defensive": StrategyConfig(
        name="defensive",
        compatible_regimes=["crash"],
        description="Preserve capital, tight stops on any positions",
        default_position_mult=0.2,
        parameters={
            "stop_loss_type": "fixed",
            "stop_pct": 0.02,
            "no_new_positions": True,
        }
    ),
    "capital_preservation": StrategyConfig(
        name="capital_preservation",
        compatible_regimes=["crash"],
        description="Focus on capital preservation above all",
        default_position_mult=0.05,
        parameters={
            "max_drawdown": 0.05,
            "exit_on_drawdown": True,
        }
    ),
}

# Position multipliers per regime
REGIME_POSITION_MULTIPLIERS = {
    "trending": 1.0,      # Normal sizing
    "ranging": 0.8,       # Slightly reduced
    "high_vol": 0.5,      # Reduced due to risk
    "quiet": 0.6,         # Reduced due to low opportunity
    "crash": 0.2,         # Minimal exposure
}


class StrategyMapping:
    """
    Maps trading strategies to appropriate market regimes.

    Provides:
    - Strategy lookup by regime
    - Compatibility checking
    - Position size multipliers
    """

    def __init__(
        self,
        strategies: Optional[Dict[str, StrategyConfig]] = None,
        custom_multipliers: Optional[Dict[str, float]] = None,
    ):
        """
        Initialize strategy mapping.

        Args:
            strategies: Custom strategy configurations (or use defaults)
            custom_multipliers: Custom regime position multipliers
        """
        self._strategies = strategies or dict(DEFAULT_STRATEGIES)
        self._multipliers = custom_multipliers or dict(REGIME_POSITION_MULTIPLIERS)

        # Build reverse mapping: regime -> strategies
        self._regime_strategies: Dict[str, List[str]] = {
            regime: [] for regime in REGIME_NAMES
        }
        for name, config in self._strategies.items():
            for regime in config.compatible_regimes:
                if regime in self._regime_strategies:
                    self._regime_strategies[regime].append(name)

        logger.info(f"Initialized StrategyMapping with {len(self._strategies)} strategies")

    def get_strategies_for_regime(
        self,
        regime: str,
        ordered: bool = False
    ) -> List[str]:
        """
        Get strategies compatible with a regime.

        Args:
            regime: Regime name (trending, ranging, high_vol, quiet, crash)
            ordered: If True, return in priority order

        Returns:
            List of strategy names
        """
        regime = self._normalize_regime(regime)
        strategies = list(self._regime_strategies.get(regime, []))

        if ordered:
            # Sort by position multiplier (higher = higher priority)
            strategies.sort(
                key=lambda s: self._strategies[s].default_position_mult,
                reverse=True
            )

        return strategies

    def is_strategy_valid_for_regime(self, strategy: str, regime: str) -> bool:
        """
        Check if a strategy is valid for a regime.

        Args:
            strategy: Strategy name
            regime: Regime name

        Returns:
            True if strategy is compatible with regime
        """
        regime = self._normalize_regime(regime)
        config = self._strategies.get(strategy)

        if not config:
            return False

        return regime in config.compatible_regimes

    def get_all_strategies(self) -> List[str]:
        """Get all registered strategy names."""
        return list(self._strategies.keys())

    def get_strategy_config(self, strategy: str) -> Optional[StrategyConfig]:
        """Get configuration for a strategy."""
        return self._strategies.get(strategy)

    def get_position_multiplier(self, regime: str) -> float:
        """
        Get position size multiplier for a regime.

        Args:
            regime: Regime name

        Returns:
            Position size multiplier (0.0 - 1.5)
        """
        regime = self._normalize_regime(regime)
        return self._multipliers.get(regime, 0.5)

    def get_strategy_position_multiplier(
        self,
        strategy: str,
        regime: str
    ) -> float:
        """
        Get combined position multiplier for strategy in regime.

        Args:
            strategy: Strategy name
            regime: Current regime

        Returns:
            Combined position multiplier
        """
        regime_mult = self.get_position_multiplier(regime)
        config = self._strategies.get(strategy)

        if not config:
            return regime_mult * 0.5  # Unknown strategy penalty

        if not self.is_strategy_valid_for_regime(strategy, regime):
            # Strategy not compatible with regime - heavy penalty
            return regime_mult * 0.2

        # Compatible: use both multipliers
        return regime_mult * config.default_position_mult

    def add_strategy(self, config: StrategyConfig):
        """
        Add a new strategy configuration.

        Args:
            config: Strategy configuration
        """
        self._strategies[config.name] = config

        for regime in config.compatible_regimes:
            if regime in self._regime_strategies:
                if config.name not in self._regime_strategies[regime]:
                    self._regime_strategies[regime].append(config.name)

        logger.info(f"Added strategy: {config.name}")

    def _normalize_regime(self, regime: str) -> str:
        """
        Normalize regime name to one of 5 standard regimes.

        Maps detailed regime names to simplified 5-regime system.
        """
        regime = regime.lower()

        # Direct match
        if regime in REGIME_NAMES:
            return regime

        # Map variations
        mappings = {
            "trending_up": "trending",
            "trending_down": "crash",  # Down trend is treated as crash-like
            "volatile": "high_vol",
            "recovery": "quiet",  # Recovery is quiet with upward bias
            "low_vol": "quiet",
            "extreme_vol": "high_vol",
            "sideways": "ranging",
        }

        return mappings.get(regime, "ranging")  # Default to ranging

    def get_regime_description(self, regime: str) -> str:
        """Get description for a regime."""
        regime = self._normalize_regime(regime)
        descriptions = {
            "trending": "Clear directional price movement",
            "ranging": "Sideways, range-bound price action",
            "high_vol": "High volatility without clear direction",
            "quiet": "Low activity, minimal price movement",
            "crash": "Rapid decline with elevated volatility",
        }
        return descriptions.get(regime, "Unknown regime")

    def to_dict(self) -> Dict[str, Any]:
        """Convert mapping to dictionary."""
        return {
            "strategies": {
                name: {
                    "name": config.name,
                    "compatible_regimes": config.compatible_regimes,
                    "description": config.description,
                    "position_mult": config.default_position_mult,
                    "parameters": config.parameters,
                }
                for name, config in self._strategies.items()
            },
            "multipliers": self._multipliers,
        }


# Singleton
_strategy_mapping: Optional[StrategyMapping] = None


def get_strategy_mapping() -> StrategyMapping:
    """Get singleton strategy mapping instance."""
    global _strategy_mapping
    if _strategy_mapping is None:
        _strategy_mapping = StrategyMapping()
    return _strategy_mapping


__all__ = [
    "StrategyMapping",
    "StrategyConfig",
    "REGIME_NAMES",
    "DEFAULT_STRATEGIES",
    "REGIME_POSITION_MULTIPLIERS",
    "get_strategy_mapping",
]
