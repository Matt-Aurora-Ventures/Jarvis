import pytest

from tg_bot.handlers import demo as demo_mod


class DummyBagsResult:
    def __init__(self, success: bool, to_amount: float = 0.0, tx_hash: str = None, error: str = None):
        self.success = success
        self.to_amount = to_amount
        self.tx_hash = tx_hash
        self.error = error


class DummyBagsClient:
    api_key = "test"
    partner_key = "partner"

    def __init__(self, result: DummyBagsResult):
        self._result = result

    async def swap(self, **_kwargs):
        return self._result


class DummyTokenInfo:
    def __init__(self, decimals: int):
        self.decimals = decimals


class DummyJupiter:
    def __init__(self, output_amount: int = 0):
        self._output_amount = output_amount
        self.quote_calls = 0

    async def get_token_info(self, _mint):
        return DummyTokenInfo(decimals=9)

    async def get_quote(self, **_kwargs):
        self.quote_calls += 1
        return object()

    async def execute_swap(self, _quote, _wallet):
        class _Result:
            success = True
            signature = "jupiter_tx"
            output_amount = self._output_amount
            error = None

        return _Result()


@pytest.mark.asyncio
async def test_swap_prefers_bags_success(monkeypatch):
    monkeypatch.setattr(
        demo_mod,
        "get_bags_client",
        lambda: DummyBagsClient(DummyBagsResult(True, to_amount=123.0, tx_hash="bags_tx")),
    )
    monkeypatch.setattr(demo_mod, "_get_jupiter_client", lambda: DummyJupiter(output_amount=999))
    monkeypatch.setattr(demo_mod, "_load_demo_wallet", lambda _addr=None: object())

    result = await demo_mod._execute_swap_with_fallback(
        from_token="So11111111111111111111111111111111111111112",
        to_token="TokenMint11111111111111111111111111111111111",
        amount=0.5,
        wallet_address="wallet",
        slippage_bps=100,
    )

    assert result["success"] is True
    assert result["source"] == "bags_fm"
    assert result["tx_hash"] == "bags_tx"
    assert result["amount_out"] == 123.0


@pytest.mark.asyncio
async def test_swap_falls_back_to_jupiter(monkeypatch):
    monkeypatch.setattr(
        demo_mod,
        "get_bags_client",
        lambda: DummyBagsClient(DummyBagsResult(False, error="bags down")),
    )
    jupiter = DummyJupiter(output_amount=1_000_000_000)
    monkeypatch.setattr(demo_mod, "_get_jupiter_client", lambda: jupiter)
    monkeypatch.setattr(demo_mod, "_load_demo_wallet", lambda _addr=None: object())

    result = await demo_mod._execute_swap_with_fallback(
        from_token="So11111111111111111111111111111111111111112",
        to_token="TokenMint11111111111111111111111111111111111",
        amount=1.0,
        wallet_address="wallet",
        slippage_bps=100,
    )

    assert result["success"] is True
    assert result["source"] == "jupiter"
    assert result["tx_hash"] == "jupiter_tx"
    assert result["amount_out"] == 1.0  # 1e9 base units with 9 decimals
    assert jupiter.quote_calls == 1
