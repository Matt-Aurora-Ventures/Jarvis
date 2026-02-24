import pytest
import asyncio
from core.open_claw.signals.engines import MacroEngine, MicroEngine, PolicyEnvelope, breaking_news_check
from core.open_claw.sdk import OpenClawSDK
from core.open_claw.signals.stats import wilson_lower_bound

def test_wilson_lower_bound():
    score = wilson_lower_bound(95, 100)
    assert score > 0.85 and score < 0.95
    score_low = wilson_lower_bound(1, 1)
    assert score_low < 0.30

def test_macro_envelope_parsing():
    policy = PolicyEnvelope(bias="BULLISH", max_lev=3.5, validation_price=50000.0)
    assert policy.bias == "BULLISH"

@pytest.mark.asyncio
async def test_micro_engine():
    policy = PolicyEnvelope(bias="BULLISH", max_lev=2.0, validation_price=10.0)
    micro = MicroEngine(policy)

    # Should be valid if price hasn't dropped below 10.0
    is_safe = await micro.evaluate_tick("SOL/USD", 15.0)
    assert is_safe is True

    # Should be invalid if price dropped below 10.0
    is_safe_danger = await micro.evaluate_tick("SOL/USD", 9.0)
    assert is_safe_danger is False

@pytest.mark.asyncio
async def test_openclaw_sdk_gate():
    sdk = OpenClawSDK()

    # strategy_1 has 95/100 history
    res = await sdk.evaluate_market_opportunity("strategy_1", "SOL/USD", 150.0)
    assert res["action"] == "BULLISH"
    assert res["confidence"] > 0.60

    # strategy_2 has 1/1 history (low wilson confidence bound)
    res_fail = await sdk.evaluate_market_opportunity("strategy_2", "SOL/USD", 150.0)
    assert res_fail["action"] == "FLAT"
    assert "Low confidence" in res_fail["reason"]
