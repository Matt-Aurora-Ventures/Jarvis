"""
Tests for Correlation Analyzer - Advanced correlation analysis for trading.

Tests cover:
- Pairwise correlation calculation
- Rolling correlation windows
- Correlation matrix and heatmap generation
- Correlation breakdown detection
- Lead/lag relationship analysis
- Portfolio diversification scoring
"""

import pytest
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile


class TestPearsonCorrelation:
    """Test basic Pearson correlation calculations."""

    def test_perfect_positive_correlation(self):
        """Identical series should have correlation of 1.0."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [1.0, 2.0, 3.0, 4.0, 5.0]

        corr = analyzer.pearson_correlation(x, y)
        assert corr == pytest.approx(1.0, abs=0.001)

    def test_perfect_negative_correlation(self):
        """Opposite series should have correlation of -1.0."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [5.0, 4.0, 3.0, 2.0, 1.0]

        corr = analyzer.pearson_correlation(x, y)
        assert corr == pytest.approx(-1.0, abs=0.001)

    def test_no_correlation(self):
        """Uncorrelated series should have correlation near 0."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [3.0, 1.0, 4.0, 2.0, 5.0]  # Random-ish ordering

        corr = analyzer.pearson_correlation(x, y)
        # Should be relatively low
        assert abs(corr) < 0.8

    def test_empty_series_returns_zero(self):
        """Empty series should return 0.0 correlation."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()
        corr = analyzer.pearson_correlation([], [])
        assert corr == 0.0

    def test_single_element_returns_zero(self):
        """Single element series returns 0.0 (no variance)."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()
        corr = analyzer.pearson_correlation([1.0], [2.0])
        assert corr == 0.0

    def test_constant_series_returns_zero(self):
        """Constant series (no variance) returns 0.0."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()
        x = [5.0, 5.0, 5.0, 5.0]
        y = [1.0, 2.0, 3.0, 4.0]

        corr = analyzer.pearson_correlation(x, y)
        assert corr == 0.0


class TestReturnsCalculation:
    """Test return series calculation."""

    def test_calculate_returns_basic(self):
        """Returns should be (p[t] - p[t-1]) / p[t-1]."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()
        prices = [100.0, 110.0, 99.0, 100.0]

        returns = analyzer.calculate_returns(prices)

        assert len(returns) == 3
        assert returns[0] == pytest.approx(0.1, abs=0.001)  # 10% gain
        assert returns[1] == pytest.approx(-0.1, abs=0.001)  # 10% loss
        assert returns[2] == pytest.approx(0.0101, abs=0.001)  # ~1% gain

    def test_empty_prices_returns_empty(self):
        """Empty price list returns empty returns."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()
        returns = analyzer.calculate_returns([])
        assert returns == []

    def test_single_price_returns_empty(self):
        """Single price returns empty list (need 2+ for returns)."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()
        returns = analyzer.calculate_returns([100.0])
        assert returns == []

    def test_handles_zero_price(self):
        """Zero price should not cause division error."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()
        prices = [100.0, 0.0, 50.0]

        returns = analyzer.calculate_returns(prices)
        # First return calculated, second skipped (div by 0)
        assert len(returns) == 1


