"""
Unit tests for Order Book Analyzer.

Tests cover:
- Depth analysis
- Bid/ask spread calculation
- Liquidity scoring
- Wall detection
- Imbalance indicators
- Slippage estimation
"""

import pytest
from dataclasses import dataclass
from typing import List, Tuple, Optional
from unittest.mock import MagicMock, patch


class TestOrderBookAnalyzerBasics:
    """Test basic order book analyzer functionality."""

    def test_analyzer_initialization(self):
        """Test analyzer can be instantiated."""
        from core.analysis.order_book_analyzer import OrderBookAnalyzer

        analyzer = OrderBookAnalyzer()
        assert analyzer is not None

    def test_analyzer_with_empty_order_book(self):
        """Test analyzer handles empty order book gracefully."""
        from core.analysis.order_book_analyzer import OrderBookAnalyzer, OrderBookSnapshot

        analyzer = OrderBookAnalyzer()
        snapshot = OrderBookSnapshot(
            symbol="SOL/USDC",
            bids=[],
            asks=[],
            timestamp="2026-01-19T12:00:00Z"
        )

        analysis = analyzer.analyze(snapshot)
        assert analysis.spread_bps == 0
        assert analysis.mid_price == 0
        assert analysis.imbalance == 0


class TestSpreadCalculation:
    """Test bid/ask spread calculations."""

    def test_spread_calculation_basic(self):
        """Test basic spread calculation."""
        from core.analysis.order_book_analyzer import OrderBookAnalyzer, OrderBookSnapshot

        analyzer = OrderBookAnalyzer()
        snapshot = OrderBookSnapshot(
            symbol="SOL/USDC",
            bids=[(100.0, 10.0), (99.5, 20.0), (99.0, 30.0)],  # (price, size)
            asks=[(100.5, 15.0), (101.0, 25.0), (101.5, 35.0)],
            timestamp="2026-01-19T12:00:00Z"
        )

        analysis = analyzer.analyze(snapshot)

        # Spread = best_ask - best_bid = 100.5 - 100.0 = 0.5
        assert analysis.spread == pytest.approx(0.5, rel=0.01)
        # Mid price = (100.0 + 100.5) / 2 = 100.25
        assert analysis.mid_price == pytest.approx(100.25, rel=0.01)
        # Spread in bps = (0.5 / 100.25) * 10000 = ~49.88 bps
        assert analysis.spread_bps == pytest.approx(49.88, rel=0.1)

    def test_spread_tight_market(self):
        """Test spread calculation for tight market."""
        from core.analysis.order_book_analyzer import OrderBookAnalyzer, OrderBookSnapshot

        analyzer = OrderBookAnalyzer()
        snapshot = OrderBookSnapshot(
            symbol="SOL/USDC",
            bids=[(100.00, 100.0)],
            asks=[(100.01, 100.0)],
            timestamp="2026-01-19T12:00:00Z"
        )

        analysis = analyzer.analyze(snapshot)

        # Spread = 0.01, mid = 100.005, spread_bps = 1 bps
        assert analysis.spread == pytest.approx(0.01, rel=0.01)
        assert analysis.spread_bps == pytest.approx(1.0, rel=0.1)

    def test_spread_wide_market(self):
        """Test spread calculation for wide/illiquid market."""
        from core.analysis.order_book_analyzer import OrderBookAnalyzer, OrderBookSnapshot

        analyzer = OrderBookAnalyzer()
        snapshot = OrderBookSnapshot(
            symbol="MEME/USDC",
            bids=[(0.001, 1000000.0)],
            asks=[(0.0015, 500000.0)],
            timestamp="2026-01-19T12:00:00Z"
        )

        analysis = analyzer.analyze(snapshot)

        # Spread = 0.0005, mid = 0.00125
        # spread_bps = (0.0005 / 0.00125) * 10000 = 4000 bps = 40%
        assert analysis.spread_bps == pytest.approx(4000, rel=1)


