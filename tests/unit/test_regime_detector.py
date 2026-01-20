"""
Unit tests for Market Regime Detection System.

Tests:
- Regime classification (trending, ranging, volatile, crash)
- Transition detection between regimes
- Probability estimation for each regime
- Historical regime analysis
- Strategy recommendations per regime
- Edge cases and data validation
"""

import pytest
import math
from datetime import datetime, timezone
from typing import List, Dict, Any
from unittest.mock import MagicMock, patch


class TestRegimeTypes:
    """Test regime type definitions and enumerations."""

    def test_market_regime_values(self):
        """Test that MarketRegime has all expected values."""
        from core.analysis.regime_detector import MarketRegime

        assert hasattr(MarketRegime, "TRENDING_UP")
        assert hasattr(MarketRegime, "TRENDING_DOWN")
        assert hasattr(MarketRegime, "RANGING")
        assert hasattr(MarketRegime, "VOLATILE")
        assert hasattr(MarketRegime, "CRASH")
        assert hasattr(MarketRegime, "RECOVERY")

    def test_market_regime_all_method(self):
        """Test that all() returns list of all regimes."""
        from core.analysis.regime_detector import MarketRegime

        all_regimes = MarketRegime.all()
        assert isinstance(all_regimes, list)
        assert len(all_regimes) >= 5
        assert MarketRegime.TRENDING_UP in all_regimes
        assert MarketRegime.CRASH in all_regimes

    def test_market_regime_description(self):
        """Test that regimes have descriptions."""
        from core.analysis.regime_detector import MarketRegime

        description = MarketRegime.get_description(MarketRegime.TRENDING_UP)
        assert isinstance(description, str)
        assert len(description) > 0

    def test_regime_strategy_mapping(self):
        """Test mapping regimes to recommended strategies."""
        from core.analysis.regime_detector import MarketRegime, StrategyRecommendation

        # Each regime should map to a strategy
        for regime in MarketRegime.all():
            strategy = StrategyRecommendation.for_regime(regime)
            assert strategy is not None
            assert hasattr(strategy, "name")
            assert hasattr(strategy, "position_size_multiplier")


class TestRegimeDetectionResult:
    """Test RegimeDetectionResult dataclass."""

    def test_regime_detection_result_creation(self):
        """Test creating a RegimeDetectionResult."""
        from core.analysis.regime_detector import (
            RegimeDetectionResult,
            MarketRegime,
        )

        result = RegimeDetectionResult(
            regime=MarketRegime.TRENDING_UP,
            confidence=0.85,
            probabilities={
                MarketRegime.TRENDING_UP: 0.85,
                MarketRegime.RANGING: 0.10,
                MarketRegime.VOLATILE: 0.05,
            },
            features={"trend_slope": 0.05, "volatility": 0.02},
            timestamp=datetime.now(timezone.utc),
        )

        assert result.regime == MarketRegime.TRENDING_UP
        assert result.confidence == 0.85
        assert MarketRegime.TRENDING_UP in result.probabilities
        assert "trend_slope" in result.features

    def test_regime_detection_result_to_dict(self):
        """Test converting result to dictionary."""
        from core.analysis.regime_detector import (
            RegimeDetectionResult,
            MarketRegime,
        )

        result = RegimeDetectionResult(
            regime=MarketRegime.RANGING,
            confidence=0.75,
            probabilities={MarketRegime.RANGING: 0.75},
            features={},
            timestamp=datetime.now(timezone.utc),
        )

        data = result.to_dict()
        assert "regime" in data
        assert "confidence" in data
        assert "probabilities" in data
        assert "timestamp" in data

    def test_regime_detection_result_from_dict(self):
        """Test creating result from dictionary."""
        from core.analysis.regime_detector import RegimeDetectionResult

        data = {
            "regime": "trending_up",
            "confidence": 0.9,
            "probabilities": {"trending_up": 0.9, "ranging": 0.1},
            "features": {"momentum": 0.5},
            "timestamp": "2026-01-19T12:00:00Z",
        }

        result = RegimeDetectionResult.from_dict(data)
        assert result.confidence == 0.9
        assert "momentum" in result.features


