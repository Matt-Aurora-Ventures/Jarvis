"""
Integration tests for US-005: bags.fm + Jupiter Backup with TP/SL

Tests the integration between:
- core/bags_api.py
- core/jupiter_api.py
- tg_bot/handlers/demo.py (execute_buy_with_tpsl)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestUS005Integration:
    """Integration tests for US-005 trading flow."""

    @pytest.mark.asyncio
    async def test_bags_api_module_imports(self):
        """Verify BagsAPI module can be imported."""
        from core.bags_api import BagsAPI, get_bags_api

        api = BagsAPI()
        assert api.BASE_URL == "https://api.bags.fm/v1"

        singleton = get_bags_api()
        assert singleton is not None

    @pytest.mark.asyncio
    async def test_jupiter_api_module_imports(self):
        """Verify JupiterAPI module can be imported."""
        from core.jupiter_api import JupiterAPI, get_jupiter_api

        api = JupiterAPI()
        assert api.BASE_URL == "https://quote-api.jup.ag/v6"

        singleton = get_jupiter_api()
        assert singleton is not None

    @pytest.mark.asyncio
    async def test_execute_buy_with_tpsl_module_imports(self):
        """Verify execute_buy_with_tpsl can be imported."""
        from tg_bot.handlers.demo import execute_buy_with_tpsl

        assert callable(execute_buy_with_tpsl)

    @pytest.mark.asyncio
    async def test_full_buy_flow_with_bags_success(self):
        """Test full buy flow when Bags.fm succeeds."""
        from tg_bot.handlers.demo import execute_buy_with_tpsl

        with patch('tg_bot.handlers.demo._execute_swap_with_fallback') as mock_swap:
            mock_swap.return_value = {
                "success": True,
                "source": "bags_fm",
                "tx_hash": "bags_tx_integration",
                "amount_out": 50000.0,
            }

            with patch('tg_bot.handlers.demo.get_ai_sentiment_for_token') as mock_sentiment:
                mock_sentiment.return_value = {
                    "symbol": "INTEG",
                    "price": 0.0001,
                }

                result = await execute_buy_with_tpsl(
                    token_address="INTEGRATION_TOKEN_MINT",
                    amount_sol=1.0,
                    wallet_address="test_wallet",
                )

                assert result["success"] is True
                assert result["source"] == "bags_fm"
                assert result["position"]["tp_percent"] == 50.0
                assert result["position"]["sl_percent"] == 20.0
                assert result["position"]["source"] == "bags_fm"

    @pytest.mark.asyncio
    async def test_full_buy_flow_with_jupiter_fallback(self):
        """Test full buy flow when Bags.fm fails and Jupiter is used."""
        from tg_bot.handlers.demo import execute_buy_with_tpsl

        with patch('tg_bot.handlers.demo._execute_swap_with_fallback') as mock_swap:
            mock_swap.return_value = {
                "success": True,
                "source": "jupiter",  # Fallback was used
                "tx_hash": "jupiter_tx_integration",
                "amount_out": 45000.0,
            }

            with patch('tg_bot.handlers.demo.get_ai_sentiment_for_token') as mock_sentiment:
                mock_sentiment.return_value = {
                    "symbol": "FALLBACK",
                    "price": 0.00012,
                }

                result = await execute_buy_with_tpsl(
                    token_address="FALLBACK_TOKEN_MINT",
                    amount_sol=0.5,
                    wallet_address="test_wallet_2",
                )

                assert result["success"] is True
                assert result["source"] == "jupiter"
                assert result["position"]["source"] == "jupiter"

    @pytest.mark.asyncio
    async def test_position_tp_sl_calculation_integration(self):
        """Test that TP/SL prices are correctly calculated in integration."""
        from tg_bot.handlers.demo import execute_buy_with_tpsl

        entry_price = 0.001  # $0.001 per token

        with patch('tg_bot.handlers.demo._execute_swap_with_fallback') as mock_swap:
            mock_swap.return_value = {
                "success": True,
                "source": "bags_fm",
                "tx_hash": "calc_test_tx",
                "amount_out": 1000.0,
            }

            with patch('tg_bot.handlers.demo.get_ai_sentiment_for_token') as mock_sentiment:
                mock_sentiment.return_value = {
                    "symbol": "CALC",
                    "price": entry_price,
                }

                # Test with 100% TP (2x), 25% SL
                result = await execute_buy_with_tpsl(
                    token_address="CALC_TOKEN",
                    amount_sol=0.1,
                    wallet_address="calc_wallet",
                    tp_percent=100.0,
                    sl_percent=25.0,
                )

                position = result["position"]

                # TP should be 2x entry price
                assert position["tp_price"] == pytest.approx(entry_price * 2.0, rel=1e-6)
                # SL should be 0.75x entry price
                assert position["sl_price"] == pytest.approx(entry_price * 0.75, rel=1e-6)

    @pytest.mark.asyncio
    async def test_bags_api_and_jupiter_api_can_coexist(self):
        """Test that both API clients can be instantiated simultaneously."""
        from core.bags_api import BagsAPI
        from core.jupiter_api import JupiterAPI

        bags = BagsAPI()
        jupiter = JupiterAPI()

        # Both should have their own URLs
        assert bags.BASE_URL != jupiter.BASE_URL
        assert "bags.fm" in bags.BASE_URL
        assert "jup.ag" in jupiter.BASE_URL

    @pytest.mark.asyncio
    async def test_execute_buy_handles_zero_price(self):
        """Test execute_buy_with_tpsl handles zero price gracefully."""
        from tg_bot.handlers.demo import execute_buy_with_tpsl

        with patch('tg_bot.handlers.demo._execute_swap_with_fallback') as mock_swap:
            mock_swap.return_value = {
                "success": True,
                "source": "bags_fm",
                "tx_hash": "zero_price_tx",
                "amount_out": 100.0,
            }

            with patch('tg_bot.handlers.demo.get_ai_sentiment_for_token') as mock_sentiment:
                mock_sentiment.return_value = {
                    "symbol": "ZERO",
                    "price": 0,  # Zero price
                }

                result = await execute_buy_with_tpsl(
                    token_address="ZERO_PRICE_TOKEN",
                    amount_sol=0.1,
                    wallet_address="zero_wallet",
                )

                # Should still succeed, but TP/SL prices will be 0
                assert result["success"] is True
                position = result["position"]
                assert position["entry_price"] == 0
                assert position["tp_price"] == 0
                assert position["sl_price"] == 0
