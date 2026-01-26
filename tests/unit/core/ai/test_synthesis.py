"""
Tests for Debate Synthesis Logic

These tests verify:
1. Synthesis of opposing bull/bear viewpoints
2. Confidence score extraction
3. Recommendation generation
4. Weighted argument analysis
"""

import pytest
from unittest.mock import Mock, AsyncMock


class TestSynthesizer:
    """Test debate synthesis logic."""

    @pytest.mark.asyncio
    async def test_synthesize_requires_both_cases(self):
        """Synthesis should require both bull and bear cases."""
        from core.ai.synthesis import DebateSynthesizer

        synthesizer = DebateSynthesizer()

        with pytest.raises(ValueError, match="bull_case"):
            await synthesizer.synthesize(bull_case=None, bear_case="Risk present")

        with pytest.raises(ValueError, match="bear_case"):
            await synthesizer.synthesize(bull_case="Good momentum", bear_case=None)

    @pytest.mark.asyncio
    async def test_synthesize_produces_recommendation(self):
        """Synthesis should produce BUY, SELL, or HOLD recommendation."""
        from core.ai.synthesis import DebateSynthesizer

        mock_client = AsyncMock()
        mock_client.generate.return_value = {
            "content": "After weighing both perspectives, I recommend BUY "
                      "with 75% confidence due to strong momentum outweighing risks.",
            "tokens_used": 100,
        }

        synthesizer = DebateSynthesizer(client=mock_client)

        result = await synthesizer.synthesize(
            bull_case="Strong momentum, volume surge, breakout pattern",
            bear_case="Overbought RSI, resistance ahead"
        )

        assert result.recommendation in ["BUY", "SELL", "HOLD"]

    @pytest.mark.asyncio
    async def test_synthesize_extracts_confidence(self):
        """Synthesis should extract confidence score."""
        from core.ai.synthesis import DebateSynthesizer

        mock_client = AsyncMock()
        mock_client.generate.return_value = {
            "content": "RECOMMENDATION: BUY\nCONFIDENCE: 78%\n"
                      "The bull case is stronger due to volume confirmation.",
            "tokens_used": 80,
        }

        synthesizer = DebateSynthesizer(client=mock_client)

        result = await synthesizer.synthesize(
            bull_case="Volume confirming breakout",
            bear_case="Potential false breakout"
        )

        assert 70 <= result.confidence <= 85  # Around 78

    @pytest.mark.asyncio
    async def test_synthesize_includes_reasoning(self):
        """Synthesis should include reasoning explanation."""
        from core.ai.synthesis import DebateSynthesizer

        mock_client = AsyncMock()
        mock_client.generate.return_value = {
            "content": "RECOMMENDATION: HOLD\nCONFIDENCE: 55%\n"
                      "REASONING: Arguments are evenly balanced. "
                      "Bull momentum valid but bear risk concerns warrant caution.",
            "tokens_used": 120,
        }

        synthesizer = DebateSynthesizer(client=mock_client)

        result = await synthesizer.synthesize(
            bull_case="Momentum",
            bear_case="Risk"
        )

        assert result.reasoning is not None
        assert len(result.reasoning) > 20


class TestSynthesisResult:
    """Test synthesis result data structure."""

    def test_synthesis_result_fields(self):
        """SynthesisResult should have all required fields."""
        from core.ai.synthesis import SynthesisResult

        result = SynthesisResult(
            recommendation="BUY",
            confidence=75.0,
            reasoning="Bull case stronger",
            key_factors=["momentum", "volume"],
            risk_assessment="moderate",
        )

        assert result.recommendation == "BUY"
        assert result.confidence == 75.0
        assert result.reasoning == "Bull case stronger"
        assert "momentum" in result.key_factors

    def test_synthesis_result_to_dict(self):
        """SynthesisResult should serialize to dict."""
        from core.ai.synthesis import SynthesisResult

        result = SynthesisResult(
            recommendation="SELL",
            confidence=65.0,
            reasoning="Bear concerns outweigh bull",
            key_factors=["overbought"],
        )

        data = result.to_dict()

        assert data["recommendation"] == "SELL"
        assert data["confidence"] == 65.0
        assert "key_factors" in data


