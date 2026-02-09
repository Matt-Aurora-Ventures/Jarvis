import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch


def _has_prev_menu_button(kb) -> bool:
    if not kb:
        return False
    for row in getattr(kb, "inline_keyboard", []) or []:
        for btn in row:
            if getattr(btn, "callback_data", None) == "demo:nav_back":
                return True
    return False


def test_success_and_error_messages_include_prev_menu():
    from tg_bot.handlers.demo import DemoMenuBuilder

    _, kb = DemoMenuBuilder.success_message("Test", "OK")
    assert _has_prev_menu_button(kb)

    _, kb = DemoMenuBuilder.error_message("Boom", retry_action="demo:main")
    assert _has_prev_menu_button(kb)


@pytest.mark.asyncio
async def test_trending_does_not_inject_fake_tokens_when_empty():
    """
    Regression: trending previously injected BONK/WIF/POPCAT/MEW placeholders.
    We want real data only: empty -> error/empty-state, no fake tokens.
    """
    from tg_bot.handlers.demo import DemoMenuBuilder, JarvisTheme
    from tg_bot.handlers.demo.callbacks.trading import handle_trading

    ctx = SimpleNamespace(
        JarvisTheme=JarvisTheme,
        DemoMenuBuilder=DemoMenuBuilder,
        get_trending_with_sentiment=AsyncMock(return_value=[]),
        register_token_id=MagicMock(return_value="tok"),
    )

    update = MagicMock()
    context = MagicMock()
    state = {"market_regime": {}, "positions": [], "sol_balance": 0.0}

    text, kb = await handle_trading(ctx, "trending", "demo:trending", update, context, state)

    assert "Trending tokens are temporarily unavailable" in text
    assert "BONK" not in text
    assert _has_prev_menu_button(kb)


@pytest.mark.asyncio
async def test_insta_snipe_does_not_use_placeholder_token_when_sources_fail():
    """
    Regression: insta_snipe used a hardcoded FARTCOIN placeholder when upstream
    sources fail. We want a real-data-only empty-state instead.
    """
    from tg_bot.handlers.demo import DemoMenuBuilder, JarvisTheme
    from tg_bot.handlers.demo.callbacks.snipe import handle_snipe

    # Minimal ctx for this branch.
    ctx = SimpleNamespace(
        JarvisTheme=JarvisTheme,
        DemoMenuBuilder=DemoMenuBuilder,
        get_bags_top_tokens_with_sentiment=AsyncMock(return_value=[]),
        register_token_id=MagicMock(return_value="tok"),
        conviction_label=MagicMock(return_value="LOW"),
    )

    # Update/callback_query scaffolding.
    query = MagicMock()
    query.from_user = SimpleNamespace(id=123)
    update = MagicMock()
    update.callback_query = query

    context = MagicMock()
    state = {"market_regime": {}}

    # Force DexScreener boosted list empty.
    with patch("core.dexscreener.get_boosted_tokens_with_data", return_value=[]):
        text, kb = await handle_snipe(ctx, "insta_snipe", "demo:insta_snipe", update, context, state)

    assert "Insta Snipe is temporarily unavailable" in text
    assert "FARTCOIN" not in text
    assert _has_prev_menu_button(kb)

