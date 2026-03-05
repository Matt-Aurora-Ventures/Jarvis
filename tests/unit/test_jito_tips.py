"""Tests for core.trading.jito_tips — Dynamic Jito tip calculator."""

import pytest
from core.trading.jito_tips import (
    calculate_jito_tip,
    tip_to_lamports,
    VolatilityRegime,
    MAX_PROFIT_TIP_FRACTION,
)


class TestCalculateJitoTip:

    def test_low_volatility_baseline(self):
        tip = calculate_jito_tip(
            projected_profit_usd=10.0,
            market_volatility="low",
            sol_price_usd=150.0,
        )
        assert 0.0005 <= tip <= 0.005

    def test_medium_volatility_higher_than_low(self):
        low = calculate_jito_tip(10.0, "low", sol_price_usd=150.0)
        med = calculate_jito_tip(10.0, "medium", sol_price_usd=150.0)
        assert med >= low

    def test_extreme_volatility_highest(self):
        tip = calculate_jito_tip(
            projected_profit_usd=100.0,
            market_volatility="extreme",
            sol_price_usd=150.0,
        )
        assert tip <= 0.05  # Max cap for extreme

    def test_sniper_entry_bumps_tip(self):
        normal = calculate_jito_tip(50.0, "low", is_sniper_entry=False, sol_price_usd=150.0)
        sniper = calculate_jito_tip(50.0, "low", is_sniper_entry=True, sol_price_usd=150.0)
        assert sniper >= normal

    def test_never_exceeds_20pct_of_profit(self):
        """Hard cap: tip never > 20% of projected profit."""
        tip = calculate_jito_tip(
            projected_profit_usd=1.0,  # Tiny profit
            market_volatility="extreme",
            sol_price_usd=150.0,
        )
        tip_usd = tip * 150.0
        assert tip_usd <= 1.0 * MAX_PROFIT_TIP_FRACTION + 0.001

    def test_minimum_floor(self):
        """Always tip at least 0.0005 SOL."""
        tip = calculate_jito_tip(0.0, "low", sol_price_usd=150.0)
        assert tip >= 0.0005

    def test_zero_profit_still_returns_minimum(self):
        tip = calculate_jito_tip(0.0, "medium", sol_price_usd=150.0)
        assert tip >= 0.0005

    def test_invalid_volatility_defaults_to_low(self):
        tip = calculate_jito_tip(10.0, "invalid_regime", sol_price_usd=150.0)
        low = calculate_jito_tip(10.0, "low", sol_price_usd=150.0)
        assert tip == low

    def test_zero_sol_price_uses_fallback(self):
        tip = calculate_jito_tip(10.0, "low", sol_price_usd=0.0)
        assert tip > 0


class TestTipToLamports:

    def test_conversion(self):
        assert tip_to_lamports(1.0) == 1_000_000_000
        assert tip_to_lamports(0.001) == 1_000_000
        assert tip_to_lamports(0.0005) == 500_000
