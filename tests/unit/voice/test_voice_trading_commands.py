"""
Unit tests for Voice Trading Commands.

Tests the execution of voice trading commands through the JARVIS voice terminal.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime


class TestVoiceTradingCommandsBasics:
    """Test basic trading commands infrastructure."""

    def test_trading_commands_exists(self):
        """VoiceTradingCommands should exist and be importable."""
        from core.voice.trading_commands import VoiceTradingCommands

        handler = VoiceTradingCommands()
        assert handler is not None

    def test_handler_registry(self):
        """Handler should have a registry of command handlers."""
        from core.voice.trading_commands import VoiceTradingCommands

        handler = VoiceTradingCommands()
        assert hasattr(handler, "handlers")
        assert isinstance(handler.handlers, dict)

    def test_execute_method(self):
        """Handler should have an execute method."""
        from core.voice.trading_commands import VoiceTradingCommands

        handler = VoiceTradingCommands()
        assert hasattr(handler, "execute")
        assert callable(handler.execute)


class TestMorningBriefingHandler:
    """Test morning briefing command execution."""

    @pytest.mark.asyncio
    async def test_morning_briefing_returns_summary(self):
        """Morning briefing should return market summary."""
        from core.voice.trading_commands import VoiceTradingCommands

        handler = VoiceTradingCommands()

        with patch.object(handler, "_get_market_data") as mock_data:
            mock_data.return_value = {
                "sol_price": 180.0,
                "sol_24h_change": 5.2,
                "btc_price": 95000.0,
                "btc_24h_change": 1.5,
                "total_positions": 5,
                "portfolio_value": 10000.0,
                "pnl_24h": 250.0,
            }

            result = await handler.execute({
                "intent": "morning_briefing",
                "params": {},
                "confidence": 0.95
            })

        assert result["success"] is True
        assert "response" in result
        assert "sol" in result["response"].lower() or "solana" in result["response"].lower()

    @pytest.mark.asyncio
    async def test_morning_briefing_includes_overnight_moves(self):
        """Briefing should mention significant overnight movements."""
        from core.voice.trading_commands import VoiceTradingCommands

        handler = VoiceTradingCommands()

        with patch.object(handler, "_get_market_data") as mock_data:
            mock_data.return_value = {
                "sol_price": 200.0,
                "sol_24h_change": 15.0,  # Big move
                "btc_price": 95000.0,
                "btc_24h_change": 2.0,
                "significant_moves": [
                    {"token": "SOL", "change": 15.0},
                    {"token": "BONK", "change": 25.0},
                ]
            }

            result = await handler.execute({
                "intent": "morning_briefing",
                "params": {},
                "confidence": 0.95
            })

        assert result["success"] is True
        # Should mention significant moves
        response_lower = result["response"].lower()
        assert "sol" in response_lower or "move" in response_lower


class TestStrategyControlHandler:
    """Test strategy activation/deactivation."""

    @pytest.mark.asyncio
    async def test_activate_strategy(self):
        """Should be able to activate a strategy."""
        from core.voice.trading_commands import VoiceTradingCommands

        handler = VoiceTradingCommands()

        with patch.object(handler, "_set_strategy_state") as mock_set:
            mock_set.return_value = True

            result = await handler.execute({
                "intent": "strategy_control",
                "params": {"action": "activate", "strategy": "momentum"},
                "confidence": 0.95
            })

        assert result["success"] is True
        assert "momentum" in result["response"].lower()
        assert "activat" in result["response"].lower()

    @pytest.mark.asyncio
    async def test_deactivate_strategy(self):
        """Should be able to deactivate a strategy."""
        from core.voice.trading_commands import VoiceTradingCommands

        handler = VoiceTradingCommands()

        with patch.object(handler, "_set_strategy_state") as mock_set:
            mock_set.return_value = True

            result = await handler.execute({
                "intent": "strategy_control",
                "params": {"action": "deactivate", "strategy": "momentum"},
                "confidence": 0.95
            })

        assert result["success"] is True
        assert "momentum" in result["response"].lower()
        assert "deactivat" in result["response"].lower() or "disabled" in result["response"].lower()

    @pytest.mark.asyncio
    async def test_invalid_strategy_returns_error(self):
        """Invalid strategy should return helpful error."""
        from core.voice.trading_commands import VoiceTradingCommands

        handler = VoiceTradingCommands()

        result = await handler.execute({
            "intent": "strategy_control",
            "params": {"action": "activate", "strategy": "nonexistent"},
            "confidence": 0.95
        })

        assert result["success"] is False
        # Should mention the invalid strategy
        response_lower = result["response"].lower()
        assert "don't recognize" in response_lower or "not found" in response_lower or "invalid" in response_lower


class TestRiskAdjustmentHandler:
    """Test risk limit adjustment commands."""

    @pytest.mark.asyncio
    async def test_set_max_position(self):
        """Should be able to set max position size."""
        from core.voice.trading_commands import VoiceTradingCommands

        handler = VoiceTradingCommands()

        with patch.object(handler, "_update_risk_limit") as mock_update:
            mock_update.return_value = True

            result = await handler.execute({
                "intent": "risk_adjustment",
                "params": {"max_position_pct": 3.0},
                "confidence": 0.95
            })

        assert result["success"] is True
        mock_update.assert_called_once()
        assert "3" in result["response"] or "three" in result["response"].lower()

    @pytest.mark.asyncio
    async def test_set_stop_loss(self):
        """Should be able to set stop loss percentage."""
        from core.voice.trading_commands import VoiceTradingCommands

        handler = VoiceTradingCommands()

        with patch.object(handler, "_update_risk_limit") as mock_update:
            mock_update.return_value = True

            result = await handler.execute({
                "intent": "risk_adjustment",
                "params": {"stop_loss_pct": 10.0},
                "confidence": 0.95
            })

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_risk_query_returns_limits(self):
        """Risk query should return current limits."""
        from core.voice.trading_commands import VoiceTradingCommands

        handler = VoiceTradingCommands()

        with patch.object(handler, "_get_risk_limits") as mock_get:
            mock_get.return_value = {
                "max_position_pct": 5.0,
                "stop_loss_pct": 8.0,
                "take_profit_pct": 30.0,
                "daily_loss_limit": 1000.0,
            }

            result = await handler.execute({
                "intent": "risk_query",
                "params": {},
                "confidence": 0.95
            })

        assert result["success"] is True
        assert "5" in result["response"] or "position" in result["response"].lower()

    @pytest.mark.asyncio
    async def test_requires_confirmation_for_aggressive_settings(self):
        """Aggressive risk settings should require confirmation."""
        from core.voice.trading_commands import VoiceTradingCommands

        handler = VoiceTradingCommands()

        result = await handler.execute({
            "intent": "risk_adjustment",
            "params": {"max_position_pct": 25.0},  # Very aggressive
            "confidence": 0.95
        })

        # Should either fail or require confirmation
        assert result.get("requires_confirmation", False) or result["success"] is False


class TestPriceAlertHandler:
    """Test price alert commands."""

    @pytest.mark.asyncio
    async def test_set_price_alert(self):
        """Should be able to set a price alert."""
        from core.voice.trading_commands import VoiceTradingCommands

        handler = VoiceTradingCommands()

        with patch.object(handler, "_create_price_alert") as mock_create:
            mock_create.return_value = {"id": "alert_123", "token": "SOL", "price": 150.0}

            result = await handler.execute({
                "intent": "price_alert",
                "params": {"token": "SOL", "price": 150.0, "direction": "at"},
                "confidence": 0.95
            })

        assert result["success"] is True
        assert "sol" in result["response"].lower()
        assert "150" in result["response"]

    @pytest.mark.asyncio
    async def test_list_alerts(self):
        """Should be able to list active alerts."""
        from core.voice.trading_commands import VoiceTradingCommands

        handler = VoiceTradingCommands()

        with patch.object(handler, "_get_alerts") as mock_get:
            mock_get.return_value = [
                {"id": "1", "token": "SOL", "price": 150.0, "direction": "above"},
                {"id": "2", "token": "BTC", "price": 100000.0, "direction": "at"},
            ]

            result = await handler.execute({
                "intent": "list_alerts",
                "params": {},
                "confidence": 0.95
            })

        assert result["success"] is True
        assert "sol" in result["response"].lower() or "alert" in result["response"].lower()

    @pytest.mark.asyncio
    async def test_cancel_alert(self):
        """Should be able to cancel an alert."""
        from core.voice.trading_commands import VoiceTradingCommands

        handler = VoiceTradingCommands()

        with patch.object(handler, "_cancel_alert") as mock_cancel:
            mock_cancel.return_value = True

            result = await handler.execute({
                "intent": "cancel_alert",
                "params": {"token": "SOL"},
                "confidence": 0.95
            })

        assert result["success"] is True


class TestPositionQueryHandler:
    """Test position query commands."""

    @pytest.mark.asyncio
    async def test_list_all_positions(self):
        """Should return all open positions."""
        from core.voice.trading_commands import VoiceTradingCommands

        handler = VoiceTradingCommands()

        with patch.object(handler, "_get_positions") as mock_get:
            mock_get.return_value = [
                {"token": "SOL", "amount": 10.0, "value_usd": 1800.0, "pnl_pct": 5.2},
                {"token": "BONK", "amount": 1000000, "value_usd": 500.0, "pnl_pct": -2.1},
            ]

            result = await handler.execute({
                "intent": "position_query",
                "params": {},
                "confidence": 0.95
            })

        assert result["success"] is True
        assert "sol" in result["response"].lower()

    @pytest.mark.asyncio
    async def test_specific_position_query(self):
        """Should return specific position details."""
        from core.voice.trading_commands import VoiceTradingCommands

        handler = VoiceTradingCommands()

        with patch.object(handler, "_get_position") as mock_get:
            mock_get.return_value = {
                "token": "SOL",
                "amount": 10.0,
                "avg_entry": 170.0,
                "current_price": 180.0,
                "value_usd": 1800.0,
                "pnl_usd": 100.0,
                "pnl_pct": 5.88,
            }

            result = await handler.execute({
                "intent": "position_query",
                "params": {"token": "SOL"},
                "confidence": 0.95
            })

        assert result["success"] is True
        assert "sol" in result["response"].lower()

    @pytest.mark.asyncio
    async def test_no_positions_message(self):
        """Should handle empty positions gracefully."""
        from core.voice.trading_commands import VoiceTradingCommands

        handler = VoiceTradingCommands()

        with patch.object(handler, "_get_positions") as mock_get:
            mock_get.return_value = []

            result = await handler.execute({
                "intent": "position_query",
                "params": {},
                "confidence": 0.95
            })

        assert result["success"] is True
        assert "no" in result["response"].lower() or "empty" in result["response"].lower()


class TestTradeCommandHandler:
    """Test voice trading command execution."""

    @pytest.mark.asyncio
    async def test_buy_command_requires_confirmation(self):
        """Buy commands should require confirmation."""
        from core.voice.trading_commands import VoiceTradingCommands

        handler = VoiceTradingCommands()

        result = await handler.execute({
            "intent": "trade_command",
            "params": {"action": "buy", "token": "SOL", "amount": 100.0, "currency": "USD"},
            "confidence": 0.95
        })

        # Trade commands should always require confirmation for safety
        assert result.get("requires_confirmation", False) is True

    @pytest.mark.asyncio
    async def test_sell_command_requires_confirmation(self):
        """Sell commands should require confirmation."""
        from core.voice.trading_commands import VoiceTradingCommands

        handler = VoiceTradingCommands()

        result = await handler.execute({
            "intent": "trade_command",
            "params": {"action": "sell", "token": "SOL", "percentage": 50.0},
            "confidence": 0.95
        })

        assert result.get("requires_confirmation", False) is True

    @pytest.mark.asyncio
    async def test_execute_confirmed_buy(self):
        """Confirmed buy should execute trade."""
        from core.voice.trading_commands import VoiceTradingCommands

        handler = VoiceTradingCommands()

        with patch.object(handler, "_execute_trade") as mock_trade:
            mock_trade.return_value = {
                "success": True,
                "tx_signature": "abc123",
                "amount_bought": 0.55,
                "price": 180.0,
            }

            result = await handler.execute({
                "intent": "trade_command",
                "params": {"action": "buy", "token": "SOL", "amount": 100.0, "currency": "USD"},
                "confidence": 0.95,
                "confirmed": True  # User confirmed
            })

        assert result["success"] is True
        assert "bought" in result["response"].lower() or "executed" in result["response"].lower()


class TestMarketDataHandler:
    """Test market data query commands."""

    @pytest.mark.asyncio
    async def test_price_query(self):
        """Should return current price for token."""
        from core.voice.trading_commands import VoiceTradingCommands

        handler = VoiceTradingCommands()

        with patch.object(handler, "_get_token_price") as mock_price:
            mock_price.return_value = {
                "token": "SOL",
                "price": 180.50,
                "change_24h": 5.2,
                "volume_24h": 1500000000,
            }

            result = await handler.execute({
                "intent": "price_query",
                "params": {"token": "SOL"},
                "confidence": 0.95
            })

        assert result["success"] is True
        assert "180" in result["response"]
        assert "sol" in result["response"].lower()

    @pytest.mark.asyncio
    async def test_market_overview(self):
        """Should return market overview."""
        from core.voice.trading_commands import VoiceTradingCommands

        handler = VoiceTradingCommands()

        with patch.object(handler, "_get_market_overview") as mock_overview:
            mock_overview.return_value = {
                "btc_dominance": 52.5,
                "total_market_cap": 3500000000000,
                "fear_greed_index": 65,
                "trending": ["SOL", "BONK", "WIF"],
            }

            result = await handler.execute({
                "intent": "market_overview",
                "params": {},
                "confidence": 0.95
            })

        assert result["success"] is True


class TestErrorHandling:
    """Test error handling in voice commands."""

    @pytest.mark.asyncio
    async def test_unknown_intent(self):
        """Unknown intents should return helpful message."""
        from core.voice.trading_commands import VoiceTradingCommands

        handler = VoiceTradingCommands()

        result = await handler.execute({
            "intent": "unknown",
            "params": {},
            "confidence": 0.3
        })

        assert result["success"] is False
        assert "understand" in result["response"].lower() or "help" in result["response"].lower()

    @pytest.mark.asyncio
    async def test_low_confidence_intent(self):
        """Low confidence commands should request clarification."""
        from core.voice.trading_commands import VoiceTradingCommands

        handler = VoiceTradingCommands()

        result = await handler.execute({
            "intent": "morning_briefing",
            "params": {},
            "confidence": 0.4  # Low confidence
        })

        # Should either ask for clarification or proceed with warning
        assert "clarify" in result["response"].lower() or result["success"] is True

    @pytest.mark.asyncio
    async def test_api_error_handling(self):
        """API errors should be handled gracefully."""
        from core.voice.trading_commands import VoiceTradingCommands

        handler = VoiceTradingCommands()

        with patch.object(handler, "_get_market_data") as mock_data:
            mock_data.side_effect = Exception("API connection failed")

            result = await handler.execute({
                "intent": "morning_briefing",
                "params": {},
                "confidence": 0.95
            })

        assert result["success"] is False
        assert "error" in result["response"].lower() or "try again" in result["response"].lower()


class TestVoiceResponseFormatting:
    """Test that responses are formatted for voice output."""

    @pytest.mark.asyncio
    async def test_response_is_speakable(self):
        """Responses should be suitable for TTS."""
        from core.voice.trading_commands import VoiceTradingCommands

        handler = VoiceTradingCommands()

        with patch.object(handler, "_get_market_data") as mock_data:
            mock_data.return_value = {
                "sol_price": 180.0,
                "sol_24h_change": 5.2,
                "btc_price": 95000.0,
                "btc_24h_change": 1.5,
            }

            result = await handler.execute({
                "intent": "morning_briefing",
                "params": {},
                "confidence": 0.95
            })

        response = result["response"]

        # Should not have excessive special characters
        assert response.count("$") <= 5  # Reasonable number of dollar signs
        assert "```" not in response  # No code blocks
        assert "<" not in response  # No HTML
        assert response.count("\n") <= 5  # Limited line breaks

    @pytest.mark.asyncio
    async def test_numbers_formatted_for_speech(self):
        """Numbers should be formatted for natural speech."""
        from core.voice.trading_commands import VoiceTradingCommands

        handler = VoiceTradingCommands()

        with patch.object(handler, "_get_token_price") as mock_price:
            mock_price.return_value = {
                "token": "SOL",
                "price": 180.50,
                "change_24h": 5.2,
            }

            result = await handler.execute({
                "intent": "price_query",
                "params": {"token": "SOL"},
                "confidence": 0.95
            })

        # Response should be readable (no raw numbers like 180.5000000)
        assert "180.5000000" not in result["response"]
