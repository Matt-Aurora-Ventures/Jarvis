"""
Tests for execute_buy_with_tpsl() - Dual execution with TP/SL defaults

US-005: bags.fm + Jupiter Backup with TP/SL
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestExecuteBuyWithTPSL:
    """Test execute_buy_with_tpsl() function in demo handler."""

    @pytest.mark.asyncio
    async def test_returns_position_with_default_tp_sl(self):
        """execute_buy_with_tpsl() should return position with 50% TP, 20% SL defaults."""
        from tg_bot.handlers.demo import execute_buy_with_tpsl

        # Mock the swap execution
        with patch('tg_bot.handlers.demo.demo_trading._execute_swap_with_fallback') as mock_swap:
            mock_swap.return_value = {
                "success": True,
                "source": "bags_fm",
                "tx_hash": "tx123",
                "amount_out": 1000.0,
            }

            with patch('tg_bot.handlers.demo.demo_sentiment.get_ai_sentiment_for_token') as mock_sentiment:
                mock_sentiment.return_value = {
                    "symbol": "TEST",
                    "price": 0.001,
                }

                result = await execute_buy_with_tpsl(
                    token_address="TOKEN_MINT_123",
                    amount_sol=0.5,
                    wallet_address="wallet123",
                )

                assert result["success"] is True
                assert result["position"]["tp_percent"] == 50.0
                assert result["position"]["sl_percent"] == 20.0

    @pytest.mark.asyncio
    async def test_allows_custom_tp_sl(self):
        """execute_buy_with_tpsl() should accept custom TP/SL values."""
        from tg_bot.handlers.demo import execute_buy_with_tpsl

        with patch('tg_bot.handlers.demo.demo_trading._execute_swap_with_fallback') as mock_swap:
            mock_swap.return_value = {
                "success": True,
                "source": "jupiter",
                "tx_hash": "tx456",
                "amount_out": 2000.0,
            }

            with patch('tg_bot.handlers.demo.demo_sentiment.get_ai_sentiment_for_token') as mock_sentiment:
                mock_sentiment.return_value = {
                    "symbol": "CUSTOM",
                    "price": 0.002,
                }

                result = await execute_buy_with_tpsl(
                    token_address="TOKEN_MINT_456",
                    amount_sol=1.0,
                    wallet_address="wallet456",
                    tp_percent=100.0,
                    sl_percent=30.0,
                )

                assert result["success"] is True
                assert result["position"]["tp_percent"] == 100.0
                assert result["position"]["sl_percent"] == 30.0

    @pytest.mark.asyncio
    async def test_tries_bags_first_falls_back_to_jupiter(self):
        """execute_buy_with_tpsl() should try Bags.fm first, fallback to Jupiter."""
        from tg_bot.handlers.demo import execute_buy_with_tpsl

        with patch('tg_bot.handlers.demo.demo_trading._execute_swap_with_fallback') as mock_swap:
            # Simulate Jupiter fallback (Bags failed)
            mock_swap.return_value = {
                "success": True,
                "source": "jupiter",  # Indicates fallback was used
                "tx_hash": "jup_tx_789",
                "amount_out": 500.0,
            }

            with patch('tg_bot.handlers.demo.demo_sentiment.get_ai_sentiment_for_token') as mock_sentiment:
                mock_sentiment.return_value = {
                    "symbol": "FALLBACK",
                    "price": 0.0005,
                }

                result = await execute_buy_with_tpsl(
                    token_address="TOKEN_MINT_789",
                    amount_sol=0.25,
                    wallet_address="wallet789",
                )

                assert result["success"] is True
                # Source should indicate which DEX was used
                assert result["position"]["source"] in ["bags_fm", "jupiter", "bags_api"]

    @pytest.mark.asyncio
    async def test_returns_error_on_swap_failure(self):
        """execute_buy_with_tpsl() should return error if both DEXs fail."""
        from tg_bot.handlers.demo import execute_buy_with_tpsl

        with patch('tg_bot.handlers.demo.demo_trading._execute_swap_with_fallback') as mock_swap:
            mock_swap.return_value = {
                "success": False,
                "error": "All swap routes failed",
            }

            result = await execute_buy_with_tpsl(
                token_address="TOKEN_MINT_FAIL",
                amount_sol=0.1,
                wallet_address="wallet_fail",
            )

            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_position_has_required_fields(self):
        """execute_buy_with_tpsl() position should have all required fields."""
        from tg_bot.handlers.demo import execute_buy_with_tpsl

        with patch('tg_bot.handlers.demo.demo_trading._execute_swap_with_fallback') as mock_swap:
            mock_swap.return_value = {
                "success": True,
                "source": "bags_fm",
                "tx_hash": "tx_complete",
                "amount_out": 10000.0,
            }

            with patch('tg_bot.handlers.demo.demo_sentiment.get_ai_sentiment_for_token') as mock_sentiment:
                mock_sentiment.return_value = {
                    "symbol": "COMPLETE",
                    "price": 0.00001,
                }

                result = await execute_buy_with_tpsl(
                    token_address="TOKEN_COMPLETE",
                    amount_sol=2.0,
                    wallet_address="wallet_complete",
                )

                position = result["position"]

                # Required fields per US-005
                assert "id" in position
                assert "symbol" in position
                assert "address" in position
                assert "amount" in position
                assert "amount_sol" in position
                assert "entry_price" in position
                assert "tp_percent" in position
                assert "sl_percent" in position
                assert "tp_price" in position
                assert "sl_price" in position
                assert "source" in position
                assert "tx_hash" in position
                assert "timestamp" in position

    @pytest.mark.asyncio
    async def test_calculates_tp_sl_prices_correctly(self):
        """execute_buy_with_tpsl() should calculate TP/SL prices from entry."""
        from tg_bot.handlers.demo import execute_buy_with_tpsl

        entry_price = 0.001

        with patch('tg_bot.handlers.demo.demo_trading._execute_swap_with_fallback') as mock_swap:
            mock_swap.return_value = {
                "success": True,
                "source": "bags_fm",
                "tx_hash": "tx_calc",
                "amount_out": 1000.0,
            }

            with patch('tg_bot.handlers.demo.demo_sentiment.get_ai_sentiment_for_token') as mock_sentiment:
                mock_sentiment.return_value = {
                    "symbol": "CALC",
                    "price": entry_price,
                }

                result = await execute_buy_with_tpsl(
                    token_address="TOKEN_CALC",
                    amount_sol=1.0,
                    wallet_address="wallet_calc",
                    tp_percent=50.0,
                    sl_percent=20.0,
                )

                position = result["position"]

                expected_tp_price = entry_price * 1.5  # +50%
                expected_sl_price = entry_price * 0.8  # -20%

                assert abs(position["tp_price"] - expected_tp_price) < 0.0001
                assert abs(position["sl_price"] - expected_sl_price) < 0.0001
