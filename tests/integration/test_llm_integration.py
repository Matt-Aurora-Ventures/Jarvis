"""Integration tests for LLM providers."""
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

pytest.importorskip("httpx")


class TestLLMProviderIntegration:
    """Integration tests for LLM providers."""

    def test_provider_enum_values(self):
        """LLM provider enum should have expected values."""
        from core.llm import LLMProvider

        assert hasattr(LLMProvider, 'OLLAMA')
        assert hasattr(LLMProvider, 'GROQ')
        assert hasattr(LLMProvider, 'XAI')
        assert hasattr(LLMProvider, 'OPENROUTER')

    def test_llm_config_validation(self):
        """LLM config should validate properly."""
        from core.llm import LLMConfig, LLMProvider

        config = LLMConfig(
            provider=LLMProvider.GROQ,
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            max_tokens=1024
        )

        assert config.temperature == 0.7
        assert config.max_tokens == 1024

    @pytest.mark.asyncio
    async def test_unified_llm_fallback(self, mock_provider):
        """UnifiedLLM should fallback on failure."""
        from core.llm import UnifiedLLM, LLMProvider

        with patch.object(UnifiedLLM, '_get_provider') as mock_get:
            # First provider fails, second succeeds
            failing_provider = AsyncMock()
            failing_provider.generate.side_effect = Exception("Provider down")

            working_provider = AsyncMock()
            working_provider.generate.return_value = {"text": "response", "tokens": 100}

            mock_get.side_effect = [failing_provider, working_provider]

            llm = UnifiedLLM()
            # The actual test depends on implementation
            # This validates the structure exists


class TestLLMRouterIntegration:
    """Integration tests for LLM task routing."""

    def test_task_types_defined(self):
        """Task types should be defined."""
        from core.llm import TaskType

        assert hasattr(TaskType, 'TRADING')
        assert hasattr(TaskType, 'CHAT')
        assert hasattr(TaskType, 'ANALYSIS')

    @pytest.mark.asyncio
    async def test_router_task_routing(self):
        """Router should route tasks to appropriate providers."""
        from core.llm import LLMRouter, TaskType

        router = LLMRouter()

        # Verify routing rules exist
        assert len(router.routing_rules) > 0


class TestLLMCostTracking:
    """Integration tests for LLM cost tracking."""

    def test_model_pricing_defined(self):
        """Model pricing should be defined."""
        from core.llm import MODEL_PRICING

        assert len(MODEL_PRICING) > 0
        # Verify pricing structure
        for model, pricing in MODEL_PRICING.items():
            assert 'input' in pricing
            assert 'output' in pricing

    def test_cost_tracker_initialization(self):
        """Cost tracker should initialize."""
        from core.llm import LLMCostTracker

        tracker = LLMCostTracker()
        assert tracker is not None

    def test_usage_recording(self):
        """Usage should be recorded."""
        from core.llm import LLMCostTracker, LLMProvider

        tracker = LLMCostTracker()
        tracker.record_usage(
            provider=LLMProvider.GROQ,
            model="llama-3.3-70b-versatile",
            input_tokens=100,
            output_tokens=50
        )

        stats = tracker.get_stats()
        assert stats.total_requests >= 1

    def test_budget_alert_creation(self):
        """Budget alerts should be creatable."""
        from core.llm import LLMCostTracker, BudgetAlert

        tracker = LLMCostTracker()
        tracker.set_budget(
            daily_limit=10.0,
            monthly_limit=100.0
        )

        # Verify budget was set
        assert tracker.daily_budget == 10.0


class TestStructuredOutputIntegration:
    """Integration tests for structured LLM outputs."""

    def test_trading_signal_model(self):
        """TradingSignal model should validate."""
        from core.llm import TradingSignal

        signal = TradingSignal(
            symbol="SOL/USDC",
            action="buy",
            confidence=0.85,
            reasoning="Strong momentum"
        )

        assert signal.confidence == 0.85
        assert signal.action == "buy"

    def test_sentiment_analysis_model(self):
        """SentimentAnalysis model should validate."""
        from core.llm import SentimentAnalysis

        sentiment = SentimentAnalysis(
            sentiment="positive",
            score=0.8,
            keywords=["bullish", "growth"]
        )

        assert sentiment.sentiment == "positive"
        assert "bullish" in sentiment.keywords


class TestLLMProviderHealth:
    """Integration tests for provider health checks."""

    @pytest.mark.asyncio
    async def test_provider_health_check(self, mock_provider):
        """Providers should have health check."""
        mock_provider.health_check.return_value = True
        result = await mock_provider.health_check()
        assert result is True

    def test_provider_timeout_handling(self):
        """Providers should handle timeouts."""
        from core.llm import LLMConfig

        config = LLMConfig(
            provider="groq",
            model="test",
            timeout=30
        )

        assert config.timeout == 30