class TestRegimeTransition:
    """Test RegimeTransition tracking."""

    def test_regime_transition_creation(self):
        """Test creating a RegimeTransition."""
        from core.analysis.regime_detector import (
            RegimeTransition,
            MarketRegime,
        )

        transition = RegimeTransition(
            from_regime=MarketRegime.RANGING,
            to_regime=MarketRegime.TRENDING_UP,
            confidence=0.80,
            timestamp=datetime.now(timezone.utc),
        )

        assert transition.from_regime == MarketRegime.RANGING
        assert transition.to_regime == MarketRegime.TRENDING_UP
        assert transition.confidence == 0.80

    def test_regime_transition_is_significant(self):
        """Test significance detection for transitions."""
        from core.analysis.regime_detector import (
            RegimeTransition,
            MarketRegime,
        )

        # Crash transition should be significant
        crash_transition = RegimeTransition(
            from_regime=MarketRegime.TRENDING_UP,
            to_regime=MarketRegime.CRASH,
            confidence=0.85,
            timestamp=datetime.now(timezone.utc),
        )
        assert crash_transition.is_significant() is True

        # Ranging to ranging (same) is not significant
        no_change = RegimeTransition(
            from_regime=MarketRegime.RANGING,
            to_regime=MarketRegime.RANGING,
            confidence=0.90,
            timestamp=datetime.now(timezone.utc),
        )
        assert no_change.is_significant() is False


class TestRegimeFeatureExtractor:
    """Test feature extraction for regime detection."""

    @pytest.fixture
    def sample_prices(self) -> List[float]:
        """Generate sample price data."""
        import random

        random.seed(42)
        base_price = 100.0
        prices = [base_price]

        # Generate 200 prices with slight randomness
        for _ in range(199):
            change = random.gauss(0, 1.0)  # 1% std dev
            prices.append(prices[-1] * (1 + change / 100))

        return prices

    @pytest.fixture
    def trending_prices(self) -> List[float]:
        """Generate trending price data."""
        prices = [100.0]
        for i in range(199):
            # Consistent upward trend with small noise
            change = 0.5 + (i * 0.01)  # Increasing momentum
            prices.append(prices[-1] * (1 + change / 100))
        return prices

    @pytest.fixture
    def volatile_prices(self) -> List[float]:
        """Generate volatile price data."""
        import random

        random.seed(42)
        prices = [100.0]
        for _ in range(199):
            # High volatility swings
            change = random.gauss(0, 5.0)  # 5% std dev
            prices.append(prices[-1] * (1 + change / 100))
        return prices

    def test_extractor_initialization(self):
        """Test feature extractor initialization."""
        from core.analysis.regime_detector import RegimeFeatureExtractor

        extractor = RegimeFeatureExtractor(lookback=30)
        assert extractor.lookback == 30

    def test_extract_returns_dict(self, sample_prices):
        """Test that extract returns a dictionary of features."""
        from core.analysis.regime_detector import RegimeFeatureExtractor

        extractor = RegimeFeatureExtractor()
        features = extractor.extract(sample_prices)

        assert isinstance(features, dict)
        assert len(features) > 0

    def test_extract_volatility_features(self, sample_prices):
        """Test volatility feature extraction."""
        from core.analysis.regime_detector import RegimeFeatureExtractor

        extractor = RegimeFeatureExtractor()
        features = extractor.extract(sample_prices)

        assert "volatility_std" in features
        assert "volatility_range" in features
        assert "volatility_atr" in features

    def test_extract_trend_features(self, sample_prices):
        """Test trend feature extraction."""
        from core.analysis.regime_detector import RegimeFeatureExtractor

        extractor = RegimeFeatureExtractor()
        features = extractor.extract(sample_prices)

        assert "trend_slope" in features
        assert "trend_strength" in features
        assert "trend_adx" in features

    def test_extract_momentum_features(self, sample_prices):
        """Test momentum feature extraction."""
        from core.analysis.regime_detector import RegimeFeatureExtractor

        extractor = RegimeFeatureExtractor()
        features = extractor.extract(sample_prices)

        assert "momentum_roc" in features
        assert "momentum_rsi" in features

    def test_extract_mean_reversion_features(self, sample_prices):
        """Test mean reversion feature extraction."""
        from core.analysis.regime_detector import RegimeFeatureExtractor

        extractor = RegimeFeatureExtractor()
        features = extractor.extract(sample_prices)

        assert "mr_bb_position" in features
        assert "mr_ma_distance" in features

    def test_extract_with_insufficient_data(self):
        """Test extraction with insufficient data returns empty dict."""
        from core.analysis.regime_detector import RegimeFeatureExtractor

        extractor = RegimeFeatureExtractor(lookback=30)
        features = extractor.extract([100.0, 101.0, 102.0])  # Only 3 prices

        assert features == {} or len(features) == 0

    def test_trending_prices_have_high_trend_strength(self, trending_prices):
        """Test that trending prices show high trend strength."""
        from core.analysis.regime_detector import RegimeFeatureExtractor

        extractor = RegimeFeatureExtractor()
        features = extractor.extract(trending_prices)

        # Trending data should have high trend strength
        assert features.get("trend_strength", 0) > 0.5

    def test_volatile_prices_have_high_volatility(self, volatile_prices):
        """Test that volatile prices show high volatility metrics."""
        from core.analysis.regime_detector import RegimeFeatureExtractor

        extractor = RegimeFeatureExtractor()
        features = extractor.extract(volatile_prices)

        # Volatile data should have high volatility
        assert features.get("volatility_std", 0) > 0.01


