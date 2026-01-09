"""
Tests for trading plugin.

Tests cover:
- Plugin lifecycle
- PAE component registration
- Provider functionality
- Action functionality
- Evaluator functionality
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Import plugin components directly for testing
from plugins.trading.main import (
    TradingPlugin,
    PriceFeedProvider,
    PositionStatusProvider,
    WalletBalanceProvider,
    ExecuteSwapAction,
    CreateExitIntentAction,
    RiskCheckEvaluator,
    OpportunityScoreEvaluator,
)
from lifeos.pae.base import EvaluationResult


# =============================================================================
# Test Providers
# =============================================================================

class TestPriceFeedProvider:
    """Test price feed provider."""

    @pytest.mark.asyncio
    async def test_requires_token(self):
        """Should require token in query."""
        provider = PriceFeedProvider("test", {})

        with pytest.raises(ValueError):
            await provider.provide({})

    @pytest.mark.asyncio
    async def test_returns_price_data(self):
        """Should return price data structure."""
        provider = PriceFeedProvider("test", {})

        # Without real price sources, should return fallback
        result = await provider.provide({"token": "So11111111111111111111111111111111111111112"})

        assert "token" in result
        assert "price_usd" in result
        assert "source" in result
        assert "timestamp" in result


class TestPositionStatusProvider:
    """Test position status provider."""

    @pytest.mark.asyncio
    async def test_returns_positions(self):
        """Should return positions structure."""
        provider = PositionStatusProvider("test", {})

        result = await provider.provide({})

        assert "positions" in result
        assert "count" in result
        assert "timestamp" in result


class TestWalletBalanceProvider:
    """Test wallet balance provider."""

    @pytest.mark.asyncio
    async def test_returns_balance(self):
        """Should return balance structure."""
        provider = WalletBalanceProvider("test", {})

        result = await provider.provide({})

        assert "sol_balance" in result
        assert "tokens" in result


# =============================================================================
# Test Actions
# =============================================================================

class TestExecuteSwapAction:
    """Test execute swap action."""

    @pytest.mark.asyncio
    async def test_requires_params(self):
        """Should require input_mint, output_mint, and amount."""
        action = ExecuteSwapAction("test", {}, paper_mode=True)

        with pytest.raises(ValueError):
            await action.execute({})

    @pytest.mark.asyncio
    async def test_paper_mode_swap(self):
        """Should simulate swap in paper mode."""
        action = ExecuteSwapAction("test", {}, paper_mode=True)

        result = await action.execute({
            "input_mint": "So11111111111111111111111111111111111111112",
            "output_mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "amount": 1000000,
        })

        assert result["success"] is True
        assert result["paper_mode"] is True
        assert result["simulated"] is True

    def test_requires_confirmation_real_mode(self):
        """Should require confirmation in real mode."""
        action = ExecuteSwapAction("test", {}, paper_mode=False)

        assert action.requires_confirmation is True

    def test_no_confirmation_paper_mode(self):
        """Should not require confirmation in paper mode."""
        action = ExecuteSwapAction("test", {}, paper_mode=True)

        assert action.requires_confirmation is False


class TestCreateExitIntentAction:
    """Test create exit intent action."""

    @pytest.mark.asyncio
    async def test_requires_position_id(self):
        """Should require position_id."""
        action = CreateExitIntentAction("test", {})

        with pytest.raises(ValueError):
            await action.execute({})

    @pytest.mark.asyncio
    async def test_handles_missing_module(self):
        """Should handle missing exit_intents module."""
        action = CreateExitIntentAction("test", {})

        result = await action.execute({"position_id": "test123"})

        # Should either succeed or return error about missing module
        assert "success" in result


# =============================================================================
# Test Evaluators
# =============================================================================

class TestRiskCheckEvaluator:
    """Test risk check evaluator."""

    @pytest.mark.asyncio
    async def test_rejects_missing_portfolio(self):
        """Should reject when no portfolio value."""
        evaluator = RiskCheckEvaluator("test", {})

        result = await evaluator.evaluate({
            "trade": {"amount": 1000},
            "portfolio_value": 0,
        })

        assert result.decision is False

    @pytest.mark.asyncio
    async def test_rejects_oversized_position(self):
        """Should reject oversized positions."""
        evaluator = RiskCheckEvaluator("test", {})

        result = await evaluator.evaluate({
            "trade": {"amount": 2000},
            "portfolio_value": 10000,
            "max_position_pct": 0.1,  # 10%
        })

        # 2000/10000 = 20% > 10% max
        assert result.decision is False
        assert "exceeds" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_accepts_reasonable_position(self):
        """Should accept reasonable position sizes."""
        evaluator = RiskCheckEvaluator("test", {})

        result = await evaluator.evaluate({
            "trade": {"amount": 500},
            "portfolio_value": 10000,
            "max_position_pct": 0.1,
        })

        # 500/10000 = 5% < 10% max
        assert result.decision is True


class TestOpportunityScoreEvaluator:
    """Test opportunity score evaluator."""

    @pytest.mark.asyncio
    async def test_scores_high_volume(self):
        """Should score higher for high volume."""
        evaluator = OpportunityScoreEvaluator("test", {})

        high_vol = await evaluator.evaluate({
            "volume_24h": 2_000_000,
            "liquidity": 100_000,
            "price_change_24h": 10,
        })

        low_vol = await evaluator.evaluate({
            "volume_24h": 50_000,
            "liquidity": 100_000,
            "price_change_24h": 10,
        })

        assert high_vol.confidence > low_vol.confidence

    @pytest.mark.asyncio
    async def test_penalizes_high_volatility(self):
        """Should penalize extreme price changes."""
        evaluator = OpportunityScoreEvaluator("test", {})

        moderate = await evaluator.evaluate({
            "price_change_24h": 15,
            "volume_24h": 500_000,
            "liquidity": 200_000,
        })

        extreme = await evaluator.evaluate({
            "price_change_24h": 100,
            "volume_24h": 500_000,
            "liquidity": 200_000,
        })

        assert moderate.metadata["score"] > extreme.metadata["score"]

    @pytest.mark.asyncio
    async def test_returns_evaluation_result(self):
        """Should return proper EvaluationResult."""
        evaluator = OpportunityScoreEvaluator("test", {})

        result = await evaluator.evaluate({
            "volume_24h": 1_000_000,
            "liquidity": 500_000,
            "price_change_24h": 10,
        })

        assert isinstance(result, EvaluationResult)
        assert "score" in result.metadata


# =============================================================================
# Test Plugin Integration
# =============================================================================

class TestTradingPluginIntegration:
    """Integration tests for trading plugin."""

    @pytest.fixture
    def mock_context(self):
        """Create mock plugin context."""
        context = MagicMock()
        context.config = {
            "paper_mode": True,
            "poll_seconds": 1,
        }

        # Mock jarvis with PAE registry
        mock_jarvis = MagicMock()
        mock_jarvis.pae = MagicMock()
        mock_jarvis.pae.register_provider = MagicMock()
        mock_jarvis.pae.register_action = MagicMock()
        mock_jarvis.pae.register_evaluator = MagicMock()

        # Mock event bus
        mock_event_bus = MagicMock()
        mock_event_bus.emit = AsyncMock()

        context.services = {
            "jarvis": mock_jarvis,
            "event_bus": mock_event_bus,
        }

        return context

    @pytest.fixture
    def mock_manifest(self):
        """Create mock plugin manifest."""
        manifest = MagicMock()
        manifest.name = "trading"
        manifest.version = "1.0.0"
        return manifest

    @pytest.mark.asyncio
    async def test_plugin_loads(self, mock_context, mock_manifest):
        """Should load without errors."""
        plugin = TradingPlugin(mock_context, mock_manifest)

        await plugin.on_load()

        # Should register providers
        assert mock_context.services["jarvis"].pae.register_provider.called

    @pytest.mark.asyncio
    async def test_plugin_enable_disable(self, mock_context, mock_manifest):
        """Should enable and disable cleanly."""
        plugin = TradingPlugin(mock_context, mock_manifest)

        await plugin.on_load()
        await plugin.on_enable()

        assert plugin._daemon_task is not None

        await plugin.on_disable()

        assert plugin._daemon_task is None

    @pytest.mark.asyncio
    async def test_plugin_emits_events(self, mock_context, mock_manifest):
        """Should emit events on enable."""
        plugin = TradingPlugin(mock_context, mock_manifest)

        await plugin.on_load()
        await plugin.on_enable()

        # Give the monitoring loop a chance to run
        await asyncio.sleep(0.05)

        await plugin.on_disable()

        # Should have emitted trading.enabled event
        event_bus = mock_context.services["event_bus"]
        assert event_bus.emit.called
