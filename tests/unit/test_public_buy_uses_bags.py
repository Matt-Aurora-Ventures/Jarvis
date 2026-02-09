import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_public_execute_swap_uses_bags_for_purchases():
    """
    PublicTradingService policy: SOL->token "purchases" execute via bags.fm by default
    (no Jupiter fallback unless explicitly enabled).
    """
    from core.public_trading_service import PublicTradingService
    from bots.treasury.jupiter import SwapQuote

    wallet_service = MagicMock()
    service = PublicTradingService(wallet_service, rpc_url="https://example.invalid")

    # If this gets called, the policy is violated.
    service.jupiter.execute_swap = AsyncMock(side_effect=AssertionError("jupiter called"))

    # Fake keypair with a pubkey() method.
    keypair = MagicMock()
    keypair.pubkey.return_value = "Wallet111111111111111111111111111111111"

    # Fake bags client.
    bags_result = MagicMock(success=True, tx_hash="TX123", to_amount=42.0, error=None)
    bags = MagicMock(api_key="k", partner_key="p")
    bags.swap = AsyncMock(return_value=bags_result)

    quote = SwapQuote(
        input_mint=service.jupiter.SOL_MINT,
        output_mint="TokenMint111111111111111111111111111111111",
        input_amount=100_000_000,
        output_amount=1,
        input_amount_ui=0.1,
        output_amount_ui=123.0,
        price_impact_pct=0.01,
        slippage_bps=100,
        fees_usd=0.0,
        route_plan=[],
        quote_response={},
    )

    with (
        patch("core.public_trading_service.get_bags_api_client", return_value=bags),
        patch.dict(os.environ, {"PUBLIC_BUY_ALLOW_JUPITER_FALLBACK": "0"}, clear=False),
    ):
        result = await service.execute_swap(quote, keypair)

    assert result.success is True
    assert result.signature == "TX123"

    await service.close()

