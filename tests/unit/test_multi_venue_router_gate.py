from unittest.mock import ANY, AsyncMock, MagicMock

import pytest

from core.events.trading_pipeline import PipelineAction, PipelineResult, RejectionReason
from core.trading.multi_venue_router import MultiVenueRouter, Quote, Venue


def _quote(venue: Venue) -> Quote:
    return Quote(
        venue=venue,
        input_mint="So11111111111111111111111111111111111111112",
        output_mint="TokenMint111111111111111111111111111111111",
        input_amount=5_000_000_000,
        output_amount=100_000_000,
        price_impact=0.20,
        fees=0,
        partner_fee_earned=0,
        route=["test"],
        expires_at=0,
        quote_data={"outAmount": "100000000"},
    )


@pytest.mark.asyncio
async def test_route_and_execute_rejects_when_execution_gate_fails():
    router = MultiVenueRouter(bags_api_key="bags-key")
    router.get_all_quotes = AsyncMock(return_value={Venue.BAGS: _quote(Venue.BAGS)})
    router._execute_bags_swap = AsyncMock(side_effect=AssertionError("bags execution called"))
    router._execute_jupiter_swap = AsyncMock(side_effect=AssertionError("jupiter execution called"))

    rejected = PipelineResult(
        action=PipelineAction.SKIP,
        rejection_reason=RejectionReason.COST_TOO_HIGH,
        rejection_detail="RT cost exceeds safety threshold",
    )
    router.execution_pipeline.evaluate = MagicMock(return_value=rejected)

    decision = router.decide_venue({Venue.BAGS: _quote(Venue.BAGS)})
    router.decide_venue = MagicMock(return_value=decision)

    with pytest.raises(ValueError, match="Execution gate rejected"):
        await router.route_and_execute(
            input_mint="So11111111111111111111111111111111111111112",
            output_mint="TokenMint111111111111111111111111111111111",
            amount=5_000_000_000,
            wallet_keypair=MagicMock(),
        )

    router.execution_pipeline.evaluate.assert_called_once()


@pytest.mark.asyncio
async def test_route_and_execute_calls_selected_venue_after_gate_passes():
    router = MultiVenueRouter(bags_api_key="bags-key")
    selected_quote = _quote(Venue.BAGS)
    router.get_all_quotes = AsyncMock(return_value={Venue.BAGS: selected_quote})
    router._execute_bags_swap = AsyncMock(return_value={"signature": "bags-tx"})
    router._execute_jupiter_swap = AsyncMock(side_effect=AssertionError("jupiter execution called"))

    allowed = PipelineResult(action=PipelineAction.ENTER, trade_size_usd=750.0)
    router.execution_pipeline.evaluate = MagicMock(return_value=allowed)

    decision = router.decide_venue({Venue.BAGS: selected_quote})
    router.decide_venue = MagicMock(return_value=decision)

    result = await router.route_and_execute(
        input_mint="So11111111111111111111111111111111111111112",
        output_mint="TokenMint111111111111111111111111111111111",
        amount=500_000_000,
        wallet_keypair=MagicMock(),
    )

    assert result["venue"] == Venue.BAGS.value
    assert result["execution"]["signature"] == "bags-tx"
    router._execute_bags_swap.assert_called_once_with(selected_quote, ANY)