class TestDepthAnalysis:
    """Test order book depth analysis."""

    def test_depth_at_percentage_levels(self):
        """Test depth calculation at different percentage levels from mid."""
        from core.analysis.order_book_analyzer import OrderBookAnalyzer, OrderBookSnapshot

        analyzer = OrderBookAnalyzer()
        # Price mid ~100, bids down to 95, asks up to 105
        snapshot = OrderBookSnapshot(
            symbol="SOL/USDC",
            bids=[
                (100.0, 10.0),   # Within 1%
                (99.0, 20.0),    # Within 2%
                (97.0, 50.0),    # Within 5%
                (95.0, 100.0),   # Within 5%
            ],
            asks=[
                (100.5, 15.0),   # Within 1%
                (101.0, 25.0),   # Within 2%
                (103.0, 60.0),   # Within 5%
                (105.0, 120.0),  # Within 5%
            ],
            timestamp="2026-01-19T12:00:00Z"
        )

        analysis = analyzer.analyze(snapshot)

        # Depth within 1% of mid (~100.25)
        # Bids: 100.0 * 10.0 = $1000 (within 99.25-100.25)
        # Asks: 100.5 * 15.0 = $1507.5 (within 100.25-101.25)
        assert analysis.depth_1pct_bid > 0
        assert analysis.depth_1pct_ask > 0

        # Depth within 5% should be larger
        assert analysis.depth_5pct_bid > analysis.depth_1pct_bid
        assert analysis.depth_5pct_ask > analysis.depth_1pct_ask

    def test_total_depth_calculation(self):
        """Test total liquidity depth calculation."""
        from core.analysis.order_book_analyzer import OrderBookAnalyzer, OrderBookSnapshot

        analyzer = OrderBookAnalyzer()
        snapshot = OrderBookSnapshot(
            symbol="SOL/USDC",
            bids=[(100.0, 10.0), (99.0, 20.0)],  # Total: $1000 + $1980 = $2980
            asks=[(101.0, 15.0), (102.0, 25.0)],  # Total: $1515 + $2550 = $4065
            timestamp="2026-01-19T12:00:00Z"
        )

        analysis = analyzer.analyze(snapshot)

        assert analysis.total_bid_depth == pytest.approx(2980.0, rel=0.01)
        assert analysis.total_ask_depth == pytest.approx(4065.0, rel=0.01)


class TestLiquidityScoring:
    """Test liquidity quality scoring."""

    def test_liquidity_score_excellent(self):
        """Test liquidity scoring for excellent liquidity."""
        from core.analysis.order_book_analyzer import (
            OrderBookAnalyzer, OrderBookSnapshot, LiquidityGrade
        )

        analyzer = OrderBookAnalyzer()
        # Tight spread, deep liquidity on both sides
        snapshot = OrderBookSnapshot(
            symbol="SOL/USDC",
            bids=[
                (100.0, 1000.0),
                (99.9, 2000.0),
                (99.8, 3000.0),
            ],
            asks=[
                (100.1, 1000.0),
                (100.2, 2000.0),
                (100.3, 3000.0),
            ],
            timestamp="2026-01-19T12:00:00Z"
        )

        analysis = analyzer.analyze(snapshot)

        # Should have excellent liquidity score
        assert analysis.liquidity_score >= 0.8
        assert analysis.liquidity_grade == LiquidityGrade.EXCELLENT

    def test_liquidity_score_poor(self):
        """Test liquidity scoring for poor liquidity."""
        from core.analysis.order_book_analyzer import (
            OrderBookAnalyzer, OrderBookSnapshot, LiquidityGrade
        )

        analyzer = OrderBookAnalyzer()
        # Wide spread, thin liquidity
        snapshot = OrderBookSnapshot(
            symbol="SCAM/USDC",
            bids=[(0.001, 100.0)],
            asks=[(0.002, 50.0)],  # 100% spread
            timestamp="2026-01-19T12:00:00Z"
        )

        analysis = analyzer.analyze(snapshot)

        # Should have poor liquidity score
        assert analysis.liquidity_score <= 0.3
        assert analysis.liquidity_grade == LiquidityGrade.POOR

    def test_liquidity_score_components(self):
        """Test liquidity score considers multiple factors."""
        from core.analysis.order_book_analyzer import OrderBookAnalyzer, OrderBookSnapshot

        analyzer = OrderBookAnalyzer()
        snapshot = OrderBookSnapshot(
            symbol="SOL/USDC",
            bids=[(100.0, 500.0), (99.0, 1000.0)],
            asks=[(101.0, 600.0), (102.0, 1200.0)],
            timestamp="2026-01-19T12:00:00Z"
        )

        analysis = analyzer.analyze(snapshot)

        # Score should be 0-1
        assert 0 <= analysis.liquidity_score <= 1
        # Should have breakdown
        assert hasattr(analysis, 'liquidity_factors')
        assert 'spread_score' in analysis.liquidity_factors
        assert 'depth_score' in analysis.liquidity_factors
        assert 'balance_score' in analysis.liquidity_factors


