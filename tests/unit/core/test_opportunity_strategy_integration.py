"""
Tests for Opportunity Engine to Decision Matrix Integration

TDD Tests for connecting opportunity detection with strategy execution.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime


class TestOpportunityStrategyIntegration:
    """Test suite for opportunity-to-strategy integration layer."""

    # =========================================================================
    # Phase 1: Opportunity to Strategy Mapping
    # =========================================================================

    def test_import_integration_module(self):
        """Integration module should be importable."""
        from core.opportunity_strategy_integration import OpportunityStrategyIntegration
        assert OpportunityStrategyIntegration is not None

    def test_create_integration_instance(self):
        """Should create integration instance with default config."""
        from core.opportunity_strategy_integration import OpportunityStrategyIntegration
        integration = OpportunityStrategyIntegration()
        assert integration is not None
        assert hasattr(integration, 'evaluate_opportunity')

    def test_evaluate_opportunity_returns_result(self):
        """evaluate_opportunity should return evaluation result."""
        from core.opportunity_strategy_integration import OpportunityStrategyIntegration
        integration = OpportunityStrategyIntegration()

        opportunity = {
            "symbol": "SOL",
            "asset_type": "crypto",
            "scores": {"opportunity": 0.75, "sentiment": 0.7, "momentum": 0.8},
            "signal": {"confidence": 0.72, "expected_edge_pct": 0.05},
            "costs": {"total_pct": 0.015},
        }

        result = integration.evaluate_opportunity(opportunity)

        assert result is not None
        assert "approved" in result
        assert "strategy" in result
        assert "confidence" in result

    def test_map_opportunity_to_strategy_momentum(self):
        """High momentum opportunity should map to momentum strategy."""
        from core.opportunity_strategy_integration import OpportunityStrategyIntegration
        integration = OpportunityStrategyIntegration()

        opportunity = {
            "symbol": "SOL",
            "asset_type": "crypto",
            "scores": {"opportunity": 0.8, "sentiment": 0.75, "momentum": 0.85},
            "signal": {"confidence": 0.75, "expected_edge_pct": 0.06},
            "costs": {"total_pct": 0.015},
        }

        result = integration.evaluate_opportunity(opportunity)

        assert result["strategy"] in ["TrendFollower", "BreakoutTrader"]

    def test_map_opportunity_to_strategy_mean_reversion(self):
        """Mean reversion signals should map to MeanReversion strategy."""
        from core.opportunity_strategy_integration import OpportunityStrategyIntegration
        integration = OpportunityStrategyIntegration()

        opportunity = {
            "symbol": "BONK",
            "asset_type": "crypto",
            "scores": {"opportunity": 0.65, "sentiment": 0.3, "momentum": 0.2},
            "signal": {
                "confidence": 0.65,
                "expected_edge_pct": 0.04,
                "strategy_hint": "mean_reversion",
            },
            "costs": {"total_pct": 0.02},
        }

        result = integration.evaluate_opportunity(opportunity)

        assert result["strategy"] == "MeanReversion"

    def test_map_tokenized_equity_to_appropriate_strategy(self):
        """Tokenized equity should map to low-latency safe strategy."""
        from core.opportunity_strategy_integration import OpportunityStrategyIntegration
        integration = OpportunityStrategyIntegration()

        opportunity = {
            "symbol": "NVDA-X",
            "asset_type": "tokenized_equity",
            "underlying_ticker": "NVDA",
            "scores": {"opportunity": 0.7, "sentiment": 0.7, "momentum": 0.6},
            "signal": {"confidence": 0.70, "expected_edge_pct": 0.03},
            "costs": {"total_pct": 0.025},
        }

        result = integration.evaluate_opportunity(opportunity)

        # Tokenized equities should use safer strategies
        assert result["strategy"] in ["TrendFollower", "DCABot", "GridTrader"]

    # =========================================================================
    # Phase 2: Confidence Thresholds
    # =========================================================================

    def test_reject_low_confidence_opportunity(self):
        """Opportunities below confidence threshold should be rejected."""
        from core.opportunity_strategy_integration import OpportunityStrategyIntegration
        integration = OpportunityStrategyIntegration()

        opportunity = {
            "symbol": "RISKY",
            "asset_type": "crypto",
            "scores": {"opportunity": 0.4, "sentiment": 0.4, "momentum": 0.3},
            "signal": {"confidence": 0.40, "expected_edge_pct": 0.02},
            "costs": {"total_pct": 0.015},
        }

        result = integration.evaluate_opportunity(opportunity)

        assert result["approved"] is False
        assert "confidence" in result["rejection_reason"].lower()

    def test_accept_high_confidence_opportunity(self):
        """Opportunities above confidence threshold should be approved."""
        from core.opportunity_strategy_integration import OpportunityStrategyIntegration
        integration = OpportunityStrategyIntegration()

        opportunity = {
            "symbol": "SOL",
            "asset_type": "crypto",
            "scores": {"opportunity": 0.8, "sentiment": 0.8, "momentum": 0.75},
            "signal": {"confidence": 0.75, "expected_edge_pct": 0.06},
            "costs": {"total_pct": 0.015},
        }

        result = integration.evaluate_opportunity(opportunity)

        assert result["approved"] is True

    def test_confidence_threshold_configurable(self):
        """Confidence threshold should be configurable."""
        from core.opportunity_strategy_integration import OpportunityStrategyIntegration

        # Higher threshold
        integration = OpportunityStrategyIntegration(min_confidence=0.80)

        opportunity = {
            "symbol": "SOL",
            "asset_type": "crypto",
            "scores": {"opportunity": 0.7, "sentiment": 0.7, "momentum": 0.7},
            "signal": {"confidence": 0.72, "expected_edge_pct": 0.05},
            "costs": {"total_pct": 0.015},
        }

        result = integration.evaluate_opportunity(opportunity)

        # 0.72 < 0.80, should be rejected
        assert result["approved"] is False

    def test_edge_to_cost_threshold(self):
        """Opportunities with poor edge-to-cost should be rejected."""
        from core.opportunity_strategy_integration import OpportunityStrategyIntegration
        integration = OpportunityStrategyIntegration()

        opportunity = {
            "symbol": "POOR",
            "asset_type": "crypto",
            "scores": {"opportunity": 0.7, "sentiment": 0.7, "momentum": 0.7},
            "signal": {"confidence": 0.75, "expected_edge_pct": 0.01},  # 1% edge
            "costs": {"total_pct": 0.03},  # 3% cost -> edge/cost = 0.33
        }

        result = integration.evaluate_opportunity(opportunity)

        assert result["approved"] is False
        assert "edge" in result["rejection_reason"].lower() or "cost" in result["rejection_reason"].lower()

    # =========================================================================
    # Phase 3: Risk Limits
    # =========================================================================

    def test_risk_limits_per_opportunity_type(self):
        """Different opportunity types should have different risk limits."""
        from core.opportunity_strategy_integration import OpportunityStrategyIntegration
        integration = OpportunityStrategyIntegration()

        crypto_limits = integration.get_risk_limits("crypto")
        equity_limits = integration.get_risk_limits("tokenized_equity")

        assert crypto_limits is not None
        assert equity_limits is not None
        assert "max_position_usd" in crypto_limits
        assert "max_position_usd" in equity_limits
        # Tokenized equities may have different limits
        assert equity_limits["max_position_usd"] <= crypto_limits["max_position_usd"]

    def test_position_size_capped_by_risk_limits(self):
        """Position size should be capped by risk limits."""
        from core.opportunity_strategy_integration import OpportunityStrategyIntegration
        integration = OpportunityStrategyIntegration()

        opportunity = {
            "symbol": "SOL",
            "asset_type": "crypto",
            "scores": {"opportunity": 0.85, "sentiment": 0.8, "momentum": 0.8},
            "signal": {"confidence": 0.80, "expected_edge_pct": 0.06},
            "costs": {"total_pct": 0.015},
        }

        result = integration.evaluate_opportunity(opportunity, requested_size_usd=10000)

        assert result["approved"] is True
        assert result["recommended_size_usd"] <= integration.get_risk_limits("crypto")["max_position_usd"]

    def test_daily_loss_limit_check(self):
        """Should reject if daily loss limit would be exceeded."""
        from core.opportunity_strategy_integration import OpportunityStrategyIntegration
        integration = OpportunityStrategyIntegration()

        opportunity = {
            "symbol": "SOL",
            "asset_type": "crypto",
            "scores": {"opportunity": 0.75, "sentiment": 0.7, "momentum": 0.7},
            "signal": {"confidence": 0.70, "expected_edge_pct": 0.05},
            "costs": {"total_pct": 0.015},
        }

        # Simulate existing daily loss
        result = integration.evaluate_opportunity(
            opportunity,
            portfolio_context={"daily_loss_usd": 450, "daily_loss_limit_usd": 500}
        )

        # Should reject or reduce size due to daily loss limit proximity
        assert result["approved"] is False or result["recommended_size_usd"] < 50

    # =========================================================================
    # Phase 4: Approval Gate for High-Value Trades
    # =========================================================================

    def test_approval_gate_required_for_large_trades(self):
        """Trades > $100 should require approval."""
        from core.opportunity_strategy_integration import OpportunityStrategyIntegration
        integration = OpportunityStrategyIntegration()

        opportunity = {
            "symbol": "SOL",
            "asset_type": "crypto",
            "scores": {"opportunity": 0.85, "sentiment": 0.8, "momentum": 0.85},
            "signal": {"confidence": 0.85, "expected_edge_pct": 0.08},
            "costs": {"total_pct": 0.015},
        }

        result = integration.evaluate_opportunity(opportunity, requested_size_usd=150)

        assert result["requires_approval"] is True
        assert result["approval_reason"] == "amount_exceeds_threshold"

    def test_auto_execute_small_trades(self):
        """Trades <= $100 should not require approval for auto-execution."""
        from core.opportunity_strategy_integration import OpportunityStrategyIntegration
        integration = OpportunityStrategyIntegration()

        opportunity = {
            "symbol": "SOL",
            "asset_type": "crypto",
            "scores": {"opportunity": 0.8, "sentiment": 0.75, "momentum": 0.8},
            "signal": {"confidence": 0.75, "expected_edge_pct": 0.06},
            "costs": {"total_pct": 0.015},
        }

        result = integration.evaluate_opportunity(opportunity, requested_size_usd=50)

        assert result["requires_approval"] is False
        assert result["auto_execute_eligible"] is True

    def test_approval_threshold_configurable(self):
        """Approval threshold should be configurable."""
        from core.opportunity_strategy_integration import OpportunityStrategyIntegration

        integration = OpportunityStrategyIntegration(approval_threshold_usd=200)

        opportunity = {
            "symbol": "SOL",
            "asset_type": "crypto",
            "scores": {"opportunity": 0.8, "sentiment": 0.75, "momentum": 0.8},
            "signal": {"confidence": 0.75, "expected_edge_pct": 0.06},
            "costs": {"total_pct": 0.015},
        }

        result = integration.evaluate_opportunity(opportunity, requested_size_usd=150)

        # $150 < $200 threshold, should not require approval
        assert result["requires_approval"] is False

    # =========================================================================
    # Phase 5: Integration with Trading Operations
    # =========================================================================

    @pytest.mark.asyncio
    async def test_execute_trade_integration(self):
        """Should integrate with trading operations for execution."""
        from core.opportunity_strategy_integration import OpportunityStrategyIntegration
        integration = OpportunityStrategyIntegration()

        opportunity = {
            "symbol": "SOL",
            "mint_address": "So11111111111111111111111111111111111111112",
            "asset_type": "crypto",
            "scores": {"opportunity": 0.8, "sentiment": 0.75, "momentum": 0.8},
            "signal": {"confidence": 0.75, "expected_edge_pct": 0.06},
            "costs": {"total_pct": 0.015},
        }

        # Mock the trading engine
        mock_trading_engine = AsyncMock()
        mock_trading_engine.open_position.return_value = (True, "Position opened", MagicMock())

        result = await integration.execute_opportunity(
            opportunity,
            trading_engine=mock_trading_engine,
            size_usd=50,
            user_id=123456,
        )

        assert result["success"] is True
        mock_trading_engine.open_position.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_skipped_if_not_approved(self):
        """Execution should be skipped if opportunity not approved."""
        from core.opportunity_strategy_integration import OpportunityStrategyIntegration
        integration = OpportunityStrategyIntegration()

        opportunity = {
            "symbol": "RISKY",
            "mint_address": "Risky111111111111111111111111111111111111",
            "asset_type": "crypto",
            "scores": {"opportunity": 0.3, "sentiment": 0.3, "momentum": 0.3},
            "signal": {"confidence": 0.30, "expected_edge_pct": 0.01},
            "costs": {"total_pct": 0.03},
        }

        mock_trading_engine = AsyncMock()

        result = await integration.execute_opportunity(
            opportunity,
            trading_engine=mock_trading_engine,
            size_usd=50,
            user_id=123456,
        )

        assert result["success"] is False
        assert "rejected" in result["reason"].lower() or "not approved" in result["reason"].lower()
        mock_trading_engine.open_position.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_requires_user_approval_for_large_trade(self):
        """Large trades should return approval-required status."""
        from core.opportunity_strategy_integration import OpportunityStrategyIntegration
        integration = OpportunityStrategyIntegration()

        opportunity = {
            "symbol": "SOL",
            "mint_address": "So11111111111111111111111111111111111111112",
            "asset_type": "crypto",
            "scores": {"opportunity": 0.85, "sentiment": 0.8, "momentum": 0.85},
            "signal": {"confidence": 0.85, "expected_edge_pct": 0.08},
            "costs": {"total_pct": 0.015},
        }

        mock_trading_engine = AsyncMock()

        result = await integration.execute_opportunity(
            opportunity,
            trading_engine=mock_trading_engine,
            size_usd=150,
            user_id=123456,
            skip_approval=False,
        )

        assert result["success"] is False
        assert result["requires_approval"] is True
        mock_trading_engine.open_position.assert_not_called()

    # =========================================================================
    # Phase 6: Logging and Metrics
    # =========================================================================

    def test_evaluation_logged(self):
        """Evaluations should be logged with metrics."""
        from core.opportunity_strategy_integration import OpportunityStrategyIntegration
        integration = OpportunityStrategyIntegration()

        opportunity = {
            "symbol": "SOL",
            "asset_type": "crypto",
            "scores": {"opportunity": 0.75, "sentiment": 0.7, "momentum": 0.7},
            "signal": {"confidence": 0.72, "expected_edge_pct": 0.05},
            "costs": {"total_pct": 0.015},
        }

        result = integration.evaluate_opportunity(opportunity)

        # Result should include logging-friendly fields
        assert "timestamp" in result
        assert "opportunity_id" in result or "symbol" in result

    def test_get_evaluation_history(self):
        """Should track evaluation history for metrics."""
        from core.opportunity_strategy_integration import OpportunityStrategyIntegration
        integration = OpportunityStrategyIntegration()

        opportunities = [
            {"symbol": "SOL", "asset_type": "crypto", "scores": {"opportunity": 0.8}, "signal": {"confidence": 0.75}, "costs": {"total_pct": 0.015}},
            {"symbol": "ETH", "asset_type": "crypto", "scores": {"opportunity": 0.7}, "signal": {"confidence": 0.65}, "costs": {"total_pct": 0.015}},
            {"symbol": "RISKY", "asset_type": "crypto", "scores": {"opportunity": 0.3}, "signal": {"confidence": 0.30}, "costs": {"total_pct": 0.03}},
        ]

        for opp in opportunities:
            opp.setdefault("signal", {}).setdefault("expected_edge_pct", 0.05)
            opp["scores"].setdefault("sentiment", 0.5)
            opp["scores"].setdefault("momentum", 0.5)
            integration.evaluate_opportunity(opp)

        history = integration.get_evaluation_history()

        assert len(history) == 3
        approved_count = sum(1 for h in history if h.get("approved"))
        rejected_count = sum(1 for h in history if not h.get("approved"))
        assert approved_count >= 1
        assert rejected_count >= 1


class TestOpportunityEngineIntegration:
    """Test suite for full opportunity engine to execution flow."""

    def test_run_engine_and_evaluate(self):
        """Should run opportunity engine and evaluate results."""
        from core.opportunity_strategy_integration import OpportunityStrategyIntegration

        # Mock opportunity engine output
        engine_output = {
            "ranked": [
                {
                    "symbol": "SOL",
                    "asset_type": "crypto",
                    "mint_address": "So11111111111111111111111111111111111111112",
                    "scores": {"opportunity": 0.8, "sentiment": 0.75, "momentum": 0.8},
                    "signal": {"confidence": 0.75, "expected_edge_pct": 0.06},
                    "costs": {"total_pct": 0.015},
                },
                {
                    "symbol": "BONK",
                    "asset_type": "crypto",
                    "mint_address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
                    "scores": {"opportunity": 0.6, "sentiment": 0.5, "momentum": 0.5},
                    "signal": {"confidence": 0.55, "expected_edge_pct": 0.04},
                    "costs": {"total_pct": 0.02},
                },
            ],
            "trade_intents": [
                {"symbol": "SOL", "tradable": True},
                {"symbol": "BONK", "tradable": True},
            ],
        }

        integration = OpportunityStrategyIntegration()
        evaluated = integration.evaluate_engine_output(engine_output)

        assert "approved_opportunities" in evaluated
        assert "rejected_opportunities" in evaluated
        assert len(evaluated["approved_opportunities"]) >= 1

    def test_batch_evaluation_respects_portfolio_limits(self):
        """Batch evaluation should respect total portfolio exposure."""
        from core.opportunity_strategy_integration import OpportunityStrategyIntegration

        engine_output = {
            "ranked": [
                {"symbol": f"TOKEN{i}", "asset_type": "crypto", "scores": {"opportunity": 0.8 - i*0.05, "sentiment": 0.7, "momentum": 0.7}, "signal": {"confidence": 0.75 - i*0.02, "expected_edge_pct": 0.05}, "costs": {"total_pct": 0.015}}
                for i in range(10)
            ],
            "trade_intents": [{"symbol": f"TOKEN{i}", "tradable": True} for i in range(10)],
        }

        integration = OpportunityStrategyIntegration(max_concurrent_positions=5)
        evaluated = integration.evaluate_engine_output(
            engine_output,
            current_positions=2,
        )

        # Should only approve up to 3 more positions (5 max - 2 current = 3)
        assert len(evaluated["approved_opportunities"]) <= 3


class TestDecisionMatrixIntegration:
    """Test decision matrix is properly used."""

    def test_uses_decision_matrix_for_strategy_selection(self):
        """Integration should use decision matrix for strategy selection."""
        from core.opportunity_strategy_integration import OpportunityStrategyIntegration
        from core.trading_decision_matrix import get_decision_matrix

        integration = OpportunityStrategyIntegration()
        matrix = get_decision_matrix()

        # All strategies returned should be registered in decision matrix
        opportunity = {
            "symbol": "SOL",
            "asset_type": "crypto",
            "scores": {"opportunity": 0.8, "sentiment": 0.75, "momentum": 0.8},
            "signal": {"confidence": 0.75, "expected_edge_pct": 0.06},
            "costs": {"total_pct": 0.015},
        }

        result = integration.evaluate_opportunity(opportunity)

        if result["strategy"]:
            strategy_def = matrix.get_strategy_by_name(result["strategy"])
            assert strategy_def is not None, f"Strategy {result['strategy']} not found in decision matrix"
