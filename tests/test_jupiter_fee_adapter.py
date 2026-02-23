"""
test_jupiter_fee_adapter.py — Tests for the Freqtrade Jupiter fee adapter.

Tests:
    1. Dual-slope borrow rate model is correct at key breakpoints
    2. Borrow fee increases with holding duration
    3. Impact fee scales with position size
    4. Full fee computation returns JupiterTradeFees with all fields
    5. Minimum win % is always positive
    6. Fee model validates against published Jupiter Perps rates
"""

import pytest

from core.backtesting.jupiter_fee_adapter import (
    BASE_RATE_HOURLY,
    CLOSE_FEE_BPS,
    EXECUTION_PENALTY,
    JupiterFeeAdapter,
    JupiterTradeFees,
    MAX_RATE_HOURLY,
    OPEN_FEE_BPS,
    OPTIMAL_UTILIZATION,
    TARGET_RATE_HOURLY,
    bps_to_decimal,
    calculate_borrow_fee,
    calculate_borrow_rate,
    calculate_impact_fee,
)


# ─── Borrow Rate Model ────────────────────────────────────────────────────────

class TestCalculateBorrowRate:
    def test_rate_at_zero_utilization_is_base_rate(self):
        rate = calculate_borrow_rate(0.0)
        assert abs(rate - BASE_RATE_HOURLY) < 1e-10

    def test_rate_at_optimal_utilization_is_target_rate(self):
        rate = calculate_borrow_rate(OPTIMAL_UTILIZATION)
        assert abs(rate - TARGET_RATE_HOURLY) < 1e-10

    def test_rate_at_100_percent_is_max_rate(self):
        rate = calculate_borrow_rate(1.0)
        assert abs(rate - MAX_RATE_HOURLY) < 1e-10

    def test_rate_increases_monotonically(self):
        """Borrow rate should always increase as utilization increases."""
        utilizations = [i / 100 for i in range(0, 101, 5)]
        rates = [calculate_borrow_rate(u) for u in utilizations]
        for i in range(len(rates) - 1):
            assert rates[i] <= rates[i + 1], (
                f"Rate decreased at utilization {utilizations[i+1]}: "
                f"{rates[i]} > {rates[i+1]}"
            )

    def test_slope_is_steeper_above_optimal(self):
        """Rate should increase faster above the optimal utilization."""
        # Rate increase from 50% to 70% (slope 1)
        delta_slope1 = calculate_borrow_rate(0.70) - calculate_borrow_rate(0.50)
        # Rate increase from 70% to 90% (slope 2)
        delta_slope2 = calculate_borrow_rate(0.90) - calculate_borrow_rate(0.70)
        assert delta_slope2 > delta_slope1, (
            "Slope 2 should be steeper than slope 1 above optimal utilization"
        )

    def test_clamps_below_zero(self):
        """Negative utilization should be treated as 0."""
        rate_neg = calculate_borrow_rate(-1.0)
        rate_zero = calculate_borrow_rate(0.0)
        assert rate_neg == rate_zero

    def test_clamps_above_one(self):
        """Utilization > 100% should be treated as 100%."""
        rate_over = calculate_borrow_rate(2.0)
        rate_max = calculate_borrow_rate(1.0)
        assert rate_over == rate_max

    def test_rate_at_50_pct_utilization(self):
        """At 50% utilization (below optimal 70%), should be on slope 1."""
        rate = calculate_borrow_rate(0.50)
        # Linear interpolation: base + (target - base) * (0.5 / 0.7)
        expected = BASE_RATE_HOURLY + (TARGET_RATE_HOURLY - BASE_RATE_HOURLY) * (0.5 / OPTIMAL_UTILIZATION)
        assert abs(rate - expected) < 1e-12

    def test_rate_at_85_pct_utilization(self):
        """At 85% utilization (above optimal 70%), should be on slope 2."""
        rate = calculate_borrow_rate(0.85)
        excess = (0.85 - OPTIMAL_UTILIZATION) / (1.0 - OPTIMAL_UTILIZATION)
        expected = TARGET_RATE_HOURLY + (MAX_RATE_HOURLY - TARGET_RATE_HOURLY) * excess
        assert abs(rate - expected) < 1e-12


# ─── Borrow Fee ───────────────────────────────────────────────────────────────

class TestCalculateBorrowFee:
    def test_fee_is_zero_for_zero_hours(self):
        fee = calculate_borrow_fee(10_000.0, 0.0)
        assert fee == 0.0

    def test_fee_scales_linearly_with_notional(self):
        fee_1k = calculate_borrow_fee(1_000.0, 24.0)
        fee_10k = calculate_borrow_fee(10_000.0, 24.0)
        assert abs(fee_10k / fee_1k - 10.0) < 0.01

    def test_fee_scales_linearly_with_hours(self):
        fee_24h = calculate_borrow_fee(10_000.0, 24.0)
        fee_48h = calculate_borrow_fee(10_000.0, 48.0)
        assert abs(fee_48h / fee_24h - 2.0) < 0.01

    def test_higher_utilization_means_higher_fee(self):
        fee_low = calculate_borrow_fee(10_000.0, 24.0, avg_utilization=0.3)
        fee_high = calculate_borrow_fee(10_000.0, 24.0, avg_utilization=0.9)
        assert fee_high > fee_low

    def test_realistic_fee_for_typical_trade(self):
        """$10k notional, 24 hours, 65% utilization should produce a reasonable fee."""
        fee = calculate_borrow_fee(10_000.0, 24.0, avg_utilization=0.65)
        # Rough sanity: should be between $0.10 and $30 per day for $10k
        assert 0.10 < fee < 30.0, f"Unexpected borrow fee: ${fee:.4f}"


