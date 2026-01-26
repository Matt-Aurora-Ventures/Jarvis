"""
Regime-Adaptive Strategy Orchestration System.
==============================================

Provides institutional-grade regime awareness for trading:
- 5 market regimes: trending, ranging, high_vol, quiet, crash
- Strategy routing based on current regime
- Automatic position sizing adjustments
- Telegram notifications for regime changes

Components:
- StrategyMapping: Maps strategies to appropriate regimes
- AdaptiveOrchestrator: Routes signals to regime-appropriate strategies
- RegimeNotifier: Sends Telegram notifications on regime changes

Usage:
    from core.regime import AdaptiveOrchestrator

    orchestrator = AdaptiveOrchestrator()
    await orchestrator.update_market_data(prices)

    # Route signals based on regime
    result = await orchestrator.route_signal(signal)
    print(f"Active strategies: {result.active_strategies}")
"""

from core.regime.strategy_mapping import (
    StrategyMapping,
    REGIME_NAMES,
)
from core.regime.adaptive_orchestrator import (
    AdaptiveOrchestrator,
    SignalRoutingResult,
    get_adaptive_orchestrator,
)
from core.regime.notifications import (
    RegimeNotifier,
    send_regime_notification,
)

__all__ = [
    # Strategy Mapping
    "StrategyMapping",
    "REGIME_NAMES",
    # Adaptive Orchestrator
    "AdaptiveOrchestrator",
    "SignalRoutingResult",
    "get_adaptive_orchestrator",
    # Notifications
    "RegimeNotifier",
    "send_regime_notification",
]
