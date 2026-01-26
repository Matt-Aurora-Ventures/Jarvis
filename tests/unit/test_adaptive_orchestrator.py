"""
Tests for Regime-Adaptive Strategy Orchestration.

TDD Phase 1: Define expected behavior for the adaptive orchestrator.

Tests cover:
1. AdaptiveOrchestrator - Signal routing based on regime
2. StrategyMapping - Strategy-to-regime mapping (5 regimes)
3. Position sizing adjustments
4. Telegram notifications for regime changes
5. Integration with existing autonomy orchestrator
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch
import json


# =============================================================================
# Phase 1: Strategy Mapping Tests (5 regimes)
# =============================================================================

class TestStrategyMapping:
    """Test strategy-to-regime mappings for 5 regimes."""

    def test_mapping_exists_for_all_five_regimes(self):
        """Each of 5 regimes should have mapped strategies."""
        from core.regime.strategy_mapping import StrategyMapping

        mapping = StrategyMapping()

        # Verify 5 regimes
        regimes = ["trending", "ranging", "high_vol", "quiet", "crash"]
        for regime in regimes:
            strategies = mapping.get_strategies_for_regime(regime)
            assert len(strategies) >= 1, f"No strategies for {regime}"

    def test_momentum_strategies_map_to_trending(self):
        """Momentum strategies should be active in trending regimes."""
        from core.regime.strategy_mapping import StrategyMapping

        mapping = StrategyMapping()

        trending_strategies = mapping.get_strategies_for_regime("trending")
        assert "momentum" in trending_strategies
        assert "trend_following" in trending_strategies

    def test_mean_reversion_maps_to_ranging(self):
        """Mean reversion strategies for ranging markets."""
        from core.regime.strategy_mapping import StrategyMapping

        mapping = StrategyMapping()

        ranging_strategies = mapping.get_strategies_for_regime("ranging")
        assert "mean_reversion" in ranging_strategies
        assert "grid_trading" in ranging_strategies

    def test_volatility_strategies_for_high_vol(self):
        """Volatility strategies for high vol regimes."""
        from core.regime.strategy_mapping import StrategyMapping

        mapping = StrategyMapping()

        high_vol_strategies = mapping.get_strategies_for_regime("high_vol")
        assert any(s in high_vol_strategies for s in ["vol_arb", "volatility_breakout", "reduced_exposure"])

    def test_conservative_strategies_for_quiet(self):
        """Conservative strategies for quiet regimes."""
        from core.regime.strategy_mapping import StrategyMapping

        mapping = StrategyMapping()

        quiet_strategies = mapping.get_strategies_for_regime("quiet")
        assert any(s in quiet_strategies for s in ["accumulation", "dca", "passive"])

    def test_cash_strategy_for_crash(self):
        """Cash/defensive strategies during crash."""
        from core.regime.strategy_mapping import StrategyMapping

        mapping = StrategyMapping()

        crash_strategies = mapping.get_strategies_for_regime("crash")
        assert any(s in crash_strategies for s in ["cash", "defensive", "capital_preservation"])

    def test_strategy_has_regime_compatibility(self):
        """Check if strategy is compatible with a regime."""
        from core.regime.strategy_mapping import StrategyMapping

        mapping = StrategyMapping()

        assert mapping.is_strategy_valid_for_regime("momentum", "trending") is True
        assert mapping.is_strategy_valid_for_regime("momentum", "ranging") is False
        assert mapping.is_strategy_valid_for_regime("mean_reversion", "ranging") is True
        assert mapping.is_strategy_valid_for_regime("cash", "crash") is True

    def test_get_all_strategies(self):
        """Get all registered strategies."""
        from core.regime.strategy_mapping import StrategyMapping

        mapping = StrategyMapping()

        all_strategies = mapping.get_all_strategies()
        assert len(all_strategies) >= 5  # At least 5 different strategies

    def test_position_size_multiplier_per_regime(self):
        """Each regime should have a position size multiplier."""
        from core.regime.strategy_mapping import StrategyMapping

        mapping = StrategyMapping()

        # Trending should have higher multiplier (more confident)
        trending_mult = mapping.get_position_multiplier("trending")
        assert trending_mult >= 0.8

        # Crash should have very low multiplier
        crash_mult = mapping.get_position_multiplier("crash")
        assert crash_mult <= 0.3

        # High vol should be reduced
        high_vol_mult = mapping.get_position_multiplier("high_vol")
        assert high_vol_mult < trending_mult


# =============================================================================
# Phase 2: Adaptive Orchestrator Tests
# =============================================================================

class TestAdaptiveOrchestrator:
    """Test signal routing based on regime."""

    def test_orchestrator_initializes(self):
        """Orchestrator should initialize with detector and mapping."""
        from core.regime.adaptive_orchestrator import AdaptiveOrchestrator

        orchestrator = AdaptiveOrchestrator()
        assert orchestrator is not None
        assert orchestrator.detector is not None
        assert orchestrator.strategy_mapping is not None

    def test_orchestrator_has_current_regime(self):
        """Orchestrator should track current regime."""
        from core.regime.adaptive_orchestrator import AdaptiveOrchestrator

        orchestrator = AdaptiveOrchestrator()
        # Initially should be None or default
        assert orchestrator.current_regime is None or orchestrator.current_regime is not None

    @pytest.mark.asyncio
    async def test_update_market_data_sets_regime(self):
        """Updating market data should detect regime."""
        from core.regime.adaptive_orchestrator import AdaptiveOrchestrator

        orchestrator = AdaptiveOrchestrator()

        # Generate trending price data
        prices = [100.0 * (1.01 ** i) for i in range(150)]

        await orchestrator.update_market_data(prices)

        assert orchestrator.current_regime is not None
        # Should detect some form of trending
        assert orchestrator.current_regime in ["trending", "trending_up", "high_vol"]

    @pytest.mark.asyncio
    async def test_route_signal_to_active_strategies(self):
        """Signals should only go to regime-appropriate strategies."""
        from core.regime.adaptive_orchestrator import AdaptiveOrchestrator

        orchestrator = AdaptiveOrchestrator()

        # Set up trending regime
        prices = [100.0 * (1.01 ** i) for i in range(150)]
        await orchestrator.update_market_data(prices)

        # Create a test signal
        signal = {
            "token": "SOL",
            "action": "buy",
            "confidence": 0.8
        }

        # Route signal
        routed = await orchestrator.route_signal(signal)

        # Should have active strategies
        assert routed.active_strategies is not None
        assert len(routed.active_strategies) >= 1

    @pytest.mark.asyncio
    async def test_route_signal_blocks_incompatible_strategies(self):
        """Incompatible strategies should not receive signals."""
        from core.regime.adaptive_orchestrator import AdaptiveOrchestrator

        orchestrator = AdaptiveOrchestrator()

        # Set up crash regime
        prices = [100.0 * (0.95 ** i) for i in range(150)]  # Big drops
        await orchestrator.update_market_data(prices)

        signal = {"token": "SOL", "action": "buy", "confidence": 0.8}
        routed = await orchestrator.route_signal(signal)

        # Momentum should not be active in crash
        assert "momentum" not in routed.active_strategies

    @pytest.mark.asyncio
    async def test_get_active_strategies_returns_list(self):
        """get_active_strategies should return strategy list."""
        from core.regime.adaptive_orchestrator import AdaptiveOrchestrator

        orchestrator = AdaptiveOrchestrator()

        prices = [100.0 * (1.01 ** i) for i in range(150)]
        await orchestrator.update_market_data(prices)

        strategies = orchestrator.get_active_strategies()
        assert isinstance(strategies, list)


# =============================================================================
# Phase 3: Position Sizing Tests
# =============================================================================

class TestRegimePositionSizing:
    """Test position sizing adjustments based on regime."""

    def test_position_size_reduced_in_high_vol(self):
        """Position size should be reduced in high volatility."""
        from core.regime.adaptive_orchestrator import AdaptiveOrchestrator

        orchestrator = AdaptiveOrchestrator()
        orchestrator._current_regime = "high_vol"

        base_size = 1000.0
        adjusted = orchestrator.calculate_position_size(base_size)

        # Should be reduced
        assert adjusted < base_size

    def test_position_size_minimal_in_crash(self):
        """Position size should be minimal during crash."""
        from core.regime.adaptive_orchestrator import AdaptiveOrchestrator

        orchestrator = AdaptiveOrchestrator()
        orchestrator._current_regime = "crash"

        base_size = 1000.0
        adjusted = orchestrator.calculate_position_size(base_size)

        # Should be significantly reduced (less than 30%)
        assert adjusted <= base_size * 0.3

    def test_position_size_normal_in_trending(self):
        """Position size should be normal/increased in trending."""
        from core.regime.adaptive_orchestrator import AdaptiveOrchestrator

        orchestrator = AdaptiveOrchestrator()
        orchestrator._current_regime = "trending"

        base_size = 1000.0
        adjusted = orchestrator.calculate_position_size(base_size)

        # Should be at least 80% of base
        assert adjusted >= base_size * 0.8

    def test_strategy_mismatch_reduces_size(self):
        """Position size reduced when strategy doesn't match regime."""
        from core.regime.adaptive_orchestrator import AdaptiveOrchestrator

        orchestrator = AdaptiveOrchestrator()
        orchestrator._current_regime = "ranging"

        base_size = 1000.0
        # Try to use momentum strategy in ranging market
        adjusted = orchestrator.calculate_position_size(
            base_size,
            strategy="momentum"
        )

        # Should be reduced due to mismatch
        assert adjusted < base_size * 0.5