class TestConfidenceExtraction:
    """Test confidence score extraction from AI responses."""

    def test_extract_percentage_format(self):
        """Should extract confidence from '75%' format."""
        from core.ai.synthesis import extract_confidence

        text = "Based on analysis, confidence is 75%"
        confidence = extract_confidence(text)

        assert 70 <= confidence <= 80

    def test_extract_decimal_format(self):
        """Should extract confidence from '0.75' format."""
        from core.ai.synthesis import extract_confidence

        text = "Confidence score: 0.82"
        confidence = extract_confidence(text)

        assert 80 <= confidence <= 85

    def test_extract_labeled_confidence(self):
        """Should extract from 'CONFIDENCE: X' format."""
        from core.ai.synthesis import extract_confidence

        text = """
        RECOMMENDATION: BUY
        CONFIDENCE: 68
        REASONING: Good entry point
        """
        confidence = extract_confidence(text)

        assert 65 <= confidence <= 70

    def test_default_confidence_if_not_found(self):
        """Should return default 50 if confidence not found."""
        from core.ai.synthesis import extract_confidence

        text = "I think we should buy but I'm not sure."
        confidence = extract_confidence(text)

        assert confidence == 50.0


class TestRecommendationExtraction:
    """Test recommendation extraction from AI responses."""

    def test_extract_buy_recommendation(self):
        """Should extract BUY recommendation."""
        from core.ai.synthesis import extract_recommendation

        text = "After analysis, RECOMMENDATION: BUY with 75% confidence"
        rec = extract_recommendation(text)

        assert rec == "BUY"

    def test_extract_sell_recommendation(self):
        """Should extract SELL recommendation."""
        from core.ai.synthesis import extract_recommendation

        text = "We should SELL due to overbought conditions"
        rec = extract_recommendation(text)

        assert rec == "SELL"

    def test_extract_hold_recommendation(self):
        """Should extract HOLD recommendation."""
        from core.ai.synthesis import extract_recommendation

        text = "Uncertain market, recommend HOLD for now"
        rec = extract_recommendation(text)

        assert rec == "HOLD"

    def test_default_to_hold_if_unclear(self):
        """Should default to HOLD if recommendation unclear."""
        from core.ai.synthesis import extract_recommendation

        text = "The market is interesting today"
        rec = extract_recommendation(text)

        assert rec == "HOLD"


class TestWeightedSynthesis:
    """Test weighted argument synthesis."""

    @pytest.mark.asyncio
    async def test_weights_by_evidence_strength(self):
        """Synthesis should weight arguments by evidence quality."""
        from core.ai.synthesis import DebateSynthesizer

        mock_client = AsyncMock()
        mock_client.generate.return_value = {
            "content": "RECOMMENDATION: BUY\nCONFIDENCE: 80%",
            "tokens_used": 50,
        }

        synthesizer = DebateSynthesizer(client=mock_client)

        # Bull case with strong evidence
        bull_case = """
        Evidence: Volume 3x average, price at key support,
        RSI oversold at 28, multiple timeframe confirmation.
        """

        # Bear case with weak evidence
        bear_case = """
        Concern: Market might go down. General uncertainty.
        """

        result = await synthesizer.synthesize(
            bull_case=bull_case,
            bear_case=bear_case,
            weight_by_evidence=True
        )

        # Strong bull evidence should lead to BUY
        assert result.recommendation == "BUY"

    @pytest.mark.asyncio
    async def test_synthesis_with_market_context(self):
        """Synthesis should consider broader market context."""
        from core.ai.synthesis import DebateSynthesizer

        mock_client = AsyncMock()
        mock_client.generate.return_value = {
            "content": "RECOMMENDATION: HOLD\nCONFIDENCE: 60%\n"
                      "Despite bullish signals, bearish market regime suggests caution.",
            "tokens_used": 80,
        }

        synthesizer = DebateSynthesizer(client=mock_client)

        result = await synthesizer.synthesize(
            bull_case="Strong token momentum",
            bear_case="General market weakness",
            market_context={"regime": "bearish", "btc_trend": "down"}
        )

        # Should be more cautious in bearish market
        assert result.recommendation in ["HOLD", "SELL"]


class TestSynthesisPromptConstruction:
    """Test synthesis prompt construction."""

    def test_synthesis_prompt_includes_both_cases(self):
        """Synthesis prompt should include both bull and bear cases."""
        from core.ai.synthesis import build_synthesis_prompt

        prompt = build_synthesis_prompt(
            bull_case="Strong momentum play",
            bear_case="Overbought risk",
            signal={"direction": "BUY", "confidence": 70}
        )

        assert "Strong momentum" in prompt
        assert "Overbought" in prompt
        assert "BUY" in prompt or "buy" in prompt.lower()

    def test_synthesis_prompt_requests_structured_output(self):
        """Prompt should request structured recommendation format."""
        from core.ai.synthesis import build_synthesis_prompt

        prompt = build_synthesis_prompt(
            bull_case="Bull",
            bear_case="Bear",
            signal={}
        )

        assert "RECOMMENDATION" in prompt or "recommendation" in prompt.lower()
        assert "CONFIDENCE" in prompt or "confidence" in prompt.lower()
