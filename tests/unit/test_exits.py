"""Tests for core.trading.exits — ATR trailing stops with volume confirmation."""

import pytest

from core.trading.exits import (
    calculate_atr,
    calculate_atr_trailing_stop,
    should_exit,
    get_new_token_trail_pct,
    get_profit_floor,
    calculate_tiered_stops,
    TIERED_EXIT_PLAN,
    VOLUME_CONFIRMATION_MULTIPLIER,
)


class TestCalculateATR:

    def test_basic_atr(self):
        highs = [11, 12, 13, 14, 15, 16, 17, 18]
        lows = [9, 10, 11, 12, 13, 14, 15, 16]
        closes = [10, 11, 12, 13, 14, 15, 16, 17]
        atr = calculate_atr(highs, lows, closes, period=7)
        assert atr > 0

    def test_constant_price_atr_is_zero_ish(self):
        """Constant price → TR = 0 for each bar."""
        highs = [100] * 10
        lows = [100] * 10
        closes = [100] * 10
        atr = calculate_atr(highs, lows, closes)
        assert atr == 0.0

    def test_volatile_atr_higher(self):
        calm_h = [101, 102, 103, 104, 105, 106, 107, 108]
        calm_l = [99, 100, 101, 102, 103, 104, 105, 106]
        calm_c = [100, 101, 102, 103, 104, 105, 106, 107]

        vol_h = [110, 120, 130, 140, 150, 160, 170, 180]
        vol_l = [90, 80, 70, 60, 50, 40, 30, 20]
        vol_c = [100, 100, 100, 100, 100, 100, 100, 100]

        calm_atr = calculate_atr(calm_h, calm_l, calm_c)
        vol_atr = calculate_atr(vol_h, vol_l, vol_c)
        assert vol_atr > calm_atr

    def test_too_few_bars(self):
        assert calculate_atr([100], [99], [100]) == 0.0
        assert calculate_atr([], [], []) == 0.0


class TestATRTrailingStop:

    def test_stop_ratchets_up(self):
        """Stop should only increase, never decrease."""
        closes = [100, 102, 104, 106, 108, 106, 104, 102, 100]
        highs = [101, 103, 105, 107, 110, 107, 105, 103, 101]
        lows = [99, 101, 103, 105, 107, 105, 103, 101, 99]

        stops = calculate_atr_trailing_stop(closes, highs, lows, multiplier=2.0)

        # Check ratchet: each stop >= previous stop
        for i in range(2, len(stops)):
            assert stops[i] >= stops[i - 1], f"Stop dropped at bar {i}: {stops[i]} < {stops[i-1]}"

    def test_stop_below_price(self):
        """Stop should be below the price in an uptrend."""
        closes = [100, 102, 104, 106, 108, 110]
        highs = [101, 103, 105, 107, 109, 111]
        lows = [99, 101, 103, 105, 107, 109]

        stops = calculate_atr_trailing_stop(closes, highs, lows)

        # In an uptrend, stop should be below close
        for i in range(3, len(stops)):
            assert stops[i] < closes[i]


class TestShouldExit:

    def test_no_exit_above_stop(self):
        """Price above stop → no exit."""
        assert not should_exit(
            current_close=105,
            trailing_stop=100,
            current_volume=1000,
            avg_volume_20=1000,
        )

    def test_exit_below_stop_with_volume(self):
        """Price below stop + high volume → exit."""
        assert should_exit(
            current_close=95,
            trailing_stop=100,
            current_volume=2000,  # 2x average
            avg_volume_20=1000,
        )

    def test_no_exit_below_stop_low_volume(self):
        """Price below stop but low volume → NO exit (flash wick protection)."""
        assert not should_exit(
            current_close=95,
            trailing_stop=100,
            current_volume=500,  # Below 1.5x average
            avg_volume_20=1000,
        )

    def test_exit_without_volume_confirmation(self):
        """Hard risk limit: exit on price only."""
        assert should_exit(
            current_close=95,
            trailing_stop=100,
            current_volume=100,  # Low volume
            avg_volume_20=1000,
            require_volume_confirmation=False,
        )

    def test_zero_avg_volume_exits_conservatively(self):
        """If avg volume is 0, can't confirm → exit conservatively."""
        assert should_exit(
            current_close=95,
            trailing_stop=100,
            current_volume=100,
            avg_volume_20=0,
        )


class TestNewTokenStopWidth:

    def test_first_hour(self):
        assert get_new_token_trail_pct(0.5) == 0.40

    def test_hours_1_to_4(self):
        assert get_new_token_trail_pct(2.0) == 0.25

    def test_hours_4_to_24(self):
        assert get_new_token_trail_pct(12.0) == 0.15

    def test_after_24_hours(self):
        """After 24h, returns None → switch to ATR-based."""
        assert get_new_token_trail_pct(48.0) is None


class TestProfitFloor:

    def test_below_100pct_no_floor(self):
        assert get_profit_floor(0.5) == 0.0

    def test_above_100pct(self):
        assert get_profit_floor(1.5) == 0.5

    def test_above_200pct(self):
        assert get_profit_floor(2.5) == 1.0

    def test_above_300pct(self):
        assert get_profit_floor(3.5) == 2.0


class TestTieredExits:

    def test_default_tiers_sum_to_one(self):
        total = sum(t.pct_position for t in TIERED_EXIT_PLAN)
        assert abs(total - 1.0) < 0.001

    def test_tiered_stops_calculated(self):
        results = calculate_tiered_stops(
            entry_price=100,
            current_high=120,
            atr=5.0,
        )
        assert len(results) == 3
        # Tight stop should be higher (closer to price)
        assert results[0]["stop_price"] > results[2]["stop_price"]

    def test_stop_prices_positive(self):
        results = calculate_tiered_stops(100, 120, 5.0)
        for r in results:
            assert r["stop_price"] >= 0
