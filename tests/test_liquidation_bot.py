"""Tests for liquidation sweep strategy."""

from datetime import datetime, timezone

from core import liquidation_bot


def test_parse_liquidation_csv_window_sum():
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    old_ms = now_ms - (60 * 60 * 1000)

    rows = [
        ["symbol", "a", "b", "c", "d", "price", "x", "time", "usd"],
        ["WIF", "x", "x", "x", "x", "1.00", "x", str(now_ms), "100"],
        ["WIF", "x", "x", "x", "x", "1.10", "x", str(now_ms - 60_000), "50"],
        ["WIF", "x", "x", "x", "x", "1.20", "x", str(old_ms), "200"],
    ]
    csv_text = "\n".join([",".join(row) for row in rows])

    total, price = liquidation_bot._parse_liquidation_csv(
        csv_text,
        symbol="WIF",
        time_window_mins=5,
        symbol_col=0,
        price_col=5,
        time_col=7,
        usd_col=8,
    )

    assert total == 150.0
    assert price == 1.10


def test_evaluate_symbol_signal(monkeypatch):
    cfg = {
        "order_usd_size": 10,
        "leverage": 3,
        "entry_offset_pct": 0.005,
        "symbols_data": {
            "WIF": {
                "liquidations": 100,
                "time_window_mins": 5,
                "sl": -6,
                "tp": 6,
            }
        },
    }

    monkeypatch.setattr(liquidation_bot, "fetch_liquidation_data", lambda s, sc, c: (150.0, 1.0))
    monkeypatch.setattr(liquidation_bot.hyperliquid, "fetch_mid_price", lambda s: 1.05)

    signal = liquidation_bot.evaluate_symbol("WIF", cfg)
    assert signal is not None
    assert signal.symbol == "WIF"
    assert signal.entry_price < 1.0
    assert signal.take_profit_price < signal.entry_price
    assert signal.stop_loss_price > signal.entry_price