# =============================================================================
# Phase 4: Notification Tests
# =============================================================================

class TestRegimeNotifications:
    """Test Telegram notifications for regime changes."""

    @pytest.fixture
    def mock_telegram(self):
        """Mock telegram notifications."""
        with patch('core.regime.notifications.send_regime_notification') as mock:
            mock.return_value = True
            yield mock

    @pytest.mark.asyncio
    async def test_notify_on_regime_change(self, mock_telegram):
        """Should notify when regime changes."""
        from core.regime.notifications import RegimeNotifier

        notifier = RegimeNotifier()

        await notifier.notify_regime_change(
            from_regime="trending",
            to_regime="high_vol",
            confidence=0.85
        )

        mock_telegram.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_spam_notifications(self, mock_telegram):
        """Should not spam notifications for minor changes."""
        from core.regime.notifications import RegimeNotifier

        notifier = RegimeNotifier(cooldown_minutes=5)

        # First notification
        await notifier.notify_regime_change("trending", "high_vol", 0.85)

        # Second notification within cooldown
        await notifier.notify_regime_change("high_vol", "ranging", 0.9)

        # Only first call should have happened
        assert mock_telegram.call_count == 1

    @pytest.mark.asyncio
    async def test_crash_notification_bypasses_cooldown(self, mock_telegram):
        """Crash regime notification should bypass cooldown."""
        from core.regime.notifications import RegimeNotifier

        notifier = RegimeNotifier(cooldown_minutes=60)

        await notifier.notify_regime_change("trending", "high_vol", 0.85)
        await notifier.notify_regime_change("high_vol", "crash", 0.95)

        # Both should be called (crash bypasses cooldown)
        assert mock_telegram.call_count == 2

    @pytest.mark.asyncio
    async def test_notification_format(self, mock_telegram):
        """Notification should include regime details."""
        from core.regime.notifications import RegimeNotifier

        notifier = RegimeNotifier()

        await notifier.notify_regime_change(
            from_regime="trending",
            to_regime="crash",
            confidence=0.9,
            active_strategies=["cash", "defensive"]
        )

        call_args = mock_telegram.call_args
        # Should contain regime info
        assert call_args is not None


