"""Tests for core.trading.position_sizing — ATR + Kelly position sizing."""

import pytest
from core.data.asset_registry import AssetClass
from core.trading.position_sizing import (
    calculate_position_size,
    calculate_kelly,
    MAX_RISK_PER_TRADE,
    MAX_POSITION_PCT,
    MAX_POOL_IMPACT_PCT,
    KELLY_FRACTION,
)


class TestCalculateKelly:

    def test_positive_ev(self):
        """60% WR, 1.5:1 risk/reward → positive Kelly."""
        kelly = calculate_kelly(0.60, 0.015, 0.01)
        assert kelly > 0

    def test_negative_ev(self):
        """40% WR, 1:1 → negative EV → Kelly = 0."""
        kelly = calculate_kelly(0.40, 0.01, 0.01)
        assert kelly == 0.0

    def test_coin_flip_even_odds(self):
        """50% WR, 1:1 → Kelly = 0 (breakeven)."""
        kelly = calculate_kelly(0.50, 0.01, 0.01)
        assert kelly == 0.0

    def test_edge_cases(self):
        assert calculate_kelly(0, 0.01, 0.01) == 0.0
        assert calculate_kelly(0.5, 0.01, 0) == 0.0
        assert calculate_kelly(1.0, 0.01, 0.01) == 0.0


class TestCalculatePositionSize:

    def test_basic_sizing(self):
        result = calculate_position_size(
            account_balance_usd=10_000,
            entry_price=150.0,
            stop_loss_price=140.0,
            atr=5.0,
            asset_class=AssetClass.NATIVE_SOLANA,
            pool_liquidity_usd=5_000_000,
        )
        assert result.position_usd > 0
        assert result.position_pct <= 0.05  # SOL max is 5%
        assert result.risk_pct <= MAX_RISK_PER_TRADE + 0.001

    def test_asset_class_caps(self):
        """Position should not exceed asset class maximum."""
        for asset_class, max_pct in MAX_POSITION_PCT.items():
            result = calculate_position_size(
                account_balance_usd=100_000,
                entry_price=100.0,
                stop_loss_price=99.0,
                atr=0.5,
                asset_class=asset_class,
                pool_liquidity_usd=10_000_000,
            )
            assert result.position_pct <= max_pct + 0.001, (
                f"{asset_class.value}: {result.position_pct:.4f} > {max_pct}"
            )

    def test_bags_pre_grad_tiny_size(self):
        """Pre-graduation Bags: max 0.25% of portfolio."""
        result = calculate_position_size(
            account_balance_usd=100_000,
            entry_price=0.001,
            stop_loss_price=0.0005,
            atr=0.0001,
            asset_class=AssetClass.BAGS_BONDING_CURVE,
            pool_liquidity_usd=30_000,
        )
        assert result.position_pct <= 0.0025 + 0.001

    def test_pool_liquidity_constraint(self):
        """Trade must be < 5% of pool liquidity."""
        result = calculate_position_size(
            account_balance_usd=1_000_000,
            entry_price=100.0,
            stop_loss_price=99.0,
            atr=0.5,
            asset_class=AssetClass.NATIVE_SOLANA,
            pool_liquidity_usd=10_000,  # Very thin pool
        )
        assert result.position_usd <= 10_000 * MAX_POOL_IMPACT_PCT + 1

    def test_kelly_constraint(self):
        """Quarter Kelly should limit sizing when provided."""
        result = calculate_position_size(
            account_balance_usd=100_000,
            entry_price=100.0,
            stop_loss_price=95.0,
            atr=3.0,
            asset_class=AssetClass.NATIVE_SOLANA,
            pool_liquidity_usd=10_000_000,
            win_rate=0.55,
            avg_win_pct=0.02,
            avg_loss_pct=0.02,
        )
        assert result.kelly_raw > 0
        assert result.kelly_quarter == result.kelly_raw * KELLY_FRACTION

    def test_zero_balance(self):
        result = calculate_position_size(
            account_balance_usd=0,
            entry_price=100.0,
            stop_loss_price=95.0,
            atr=3.0,
            asset_class=AssetClass.NATIVE_SOLANA,
            pool_liquidity_usd=1_000_000,
        )
        assert result.position_usd == 0

    def test_zero_entry_price(self):
        result = calculate_position_size(
            account_balance_usd=10_000,
            entry_price=0,
            stop_loss_price=0,
            atr=0,
            asset_class=AssetClass.NATIVE_SOLANA,
            pool_liquidity_usd=1_000_000,
        )
        assert result.position_usd == 0

    def test_summary_string(self):
        result = calculate_position_size(
            account_balance_usd=10_000,
            entry_price=150.0,
            stop_loss_price=140.0,
            atr=5.0,
            asset_class=AssetClass.NATIVE_SOLANA,
            pool_liquidity_usd=5_000_000,
        )
        s = result.summary()
        assert "Size:" in s
        assert "Risk:" in s