class TestWallDetection:
    """Test detection of large walls (support/resistance)."""

    def test_detect_bid_wall(self):
        """Test detection of large bid wall (support)."""
        from core.analysis.order_book_analyzer import OrderBookAnalyzer, OrderBookSnapshot

        analyzer = OrderBookAnalyzer()
        snapshot = OrderBookSnapshot(
            symbol="SOL/USDC",
            bids=[
                (100.0, 10.0),
                (99.0, 20.0),
                (98.0, 1000.0),  # Large wall - 50x average
                (97.0, 15.0),
            ],
            asks=[
                (101.0, 15.0),
                (102.0, 20.0),
                (103.0, 25.0),
            ],
            timestamp="2026-01-19T12:00:00Z"
        )

        analysis = analyzer.analyze(snapshot)

        assert len(analysis.bid_walls) >= 1
        wall = analysis.bid_walls[0]
        assert wall.price == pytest.approx(98.0, rel=0.01)
        assert wall.size == pytest.approx(1000.0, rel=0.01)
        assert wall.wall_type == "support"

    def test_detect_ask_wall(self):
        """Test detection of large ask wall (resistance)."""
        from core.analysis.order_book_analyzer import OrderBookAnalyzer, OrderBookSnapshot

        analyzer = OrderBookAnalyzer()
        snapshot = OrderBookSnapshot(
            symbol="SOL/USDC",
            bids=[
                (100.0, 15.0),
                (99.0, 20.0),
                (98.0, 25.0),
            ],
            asks=[
                (101.0, 10.0),
                (102.0, 20.0),
                (103.0, 2000.0),  # Large wall - 100x average
                (104.0, 15.0),
            ],
            timestamp="2026-01-19T12:00:00Z"
        )

        analysis = analyzer.analyze(snapshot)

        assert len(analysis.ask_walls) >= 1
        wall = analysis.ask_walls[0]
        assert wall.price == pytest.approx(103.0, rel=0.01)
        assert wall.size == pytest.approx(2000.0, rel=0.01)
        assert wall.wall_type == "resistance"

    def test_detect_multiple_walls(self):
        """Test detection of multiple walls."""
        from core.analysis.order_book_analyzer import OrderBookAnalyzer, OrderBookSnapshot

        analyzer = OrderBookAnalyzer()
        snapshot = OrderBookSnapshot(
            symbol="SOL/USDC",
            bids=[
                (100.0, 10.0),
                (99.0, 500.0),   # Wall 1
                (98.0, 20.0),
                (97.0, 800.0),   # Wall 2
            ],
            asks=[
                (101.0, 15.0),
                (102.0, 600.0),  # Wall 3
                (103.0, 25.0),
            ],
            timestamp="2026-01-19T12:00:00Z"
        )

        analysis = analyzer.analyze(snapshot)

        total_walls = len(analysis.bid_walls) + len(analysis.ask_walls)
        assert total_walls >= 2

    def test_wall_strength_calculation(self):
        """Test wall strength is calculated relative to surrounding levels."""
        from core.analysis.order_book_analyzer import OrderBookAnalyzer, OrderBookSnapshot

        analyzer = OrderBookAnalyzer()
        snapshot = OrderBookSnapshot(
            symbol="SOL/USDC",
            bids=[
                (100.0, 10.0),
                (99.0, 10.0),
                (98.0, 500.0),  # 50x surrounding average
                (97.0, 10.0),
            ],
            asks=[(101.0, 10.0)],
            timestamp="2026-01-19T12:00:00Z"
        )

        analysis = analyzer.analyze(snapshot)

        if analysis.bid_walls:
            wall = analysis.bid_walls[0]
            # Strength should be ratio vs average
            assert wall.strength >= 10.0  # At least 10x average


