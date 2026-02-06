"""
Tests for core.costs.calculator module.

Tests the CostCalculator class and model pricing.
"""

import pytest
from decimal import Decimal


class TestCostCalculator:
    """Test suite for CostCalculator class."""

    def test_calculator_initialization(self):
        """Test CostCalculator can be instantiated."""
        from core.costs.calculator import CostCalculator

        calc = CostCalculator()
        assert calc is not None

    def test_calculate_cost_grok3(self):
        """Test Grok 3 pricing: $0.001/1K tokens (both input and output)."""
        from core.costs.calculator import CostCalculator

        calc = CostCalculator()

        # 1000 input + 500 output = 1500 tokens
        # $0.001/1K * 1.5K = $0.0015
        cost = calc.calculate_cost(
            provider="grok",
            model="grok-3",
            input_tokens=1000,
            output_tokens=500
        )

        assert cost == pytest.approx(0.0015, rel=0.01)

    def test_calculate_cost_gpt4o(self):
        """Test GPT-4o pricing: $0.015/1K input, $0.06/1K output."""
        from core.costs.calculator import CostCalculator

        calc = CostCalculator()

        # 1000 input * $0.015/1K = $0.015
        # 500 output * $0.06/1K = $0.03
        # Total = $0.045
        cost = calc.calculate_cost(
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500
        )

        assert cost == pytest.approx(0.045, rel=0.01)

    def test_calculate_cost_opus(self):
        """Test Opus pricing: $0.015/1K input, $0.075/1K output."""
        from core.costs.calculator import CostCalculator

        calc = CostCalculator()

        # 1000 input * $0.015/1K = $0.015
        # 500 output * $0.075/1K = $0.0375
        # Total = $0.0525
        cost = calc.calculate_cost(
            provider="anthropic",
            model="claude-opus-4",
            input_tokens=1000,
            output_tokens=500
        )

        assert cost == pytest.approx(0.0525, rel=0.01)

    def test_calculate_cost_zero_tokens(self):
        """Test cost calculation with zero tokens."""
        from core.costs.calculator import CostCalculator

        calc = CostCalculator()

        cost = calc.calculate_cost(
            provider="openai",
            model="gpt-4o",
            input_tokens=0,
            output_tokens=0
        )

        assert cost == 0.0

    def test_calculate_cost_large_token_count(self):
        """Test cost calculation with large token counts."""
        from core.costs.calculator import CostCalculator

        calc = CostCalculator()

        # 1M input + 500K output for GPT-4o
        # 1M * $0.015/1K = $15
        # 500K * $0.06/1K = $30
        # Total = $45
        cost = calc.calculate_cost(
            provider="openai",
            model="gpt-4o",
            input_tokens=1_000_000,
            output_tokens=500_000
        )

        assert cost == pytest.approx(45.0, rel=0.01)

    def test_calculate_cost_unknown_provider_returns_zero(self):
        """Test unknown provider returns zero cost (safe default)."""
        from core.costs.calculator import CostCalculator

        calc = CostCalculator()

        cost = calc.calculate_cost(
            provider="unknown_provider",
            model="unknown_model",
            input_tokens=1000,
            output_tokens=500
        )

        # Should return 0 or raise? Design decision: return 0 for unknown
        assert cost == 0.0

    def test_get_pricing_returns_model_info(self):
        """Test get_pricing returns pricing info for a provider/model."""
        from core.costs.calculator import CostCalculator

        calc = CostCalculator()

        pricing = calc.get_pricing("openai", "gpt-4o")

        assert "input" in pricing
        assert "output" in pricing
        assert pricing["input"] == 0.015
        assert pricing["output"] == 0.06

    def test_list_supported_providers(self):
        """Test listing all supported providers."""
        from core.costs.calculator import CostCalculator

        calc = CostCalculator()

        providers = calc.list_providers()

        assert "grok" in providers
        assert "openai" in providers
        assert "anthropic" in providers

    def test_grok_mini_pricing(self):
        """Test grok-3-mini has lower pricing than grok-3."""
        from core.costs.calculator import CostCalculator

        calc = CostCalculator()

        # grok-3-mini should be cheaper
        cost_mini = calc.calculate_cost(
            provider="grok",
            model="grok-3-mini",
            input_tokens=1000,
            output_tokens=500
        )

        cost_full = calc.calculate_cost(
            provider="grok",
            model="grok-3",
            input_tokens=1000,
            output_tokens=500
        )

        # Mini should be same or less
        assert cost_mini <= cost_full


class TestModelPricing:
    """Test model pricing constants."""

    def test_grok3_pricing_constant(self):
        """Verify Grok 3 pricing: $0.001/1K tokens."""
        from core.costs.calculator import MODEL_PRICING

        assert "grok" in MODEL_PRICING
        assert "grok-3" in MODEL_PRICING["grok"]
        pricing = MODEL_PRICING["grok"]["grok-3"]

        # $0.001 per 1K = $1 per 1M
        assert pricing["input_per_1k"] == 0.001
        assert pricing["output_per_1k"] == 0.001

    def test_gpt4o_pricing_constant(self):
        """Verify GPT-4o pricing: $0.015/1K input, $0.06/1K output."""
        from core.costs.calculator import MODEL_PRICING

        assert "openai" in MODEL_PRICING
        assert "gpt-4o" in MODEL_PRICING["openai"]
        pricing = MODEL_PRICING["openai"]["gpt-4o"]

        assert pricing["input_per_1k"] == 0.015
        assert pricing["output_per_1k"] == 0.06

    def test_opus_pricing_constant(self):
        """Verify Opus pricing: $0.015/1K input, $0.075/1K output."""
        from core.costs.calculator import MODEL_PRICING

        assert "anthropic" in MODEL_PRICING
        # Allow for different model name variations
        opus_key = None
        for key in MODEL_PRICING["anthropic"]:
            if "opus" in key.lower():
                opus_key = key
                break

        assert opus_key is not None, "No Opus model found in pricing"
        pricing = MODEL_PRICING["anthropic"][opus_key]

        assert pricing["input_per_1k"] == 0.015
        assert pricing["output_per_1k"] == 0.075
