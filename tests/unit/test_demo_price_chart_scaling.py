from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest


def test_generate_price_chart_does_not_fill_to_zero_for_high_prices():
    """
    Regression test: the old chart renderer used fill_between(y2=0) which forced
    the Y-axis to include zero, making BTC/SOL charts look flat in Telegram.
    """
    from tg_bot.handlers.demo.demo_ui import MATPLOTLIB_AVAILABLE, generate_price_chart

    if not MATPLOTLIB_AVAILABLE:
        pytest.skip("matplotlib not installed in this environment")

    now = datetime.now(timezone.utc)
    timestamps = [now - timedelta(hours=2), now - timedelta(hours=1), now]
    prices = [42000.0, 43000.0, 42500.0]

    captured: dict[str, float] = {}

    from matplotlib.axes._axes import Axes  # type: ignore

    orig = Axes.fill_between

    def _spy(self, x, y1, y2=0, *args, **kwargs):  # noqa: ANN001
        # Record the baseline used by the primary fill.
        if "y2" not in captured:
            try:
                captured["y2"] = float(y2)  # type: ignore[arg-type]
            except Exception:
                captured["y2"] = 0.0
        return orig(self, x, y1, y2, *args, **kwargs)

    with patch.object(Axes, "fill_between", new=_spy):
        buf = generate_price_chart(prices=prices, timestamps=timestamps, symbol="BTC", timeframe="24H")

    assert buf is not None
    assert buf.getbuffer().nbytes > 0
    assert captured.get("y2", 0.0) > 1000.0