class TestImbalanceIndicators:
    """Test order book imbalance calculations."""

    def test_imbalance_bid_heavy(self):
        """Test imbalance calculation when bids dominate."""
        from core.analysis.order_book_analyzer import OrderBookAnalyzer, OrderBookSnapshot

        analyzer = OrderBookAnalyzer()
        snapshot = OrderBookSnapshot(
            symbol="SOL/USDC",
            bids=[
                (100.0, 1000.0),  # $100,000
                (99.0, 1000.0),   # $99,000
            ],
            asks=[
                (101.0, 100.0),   # $10,100
                (102.0, 100.0),   # $10,200
            ],
            timestamp="2026-01-19T12:00:00Z"
        )

        analysis = analyzer.analyze(snapshot)

        # Imbalance should be positive (more bids)
        # Range is -1 to 1
        assert analysis.imbalance > 0.5
        assert analysis.imbalance_signal == "bullish"

    def test_imbalance_ask_heavy(self):
        """Test imbalance calculation when asks dominate."""
        from core.analysis.order_book_analyzer import OrderBookAnalyzer, OrderBookSnapshot

        analyzer = OrderBookAnalyzer()
        snapshot = OrderBookSnapshot(
            symbol="SOL/USDC",
            bids=[
                (100.0, 100.0),   # $10,000
                (99.0, 100.0),    # $9,900
            ],
            asks=[
                (101.0, 1000.0),  # $101,000
                (102.0, 1000.0),  # $102,000
            ],
            timestamp="2026-01-19T12:00:00Z"
        )

        analysis = analyzer.analyze(snapshot)

        # Imbalance should be negative (more asks)
        assert analysis.imbalance < -0.5
        assert analysis.imbalance_signal == "bearish"

    def test_imbalance_balanced(self):
        """Test imbalance calculation when book is balanced."""
        from core.analysis.order_book_analyzer import OrderBookAnalyzer, OrderBookSnapshot

        analyzer = OrderBookAnalyzer()
        snapshot = OrderBookSnapshot(
            symbol="SOL/USDC",
            bids=[
                (100.0, 100.0),
                (99.0, 100.0),
            ],
            asks=[
                (101.0, 100.0),
                (102.0, 100.0),
            ],
            timestamp="2026-01-19T12:00:00Z"
        )

        analysis = analyzer.analyze(snapshot)

        # Should be near zero
        assert abs(analysis.imbalance) < 0.2
        assert analysis.imbalance_signal == "neutral"

    def test_imbalance_at_depth_levels(self):
        """Test imbalance at different depth levels."""
        from core.analysis.order_book_analyzer import OrderBookAnalyzer, OrderBookSnapshot

        analyzer = OrderBookAnalyzer()
        snapshot = OrderBookSnapshot(
            symbol="SOL/USDC",
            bids=[
                (100.0, 500.0),   # Near best
                (99.0, 100.0),
                (98.0, 50.0),     # Deeper
            ],
            asks=[
                (101.0, 100.0),   # Near best
                (102.0, 500.0),
                (103.0, 1000.0),  # Deeper
            ],
            timestamp="2026-01-19T12:00:00Z"
        )

        analysis = analyzer.analyze(snapshot)

        # Should have imbalance at different depths
        assert hasattr(analysis, 'imbalance_1pct')
        assert hasattr(analysis, 'imbalance_5pct')


