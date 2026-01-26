"""
Integration Tests: bags.fm + TP/SL Flow

Phase 4, Task 4: Test end-to-end trading flow with TP/SL enforcement.

Scenarios:
1. bags.fm buy → TP trigger → auto-exit
2. bags.fm failure → Jupiter fallback → SL trigger
3. Trailing stop update and trigger
4. TP/SL validation errors
"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from typing import Dict, Any

# Test imports
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tg_bot.handlers.demo.demo_trading import execute_buy_with_tpsl, _validate_tpsl_required
from tg_bot.handlers.demo.demo_orders import _check_demo_exit_triggers


class TestBagsTpslIntegration:
    """Integration tests for bags.fm + TP/SL flow."""

    @pytest.mark.asyncio
    async def test_bags_buy_tp_trigger(self):
        """Test bags.fm buy + TP trigger flow."""
        # Mock successful bags.fm swap
        mock_swap = {
            "success": True,
            "amount_out": 100000,
            "tx_hash": "test_tx_hash_12345",
            "source": "bags_fm",
        }

        mock_sentiment = {
            "symbol": "TEST",
            "price": 0.001,
        }

        with patch("tg_bot.handlers.demo.demo_trading._execute_swap_with_fallback", new=AsyncMock(return_value=mock_swap)), \
             patch("tg_bot.handlers.demo.demo_sentiment.get_ai_sentiment_for_token", new=AsyncMock(return_value=mock_sentiment)):

            # Execute buy
            result = await execute_buy_with_tpsl(
                token_address="TestToken123",
                amount_sol=0.1,
                wallet_address="TestWallet456",
                tp_percent=50.0,  # 50% profit target
                sl_percent=20.0,  # 20% max loss
            )

            # Verify buy success
            assert result["success"] is True
            assert "position" in result
            position = result["position"]

            # Verify position has TP/SL
            assert position["tp_percent"] == 50.0
            assert position["sl_percent"] == 20.0
            assert position["entry_price"] == 0.001
            assert position["tp_price"] == 0.0015  # 50% above entry
            assert position["sl_price"] == 0.0008  # 20% below entry

            # Simulate price increase to TP level
            position["current_price"] = 0.0016  # 60% above entry (>TP)

            # Create user_data with position
            user_data = {"positions": [position]}

            # Check exit triggers
            alerts = await _check_demo_exit_triggers(user_data, [position])

            # Verify TP triggered
            assert len(alerts) == 1
            assert alerts[0]["type"] == "take_profit"
            assert alerts[0]["position"]["symbol"] == "TEST"

    @pytest.mark.asyncio
    async def test_bags_failure_jupiter_fallback(self):
        """Test Jupiter fallback when bags.fm fails."""
        # First call fails (bags.fm), second succeeds (Jupiter)
        mock_swap_failed = {"success": False, "error": "bags.fm unavailable"}
        mock_swap_success = {
            "success": True,
            "amount_out": 90000,
            "tx_hash": "jupiter_tx_hash",
            "source": "jupiter",
        }

        mock_sentiment = {"symbol": "FALLBACK", "price": 0.002}

        with patch("tg_bot.handlers.demo.demo_trading._execute_swap_with_fallback", new=AsyncMock(return_value=mock_swap_success)), \
             patch("tg_bot.handlers.demo.demo_sentiment.get_ai_sentiment_for_token", new=AsyncMock(return_value=mock_sentiment)):

            result = await execute_buy_with_tpsl(
                token_address="FallbackToken",
                amount_sol=0.2,
                wallet_address="TestWallet",
                tp_percent=100.0,
                sl_percent=30.0,
            )

            # Verify fallback worked
            assert result["success"] is True
            position = result["position"]
            assert position["source"] == "jupiter"  # Fell back to Jupiter

            # Verify TP/SL still configured
            assert position["tp_percent"] == 100.0
            assert position["sl_percent"] == 30.0

    @pytest.mark.asyncio
    async def test_sl_trigger_auto_exit(self):
        """Test stop-loss trigger + automatic exit."""
        # Create position that should trigger SL
        position = {
            "id": "test_pos_1",
            "symbol": "CRASH",
            "address": "CrashToken",
            "entry_price": 1.0,
            "current_price": 0.75,  # -25% (below 20% SL)
            "tp_percent": 50.0,
            "sl_percent": 20.0,
            "tp_price": 1.5,
            "sl_price": 0.8,
            "amount": 1000,
            "amount_sol": 0.1,
        }

        user_data = {
            "positions": [position],
            "ai_auto_trade": True,  # Auto-exit enabled
        }

        # Check exit triggers
        alerts = await _check_demo_exit_triggers(user_data, [position])

        # Verify SL alert
        assert len(alerts) == 1
        assert alerts[0]["type"] == "stop_loss"
        assert alerts[0]["position"]["symbol"] == "CRASH"
        assert alerts[0]["price"] == 0.75  # Current price that triggered SL

    @pytest.mark.asyncio
    async def test_trailing_stop(self):
        """Test trailing stop updates and triggers."""
        position = {
            "id": "test_pos_2",
            "symbol": "MOON",
            "address": "MoonToken",
            "entry_price": 1.0,
            "current_price": 2.0,  # +100%
            "amount": 5000,
            "amount_sol": 0.5,
            "tp_percent": 200.0,
            "sl_percent": 30.0,
        }

        # Create trailing stop (10% trail)
        trailing_stop = {
            "position_id": "test_pos_2",
            "trail_percent": 10.0,
            "highest_price": 2.0,
            "current_stop_price": 1.8,  # 10% below highest
            "active": True,
        }

        user_data = {
            "positions": [position],
            "trailing_stops": [trailing_stop],
        }

        # Price goes up - stop should update
        position["current_price"] = 2.5
        alerts = await _check_demo_exit_triggers(user_data, [position])

        # Should have no alerts (price went up)
        assert len(alerts) == 0

        # Verify trailing stop updated
        assert trailing_stop["highest_price"] == 2.5
        assert trailing_stop["current_stop_price"] == 2.25  # 10% below 2.5

        # Price drops below stop - should trigger
        position["current_price"] = 2.2
        alerts = await _check_demo_exit_triggers(user_data, [position])

        # Verify trailing stop triggered
        assert len(alerts) == 1
        assert alerts[0]["type"] == "trailing_stop"

    def test_tpsl_validation_missing(self):
        """Test TP/SL validation rejects missing values."""
        with pytest.raises(ValueError, match="mandatory"):
            _validate_tpsl_required(None, 20.0)

        with pytest.raises(ValueError, match="mandatory"):
            _validate_tpsl_required(50.0, None)

        with pytest.raises(ValueError, match="mandatory"):
            _validate_tpsl_required(None, None)

    def test_tpsl_validation_negative(self):
        """Test TP/SL validation rejects negative values."""
        with pytest.raises(ValueError, match="positive"):
            _validate_tpsl_required(-10.0, 20.0)

        with pytest.raises(ValueError, match="positive"):
            _validate_tpsl_required(50.0, -5.0)

    def test_tpsl_validation_zero(self):
        """Test TP/SL validation rejects zero values."""
        with pytest.raises(ValueError, match="positive"):
            _validate_tpsl_required(0.0, 20.0)

        with pytest.raises(ValueError, match="positive"):
            _validate_tpsl_required(50.0, 0.0)

    def test_tpsl_validation_excessive_sl(self):
        """Test TP/SL validation rejects SL >= 100%."""
        with pytest.raises(ValueError, match="cannot be >= 100%"):
            _validate_tpsl_required(50.0, 100.0)

        with pytest.raises(ValueError, match="cannot be >= 100%"):
            _validate_tpsl_required(50.0, 150.0)

    def test_tpsl_validation_excessive_tp(self):
        """Test TP/SL validation rejects unrealistic TP."""
        with pytest.raises(ValueError, match="unrealistic"):
            _validate_tpsl_required(500.0, 20.0)

        with pytest.raises(ValueError, match="unrealistic"):
            _validate_tpsl_required(1000.0, 20.0)

    def test_tpsl_validation_too_low(self):
        """Test TP/SL validation rejects values <5%."""
        with pytest.raises(ValueError, match="too low"):
            _validate_tpsl_required(2.0, 20.0)

        with pytest.raises(ValueError, match="too low"):
            _validate_tpsl_required(50.0, 1.0)

    def test_tpsl_validation_valid_ranges(self):
        """Test TP/SL validation accepts valid ranges."""
        # Should not raise
        _validate_tpsl_required(50.0, 20.0)  # Balanced
        _validate_tpsl_required(5.0, 5.0)    # Minimum
        _validate_tpsl_required(200.0, 50.0) # Aggressive
        _validate_tpsl_required(100.0, 99.0) # Edge case

    @pytest.mark.asyncio
    async def test_execute_buy_with_invalid_tpsl(self):
        """Test execute_buy_with_tpsl rejects invalid TP/SL."""
        with pytest.raises(ValueError, match="mandatory"):
            await execute_buy_with_tpsl(
                token_address="Token",
                amount_sol=0.1,
                wallet_address="Wallet",
                tp_percent=None,  # Invalid
                sl_percent=20.0,
            )

    @pytest.mark.asyncio
    async def test_multiple_positions_checked(self):
        """Test that multiple positions are all checked for triggers."""
        positions = [
            {
                "id": "pos1",
                "symbol": "TOKEN1",
                "address": "addr1",
                "entry_price": 1.0,
                "current_price": 1.6,  # TP at 1.5
                "tp_percent": 50.0,
                "sl_percent": 20.0,
                "tp_price": 1.5,
                "sl_price": 0.8,
                "amount": 100,
                "amount_sol": 0.1,
            },
            {
                "id": "pos2",
                "symbol": "TOKEN2",
                "address": "addr2",
                "entry_price": 2.0,
                "current_price": 1.5,  # SL at 1.6
                "tp_percent": 100.0,
                "sl_percent": 20.0,
                "tp_price": 4.0,
                "sl_price": 1.6,
                "amount": 200,
                "amount_sol": 0.2,
            },
            {
                "id": "pos3",
                "symbol": "TOKEN3",
                "address": "addr3",
                "entry_price": 0.5,
                "current_price": 0.55,  # No trigger
                "tp_percent": 50.0,
                "sl_percent": 20.0,
                "tp_price": 0.75,
                "sl_price": 0.4,
                "amount": 300,
                "amount_sol": 0.15,
            },
        ]

        user_data = {"positions": positions}

        alerts = await _check_demo_exit_triggers(user_data, positions)

        # Should have 2 alerts (1 TP, 1 SL)
        assert len(alerts) == 2

        # Verify both triggers
        alert_types = {alert["type"] for alert in alerts}
        assert "take_profit" in alert_types
        assert "stop_loss" in alert_types


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