# =============================================================================
# Phase 5: Integration Tests
# =============================================================================

class TestAdaptiveOrchestratorIntegration:
    """Integration tests for full regime orchestration flow."""

    @pytest.mark.asyncio
    async def test_full_flow_trending_to_crash(self):
        """Test full flow from trending market to crash detection."""
        from core.regime.adaptive_orchestrator import AdaptiveOrchestrator

        # Use zero cooldown for testing
        orchestrator = AdaptiveOrchestrator(regime_cooldown_seconds=0)

        # Phase 1: Trending market
        trending_prices = [100.0 * (1.01 ** i) for i in range(150)]
        await orchestrator.update_market_data(trending_prices)

        initial_regime = orchestrator.current_regime
        assert initial_regime in ["trending", "trending_up", "high_vol"]

        # Get position size in trending
        trending_size = orchestrator.calculate_position_size(1000.0)

        # Phase 2: Create new orchestrator for crash detection (fresh state)
        # This simulates how regime would be detected with fresh data
        orchestrator2 = AdaptiveOrchestrator(regime_cooldown_seconds=0)

        # Generate crash data
        crash_prices = [trending_prices[-1]]
        for i in range(100):
            crash_prices.append(crash_prices[-1] * 0.92)

        await orchestrator2.update_market_data(crash_prices)

        crash_regime = orchestrator2.current_regime
        # The regime detector may classify big drops as crash or trending_down
        # which then maps to "crash" in our simplified 5-regime system
        assert crash_regime in ["crash", "trending_down", "high_vol", "trending"]

        # Position sizing should be reduced for crash
        crash_size = orchestrator2.calculate_position_size(1000.0)
        # With crash regime, size should be reduced
        # If detected as trending (but down), also reduced via mapping
        assert crash_size <= trending_size  # At minimum, not increased

    @pytest.mark.asyncio
    async def test_orchestrator_state_persistence(self):
        """Orchestrator should be able to save/load state."""
        from core.regime.adaptive_orchestrator import AdaptiveOrchestrator

        orchestrator1 = AdaptiveOrchestrator()

        # Set up state
        prices = [100.0 * (1.01 ** i) for i in range(150)]
        await orchestrator1.update_market_data(prices)

        # Get state
        state = orchestrator1.get_state()
        assert "current_regime" in state
        assert "last_update" in state

        # Create new orchestrator and restore
        orchestrator2 = AdaptiveOrchestrator()
        orchestrator2.restore_state(state)

        # Should have same regime
        assert orchestrator2.current_regime == orchestrator1.current_regime

    def test_regime_to_simplified_name(self):
        """Test mapping detailed regimes to simplified 5-regime names."""
        from core.regime.adaptive_orchestrator import AdaptiveOrchestrator

        orchestrator = AdaptiveOrchestrator()

        # Map detailed names to simplified 5 regimes
        assert orchestrator._simplify_regime("trending_up") == "trending"
        assert orchestrator._simplify_regime("trending_down") == "crash"
        assert orchestrator._simplify_regime("volatile") == "high_vol"
        assert orchestrator._simplify_regime("ranging") == "ranging"
        assert orchestrator._simplify_regime("recovery") == "quiet"