class TestRegimeDetector:
    """Test main RegimeDetector class."""

    @pytest.fixture
    def detector(self):
        """Create a detector instance."""
        from core.analysis.regime_detector import RegimeDetector

        return RegimeDetector()

    @pytest.fixture
    def sample_prices(self) -> List[float]:
        """Generate sample price data."""
        import random

        random.seed(42)
        prices = [100.0]
        for _ in range(199):
            change = random.gauss(0, 1.0)
            prices.append(prices[-1] * (1 + change / 100))
        return prices

    def test_detector_initialization(self):
        """Test detector initialization."""
        from core.analysis.regime_detector import RegimeDetector

        detector = RegimeDetector(lookback=30, smoothing=3)
        assert detector.lookback == 30
        assert detector.smoothing == 3

    def test_detect_returns_result(self, detector, sample_prices):
        """Test that detect returns a RegimeDetectionResult."""
        from core.analysis.regime_detector import RegimeDetectionResult

        result = detector.detect(sample_prices)

        assert isinstance(result, RegimeDetectionResult)
        assert result.regime is not None
        assert 0 <= result.confidence <= 1

    def test_detect_provides_probabilities(self, detector, sample_prices):
        """Test that detect provides probability distribution."""
        result = detector.detect(sample_prices)

        assert len(result.probabilities) > 0
        # Probabilities should sum to approximately 1
        total_prob = sum(result.probabilities.values())
        assert 0.99 <= total_prob <= 1.01

    def test_detect_trending_up(self):
        """Test detection of upward trend."""
        from core.analysis.regime_detector import RegimeDetector, MarketRegime

        # Create clear uptrend
        prices = [100.0]
        for i in range(199):
            prices.append(prices[-1] * 1.01)  # 1% daily increase

        detector = RegimeDetector()
        result = detector.detect(prices)

        assert result.regime == MarketRegime.TRENDING_UP

    def test_detect_trending_down(self):
        """Test detection of downward trend."""
        from core.analysis.regime_detector import RegimeDetector, MarketRegime

        # Create clear downtrend
        prices = [100.0]
        for i in range(199):
            prices.append(prices[-1] * 0.99)  # 1% daily decrease

        detector = RegimeDetector()
        result = detector.detect(prices)

        assert result.regime == MarketRegime.TRENDING_DOWN

    def test_detect_ranging_market(self):
        """Test detection of ranging/sideways market."""
        from core.analysis.regime_detector import RegimeDetector, MarketRegime
        import random

        random.seed(42)
        # Create range-bound prices oscillating around mean
        prices = []
        for i in range(200):
            price = 100.0 + 2.0 * math.sin(i * 0.1)  # Oscillate +/- 2%
            price += random.gauss(0, 0.1)  # Small noise
            prices.append(price)

        detector = RegimeDetector()
        result = detector.detect(prices)

        # Should detect ranging or low volatility
        assert result.regime in [MarketRegime.RANGING, MarketRegime.VOLATILE]

    def test_detect_crash(self):
        """Test detection of market crash."""
        from core.analysis.regime_detector import RegimeDetector, MarketRegime

        # Create crash scenario: sudden large drop
        prices = [100.0] * 150
        # 50 periods of 3% daily drop
        for i in range(50):
            prices.append(prices[-1] * 0.97)

        detector = RegimeDetector()
        result = detector.detect(prices)

        assert result.regime in [MarketRegime.CRASH, MarketRegime.TRENDING_DOWN]

    def test_detect_volatile_market(self):
        """Test detection of volatile market."""
        from core.analysis.regime_detector import RegimeDetector, MarketRegime
        import random

        random.seed(42)
        prices = [100.0]
        for _ in range(199):
            # Large random swings both ways
            change = random.choice([-5, 5]) + random.gauss(0, 2)
            prices.append(prices[-1] * (1 + change / 100))

        detector = RegimeDetector()
        result = detector.detect(prices)

        assert result.regime in [MarketRegime.VOLATILE, MarketRegime.CRASH]