class TestCorrelationMatrix:
    """Test correlation matrix generation."""

    def test_correlation_matrix_structure(self):
        """Matrix should be symmetric with 1.0 on diagonal."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()

        # Create sample price data
        price_data = {
            "BTC": [100.0, 110.0, 105.0, 115.0, 120.0],
            "ETH": [10.0, 11.0, 10.5, 11.5, 12.0],
            "SOL": [1.0, 1.1, 1.05, 1.15, 1.2]
        }

        matrix = analyzer.calculate_correlation_matrix(price_data)

        # Check diagonal is 1.0
        assert matrix["BTC"]["BTC"] == pytest.approx(1.0, abs=0.001)
        assert matrix["ETH"]["ETH"] == pytest.approx(1.0, abs=0.001)
        assert matrix["SOL"]["SOL"] == pytest.approx(1.0, abs=0.001)

        # Check symmetry
        assert matrix["BTC"]["ETH"] == pytest.approx(matrix["ETH"]["BTC"], abs=0.001)
        assert matrix["BTC"]["SOL"] == pytest.approx(matrix["SOL"]["BTC"], abs=0.001)

    def test_empty_price_data(self):
        """Empty data returns empty matrix."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()
        matrix = analyzer.calculate_correlation_matrix({})
        assert matrix == {}

    def test_single_asset_matrix(self):
        """Single asset returns 1x1 matrix with 1.0."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()
        price_data = {"BTC": [100.0, 110.0, 105.0]}

        matrix = analyzer.calculate_correlation_matrix(price_data)
        assert matrix["BTC"]["BTC"] == pytest.approx(1.0, abs=0.001)

    def test_insufficient_data_handled(self):
        """Assets with insufficient data handled gracefully."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()
        price_data = {
            "BTC": [100.0],  # Only 1 price
            "ETH": [10.0, 11.0, 12.0, 13.0, 14.0]
        }

        matrix = analyzer.calculate_correlation_matrix(price_data)
        # Should still work but correlation will be 0 for BTC pairs
        assert "BTC" in matrix
        assert "ETH" in matrix


