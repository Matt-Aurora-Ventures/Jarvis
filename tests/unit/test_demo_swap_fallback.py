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
    # Patch the actual bags client that gets imported in get_bags_client
    def mock_get_bags(profile=None):
        return DummyBagsClient(DummyBagsResult(True, to_amount=123.0, tx_hash="bags_tx"))

    async def mock_to_base(mint, amt, jup):
        return int(amt * 1e9)

    async def mock_from_base(mint, amt, jup):
        return amt / 1e9

    monkeypatch.setattr("core.trading.bags_client.get_bags_client", mock_get_bags)
    monkeypatch.setattr("tg_bot.handlers.demo.demo_trading._get_jupiter_client", lambda: DummyJupiter(output_amount=999))
    monkeypatch.setattr("tg_bot.handlers.demo.demo_trading._load_demo_wallet", lambda _addr=None: object())
    monkeypatch.setattr("tg_bot.handlers.demo.demo_trading._to_base_units", mock_to_base)
    monkeypatch.setattr("tg_bot.handlers.demo.demo_trading._from_base_units", mock_from_base)

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
    # Patch the actual bags client that gets imported in get_bags_client
    def mock_get_bags(profile=None):
        return DummyBagsClient(DummyBagsResult(False, error="bags down"))

    async def mock_to_base(mint, amt, jup):
        return int(amt * 1e9)

    async def mock_from_base(mint, amt, jup):
        return amt / 1e9

    # Set up dummy Jupiter client
    jupiter = DummyJupiter(output_amount=1_000_000_000)

    # Reset the global Jupiter client cache in demo_trading module
    import tg_bot.handlers.demo.demo_trading as demo_trading_mod
    demo_trading_mod._JUPITER_CLIENT = jupiter

    class DummyWallet:
        pass

    def mock_load_wallet(_addr=None):
        return DummyWallet()

    monkeypatch.setattr("core.trading.bags_client.get_bags_client", mock_get_bags)
    monkeypatch.setattr("tg_bot.handlers.demo.demo_trading._get_jupiter_client", lambda: jupiter)
    monkeypatch.setattr("tg_bot.handlers.demo.demo_trading._load_demo_wallet", mock_load_wallet)
    monkeypatch.setattr("tg_bot.handlers.demo.demo_trading._to_base_units", mock_to_base)
    monkeypatch.setattr("tg_bot.handlers.demo.demo_trading._from_base_units", mock_from_base)

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