class TestSlippageEstimation:
    """Test slippage estimation for different order sizes."""

    def test_slippage_small_order(self):
        """Test slippage for small order that fills at best price."""
        from core.analysis.order_book_analyzer import OrderBookAnalyzer, OrderBookSnapshot

        analyzer = OrderBookAnalyzer()
        snapshot = OrderBookSnapshot(
            symbol="SOL/USDC",
            bids=[
                (100.0, 1000.0),  # $100,000 available
                (99.0, 1000.0),
            ],
            asks=[
                (101.0, 1000.0),  # $101,000 available
                (102.0, 1000.0),
            ],
            timestamp="2026-01-19T12:00:00Z"
        )

        # Small buy order - $1000
        slippage = analyzer.estimate_slippage(snapshot, "buy", 1000.0)

        # Should fill entirely at best ask (101.0)
        assert slippage.avg_price == pytest.approx(101.0, rel=0.01)
        assert slippage.slippage_bps == pytest.approx(0, abs=1)  # ~0 bps

    def test_slippage_large_order(self):
        """Test slippage for large order that walks the book."""
        from core.analysis.order_book_analyzer import OrderBookAnalyzer, OrderBookSnapshot

        analyzer = OrderBookAnalyzer()
        snapshot = OrderBookSnapshot(
            symbol="SOL/USDC",
            bids=[
                (100.0, 10.0),    # $1,000
                (99.0, 10.0),     # $990
            ],
            asks=[
                (101.0, 10.0),    # $1,010 available
                (102.0, 10.0),    # $1,020 available
                (103.0, 10.0),    # $1,030 available
            ],
            timestamp="2026-01-19T12:00:00Z"
        )

        # Large buy order - $2500 (will eat through multiple levels)
        slippage = analyzer.estimate_slippage(snapshot, "buy", 2500.0)

        # Should fill at multiple prices
        assert slippage.avg_price > 101.0
        assert slippage.slippage_bps > 0
        assert slippage.filled_pct > 0

    def test_slippage_sell_order(self):
        """Test slippage estimation for sell order."""
        from core.analysis.order_book_analyzer import OrderBookAnalyzer, OrderBookSnapshot

        analyzer = OrderBookAnalyzer()
        snapshot = OrderBookSnapshot(
            symbol="SOL/USDC",
            bids=[
                (100.0, 10.0),    # $1,000
                (99.0, 10.0),     # $990
                (98.0, 10.0),     # $980
            ],
            asks=[
                (101.0, 10.0),
            ],
            timestamp="2026-01-19T12:00:00Z"
        )

        # Sell order - $2000
        slippage = analyzer.estimate_slippage(snapshot, "sell", 2000.0)

        # Should fill starting at best bid going down
        assert slippage.avg_price < 100.0
        assert slippage.slippage_bps > 0

    def test_slippage_insufficient_liquidity(self):
        """Test slippage when order exceeds available liquidity."""
        from core.analysis.order_book_analyzer import OrderBookAnalyzer, OrderBookSnapshot

        analyzer = OrderBookAnalyzer()
        snapshot = OrderBookSnapshot(
            symbol="SOL/USDC",
            bids=[(100.0, 10.0)],  # Only $1000 available
            asks=[(101.0, 10.0)],  # Only $1010 available
            timestamp="2026-01-19T12:00:00Z"
        )

        # Order larger than available liquidity
        slippage = analyzer.estimate_slippage(snapshot, "buy", 5000.0)

        assert slippage.filled_pct < 100.0
        assert slippage.unfilled_amount > 0


class TestVWAPCalculation:
    """Test volume-weighted average price calculations."""

    def test_vwap_calculation(self):
        """Test VWAP calculation for order book."""
        from core.analysis.order_book_analyzer import OrderBookAnalyzer, OrderBookSnapshot

        analyzer = OrderBookAnalyzer()
        snapshot = OrderBookSnapshot(
            symbol="SOL/USDC",
            bids=[
                (100.0, 100.0),   # $10,000
                (99.0, 200.0),    # $19,800
            ],
            asks=[
                (101.0, 150.0),   # $15,150
                (102.0, 250.0),   # $25,500
            ],
            timestamp="2026-01-19T12:00:00Z"
        )

        analysis = analyzer.analyze(snapshot)

        # VWAP bid = (100*100 + 99*200) / (100 + 200) = 29800 / 300 = 99.33
        assert analysis.vwap_bid == pytest.approx(99.33, rel=0.01)
        # VWAP ask = (101*150 + 102*250) / (150 + 250) = 40650 / 400 = 101.625
        assert analysis.vwap_ask == pytest.approx(101.625, rel=0.01)


