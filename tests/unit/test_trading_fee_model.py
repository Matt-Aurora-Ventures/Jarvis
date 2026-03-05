"""Tests for core.trading.fee_model — Realistic cost modeling."""

import pytest
from core.data.asset_registry import AssetClass
from core.trading.fee_model import (
    TradeCost,
    LiquidityTier,
    calculate_trade_cost,
    classify_liquidity,
    deduct_costs,
    edge_to_cost_ratio,
    is_trade_viable,
    minimum_edge_for_asset,
    MINIMUM_EDGE_TO_COST_RATIO,
)


class TestClassifyLiquidity:

    def test_high(self):
        assert classify_liquidity(5_000_000) == LiquidityTier.HIGH

    def test_mid(self):
        assert classify_liquidity(500_000) == LiquidityTier.MID

    def test_micro(self):
        assert classify_liquidity(50_000) == LiquidityTier.MICRO

    def test_boundary_high(self):
        assert classify_liquidity(1_000_000) == LiquidityTier.HIGH

    def test_boundary_mid(self):
        assert classify_liquidity(100_000) == LiquidityTier.MID


class TestCalculateTradeCost:

    def test_high_liquidity_round_trip_below_1_pct(self):
        """HIGH tier should have < 1% round-trip cost for small trades."""
        cost = calculate_trade_cost(
            AssetClass.NATIVE_SOLANA,
            pool_liquidity_usd=5_000_000,
            trade_size_usd=500,
        )
        assert cost.total_round_trip_pct < 0.01  # < 1%
        assert cost.total_round_trip_pct > 0.003  # > 0.3%
        assert cost.liquidity_tier == LiquidityTier.HIGH

    def test_mid_tier_higher_costs(self):
        cost = calculate_trade_cost(
            AssetClass.MEMECOIN,
            pool_liquidity_usd=200_000,
            trade_size_usd=500,
        )
        assert cost.total_round_trip_pct > 0.01  # > 1%
        assert cost.liquidity_tier == LiquidityTier.MID

    def test_micro_tier_significant_costs(self):
        cost = calculate_trade_cost(
            AssetClass.MEMECOIN,
            pool_liquidity_usd=20_000,
            trade_size_usd=500,
        )
        assert cost.total_round_trip_pct > 0.03  # > 3%

    def test_bags_pre_grad_includes_creator_fee(self):
        cost = calculate_trade_cost(
            AssetClass.BAGS_BONDING_CURVE,
            pool_liquidity_usd=30_000,
            trade_size_usd=200,
            bags_creator_fee_pct=1.0,
        )
        assert cost.creator_fee_pct == 0.01  # 1%
        assert cost.total_round_trip_pct > 0.04  # > 4% (2% creator + 2% base fees)
        assert cost.liquidity_tier == LiquidityTier.BAGS_PRE_GRAD

    def test_bags_default_creator_fee(self):
        """Without explicit bags_creator_fee_pct, should default to 1%."""
        cost = calculate_trade_cost(
            AssetClass.BAGS_BONDING_CURVE,
            pool_liquidity_usd=30_000,
            trade_size_usd=200,
        )
        assert cost.creator_fee_pct == 0.01

    def test_xstock_tier(self):
        cost = calculate_trade_cost(
            AssetClass.XSTOCK,
            pool_liquidity_usd=500_000,
            trade_size_usd=500,
        )
        assert cost.liquidity_tier == LiquidityTier.XSTOCK

    def test_xstock_oracle_staleness_widens_spread(self):
        fresh = calculate_trade_cost(
            AssetClass.XSTOCK,
            pool_liquidity_usd=500_000,
            trade_size_usd=500,
            oracle_staleness_minutes=0,
        )
        stale = calculate_trade_cost(
            AssetClass.XSTOCK,
            pool_liquidity_usd=500_000,
            trade_size_usd=500,
            oracle_staleness_minutes=30,
        )
        assert stale.total_round_trip_pct > fresh.total_round_trip_pct

    def test_price_impact_scales_with_trade_size(self):
        small = calculate_trade_cost(
            AssetClass.NATIVE_SOLANA, 1_000_000, 100,
        )
        large = calculate_trade_cost(
            AssetClass.NATIVE_SOLANA, 1_000_000, 50_000,
        )
        assert large.price_impact_pct > small.price_impact_pct

    def test_zero_liquidity_fallback(self):
        cost = calculate_trade_cost(
            AssetClass.MEMECOIN, 0, 500,
        )
        assert cost.price_impact_pct == 0.10  # 10% fallback

    def test_to_dict(self):
        cost = calculate_trade_cost(AssetClass.NATIVE_SOLANA, 5_000_000, 500)
        d = cost.to_dict()
        assert "total_round_trip_pct" in d
        assert d["liquidity_tier"] == "high"


class TestIsTradeViable:

    def test_viable_with_good_edge(self):
        cost = calculate_trade_cost(AssetClass.NATIVE_SOLANA, 5_000_000, 500)
        assert is_trade_viable(0.05, cost)  # 5% edge vs < 1% cost

    def test_not_viable_with_tiny_edge(self):
        cost = calculate_trade_cost(AssetClass.MEMECOIN, 20_000, 500)
        assert not is_trade_viable(0.001, cost)  # 0.1% edge vs ~5% cost

    def test_edge_to_cost_ratio(self):
        cost = calculate_trade_cost(AssetClass.NATIVE_SOLANA, 5_000_000, 500)
        ratio = edge_to_cost_ratio(0.05, cost)
        assert ratio > 2.0


class TestMinimumEdge:

    def test_high_tier_minimum(self):
        min_edge = minimum_edge_for_asset(AssetClass.NATIVE_SOLANA, 5_000_000)
        assert 0.005 < min_edge < 0.02  # 0.5% - 2%

    def test_bags_minimum_much_higher(self):
        bags_min = minimum_edge_for_asset(
            AssetClass.BAGS_BONDING_CURVE, 30_000, bags_creator_fee_pct=1.0,
        )
        sol_min = minimum_edge_for_asset(AssetClass.NATIVE_SOLANA, 5_000_000)
        assert bags_min > sol_min * 3  # Bags requires 3x+ the edge


class TestDeductCosts:

    def test_profitable_trade_reduced_by_costs(self):
        cost = calculate_trade_cost(AssetClass.NATIVE_SOLANA, 5_000_000, 500)
        net = deduct_costs(100.0, 105.0, cost)
        gross = (105.0 - 100.0) / 100.0  # 5%
        assert net < gross
        assert net > 0  # Still profitable after costs

    def test_marginal_trade_becomes_loss(self):
        cost = calculate_trade_cost(AssetClass.MEMECOIN, 20_000, 500)
        # 0.5% gross gain — should be wiped out by > 3% costs
        net = deduct_costs(100.0, 100.5, cost)
        assert net < 0  # Loss after costs

    def test_zero_price_safety(self):
        cost = calculate_trade_cost(AssetClass.NATIVE_SOLANA, 5_000_000, 500)
        net = deduct_costs(0.0, 100.0, cost)
        assert net == 0.0
