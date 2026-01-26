"""
Adaptive Strategy Orchestrator for Regime-Based Trading.
=========================================================

Routes trading signals to regime-appropriate strategies and
automatically adjusts position sizing based on market conditions.

This is what makes AI trading agents different from static bots:
- Static bots use fixed rules
- AI agents adapt to market conditions

Features:
- Real-time regime detection
- Signal routing to active strategies only
- Position size adjustment based on regime
- Strategy compatibility checking
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.regime.strategy_mapping import StrategyMapping, get_strategy_mapping, REGIME_NAMES

logger = logging.getLogger(__name__)


@dataclass
class SignalRoutingResult:
    """Result of signal routing through the orchestrator."""
    active_strategies: List[str]
    blocked_strategies: List[str]
    regime: str
    confidence: float
    position_multiplier: float
    signal: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_strategies": self.active_strategies,
            "blocked_strategies": self.blocked_strategies,
            "regime": self.regime,
            "confidence": round(self.confidence, 4),
            "position_multiplier": round(self.position_multiplier, 4),
            "signal": self.signal,
            "timestamp": self.timestamp,
        }


class AdaptiveOrchestrator:
    """
    Adaptive strategy orchestrator that routes signals based on regime.

    Integrates with the existing regime detector and provides:
    - Market data updates for regime detection
    - Signal routing to compatible strategies
    - Position sizing adjustments
    - State persistence for continuity
    """

    def __init__(
        self,
        strategy_mapping: Optional[StrategyMapping] = None,
        regime_cooldown_seconds: float = 300.0,  # 5 min between regime changes
    ):
        """
        Initialize the adaptive orchestrator.

        Args:
            strategy_mapping: Strategy-to-regime mapping (or use default)
            regime_cooldown_seconds: Minimum time between regime changes
        """
        self._strategy_mapping = strategy_mapping or get_strategy_mapping()
        self._regime_cooldown = regime_cooldown_seconds

        # State
        self._current_regime: Optional[str] = None
        self._regime_confidence: float = 0.0
        self._last_regime_change: float = 0.0
        self._price_history: List[float] = []

        # Lazy load detector to avoid circular imports
        self._detector = None

        logger.info("Initialized AdaptiveOrchestrator")

    @property
    def detector(self):
        """Lazy load regime detector."""
        if self._detector is None:
            from core.analysis.regime_detector import RegimeDetector
            self._detector = RegimeDetector(lookback=20, smoothing=3)
        return self._detector

    @property
    def strategy_mapping(self) -> StrategyMapping:
        """Get strategy mapping."""
        return self._strategy_mapping

    @property
    def current_regime(self) -> Optional[str]:
        """Get current detected regime (simplified name)."""
        return self._current_regime

    async def update_market_data(
        self,
        prices: List[float],
        volumes: Optional[List[float]] = None,
    ):
        """
        Update market data and detect current regime.

        Args:
            prices: Recent price history (newest last)
            volumes: Optional volume data
        """
        if not prices or len(prices) < 20:
            logger.debug("Insufficient price data for regime detection")
            return

        # Store price history
        self._price_history = prices[-200:] if len(prices) > 200 else prices

        # Detect regime
        result = self.detector.detect(prices, volumes)

        # Simplify to 5-regime system
        new_regime = self._simplify_regime(result.regime.value)
        confidence = result.confidence

        # Check if regime changed
        if new_regime != self._current_regime:
            time_since_change = time.time() - self._last_regime_change

            if time_since_change >= self._regime_cooldown or self._current_regime is None:
                old_regime = self._current_regime
                self._current_regime = new_regime
                self._regime_confidence = confidence
                self._last_regime_change = time.time()

                logger.info(
                    f"Regime changed: {old_regime} -> {new_regime} "
                    f"(confidence: {confidence:.1%})"
                )

                # Trigger notification (fire and forget)
                asyncio.create_task(self._notify_regime_change(old_regime, new_regime, confidence))
            else:
                logger.debug(
                    f"Regime change suppressed (cooldown): {self._current_regime} -> {new_regime}"
                )
        else:
            # Update confidence
            self._regime_confidence = confidence

    async def route_signal(self, signal: Dict[str, Any]) -> SignalRoutingResult:
        """
        Route a trading signal to appropriate strategies.

        Only routes to strategies that are valid for the current regime.

        Args:
            signal: Trading signal dict with token, action, confidence, etc.

        Returns:
            SignalRoutingResult with active and blocked strategies
        """
        regime = self._current_regime or "ranging"

        # Get all strategies
        all_strategies = self._strategy_mapping.get_all_strategies()

        # Filter to regime-compatible strategies
        active = []
        blocked = []

        for strategy in all_strategies:
            if self._strategy_mapping.is_strategy_valid_for_regime(strategy, regime):
                active.append(strategy)
            else:
                blocked.append(strategy)

        # Calculate position multiplier
        position_mult = self._strategy_mapping.get_position_multiplier(regime)

        return SignalRoutingResult(
            active_strategies=active,
            blocked_strategies=blocked,
            regime=regime,
            confidence=self._regime_confidence,
            position_multiplier=position_mult,
            signal=signal,
        )

    def get_active_strategies(self) -> List[str]:
        """Get list of currently active strategies based on regime."""
        regime = self._current_regime or "ranging"
        return self._strategy_mapping.get_strategies_for_regime(regime)

    def calculate_position_size(
        self,
        base_size: float,
        strategy: Optional[str] = None,
    ) -> float:
        """
        Calculate adjusted position size based on regime and strategy.

        Args:
            base_size: Base position size in USD
            strategy: Optional strategy name for compatibility check

        Returns:
            Adjusted position size
        """
        regime = self._current_regime or "ranging"

        if strategy:
            # Use combined multiplier
            multiplier = self._strategy_mapping.get_strategy_position_multiplier(
                strategy, regime
            )
        else:
            # Use regime multiplier only
            multiplier = self._strategy_mapping.get_position_multiplier(regime)

        # Cap multiplier at reasonable bounds
        multiplier = max(0.05, min(1.5, multiplier))

        return base_size * multiplier

    def _simplify_regime(self, regime_value: str) -> str:
        """
        Map detailed regime names to simplified 5-regime system.

        Args:
            regime_value: Detailed regime name from detector

        Returns:
            Simplified regime name (trending, ranging, high_vol, quiet, crash)
        """
        regime_value = regime_value.lower()

        # Direct matches
        if regime_value in REGIME_NAMES:
            return regime_value

        # Map detailed regimes
        mappings = {
            "trending_up": "trending",
            "trending_down": "crash",  # Down trend is defensive
            "volatile": "high_vol",
            "recovery": "quiet",
            "low_volatility": "quiet",
            "medium_volatility": "ranging",
            "high_volatility": "high_vol",
            "extreme_volatility": "crash",
        }

        return mappings.get(regime_value, "ranging")

    def get_state(self) -> Dict[str, Any]:
        """Get current orchestrator state for persistence."""
        return {
            "current_regime": self._current_regime,
            "regime_confidence": self._regime_confidence,
            "last_regime_change": self._last_regime_change,
            "last_update": time.time(),
        }

    def restore_state(self, state: Dict[str, Any]):
        """Restore orchestrator state from persistence."""
        self._current_regime = state.get("current_regime")
        self._regime_confidence = state.get("regime_confidence", 0.0)
        self._last_regime_change = state.get("last_regime_change", 0.0)

        logger.info(f"Restored orchestrator state: regime={self._current_regime}")

    async def _notify_regime_change(
        self,
        from_regime: Optional[str],
        to_regime: str,
        confidence: float,
    ):
        """Send notification about regime change."""
        try:
            from core.regime.notifications import get_regime_notifier

            notifier = get_regime_notifier()
            active = self.get_active_strategies()

            await notifier.notify_regime_change(
                from_regime=from_regime or "unknown",
                to_regime=to_regime,
                confidence=confidence,
                active_strategies=active,
            )
        except Exception as e:
            logger.debug(f"Regime notification error: {e}")

    def get_regime_summary(self) -> Dict[str, Any]:
        """Get summary of current regime state."""
        regime = self._current_regime or "unknown"
        active = self.get_active_strategies() if self._current_regime else []
        multiplier = self._strategy_mapping.get_position_multiplier(regime) if self._current_regime else 0.5

        return {
            "regime": regime,
            "confidence": round(self._regime_confidence, 4),
            "active_strategies": active,
            "position_multiplier": round(multiplier, 4),
            "description": self._strategy_mapping.get_regime_description(regime),
            "last_change": datetime.fromtimestamp(
                self._last_regime_change, tz=timezone.utc
            ).isoformat() if self._last_regime_change else None,
        }


# Singleton
_adaptive_orchestrator: Optional[AdaptiveOrchestrator] = None


def get_adaptive_orchestrator() -> AdaptiveOrchestrator:
    """Get singleton adaptive orchestrator instance."""
    global _adaptive_orchestrator
    if _adaptive_orchestrator is None:
        _adaptive_orchestrator = AdaptiveOrchestrator()
    return _adaptive_orchestrator


__all__ = [
    "AdaptiveOrchestrator",
    "SignalRoutingResult",
    "get_adaptive_orchestrator",
]
