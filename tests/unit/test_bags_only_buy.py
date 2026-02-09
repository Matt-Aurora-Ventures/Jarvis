import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_execute_swap_bags_only_does_not_call_jupiter():
    """
    If allow_jupiter_fallback=False, _execute_swap_with_fallback must never
    attempt Jupiter even when bags.fm fails.
    """
    from tg_bot.handlers.demo import demo_trading

    mock_bags = MagicMock()
    mock_bags.api_key = "k"
    mock_bags.partner_key = "p"
    mock_bags.swap = AsyncMock(side_effect=Exception("bags down"))

    with (
        patch("tg_bot.handlers.demo.demo_trading._get_demo_circuit_breaker", return_value=None),
        patch("tg_bot.handlers.demo.demo_trading.get_bags_client", return_value=mock_bags),
        patch("tg_bot.handlers.demo.demo_trading._get_jupiter_client", side_effect=AssertionError("jupiter called")),
    ):
        with pytest.raises(demo_trading.BagsAPIError):
            await demo_trading._execute_swap_with_fallback(
                from_token="So11111111111111111111111111111111111111112",
                to_token="TokenMint1111111111111111111111111111111111",
                amount=0.1,
                wallet_address="Wallet111111111111111111111111111111111",
                slippage_bps=100,
                allow_jupiter_fallback=False,
            )