class TestPressureAnalysis:
    """Test buying/selling pressure analysis."""

    def test_buying_pressure(self):
        """Test buying pressure indicator."""
        from core.analysis.order_book_analyzer import OrderBookAnalyzer, OrderBookSnapshot

        analyzer = OrderBookAnalyzer()
        snapshot = OrderBookSnapshot(
            symbol="SOL/USDC",
            bids=[
                (100.0, 1000.0),  # Heavy buying interest
                (99.5, 800.0),
                (99.0, 600.0),
            ],
            asks=[
                (100.5, 100.0),   # Light selling
                (101.0, 100.0),
            ],
            timestamp="2026-01-19T12:00:00Z"
        )

        analysis = analyzer.analyze(snapshot)

        # Pressure should indicate buying
        assert analysis.buying_pressure > 0.6
        assert analysis.selling_pressure < 0.4

    def test_selling_pressure(self):
        """Test selling pressure indicator."""
        from core.analysis.order_book_analyzer import OrderBookAnalyzer, OrderBookSnapshot

        analyzer = OrderBookAnalyzer()
        snapshot = OrderBookSnapshot(
            symbol="SOL/USDC",
            bids=[
                (100.0, 100.0),   # Light buying
                (99.0, 100.0),
            ],
            asks=[
                (100.5, 1000.0),  # Heavy selling interest
                (101.0, 800.0),
                (101.5, 600.0),
            ],
            timestamp="2026-01-19T12:00:00Z"
        )

        analysis = analyzer.analyze(snapshot)

        # Pressure should indicate selling
        assert analysis.selling_pressure > 0.6
        assert analysis.buying_pressure < 0.4


class TestMicrostructureMetrics:
    """Test advanced market microstructure metrics."""

    def test_order_book_density(self):
        """Test order book density calculation."""
        from core.analysis.order_book_analyzer import OrderBookAnalyzer, OrderBookSnapshot

        analyzer = OrderBookAnalyzer()
        # Dense book - many levels close together
        snapshot = OrderBookSnapshot(
            symbol="SOL/USDC",
            bids=[
                (100.0, 10.0),
                (99.99, 10.0),
                (99.98, 10.0),
                (99.97, 10.0),
            ],
            asks=[
                (100.01, 10.0),
                (100.02, 10.0),
                (100.03, 10.0),
                (100.04, 10.0),
            ],
            timestamp="2026-01-19T12:00:00Z"
        )

        analysis = analyzer.analyze(snapshot)

        # Should indicate dense order book
        assert analysis.bid_density > 0
        assert analysis.ask_density > 0

    def test_price_level_count(self):
        """Test counting unique price levels."""
        from core.analysis.order_book_analyzer import OrderBookAnalyzer, OrderBookSnapshot

        analyzer = OrderBookAnalyzer()
        snapshot = OrderBookSnapshot(
            symbol="SOL/USDC",
            bids=[(100.0 - i*0.1, 10.0) for i in range(20)],  # 20 levels
            asks=[(100.5 + i*0.1, 10.0) for i in range(15)],  # 15 levels
            timestamp="2026-01-19T12:00:00Z"
        )

        analysis = analyzer.analyze(snapshot)

        assert analysis.bid_levels == 20
        assert analysis.ask_levels == 15