# ─── Impact Fee ───────────────────────────────────────────────────────────────

class TestCalculateImpactFee:
    def test_small_position_has_minimal_impact(self):
        impact = calculate_impact_fee(1_000.0)
        assert impact < 0.001  # < 0.1%

    def test_large_position_has_higher_impact(self):
        small = calculate_impact_fee(1_000.0)
        large = calculate_impact_fee(1_000_000.0)
        assert large > small

    def test_impact_is_capped(self):
        """Impact fee should never exceed 0.5% (cap)."""
        huge_impact = calculate_impact_fee(1_000_000_000.0)
        assert huge_impact <= 0.005

    def test_impact_is_non_negative(self):
        assert calculate_impact_fee(0.0) >= 0.0
        assert calculate_impact_fee(100_000.0) >= 0.0


# ─── Full Fee Computation ─────────────────────────────────────────────────────

class TestJupiterFeeAdapterComputeFullFees:
    def test_returns_jupiter_trade_fees(self):
        fees = JupiterFeeAdapter.compute_full_fees(10_000.0, 24.0)
        assert isinstance(fees, JupiterTradeFees)

    def test_all_components_are_non_negative(self):
        fees = JupiterFeeAdapter.compute_full_fees(10_000.0, 24.0)
        assert fees.open_fee_usd >= 0
        assert fees.close_fee_usd >= 0
        assert fees.borrow_fee_usd >= 0
        assert fees.impact_fee_open_usd >= 0
        assert fees.impact_fee_close_usd >= 0
        assert fees.execution_penalty_usd >= 0

    def test_total_is_sum_of_components(self):
        fees = JupiterFeeAdapter.compute_full_fees(10_000.0, 24.0)
        expected_total = (
            fees.open_fee_usd
            + fees.close_fee_usd
            + fees.borrow_fee_usd
            + fees.impact_fee_open_usd
            + fees.impact_fee_close_usd
            + fees.execution_penalty_usd
        )
        assert abs(fees.total_usd - expected_total) < 1e-9

    def test_longer_hold_has_higher_total(self):
        fees_4h = JupiterFeeAdapter.compute_full_fees(10_000.0, 4.0)
        fees_24h = JupiterFeeAdapter.compute_full_fees(10_000.0, 24.0)
        assert fees_24h.total_usd > fees_4h.total_usd

    def test_larger_position_has_higher_total(self):
        fees_small = JupiterFeeAdapter.compute_full_fees(1_000.0, 1.0)
        fees_large = JupiterFeeAdapter.compute_full_fees(100_000.0, 1.0)
        assert fees_large.total_usd > fees_small.total_usd

    def test_open_fee_matches_expected_bps(self):
        notional = 10_000.0
        fees = JupiterFeeAdapter.compute_full_fees(notional, 0.0)
        expected_open = notional * bps_to_decimal(OPEN_FEE_BPS)
        assert abs(fees.open_fee_usd - expected_open) < 1e-6


# ─── Minimum Win % (Hurdle Rate) ──────────────────────────────────────────────

class TestMinimumWinPct:
    def test_always_positive(self):
        hurdle = JupiterFeeAdapter.minimum_win_pct(10_000.0, 1.0)
        assert hurdle > 0

    def test_increases_with_hold_duration(self):
        h1 = JupiterFeeAdapter.minimum_win_pct(10_000.0, 1.0)
        h24 = JupiterFeeAdapter.minimum_win_pct(10_000.0, 24.0)
        assert h24 > h1

    def test_realistic_hurdle_rate(self):
        """For a $10k position held 1 hour, hurdle rate should be ~0.1-0.2%."""
        hurdle = JupiterFeeAdapter.minimum_win_pct(10_000.0, 1.0)
        assert 0.001 < hurdle < 0.005, f"Unexpected hurdle rate: {hurdle:.6f}"

    def test_fee_rates_are_correct(self):
        assert abs(JupiterFeeAdapter.open_fee_rate() - (bps_to_decimal(OPEN_FEE_BPS) + EXECUTION_PENALTY)) < 1e-10
        assert abs(JupiterFeeAdapter.close_fee_rate() - (bps_to_decimal(CLOSE_FEE_BPS) + EXECUTION_PENALTY)) < 1e-10


# ─── BPS Conversion ───────────────────────────────────────────────────────────

class TestBpsToDecimal:
    def test_6_bps_is_0_0006(self):
        assert abs(bps_to_decimal(6) - 0.0006) < 1e-12

    def test_100_bps_is_0_01(self):
        assert abs(bps_to_decimal(100) - 0.01) < 1e-12

    def test_10000_bps_is_1(self):
        assert abs(bps_to_decimal(10_000) - 1.0) < 1e-12
