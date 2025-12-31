"""Tests for deterministic trading pipeline."""

import math

from core import trading_pipeline


def _build_candles(count: int = 80):
    candles = []
    base = 100.0
    for i in range(count):
        price = base + (i * 0.15) + math.sin(i / 4) * 1.5
        candles.append({
            "timestamp": i,
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "volume": 1.0,
        })
    return candles


def test_backtest_sma_cross_runs():
    candles = _build_candles()
    strategy = trading_pipeline.StrategyConfig(
        kind="sma_cross",
        params={"fast": 5, "slow": 15},
        capital_usd=1000.0,
    )
    result = trading_pipeline.run_backtest(candles, "BTC", "1h", strategy)

    assert result.error is None
    assert result.total_trades >= 0
    assert isinstance(result.sharpe_ratio, float)
    assert isinstance(result.roi, float)


def test_backtest_rsi_runs():
    candles = _build_candles()
    strategy = trading_pipeline.StrategyConfig(
        kind="rsi",
        params={"period": 7, "lower": 30, "upper": 70},
        capital_usd=1000.0,
    )
    result = trading_pipeline.run_backtest(candles, "ETH", "1h", strategy)

    assert result.error is None
    assert result.total_trades >= 0
    assert isinstance(result.expectancy, float)
