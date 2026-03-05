"""Tests for core.data.historical — OHLCV quality validation."""

from datetime import datetime, timezone, timedelta

import pytest

pd = pytest.importorskip("pandas")

from core.data.historical import (
    validate_ohlcv,
    DataQualityReport,
    MIN_CANDLES_FOR_BACKTEST,
    MIN_VOLUME_USD,
    SANDWICH_WICK_THRESHOLD,
    TIMEFRAME_SECONDS,
    CEX_LISTED_SYMBOLS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_df(n: int, *, timeframe: str = "1h", start_ts: datetime = None,
             volume: float = 1000.0, close: float = 100.0) -> pd.DataFrame:
    """Generate a clean OHLCV DataFrame with *n* candles."""
    start = start_ts or datetime(2025, 6, 1, tzinfo=timezone.utc)
    interval = timedelta(seconds=TIMEFRAME_SECONDS[timeframe])
    rows = []
    for i in range(n):
        ts = start + interval * i
        rows.append({
            "timestamp": ts,
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume_usd": volume,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestValidateOhlcv:

    def test_empty_df_returns_empty(self):
        df = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume_usd"])
        cleaned, report = validate_ohlcv(df, "1h")
        assert cleaned.empty
        assert report.total_candles == 0

    def test_drops_low_volume_candles(self):
        df = _make_df(10, volume=100.0)  # Below MIN_VOLUME_USD (500)
        cleaned, report = validate_ohlcv(df, "1h")
        assert len(cleaned) == 0
        assert report.dropped_low_volume == 10

    def test_keeps_adequate_volume(self):
        df = _make_df(10, volume=1000.0)
        cleaned, report = validate_ohlcv(df, "1h")
        assert len(cleaned) == 10
        assert report.dropped_low_volume == 0

    def test_detects_sandwich_wicks(self):
        """Sandwich wick: (high - low) / close > 0.15 on 1m data."""
        df = _make_df(5, timeframe="1m", close=100.0)
        # Make candle 2 have a massive wick
        df.loc[2, "high"] = 120.0
        df.loc[2, "low"] = 80.0  # range=40, close=100 → ratio=0.40 > 0.15
        cleaned, report = validate_ohlcv(df, "1m")
        assert report.sandwich_wicks >= 1

    def test_no_sandwich_wicks_on_non_1m(self):
        """Sandwich wick detection only runs on 1m data."""
        df = _make_df(5, timeframe="1h", close=100.0)
        df.loc[2, "high"] = 200.0
        df.loc[2, "low"] = 10.0
        _, report = validate_ohlcv(df, "1h")
        assert report.sandwich_wicks == 0

    def test_deduplicates_timestamps(self):
        df = _make_df(5, volume=1000.0)
        df = pd.concat([df, df.iloc[[0]]]).reset_index(drop=True)
        assert len(df) == 6
        cleaned, _ = validate_ohlcv(df, "1h")
        assert len(cleaned) == 5

    def test_detects_stale_prices(self):
        df = _make_df(10, volume=1000.0, close=50.0)
        # Make all candles identical OHLC
        for col in ["open", "high", "low", "close"]:
            df[col] = 50.0
        _, report = validate_ohlcv(df, "1h")
        assert report.stale_candles > 0

    def test_gap_percentage_calculation(self):
        """Remove half the candles — gap_pct should be ~0.5."""
        df = _make_df(20, timeframe="1h", volume=1000.0)
        # Keep only even-indexed candles
        df = df.iloc[::2].reset_index(drop=True)
        assert len(df) == 10
        _, report = validate_ohlcv(df, "1h")
        assert report.gap_pct > 0.4
        assert report.missing_candles > 0

    def test_backtest_eligibility_true(self):
        df = _make_df(1200, volume=1000.0)
        _, report = validate_ohlcv(df, "1h")
        assert report.is_backtest_eligible

    def test_backtest_eligibility_false_too_few(self):
        df = _make_df(500, volume=1000.0)
        _, report = validate_ohlcv(df, "1h")
        assert not report.is_backtest_eligible

    def test_backtest_eligibility_false_high_gaps(self):
        df = _make_df(2000, timeframe="1h", volume=1000.0)
        # Remove 50% of candles
        df = df.iloc[::3].reset_index(drop=True)
        _, report = validate_ohlcv(df, "1h")
        assert not report.is_backtest_eligible  # gap_pct > 20%

    def test_report_summary_string(self):
        df = _make_df(100, volume=1000.0)
        _, report = validate_ohlcv(df, "1h")
        s = report.summary()
        assert "Candles:" in s
        assert "Eligible:" in s


class TestConstants:

    def test_timeframe_seconds(self):
        assert TIMEFRAME_SECONDS["1m"] == 60
        assert TIMEFRAME_SECONDS["1h"] == 3600
        assert TIMEFRAME_SECONDS["1d"] == 86400

    def test_cex_listed_symbols(self):
        assert "SOL" in CEX_LISTED_SYMBOLS
        assert CEX_LISTED_SYMBOLS["SOL"] == "SOL/USDT"
