import pytest
from types import SimpleNamespace

from tg_bot.handlers.demo.demo_callbacks import CallbackRouter


@pytest.mark.asyncio
async def test_router_routes_exact_action(monkeypatch):
    async def fake_wallet(ctx, action, data, update, context, state):
        return "wallet_ok", None

    import tg_bot.handlers.demo.callbacks.wallet as wallet_mod
    monkeypatch.setattr(wallet_mod, "handle_wallet", fake_wallet)

    router = CallbackRouter(context_loader=SimpleNamespace())
    result = await router.route(
        "wallet_menu",
        "demo:wallet_menu",
        SimpleNamespace(),
        SimpleNamespace(),
        {},
    )

    assert result == ("wallet_ok", None)


@pytest.mark.asyncio
async def test_router_routes_prefix_buy(monkeypatch):
    async def fake_buy(ctx, action, data, update, context, state):
        return "buy_ok", None

    import tg_bot.handlers.demo.callbacks.buy as buy_mod
    monkeypatch.setattr(buy_mod, "handle_buy", fake_buy)

    router = CallbackRouter(context_loader=SimpleNamespace())
    result = await router.route(
        "buy",
        "demo:buy:So11111111111111111111111111111111111111112:0.1",
        SimpleNamespace(),
        SimpleNamespace(),
        {},
    )

    assert result == ("buy_ok", None)


@pytest.mark.asyncio
async def test_router_routes_unknown_to_main(monkeypatch):
    calls = {}

    async def fake_nav(ctx, action, data, update, context, state):
        calls["action"] = action
        calls["data"] = data
        return "main_ok", None

    import tg_bot.handlers.demo.callbacks.navigation as nav_mod
    monkeypatch.setattr(nav_mod, "handle_navigation", fake_nav)

    router = CallbackRouter(context_loader=SimpleNamespace())
    result = await router.route(
        "unknown",
        "demo:unknown",
        SimpleNamespace(),
        SimpleNamespace(),
        {},
    )

    assert result == ("main_ok", None)
    assert calls["action"] == "main"
    assert calls["data"] == "demo:main"