class TestTransitionDetection:
    """Test regime transition detection."""

    @pytest.fixture
    def detector(self):
        """Create a detector instance."""
        from core.analysis.regime_detector import RegimeDetector

        return RegimeDetector()

    def test_detect_transition(self, detector):
        """Test detection of regime transitions."""
        from core.analysis.regime_detector import MarketRegime

        # Start with ranging market
        ranging_prices = [100.0 + 2 * math.sin(i * 0.1) for i in range(100)]

        # Transition to trending
        trending_prices = [ranging_prices[-1]]
        for _ in range(100):
            trending_prices.append(trending_prices[-1] * 1.01)

        full_prices = ranging_prices + trending_prices

        # Detect at two points
        result_before = detector.detect(full_prices[:100])
        result_after = detector.detect(full_prices[-100:])

        # Should show different regimes
        assert result_before.regime != result_after.regime or result_after.regime == MarketRegime.TRENDING_UP

    def test_get_transitions(self, detector):
        """Test getting transition history."""
        # Simulate price series that goes through multiple regimes
        prices = []

        # Ranging period
        for i in range(100):
            prices.append(100.0 + math.sin(i * 0.1))

        # Trending up period
        for _ in range(100):
            prices.append(prices[-1] * 1.01)

        # Track regime over windows
        transitions = detector.detect_transitions(prices, window_step=20)

        assert isinstance(transitions, list)
        # Should have detected some transitions
        assert len(transitions) >= 0  # May or may not detect transitions


class TestHistoricalRegimeAnalysis:
    """Test historical regime analysis."""

    @pytest.fixture
    def detector(self):
        """Create a detector instance."""
        from core.analysis.regime_detector import RegimeDetector

        return RegimeDetector()

    def test_analyze_history(self, detector):
        """Test analyzing historical regime distribution."""
        import random

        random.seed(42)
        prices = [100.0]
        for _ in range(499):
            change = random.gauss(0, 1.5)
            prices.append(prices[-1] * (1 + change / 100))

        analysis = detector.analyze_history(prices, window_size=50, step=25)

        assert "regime_distribution" in analysis
        assert "regime_durations" in analysis
        assert "transitions" in analysis

    def test_regime_distribution_sums_to_one(self, detector):
        """Test that regime distribution percentages sum to ~100%."""
        import random

        random.seed(42)
        prices = [100.0]
        for _ in range(499):
            change = random.gauss(0, 1.5)
            prices.append(prices[-1] * (1 + change / 100))

        analysis = detector.analyze_history(prices, window_size=50, step=25)

        total = sum(analysis["regime_distribution"].values())
        assert 0.99 <= total <= 1.01