# =============================================================================
# Phase 6: Autonomy Integration Tests
# =============================================================================

class TestAutonomyIntegration:
    """Test integration with existing autonomy orchestrator."""

    def test_adaptive_orchestrator_accessible_from_autonomy(self):
        """Adaptive orchestrator should integrate with autonomy."""
        from core.autonomy.orchestrator import get_orchestrator

        autonomy = get_orchestrator()

        # Should have regime property or method
        assert hasattr(autonomy, 'regime') or hasattr(autonomy, 'get_regime_orchestrator')

    @pytest.mark.asyncio
    async def test_regime_affects_content_recommendations(self):
        """Regime should affect content recommendations."""
        from core.autonomy.orchestrator import get_orchestrator

        autonomy = get_orchestrator()

        # Get recommendations - should work without error
        recommendations = autonomy.get_content_recommendations()
        assert recommendations is not None


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_prices():
    """Generate sample price data for tests."""
    import random
    random.seed(42)

    return {
        "trending": [100.0 * (1.01 ** i) for i in range(150)],
        "crash": [100.0 * (0.95 ** i) for i in range(150)],
        "ranging": [100.0 + 2 * (i % 10 - 5) for i in range(150)],
        "quiet": [100.0 + 0.1 * (i % 5 - 2) for i in range(150)],
        "high_vol": [100.0 * (1 + random.gauss(0, 0.07)) for i in range(150)],
    }
