"""
Token Scorer Tests

Tests for the comprehensive token scoring system that:
- Calculates composite scores from multiple factors
- Tracks fundamental metrics (liquidity, volume, holder count)
- Evaluates technical metrics (momentum, volatility)
- Incorporates sentiment analysis
- Assesses risk levels
- Maintains score history
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
from pathlib import Path
import json


class TestTokenScorer:
    """Tests for the core token scoring functionality."""

    @pytest.fixture
    def scorer(self, tmp_path):
        """Create a token scorer instance."""
        from core.analysis.token_scorer import TokenScorer
        return TokenScorer(storage_path=tmp_path / "scorer_data.json")

    def test_initialization(self, tmp_path):
        """Test scorer initializes correctly with default weights."""
        from core.analysis.token_scorer import TokenScorer
        scorer = TokenScorer(storage_path=tmp_path / "scorer_data.json")
        assert scorer is not None
        assert scorer.weights is not None
        assert "fundamental" in scorer.weights
        assert "technical" in scorer.weights
        assert "sentiment" in scorer.weights
        assert "risk" in scorer.weights

    def test_score_token_returns_composite_score(self, scorer):
        """Test that scoring a token returns a score between 0-100."""
        token_data = {
            "address": "TokenABC123",
            "symbol": "TEST",
            "liquidity_usd": 100000,
            "volume_24h": 50000,
            "holder_count": 500,
            "price": 1.0,
            "price_change_24h": 5.0,
            "market_cap": 1000000,
        }

        result = scorer.score_token(token_data)

        assert "composite_score" in result
        assert 0 <= result["composite_score"] <= 100
        assert "token_address" in result
        assert result["token_address"] == "TokenABC123"

    def test_score_includes_factor_breakdown(self, scorer):
        """Test that score includes breakdown by factor category."""
        token_data = {
            "address": "TokenABC123",
            "symbol": "TEST",
            "liquidity_usd": 100000,
            "volume_24h": 50000,
            "holder_count": 500,
            "price": 1.0,
            "price_change_24h": 5.0,
        }

        result = scorer.score_token(token_data)

        assert "factor_scores" in result
        assert "fundamental" in result["factor_scores"]
        assert "technical" in result["factor_scores"]
        assert "sentiment" in result["factor_scores"]
        assert "risk" in result["factor_scores"]

    def test_high_liquidity_increases_score(self, scorer):
        """Test that higher liquidity leads to higher fundamental score."""
        low_liquidity = {
            "address": "TokenLowLiq",
            "symbol": "LOW",
            "liquidity_usd": 1000,
            "volume_24h": 500,
            "holder_count": 50,
            "price": 1.0,
            "price_change_24h": 0,
        }

        high_liquidity = {
            "address": "TokenHighLiq",
            "symbol": "HIGH",
            "liquidity_usd": 1000000,
            "volume_24h": 500000,
            "holder_count": 5000,
            "price": 1.0,
            "price_change_24h": 0,
        }

        low_result = scorer.score_token(low_liquidity)
        high_result = scorer.score_token(high_liquidity)

        assert high_result["factor_scores"]["fundamental"] > low_result["factor_scores"]["fundamental"]

    def test_high_volatility_reduces_risk_score(self, scorer):
        """Test that high volatility negatively impacts the risk score."""
        stable_token = {
            "address": "StableToken",
            "symbol": "STABLE",
            "liquidity_usd": 100000,
            "volume_24h": 50000,
            "holder_count": 500,
            "price": 1.0,
            "price_change_24h": 1.0,
            "volatility_24h": 5.0,  # Low volatility
        }

        volatile_token = {
            "address": "VolatileToken",
            "symbol": "VOL",
            "liquidity_usd": 100000,
            "volume_24h": 50000,
            "holder_count": 500,
            "price": 1.0,
            "price_change_24h": 50.0,
            "volatility_24h": 80.0,  # High volatility
        }

        stable_result = scorer.score_token(stable_token)
        volatile_result = scorer.score_token(volatile_token)

        # Higher risk penalty for volatile token
        assert stable_result["factor_scores"]["risk"] > volatile_result["factor_scores"]["risk"]

    def test_scoring_handles_missing_optional_data(self, scorer):
        """Test scoring works with minimal required data."""
        minimal_data = {
            "address": "MinimalToken",
            "symbol": "MIN",
            "price": 0.001,
        }

        result = scorer.score_token(minimal_data)

        assert "composite_score" in result
        assert 0 <= result["composite_score"] <= 100
        assert "data_completeness" in result
        assert result["data_completeness"] < 1.0  # Partial data

    def test_scoring_timestamp_included(self, scorer):
        """Test that scoring result includes timestamp."""
        token_data = {
            "address": "TokenABC123",
            "symbol": "TEST",
            "price": 1.0,
        }

        result = scorer.score_token(token_data)

        assert "scored_at" in result
        assert isinstance(result["scored_at"], str)


class TestFundamentalMetrics:
    """Tests for fundamental metric calculations."""

    @pytest.fixture
    def scorer(self, tmp_path):
        from core.analysis.token_scorer import TokenScorer
        return TokenScorer(storage_path=tmp_path / "scorer_data.json")

    def test_calculate_liquidity_score(self, scorer):
        """Test liquidity score calculation."""
        # Very low liquidity
        assert scorer.calculate_liquidity_score(100) < 20
        # Low liquidity
        assert scorer.calculate_liquidity_score(5000) < 40
        # Medium liquidity
        assert 40 <= scorer.calculate_liquidity_score(50000) <= 70
        # High liquidity
        assert scorer.calculate_liquidity_score(500000) > 70
        # Very high liquidity
        assert scorer.calculate_liquidity_score(5000000) > 85

    def test_calculate_volume_score(self, scorer):
        """Test volume score calculation."""
        # Low volume
        assert scorer.calculate_volume_score(1000) < 30
        # Medium volume
        assert 30 <= scorer.calculate_volume_score(50000) <= 70
        # High volume
        assert scorer.calculate_volume_score(500000) > 70

    def test_calculate_holder_score(self, scorer):
        """Test holder count score calculation."""
        # Very few holders (risky)
        assert scorer.calculate_holder_score(10) < 20
        # Few holders
        assert scorer.calculate_holder_score(50) < 40
        # Medium holder count
        assert 40 <= scorer.calculate_holder_score(500) <= 70
        # Many holders (distributed)
        assert scorer.calculate_holder_score(5000) > 70

    def test_calculate_volume_to_liquidity_ratio(self, scorer):
        """Test volume to liquidity ratio scoring."""
        # Healthy ratio (around 0.5-1.0 is good)
        healthy_score = scorer.calculate_volume_liquidity_ratio_score(50000, 100000)
        assert healthy_score > 60

        # Too low ratio (low activity)
        low_score = scorer.calculate_volume_liquidity_ratio_score(1000, 100000)
        assert low_score < healthy_score

        # Too high ratio (potential manipulation)
        high_score = scorer.calculate_volume_liquidity_ratio_score(500000, 10000)
        assert high_score < healthy_score


class TestTechnicalMetrics:
    """Tests for technical metric calculations."""

    @pytest.fixture
    def scorer(self, tmp_path):
        from core.analysis.token_scorer import TokenScorer
        return TokenScorer(storage_path=tmp_path / "scorer_data.json")

    def test_calculate_momentum_score_positive(self, scorer):
        """Test momentum scoring for positive price movement."""
        # Strong positive momentum
        score = scorer.calculate_momentum_score(price_change_24h=15.0)
        assert score > 60

        # Extreme positive (might be concerning)
        extreme_score = scorer.calculate_momentum_score(price_change_24h=100.0)
        # Extreme moves should be capped or reduced
        assert extreme_score <= score or extreme_score < 90

    def test_calculate_momentum_score_negative(self, scorer):
        """Test momentum scoring for negative price movement."""
        # Moderate decline
        score = scorer.calculate_momentum_score(price_change_24h=-10.0)
        assert score < 50

        # Severe decline
        severe_score = scorer.calculate_momentum_score(price_change_24h=-50.0)
        assert severe_score < score

    def test_calculate_volatility_score(self, scorer):
        """Test volatility scoring."""
        # Low volatility (stable - good)
        low_vol = scorer.calculate_volatility_score(volatility=5.0)
        assert low_vol > 70

        # Medium volatility
        med_vol = scorer.calculate_volatility_score(volatility=25.0)
        assert 40 <= med_vol <= 70

        # High volatility (risky)
        high_vol = scorer.calculate_volatility_score(volatility=80.0)
        assert high_vol < 40

    def test_calculate_trend_score(self, scorer):
        """Test trend calculation from price history."""
        # Uptrend
        uptrend_history = [1.0, 1.1, 1.2, 1.3, 1.4, 1.5]
        uptrend_score = scorer.calculate_trend_score(uptrend_history)
        assert uptrend_score > 60

        # Downtrend
        downtrend_history = [1.5, 1.4, 1.3, 1.2, 1.1, 1.0]
        downtrend_score = scorer.calculate_trend_score(downtrend_history)
        assert downtrend_score < 50

        # Sideways
        sideways_history = [1.0, 1.01, 0.99, 1.0, 1.01, 1.0]
        sideways_score = scorer.calculate_trend_score(sideways_history)
        assert 40 <= sideways_score <= 60


class TestSentimentMetrics:
    """Tests for sentiment metric calculations."""

    @pytest.fixture
    def scorer(self, tmp_path):
        from core.analysis.token_scorer import TokenScorer
        return TokenScorer(storage_path=tmp_path / "scorer_data.json")

    def test_calculate_sentiment_score_positive(self, scorer):
        """Test positive sentiment scoring."""
        sentiment_data = {
            "overall_sentiment": 0.8,  # Scale -1 to 1
            "social_mentions": 1000,
            "positive_mentions": 800,
            "negative_mentions": 100,
        }

        score = scorer.calculate_sentiment_score(sentiment_data)
        assert score > 70

    def test_calculate_sentiment_score_negative(self, scorer):
        """Test negative sentiment scoring."""
        sentiment_data = {
            "overall_sentiment": -0.6,
            "social_mentions": 1000,
            "positive_mentions": 100,
            "negative_mentions": 700,
        }

        score = scorer.calculate_sentiment_score(sentiment_data)
        assert score < 40

    def test_calculate_sentiment_score_neutral(self, scorer):
        """Test neutral sentiment scoring."""
        sentiment_data = {
            "overall_sentiment": 0.0,
            "social_mentions": 500,
            "positive_mentions": 200,
            "negative_mentions": 200,
        }

        score = scorer.calculate_sentiment_score(sentiment_data)
        assert 40 <= score <= 60

    def test_sentiment_with_no_data(self, scorer):
        """Test sentiment scoring with no social data."""
        sentiment_data = {}

        score = scorer.calculate_sentiment_score(sentiment_data)
        assert score == 50  # Neutral default


class TestRiskMetrics:
    """Tests for risk assessment calculations."""

    @pytest.fixture
    def scorer(self, tmp_path):
        from core.analysis.token_scorer import TokenScorer
        return TokenScorer(storage_path=tmp_path / "scorer_data.json")

    def test_calculate_concentration_risk(self, scorer):
        """Test holder concentration risk calculation."""
        # High concentration (top 10 holders own 80%)
        high_conc = scorer.calculate_concentration_risk(top_10_holder_pct=80.0)
        assert high_conc < 30  # High risk = low score

        # Medium concentration
        med_conc = scorer.calculate_concentration_risk(top_10_holder_pct=50.0)
        assert 30 <= med_conc <= 70

        # Low concentration (distributed)
        low_conc = scorer.calculate_concentration_risk(top_10_holder_pct=20.0)
        assert low_conc > 70

    def test_calculate_age_risk(self, scorer):
        """Test token age risk calculation."""
        # Very new token (risky)
        very_new = scorer.calculate_age_risk(days_since_creation=1)
        assert very_new < 30

        # New token
        new = scorer.calculate_age_risk(days_since_creation=7)
        assert new < 50

        # Established token
        established = scorer.calculate_age_risk(days_since_creation=90)
        assert established > 60

        # Old token
        old = scorer.calculate_age_risk(days_since_creation=365)
        assert old > 80

    def test_calculate_smart_contract_risk(self, scorer):
        """Test smart contract risk factors."""
        # Verified contract, no red flags
        safe = scorer.calculate_contract_risk(
            is_verified=True,
            is_renounced=True,
            has_honeypot_risk=False,
            has_hidden_owner=False,
        )
        assert safe > 80

        # Unverified contract
        unverified = scorer.calculate_contract_risk(
            is_verified=False,
            is_renounced=True,
            has_honeypot_risk=False,
            has_hidden_owner=False,
        )
        assert unverified < safe

        # Potential honeypot
        honeypot = scorer.calculate_contract_risk(
            is_verified=True,
            is_renounced=False,
            has_honeypot_risk=True,
            has_hidden_owner=False,
        )
        assert honeypot < 30

    def test_calculate_overall_risk_score(self, scorer):
        """Test overall risk score calculation."""
        risk_factors = {
            "concentration_risk": 50,
            "age_risk": 40,
            "contract_risk": 70,
            "volatility_risk": 60,
        }

        overall = scorer.calculate_overall_risk(risk_factors)
        assert 0 <= overall <= 100
        # Should be weighted average
        assert 40 <= overall <= 70


class TestCustomScoringModels:
    """Tests for custom scoring model support."""

    @pytest.fixture
    def scorer(self, tmp_path):
        from core.analysis.token_scorer import TokenScorer
        return TokenScorer(storage_path=tmp_path / "scorer_data.json")

    def test_custom_weight_configuration(self, tmp_path):
        """Test custom weight configuration."""
        from core.analysis.token_scorer import TokenScorer, ScoringWeights

        custom_weights = ScoringWeights(
            fundamental=0.5,
            technical=0.2,
            sentiment=0.1,
            risk=0.2,
        )

        scorer = TokenScorer(
            storage_path=tmp_path / "scorer_data.json",
            weights=custom_weights,
        )

        assert scorer.weights.fundamental == 0.5
        assert scorer.weights.technical == 0.2
        assert scorer.weights.sentiment == 0.1
        assert scorer.weights.risk == 0.2

    def test_weights_must_sum_to_one(self, tmp_path):
        """Test that weights validation enforces sum to 1.0."""
        from core.analysis.token_scorer import TokenScorer, ScoringWeights

        with pytest.raises(ValueError):
            ScoringWeights(
                fundamental=0.5,
                technical=0.5,
                sentiment=0.5,
                risk=0.5,
            )

    def test_register_custom_factor(self, scorer):
        """Test registering a custom scoring factor."""

        def custom_factor(token_data: dict) -> float:
            # Custom logic based on market cap to volume ratio
            mc = token_data.get("market_cap", 0)
            vol = token_data.get("volume_24h", 1)
            ratio = mc / vol if vol > 0 else 100
            # Healthy ratio between 10-50
            if 10 <= ratio <= 50:
                return 80
            return 40

        scorer.register_custom_factor(
            name="mc_vol_ratio",
            category="fundamental",
            weight=0.1,
            calculator=custom_factor,
        )

        token_data = {
            "address": "CustomToken",
            "symbol": "CUST",
            "market_cap": 1000000,
            "volume_24h": 50000,  # Ratio = 20, should score 80
            "price": 1.0,
        }

        result = scorer.score_token(token_data)
        assert "mc_vol_ratio" in result.get("custom_factors", {})

    def test_remove_custom_factor(self, scorer):
        """Test removing a custom scoring factor."""
        def dummy_factor(data: dict) -> float:
            return 50

        scorer.register_custom_factor(
            name="dummy",
            category="fundamental",
            weight=0.1,
            calculator=dummy_factor,
        )

        assert "dummy" in scorer.custom_factors

        scorer.remove_custom_factor("dummy")
        assert "dummy" not in scorer.custom_factors


class TestScoreHistoryTracking:
    """Tests for score history tracking."""

    @pytest.fixture
    def scorer(self, tmp_path):
        from core.analysis.token_scorer import TokenScorer
        return TokenScorer(storage_path=tmp_path / "scorer_data.json")

    def test_score_is_recorded_in_history(self, scorer):
        """Test that scores are recorded in history."""
        token_data = {
            "address": "HistoryToken",
            "symbol": "HIST",
            "price": 1.0,
        }

        scorer.score_token(token_data)
        scorer.score_token(token_data)  # Score again

        history = scorer.get_score_history("HistoryToken")

        assert len(history) == 2
        assert all("composite_score" in h for h in history)
        assert all("scored_at" in h for h in history)

    def test_get_score_history_empty(self, scorer):
        """Test getting history for unscored token."""
        history = scorer.get_score_history("UnknownToken")
        assert history == []

    def test_score_history_limit(self, scorer):
        """Test that history respects limit parameter."""
        token_data = {
            "address": "LimitToken",
            "symbol": "LIM",
            "price": 1.0,
        }

        # Score multiple times
        for _ in range(10):
            scorer.score_token(token_data)

        history = scorer.get_score_history("LimitToken", limit=5)
        assert len(history) == 5

    def test_score_change_calculation(self, scorer):
        """Test score change calculation between periods."""
        token_data_1 = {
            "address": "ChangeToken",
            "symbol": "CHG",
            "price": 1.0,
            "liquidity_usd": 10000,
        }

        token_data_2 = {
            "address": "ChangeToken",
            "symbol": "CHG",
            "price": 1.5,
            "liquidity_usd": 50000,  # Improved liquidity
        }

        scorer.score_token(token_data_1)
        result = scorer.score_token(token_data_2)

        assert "score_change" in result
        # Improved fundamentals should lead to positive change
        assert result["score_change"] != 0

    def test_get_score_trend(self, scorer):
        """Test score trend analysis."""
        # Simulate improving scores over time
        for i in range(5):
            token_data = {
                "address": "TrendToken",
                "symbol": "TRD",
                "price": 1.0,
                "liquidity_usd": 10000 * (i + 1),  # Increasing liquidity
            }
            scorer.score_token(token_data)

        trend = scorer.get_score_trend("TrendToken")

        assert "direction" in trend
        assert trend["direction"] in ["up", "down", "stable"]
        assert "average_change" in trend


class TestScorePersistence:
    """Tests for score data persistence."""

    def test_save_and_load_history(self, tmp_path):
        """Test saving and loading score history."""
        from core.analysis.token_scorer import TokenScorer

        scorer1 = TokenScorer(storage_path=tmp_path / "scorer_data.json")

        token_data = {
            "address": "PersistToken",
            "symbol": "PER",
            "price": 1.0,
            "liquidity_usd": 100000,
        }

        scorer1.score_token(token_data)
        scorer1.save()

        # Create new scorer instance
        scorer2 = TokenScorer(storage_path=tmp_path / "scorer_data.json")
        scorer2.load()

        history = scorer2.get_score_history("PersistToken")
        assert len(history) == 1

    def test_clear_history(self, tmp_path):
        """Test clearing score history."""
        from core.analysis.token_scorer import TokenScorer

        scorer = TokenScorer(storage_path=tmp_path / "scorer_data.json")

        token_data = {"address": "ClearToken", "symbol": "CLR", "price": 1.0}
        scorer.score_token(token_data)

        scorer.clear_history("ClearToken")

        history = scorer.get_score_history("ClearToken")
        assert len(history) == 0

    def test_clear_all_history(self, tmp_path):
        """Test clearing all score history."""
        from core.analysis.token_scorer import TokenScorer

        scorer = TokenScorer(storage_path=tmp_path / "scorer_data.json")

        for i in range(3):
            scorer.score_token({"address": f"Token{i}", "symbol": f"T{i}", "price": 1.0})

        scorer.clear_all_history()

        for i in range(3):
            assert scorer.get_score_history(f"Token{i}") == []


class TestBatchScoring:
    """Tests for batch token scoring."""

    @pytest.fixture
    def scorer(self, tmp_path):
        from core.analysis.token_scorer import TokenScorer
        return TokenScorer(storage_path=tmp_path / "scorer_data.json")

    def test_score_multiple_tokens(self, scorer):
        """Test scoring multiple tokens at once."""
        tokens = [
            {"address": "Token1", "symbol": "T1", "price": 1.0, "liquidity_usd": 100000},
            {"address": "Token2", "symbol": "T2", "price": 2.0, "liquidity_usd": 50000},
            {"address": "Token3", "symbol": "T3", "price": 0.5, "liquidity_usd": 200000},
        ]

        results = scorer.score_tokens(tokens)

        assert len(results) == 3
        assert all("composite_score" in r for r in results)
        assert results[0]["token_address"] == "Token1"

    def test_score_and_rank_tokens(self, scorer):
        """Test scoring and ranking tokens."""
        tokens = [
            {"address": "Low", "symbol": "LOW", "price": 1.0, "liquidity_usd": 1000},
            {"address": "High", "symbol": "HIGH", "price": 1.0, "liquidity_usd": 1000000},
            {"address": "Med", "symbol": "MED", "price": 1.0, "liquidity_usd": 100000},
        ]

        ranked = scorer.score_and_rank(tokens)

        assert len(ranked) == 3
        # Highest liquidity should rank first
        assert ranked[0]["token_address"] == "High"
        assert ranked[-1]["token_address"] == "Low"
        assert all("rank" in r for r in ranked)

    def test_filter_by_score_threshold(self, scorer):
        """Test filtering tokens by minimum score."""
        tokens = [
            {"address": "Good", "symbol": "GOOD", "price": 1.0, "liquidity_usd": 500000, "holder_count": 1000},
            {"address": "Bad", "symbol": "BAD", "price": 1.0, "liquidity_usd": 100, "holder_count": 5},
        ]

        # Score all tokens and filter
        results = scorer.score_tokens(tokens)
        filtered = scorer.filter_by_threshold(results, min_score=40)

        # Good token should pass, bad token should not
        assert any(r["token_address"] == "Good" for r in filtered)


class TestScoringModelPresets:
    """Tests for preset scoring models."""

    def test_conservative_model(self, tmp_path):
        """Test conservative scoring model (high risk weight)."""
        from core.analysis.token_scorer import TokenScorer, ScoringModelPreset

        scorer = TokenScorer(
            storage_path=tmp_path / "scorer_data.json",
            preset=ScoringModelPreset.CONSERVATIVE,
        )

        # Conservative should weight risk higher
        assert scorer.weights.risk >= 0.3

    def test_aggressive_model(self, tmp_path):
        """Test aggressive scoring model (low risk weight)."""
        from core.analysis.token_scorer import TokenScorer, ScoringModelPreset

        scorer = TokenScorer(
            storage_path=tmp_path / "scorer_data.json",
            preset=ScoringModelPreset.AGGRESSIVE,
        )

        # Aggressive should weight technical/momentum higher
        assert scorer.weights.technical >= 0.3

    def test_balanced_model(self, tmp_path):
        """Test balanced scoring model."""
        from core.analysis.token_scorer import TokenScorer, ScoringModelPreset

        scorer = TokenScorer(
            storage_path=tmp_path / "scorer_data.json",
            preset=ScoringModelPreset.BALANCED,
        )

        # Balanced should have roughly equal weights
        weights = [scorer.weights.fundamental, scorer.weights.technical,
                   scorer.weights.sentiment, scorer.weights.risk]
        assert max(weights) - min(weights) < 0.2


class TestScoreExplanation:
    """Tests for score explanation generation."""

    @pytest.fixture
    def scorer(self, tmp_path):
        from core.analysis.token_scorer import TokenScorer
        return TokenScorer(storage_path=tmp_path / "scorer_data.json")

    def test_generate_score_explanation(self, scorer):
        """Test generating human-readable score explanation."""
        token_data = {
            "address": "ExplainToken",
            "symbol": "EXP",
            "price": 1.0,
            "liquidity_usd": 100000,
            "volume_24h": 50000,
            "holder_count": 500,
        }

        result = scorer.score_token(token_data)
        explanation = scorer.explain_score(result)

        assert isinstance(explanation, str)
        assert len(explanation) > 50  # Should have meaningful content
        assert "liquidity" in explanation.lower() or "volume" in explanation.lower()

    def test_explain_high_score(self, scorer):
        """Test explanation for high-scoring token."""
        token_data = {
            "address": "HighScoreToken",
            "symbol": "HST",
            "price": 1.0,
            "liquidity_usd": 5000000,
            "volume_24h": 2000000,
            "holder_count": 10000,
        }

        result = scorer.score_token(token_data)
        explanation = scorer.explain_score(result)

        assert "strong" in explanation.lower() or "high" in explanation.lower() or "good" in explanation.lower()

    def test_explain_low_score(self, scorer):
        """Test explanation for low-scoring token."""
        token_data = {
            "address": "LowScoreToken",
            "symbol": "LST",
            "price": 0.00001,
            "liquidity_usd": 100,
            "volume_24h": 10,
            "holder_count": 5,
        }

        result = scorer.score_token(token_data)
        explanation = scorer.explain_score(result)

        assert "low" in explanation.lower() or "risk" in explanation.lower() or "caution" in explanation.lower()

    def test_get_score_factors_summary(self, scorer):
        """Test getting a structured summary of scoring factors."""
        token_data = {
            "address": "SummaryToken",
            "symbol": "SUM",
            "price": 1.0,
            "liquidity_usd": 100000,
        }

        result = scorer.score_token(token_data)
        summary = scorer.get_factors_summary(result)

        assert "strengths" in summary
        assert "weaknesses" in summary
        assert "recommendations" in summary
        assert isinstance(summary["strengths"], list)
        assert isinstance(summary["weaknesses"], list)