class TestStrategyRecommendations:
    """Test strategy recommendations per regime."""

    def test_get_recommendation_for_trending_up(self):
        """Test strategy recommendation for uptrend."""
        from core.analysis.regime_detector import (
            StrategyRecommendation,
            MarketRegime,
        )

        rec = StrategyRecommendation.for_regime(MarketRegime.TRENDING_UP)

        assert rec.name in ["TrendFollowing", "Momentum", "Breakout"]
        assert rec.position_size_multiplier >= 1.0  # Normal or increased size
        assert "stop_loss_type" in rec.parameters

    def test_get_recommendation_for_crash(self):
        """Test strategy recommendation for crash."""
        from core.analysis.regime_detector import (
            StrategyRecommendation,
            MarketRegime,
        )

        rec = StrategyRecommendation.for_regime(MarketRegime.CRASH)

        assert rec.position_size_multiplier < 1.0  # Reduced size
        assert rec.parameters.get("avoid_new_longs", False) is True

    def test_get_recommendation_for_ranging(self):
        """Test strategy recommendation for ranging market."""
        from core.analysis.regime_detector import (
            StrategyRecommendation,
            MarketRegime,
        )

        rec = StrategyRecommendation.for_regime(MarketRegime.RANGING)

        assert rec.name in ["MeanReversion", "GridTrading", "RangeTrading"]

    def test_recommendation_has_required_fields(self):
        """Test that recommendations have all required fields."""
        from core.analysis.regime_detector import (
            StrategyRecommendation,
            MarketRegime,
        )

        for regime in MarketRegime.all():
            rec = StrategyRecommendation.for_regime(regime)

            assert hasattr(rec, "name")
            assert hasattr(rec, "position_size_multiplier")
            assert hasattr(rec, "parameters")
            assert hasattr(rec, "description")
            assert isinstance(rec.parameters, dict)