class TestRollingCorrelation:
    """Test rolling window correlation calculations."""

    def test_rolling_correlation_basic(self):
        """Rolling correlation should return a time series."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()

        # Create longer price series
        prices_a = [100 + i + (i % 3) for i in range(30)]
        prices_b = [50 + i * 0.5 + (i % 2) for i in range(30)]

        rolling = analyzer.calculate_rolling_correlation(
            prices_a, prices_b, window=10
        )

        # Should have (n - window + 1) values
        assert len(rolling) == 30 - 10 + 1

    def test_rolling_correlation_window_too_large(self):
        """Window larger than data returns empty list."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()
        prices_a = [100.0, 110.0, 105.0]
        prices_b = [10.0, 11.0, 10.5]

        rolling = analyzer.calculate_rolling_correlation(
            prices_a, prices_b, window=10
        )
        assert rolling == []

    def test_rolling_correlation_values_bounded(self):
        """All correlation values should be between -1 and 1."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()
        prices_a = [100 + i * 2 for i in range(50)]
        prices_b = [50 + i for i in range(50)]

        rolling = analyzer.calculate_rolling_correlation(
            prices_a, prices_b, window=10
        )

        for corr in rolling:
            assert -1.0 <= corr <= 1.0


class TestCorrelationBreakdown:
    """Test correlation breakdown detection."""

    def test_detect_breakdown_significant_change(self):
        """Detect when correlation changes significantly."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()

        # Simulate correlation that suddenly drops
        rolling_correlations = [
            0.9, 0.85, 0.88, 0.92, 0.87,  # Stable high correlation
            0.2, 0.15, 0.25, 0.18         # Sudden drop
        ]

        breakdowns = analyzer.detect_correlation_breakdown(
            rolling_correlations,
            threshold=0.3
        )

        assert len(breakdowns) >= 1
        # First breakdown should be around index 5
        assert any(b["index"] == 5 for b in breakdowns)

    def test_no_breakdown_stable_correlation(self):
        """No breakdown detected for stable correlation."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()

        rolling_correlations = [0.85, 0.87, 0.86, 0.88, 0.84, 0.86]

        breakdowns = analyzer.detect_correlation_breakdown(
            rolling_correlations,
            threshold=0.3
        )

        assert breakdowns == []

    def test_breakdown_both_directions(self):
        """Detect breakdowns in both directions."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()

        rolling_correlations = [
            0.9, 0.2,   # Drop
            0.25, 0.85  # Rise back up
        ]

        breakdowns = analyzer.detect_correlation_breakdown(
            rolling_correlations,
            threshold=0.3
        )

        assert len(breakdowns) >= 2

    def test_empty_rolling_returns_empty(self):
        """Empty input returns no breakdowns."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()
        breakdowns = analyzer.detect_correlation_breakdown([], threshold=0.3)
        assert breakdowns == []


class TestLeadLagAnalysis:
    """Test lead/lag relationship detection."""

    def test_detect_lead_basic(self):
        """Detect when one series leads another."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()

        # Create series where A leads B by 2 periods
        base = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
        prices_a = [float(x) for x in base]
        prices_b = [float(x) for x in [0, 0] + base[:-2]]  # Shifted by 2

        result = analyzer.detect_lead_lag(prices_a, prices_b, max_lag=5)

        assert result is not None
        assert result["leader"] == "A"
        assert result["lag_periods"] >= 1

    def test_no_lead_lag_synchronous(self):
        """Synchronous series should have lag of 0."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()

        prices_a = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        prices_b = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]

        result = analyzer.detect_lead_lag(prices_a, prices_b, max_lag=3)

        assert result is not None
        assert result["lag_periods"] == 0

    def test_lead_lag_insufficient_data(self):
        """Insufficient data returns None."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()
        result = analyzer.detect_lead_lag([1.0, 2.0], [1.0, 2.0], max_lag=5)
        assert result is None

    def test_lead_lag_returns_confidence(self):
        """Result includes confidence score."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()

        prices_a = [float(i) for i in range(20)]
        prices_b = [float(i) for i in range(20)]

        result = analyzer.detect_lead_lag(prices_a, prices_b, max_lag=3)

        assert result is not None
        assert "confidence" in result
        assert 0.0 <= result["confidence"] <= 1.0


class TestHeatmapGeneration:
    """Test correlation heatmap data generation."""

    def test_generate_heatmap_data(self):
        """Generate heatmap data from correlation matrix."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()

        price_data = {
            "BTC": [100.0, 110.0, 105.0, 115.0, 120.0],
            "ETH": [10.0, 11.0, 10.5, 11.5, 12.0],
            "SOL": [1.0, 1.1, 1.05, 1.15, 1.2]
        }

        heatmap = analyzer.generate_heatmap_data(price_data)

        assert "assets" in heatmap
        assert "matrix" in heatmap
        assert "values" in heatmap

        assert len(heatmap["assets"]) == 3
        assert len(heatmap["matrix"]) == 3
        assert len(heatmap["matrix"][0]) == 3

    def test_heatmap_values_normalized(self):
        """Heatmap values should be normalized for display."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()

        price_data = {
            "BTC": [100.0, 110.0, 105.0, 115.0, 120.0],
            "ETH": [10.0, 11.0, 10.5, 11.5, 12.0],
        }

        heatmap = analyzer.generate_heatmap_data(price_data)

        # All values should be between -1 and 1
        for row in heatmap["matrix"]:
            for val in row:
                assert -1.0 <= val <= 1.0


class TestDiversificationAnalysis:
    """Test portfolio diversification analysis."""

    def test_high_correlation_low_diversification(self):
        """Highly correlated assets = poor diversification."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()

        # All assets move together
        price_data = {
            "BTC": [100.0, 110.0, 121.0, 133.1, 146.4],
            "ETH": [10.0, 11.0, 12.1, 13.3, 14.6],
            "SOL": [1.0, 1.1, 1.21, 1.33, 1.46]
        }
        holdings = {"BTC": 0.4, "ETH": 0.3, "SOL": 0.3}

        result = analyzer.analyze_diversification(price_data, holdings)

        assert result["score"] < 50  # Poor diversification
        assert result["avg_correlation"] > 0.7

    def test_low_correlation_high_diversification(self):
        """Uncorrelated assets = good diversification."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()

        # Assets move independently
        price_data = {
            "BTC": [100.0, 110.0, 105.0, 115.0, 108.0],
            "ETH": [10.0, 9.5, 10.5, 9.0, 11.0],
            "SOL": [1.0, 1.2, 0.9, 1.3, 0.8]
        }
        holdings = {"BTC": 0.34, "ETH": 0.33, "SOL": 0.33}

        result = analyzer.analyze_diversification(price_data, holdings)

        assert result["score"] > 50  # Better diversification
        assert result["avg_correlation"] < 0.7

    def test_single_asset_perfect_diversification(self):
        """Single asset is trivially 'diversified'."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()

        price_data = {"BTC": [100.0, 110.0, 105.0]}
        holdings = {"BTC": 1.0}

        result = analyzer.analyze_diversification(price_data, holdings)
        assert result["score"] == 100.0

    def test_diversification_recommendations(self):
        """Recommendations provided based on score."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()

        price_data = {
            "BTC": [100.0, 110.0, 121.0, 133.1],
            "ETH": [10.0, 11.0, 12.1, 13.3],
        }
        holdings = {"BTC": 0.5, "ETH": 0.5}

        result = analyzer.analyze_diversification(price_data, holdings)
        assert "recommendation" in result


class TestCorrelationPairs:
    """Test finding correlated pairs."""

    def test_find_highly_correlated_pairs(self):
        """Find pairs with correlation above threshold."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()

        # Create correlated and uncorrelated assets
        price_data = {
            "BTC": [100.0, 110.0, 105.0, 115.0, 120.0],
            "ETH": [10.0, 11.0, 10.5, 11.5, 12.0],  # Correlated with BTC
            "GOLD": [50.0, 48.0, 52.0, 47.0, 53.0],  # Uncorrelated
        }

        pairs = analyzer.find_correlated_pairs(price_data, min_correlation=0.8)

        # BTC-ETH should be highly correlated
        pair_names = [(p["asset_a"], p["asset_b"]) for p in pairs]
        assert ("BTC", "ETH") in pair_names or ("ETH", "BTC") in pair_names

    def test_find_inversely_correlated_pairs(self):
        """Find pairs with strong negative correlation."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()

        price_data = {
            "BTC": [100.0, 110.0, 120.0, 130.0, 140.0],
            "INVERSE": [50.0, 45.0, 40.0, 35.0, 30.0],
        }

        pairs = analyzer.find_correlated_pairs(
            price_data,
            min_correlation=0.8,
            include_negative=True
        )

        assert len(pairs) >= 1
        assert any(p["correlation"] < -0.8 for p in pairs)


class TestStatisticalSignificance:
    """Test statistical significance calculations."""

    def test_p_value_calculation(self):
        """P-value should indicate statistical significance."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()

        # Strong correlation with many samples
        x = [float(i) for i in range(100)]
        y = [float(i) * 2 for i in range(100)]

        corr, p_value = analyzer.correlation_with_significance(x, y)

        assert abs(corr) > 0.99
        assert p_value < 0.05  # Statistically significant

    def test_p_value_high_for_random(self):
        """P-value should be high for weak correlations."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()

        # Uncorrelated data
        x = [1.0, 3.0, 2.0, 5.0, 4.0]
        y = [3.0, 1.0, 4.0, 2.0, 5.0]

        corr, p_value = analyzer.correlation_with_significance(x, y)

        # Should not be highly significant
        assert abs(corr) < 0.9 or p_value > 0.01


class TestCorrelationAnalyzerIntegration:
    """Integration tests for the full analyzer."""

    def test_full_analysis_workflow(self):
        """Test complete analysis workflow."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()

        # Generate realistic-ish price data
        import random
        random.seed(42)

        base = 100
        prices = {"BTC": [], "ETH": [], "SOL": [], "DOGE": []}

        for i in range(50):
            btc = base * (1 + i * 0.01 + random.gauss(0, 0.02))
            eth = btc * 0.1 + random.gauss(0, 2)  # Correlated with BTC
            sol = 20 + random.gauss(0, 3)  # Less correlated
            doge = 0.1 * (1 + random.gauss(0, 0.1))

            prices["BTC"].append(btc)
            prices["ETH"].append(eth)
            prices["SOL"].append(sol)
            prices["DOGE"].append(doge)

        # Calculate matrix
        matrix = analyzer.calculate_correlation_matrix(prices)
        assert len(matrix) == 4

        # Generate heatmap
        heatmap = analyzer.generate_heatmap_data(prices)
        assert len(heatmap["assets"]) == 4

        # Analyze diversification
        holdings = {"BTC": 0.4, "ETH": 0.3, "SOL": 0.2, "DOGE": 0.1}
        diversification = analyzer.analyze_diversification(prices, holdings)
        assert "score" in diversification

    def test_analyzer_handles_missing_data(self):
        """Analyzer handles assets with different data lengths."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()

        price_data = {
            "BTC": [100.0, 110.0, 120.0, 130.0, 140.0],
            "ETH": [10.0, 11.0, 12.0],  # Shorter
        }

        matrix = analyzer.calculate_correlation_matrix(price_data)
        assert "BTC" in matrix
        assert "ETH" in matrix


class TestCorrelationDataclass:
    """Test correlation result dataclass."""

    def test_correlation_result_creation(self):
        """CorrelationResult dataclass stores all fields."""
        from core.analysis.correlation_analyzer import CorrelationResult

        result = CorrelationResult(
            asset_a="BTC",
            asset_b="ETH",
            correlation=0.85,
            sample_size=100,
            p_value=0.001,
            confidence_interval=(-0.9, 0.9)
        )

        assert result.asset_a == "BTC"
        assert result.asset_b == "ETH"
        assert result.correlation == 0.85
        assert result.sample_size == 100
        assert result.p_value == 0.001
        assert result.confidence_interval == (-0.9, 0.9)

    def test_correlation_result_is_significant(self):
        """Check significance helper method."""
        from core.analysis.correlation_analyzer import CorrelationResult

        significant = CorrelationResult(
            asset_a="BTC", asset_b="ETH",
            correlation=0.85, sample_size=100,
            p_value=0.001
        )

        not_significant = CorrelationResult(
            asset_a="BTC", asset_b="SOL",
            correlation=0.2, sample_size=10,
            p_value=0.15
        )

        assert significant.is_significant(alpha=0.05)
        assert not not_significant.is_significant(alpha=0.05)


class TestBreakdownEvent:
    """Test correlation breakdown event dataclass."""

    def test_breakdown_event_creation(self):
        """BreakdownEvent dataclass stores all fields."""
        from core.analysis.correlation_analyzer import BreakdownEvent

        event = BreakdownEvent(
            index=5,
            previous_correlation=0.9,
            current_correlation=0.2,
            change=-0.7,
            timestamp=None
        )

        assert event.index == 5
        assert event.previous_correlation == 0.9
        assert event.current_correlation == 0.2
        assert event.change == -0.7


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_nan_handling(self):
        """NaN values should be handled gracefully."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()

        prices_a = [100.0, float('nan'), 105.0, 110.0]
        prices_b = [10.0, 11.0, float('nan'), 12.0]

        # Should not raise, should handle gracefully
        returns_a = analyzer.calculate_returns(prices_a)
        returns_b = analyzer.calculate_returns(prices_b)

        # Returns may be shorter due to NaN handling
        assert isinstance(returns_a, list)
        assert isinstance(returns_b, list)

    def test_inf_handling(self):
        """Infinity values should be handled gracefully."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()

        prices = [100.0, float('inf'), 105.0]
        returns = analyzer.calculate_returns(prices)

        # Should handle without crashing
        assert isinstance(returns, list)

    def test_very_large_dataset(self):
        """Should handle large datasets efficiently."""
        from core.analysis.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()

        # 10000 data points
        prices_a = [100 + i * 0.01 for i in range(10000)]
        prices_b = [50 + i * 0.005 for i in range(10000)]

        # Should complete in reasonable time
        corr = analyzer.pearson_correlation(
            analyzer.calculate_returns(prices_a),
            analyzer.calculate_returns(prices_b)
        )

        assert -1.0 <= corr <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
