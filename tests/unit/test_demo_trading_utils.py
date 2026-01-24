import pytest
from types import SimpleNamespace

from tg_bot.handlers.demo import demo_trading as dt


class DummyJupiter:
    def __init__(self, decimals=None, raise_error=False):
        self._decimals = decimals
        self._raise = raise_error

    async def get_token_info(self, _mint: str):
        if self._raise:
            raise RuntimeError("boom")
        if self._decimals is None:
            return None
        return SimpleNamespace(decimals=self._decimals)


@pytest.mark.asyncio
async def test_get_token_decimals_sol_override():
    jup = DummyJupiter(decimals=6)
    decimals = await dt._get_token_decimals("So11111111111111111111111111111111111111112", jup)
    assert decimals == 9


@pytest.mark.asyncio
async def test_get_token_decimals_from_info():
    jup = DummyJupiter(decimals=8)
    decimals = await dt._get_token_decimals("mint", jup)
    assert decimals == 8


@pytest.mark.asyncio
async def test_get_token_decimals_fallback():
    jup = DummyJupiter(raise_error=True)
    decimals = await dt._get_token_decimals("mint", jup)
    assert decimals == 6


@pytest.mark.asyncio
async def test_unit_conversions():
    jup = DummyJupiter(decimals=6)
    base = await dt._to_base_units("mint", 1.5, jup)
    assert base == 1_500_000

    human = await dt._from_base_units("mint", 1_500_000, jup)
    assert human == pytest.approx(1.5)


def test_validate_buy_amount():
    ok, msg = dt.validate_buy_amount(0.009)
    assert ok is False
    assert "Minimum" in msg

    ok, msg = dt.validate_buy_amount(0.5)
    assert ok is True
    assert msg == ""

    ok, msg = dt.validate_buy_amount(100)
    assert ok is False
    assert "Maximum" in msg