class TestAnalysisResult:
    """Test the analysis result structure."""

    def test_analysis_result_has_all_fields(self):
        """Test analysis result contains all expected fields."""
        from core.analysis.order_book_analyzer import OrderBookAnalyzer, OrderBookSnapshot

        analyzer = OrderBookAnalyzer()
        snapshot = OrderBookSnapshot(
            symbol="SOL/USDC",
            bids=[(100.0, 10.0), (99.0, 20.0)],
            asks=[(101.0, 15.0), (102.0, 25.0)],
            timestamp="2026-01-19T12:00:00Z"
        )

        analysis = analyzer.analyze(snapshot)

        # Core metrics
        assert hasattr(analysis, 'symbol')
        assert hasattr(analysis, 'timestamp')
        assert hasattr(analysis, 'mid_price')
        assert hasattr(analysis, 'spread')
        assert hasattr(analysis, 'spread_bps')

        # Depth
        assert hasattr(analysis, 'depth_1pct_bid')
        assert hasattr(analysis, 'depth_1pct_ask')
        assert hasattr(analysis, 'depth_5pct_bid')
        assert hasattr(analysis, 'depth_5pct_ask')
        assert hasattr(analysis, 'total_bid_depth')
        assert hasattr(analysis, 'total_ask_depth')

        # Liquidity
        assert hasattr(analysis, 'liquidity_score')
        assert hasattr(analysis, 'liquidity_grade')
        assert hasattr(analysis, 'liquidity_factors')

        # Walls
        assert hasattr(analysis, 'bid_walls')
        assert hasattr(analysis, 'ask_walls')

        # Imbalance
        assert hasattr(analysis, 'imbalance')
        assert hasattr(analysis, 'imbalance_signal')

        # VWAP
        assert hasattr(analysis, 'vwap_bid')
        assert hasattr(analysis, 'vwap_ask')

        # Pressure
        assert hasattr(analysis, 'buying_pressure')
        assert hasattr(analysis, 'selling_pressure')

    def test_analysis_result_serializable(self):
        """Test analysis result can be serialized to dict."""
        from core.analysis.order_book_analyzer import OrderBookAnalyzer, OrderBookSnapshot

        analyzer = OrderBookAnalyzer()
        snapshot = OrderBookSnapshot(
            symbol="SOL/USDC",
            bids=[(100.0, 10.0)],
            asks=[(101.0, 15.0)],
            timestamp="2026-01-19T12:00:00Z"
        )

        analysis = analyzer.analyze(snapshot)

        # Should be convertible to dict
        result_dict = analysis.to_dict()
        assert isinstance(result_dict, dict)
        assert 'symbol' in result_dict
        assert 'spread_bps' in result_dict


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_single_level_each_side(self):
        """Test with only one level on each side."""
        from core.analysis.order_book_analyzer import OrderBookAnalyzer, OrderBookSnapshot

        analyzer = OrderBookAnalyzer()
        snapshot = OrderBookSnapshot(
            symbol="SOL/USDC",
            bids=[(100.0, 10.0)],
            asks=[(101.0, 10.0)],
            timestamp="2026-01-19T12:00:00Z"
        )

        analysis = analyzer.analyze(snapshot)

        assert analysis.mid_price > 0
        assert analysis.spread > 0
        assert len(analysis.bid_walls) == 0  # Can't detect walls with 1 level

    def test_crossed_book(self):
        """Test handling of crossed order book (should not happen in practice)."""
        from core.analysis.order_book_analyzer import OrderBookAnalyzer, OrderBookSnapshot

        analyzer = OrderBookAnalyzer()
        # Crossed book: best bid > best ask (invalid state)
        snapshot = OrderBookSnapshot(
            symbol="SOL/USDC",
            bids=[(102.0, 10.0)],  # Bid higher than ask
            asks=[(101.0, 10.0)],
            timestamp="2026-01-19T12:00:00Z"
        )

        analysis = analyzer.analyze(snapshot)

        # Should flag as invalid or handle gracefully
        assert analysis.is_valid == False or analysis.spread < 0

    def test_zero_size_levels(self):
        """Test handling of zero-size levels."""
        from core.analysis.order_book_analyzer import OrderBookAnalyzer, OrderBookSnapshot

        analyzer = OrderBookAnalyzer()
        snapshot = OrderBookSnapshot(
            symbol="SOL/USDC",
            bids=[(100.0, 0.0), (99.0, 10.0)],  # First level has 0 size
            asks=[(101.0, 10.0)],
            timestamp="2026-01-19T12:00:00Z"
        )

        analysis = analyzer.analyze(snapshot)

        # Should skip zero-size levels
        assert analysis.mid_price > 0

    def test_very_small_prices(self):
        """Test handling of micro-cap token prices."""
        from core.analysis.order_book_analyzer import OrderBookAnalyzer, OrderBookSnapshot

        analyzer = OrderBookAnalyzer()
        snapshot = OrderBookSnapshot(
            symbol="MICRO/USDC",
            bids=[(0.000001, 1000000.0)],
            asks=[(0.0000015, 500000.0)],
            timestamp="2026-01-19T12:00:00Z"
        )

        analysis = analyzer.analyze(snapshot)

        assert analysis.mid_price > 0
        assert analysis.spread_bps > 0


class TestIntegrationWithOrderBook:
    """Test integration with existing OrderBook system."""

    def test_analyze_from_order_book_data(self):
        """Test analyzing data in OrderBook format."""
        from core.analysis.order_book_analyzer import OrderBookAnalyzer, OrderBookSnapshot

        analyzer = OrderBookAnalyzer()

        # Simulate data from OrderBookManager
        order_book_data = {
            'symbol': 'SOL',
            'bids': [(100.0, 50.0), (99.5, 100.0), (99.0, 150.0)],
            'asks': [(100.5, 60.0), (101.0, 120.0), (101.5, 180.0)],
            'timestamp': '2026-01-19T12:00:00Z',
        }

        snapshot = OrderBookSnapshot.from_dict(order_book_data)
        analysis = analyzer.analyze(snapshot)

        assert analysis.symbol == 'SOL'
        assert analysis.mid_price > 0
