"""Tests for core.trading.xstock_strategy — Market hours gate and oracle validation."""

import pytest
from datetime import datetime, timezone, timedelta, date, time

from core.trading.xstock_strategy import (
    is_market_hours,
    is_market_day,
    get_oracle_status,
    get_xstock_max_position_pct,
    get_xstock_expected_slippage,
    validate_xstock_backtest_period,
    OracleCondition,
    US_MARKET_HOLIDAYS,
    XSTOCK_LAUNCH_DATE,
    HIGH_LIQUIDITY_XSTOCKS,
)


class TestIsMarketHours:

    def test_tuesday_noon_et(self):
        """Tuesday 12:00 PM ET = market open."""
        # Tuesday Jan 7 2025, 17:00 UTC = 12:00 PM ET
        dt = datetime(2025, 1, 7, 17, 0, tzinfo=timezone.utc)
        assert is_market_hours(dt)

    def test_tuesday_early_morning_et(self):
        """Tuesday 8:00 AM ET = before market open."""
        # Tuesday Jan 7 2025, 13:00 UTC = 8:00 AM ET
        dt = datetime(2025, 1, 7, 13, 0, tzinfo=timezone.utc)
        assert not is_market_hours(dt)

    def test_tuesday_after_close_et(self):
        """Tuesday 5:00 PM ET = after market close."""
        # Tuesday Jan 7 2025, 22:00 UTC = 5:00 PM ET
        dt = datetime(2025, 1, 7, 22, 0, tzinfo=timezone.utc)
        assert not is_market_hours(dt)

    def test_saturday(self):
        """Saturday = weekend, no market."""
        # Saturday Jan 4 2025, 17:00 UTC
        dt = datetime(2025, 1, 4, 17, 0, tzinfo=timezone.utc)
        assert not is_market_hours(dt)

    def test_sunday(self):
        """Sunday = weekend, no market."""
        dt = datetime(2025, 1, 5, 17, 0, tzinfo=timezone.utc)
        assert not is_market_hours(dt)

    def test_new_years_day(self):
        """Jan 1 = holiday, no market."""
        dt = datetime(2025, 1, 1, 17, 0, tzinfo=timezone.utc)
        assert not is_market_hours(dt)

    def test_thanksgiving(self):
        dt = datetime(2025, 11, 27, 17, 0, tzinfo=timezone.utc)
        assert not is_market_hours(dt)

    def test_exact_open_time(self):
        """9:30 AM ET = market open (inclusive)."""
        # 9:30 AM ET = 14:30 UTC (EST, January)
        dt = datetime(2025, 1, 7, 14, 30, tzinfo=timezone.utc)
        assert is_market_hours(dt)

    def test_exact_close_time(self):
        """4:00 PM ET = market closed (exclusive)."""
        # 4:00 PM ET = 21:00 UTC (EST, January)
        dt = datetime(2025, 1, 7, 21, 0, tzinfo=timezone.utc)
        assert not is_market_hours(dt)


class TestIsMarketDay:

    def test_weekday_non_holiday(self):
        dt = datetime(2025, 1, 7, 17, 0, tzinfo=timezone.utc)  # Noon ET Tuesday
        assert is_market_day(dt)

    def test_weekend(self):
        # Saturday Jan 4 2025, 17:00 UTC = Saturday noon ET
        dt = datetime(2025, 1, 4, 17, 0, tzinfo=timezone.utc)
        assert not is_market_day(dt)

    def test_holiday(self):
        # Christmas 2025, use a time clearly in ET date range
        dt = datetime(2025, 12, 25, 17, 0, tzinfo=timezone.utc)
        assert not is_market_day(dt)


class TestOracleStatus:

    def test_fresh_oracle(self):
        """Oracle updated 2 minutes ago during market hours → FRESH."""
        now = datetime(2025, 1, 7, 17, 0, tzinfo=timezone.utc)  # Noon ET
        last_update = now - timedelta(minutes=2)
        status = get_oracle_status(last_update, now)
        assert status.condition == OracleCondition.FRESH
        assert not status.halted
        assert status.spread_multiplier == 1.0

    def test_degraded_oracle(self):
        """Oracle updated 15 minutes ago → DEGRADED."""
        now = datetime(2025, 1, 7, 17, 0, tzinfo=timezone.utc)
        last_update = now - timedelta(minutes=15)
        status = get_oracle_status(last_update, now)
        assert status.condition == OracleCondition.DEGRADED
        assert not status.halted
        assert status.spread_multiplier > 1.0

    def test_halted_oracle(self):
        """Oracle updated 45 minutes ago → HALTED."""
        now = datetime(2025, 1, 7, 17, 0, tzinfo=timezone.utc)
        last_update = now - timedelta(minutes=45)
        status = get_oracle_status(last_update, now)
        assert status.condition == OracleCondition.HALTED
        assert status.halted

    def test_after_hours(self):
        """After market close → AFTER_HOURS, always halted."""
        now = datetime(2025, 1, 7, 22, 0, tzinfo=timezone.utc)  # 5 PM ET
        last_update = now - timedelta(minutes=1)
        status = get_oracle_status(last_update, now)
        assert status.condition == OracleCondition.AFTER_HOURS
        assert status.halted

    def test_spread_increases_with_staleness(self):
        """Spread multiplier should increase linearly with staleness."""
        now = datetime(2025, 1, 7, 17, 0, tzinfo=timezone.utc)
        s10 = get_oracle_status(now - timedelta(minutes=10), now)
        s20 = get_oracle_status(now - timedelta(minutes=20), now)
        assert s20.spread_multiplier > s10.spread_multiplier


class TestXStockLiquidityTiers:

    def test_high_liquidity(self):
        assert get_xstock_max_position_pct("TSLA") == 0.02
        assert get_xstock_max_position_pct("NVDA") == 0.02

    def test_low_liquidity(self):
        assert get_xstock_max_position_pct("GME") == 0.0025

    def test_slippage_high_liquidity(self):
        assert get_xstock_expected_slippage("AAPL") == 0.01

    def test_slippage_low_liquidity(self):
        assert get_xstock_expected_slippage("PLTR") == 0.03


class TestBacktestValidation:

    def test_valid_period(self):
        start = datetime(2025, 7, 1, tzinfo=timezone.utc)
        end = datetime(2025, 12, 1, tzinfo=timezone.utc)
        assert validate_xstock_backtest_period(start, end)

    def test_before_launch(self):
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 12, 1, tzinfo=timezone.utc)
        assert not validate_xstock_backtest_period(start, end)
