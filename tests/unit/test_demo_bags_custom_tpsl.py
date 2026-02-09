import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_bags_custom_tpsl_menu_is_handled_and_links_back_to_bags_buy():
    """
    Regression: legacy DemoMenuBuilder emits demo:bags_custom_tpsl:<token_ref>, but the
    modular bags callback handler must support it (no "Unknown Bags.fm action").
    """
    from tg_bot.handlers.demo import DemoMenuBuilder, JarvisTheme
    from tg_bot.handlers.demo.callbacks.bags import handle_bags

    ctx = SimpleNamespace(
        JarvisTheme=JarvisTheme,
        DemoMenuBuilder=DemoMenuBuilder,
        get_bags_top_tokens_with_sentiment=AsyncMock(return_value=[{"address": "addr", "symbol": "BUTT"}]),
        resolve_token_ref=MagicMock(return_value="addr"),
    )

    update = MagicMock()
    context = MagicMock()
    context.user_data = {"bags_tp_percent": 15.0, "bags_sl_percent": 15.0}
    state = {"market_regime": {}}

    text, kb = await handle_bags(
        ctx,
        "bags_custom_tpsl",
        "demo:bags_custom_tpsl:tok123",
        update,
        context,
        state,
    )

    assert "CUSTOM TP/SL" in (text or "")
    assert kb is not None

    found_buy = False
    for row in getattr(kb, "inline_keyboard", []) or []:
        for btn in row:
            cb = str(getattr(btn, "callback_data", "") or "")
            if cb.startswith("demo:bags_buy:tok123:"):
                found_buy = True
                break
        if found_buy:
            break

    assert found_buy is True