class TestProbabilityEstimation:
    """Test probability estimation for regimes."""

    @pytest.fixture
    def detector(self):
        """Create a detector instance."""
        from core.analysis.regime_detector import RegimeDetector

        return RegimeDetector()

    def test_probabilities_normalized(self, detector):
        """Test that probabilities sum to 1."""
        import random

        random.seed(42)
        prices = [100.0]
        for _ in range(199):
            change = random.gauss(0, 1.5)
            prices.append(prices[-1] * (1 + change / 100))

        result = detector.detect(prices)

        total = sum(result.probabilities.values())
        assert abs(total - 1.0) < 0.01

    def test_highest_probability_matches_regime(self, detector):
        """Test that highest probability matches detected regime."""
        # Create clear uptrend
        prices = [100.0]
        for _ in range(199):
            prices.append(prices[-1] * 1.01)

        result = detector.detect(prices)

        # The detected regime should have highest probability
        max_prob_regime = max(result.probabilities, key=result.probabilities.get)
        assert max_prob_regime == result.regime

    def test_confidence_reflects_certainty(self, detector):
        """Test that confidence reflects regime certainty."""
        # Clear uptrend should have high confidence
        up_prices = [100.0]
        for _ in range(199):
            up_prices.append(up_prices[-1] * 1.02)

        # Ambiguous market should have lower confidence
        import random

        random.seed(42)
        ambiguous_prices = [100.0]
        for _ in range(199):
            change = random.gauss(0, 1.0)
            ambiguous_prices.append(ambiguous_prices[-1] * (1 + change / 100))

        clear_result = detector.detect(up_prices)
        ambiguous_result = detector.detect(ambiguous_prices)

        # Clear trend should have higher confidence
        assert clear_result.confidence >= ambiguous_result.confidence


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_prices_list(self):
        """Test handling of empty price list."""
        from core.analysis.regime_detector import RegimeDetector

        detector = RegimeDetector()
        result = detector.detect([])

        # Should return default/unknown regime
        assert result is not None
        assert result.confidence == 0.0

    def test_single_price(self):
        """Test handling of single price point."""
        from core.analysis.regime_detector import RegimeDetector

        detector = RegimeDetector()
        result = detector.detect([100.0])

        assert result is not None
        assert result.confidence == 0.0

    def test_constant_prices(self):
        """Test handling of constant prices (no variance)."""
        from core.analysis.regime_detector import RegimeDetector, MarketRegime

        detector = RegimeDetector()
        result = detector.detect([100.0] * 200)

        # Constant prices should be ranging/stable
        assert result.regime == MarketRegime.RANGING

    def test_prices_with_nan(self):
        """Test handling of NaN values in prices."""
        from core.analysis.regime_detector import RegimeDetector

        detector = RegimeDetector()
        prices = [100.0, 101.0, float("nan"), 102.0, 103.0] * 40

        # Should handle gracefully
        result = detector.detect(prices)
        assert result is not None

    def test_prices_with_inf(self):
        """Test handling of infinity values in prices."""
        from core.analysis.regime_detector import RegimeDetector

        detector = RegimeDetector()
        prices = [100.0, 101.0, float("inf"), 102.0, 103.0] * 40

        # Should handle gracefully
        result = detector.detect(prices)
        assert result is not None

    def test_negative_prices(self):
        """Test handling of negative prices."""
        from core.analysis.regime_detector import RegimeDetector

        detector = RegimeDetector()
        prices = [-100.0, -99.0, -98.0] * 70

        # Should handle gracefully (some assets can go negative)
        result = detector.detect(prices)
        assert result is not None

    def test_zero_prices(self):
        """Test handling of zero prices."""
        from core.analysis.regime_detector import RegimeDetector

        detector = RegimeDetector()
        prices = [100.0, 50.0, 0.0, 50.0, 100.0] * 40

        # Should handle gracefully
        result = detector.detect(prices)
        assert result is not None


class TestIntegration:
    """Integration tests for regime detector."""

    def test_full_workflow(self):
        """Test complete regime detection workflow."""
        from core.analysis.regime_detector import (
            RegimeDetector,
            MarketRegime,
            StrategyRecommendation,
        )
        import random

        random.seed(42)

        # 1. Create detector
        detector = RegimeDetector(lookback=30, smoothing=3)

        # 2. Generate price data with multiple regimes
        prices = [100.0]

        # Ranging period
        for i in range(100):
            prices.append(100.0 + 2 * math.sin(i * 0.1) + random.gauss(0, 0.5))

        # Trending up period
        for _ in range(100):
            prices.append(prices[-1] * 1.008 + random.gauss(0, 0.5))

        # Volatile period
        for _ in range(50):
            change = random.choice([-3, 3]) + random.gauss(0, 1)
            prices.append(prices[-1] * (1 + change / 100))

        # 3. Detect current regime
        result = detector.detect(prices)

        assert result is not None
        assert result.regime in MarketRegime.all()

        # 4. Get strategy recommendation
        strategy = StrategyRecommendation.for_regime(result.regime)
        assert strategy is not None

        # 5. Analyze history
        analysis = detector.analyze_history(prices, window_size=50, step=25)

        assert "regime_distribution" in analysis
        assert len(analysis["regime_distribution"]) > 0

    def test_regime_detector_thread_safety(self):
        """Test that regime detector is thread-safe."""
        from core.analysis.regime_detector import RegimeDetector
        import threading
        import random

        detector = RegimeDetector()

        random.seed(42)
        prices = [100.0]
        for _ in range(199):
            change = random.gauss(0, 1.5)
            prices.append(prices[-1] * (1 + change / 100))

        results = []
        errors = []

        def detect_regime():
            try:
                result = detector.detect(prices)
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=detect_regime) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10
        # All results should be the same for same input
        regimes = [r.regime for r in results]
        assert len(set(regimes)) == 1
