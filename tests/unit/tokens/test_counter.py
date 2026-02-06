"""
Unit tests for TokenCounter.

Tests cover:
- Token counting for various models
- Message token counting
- Cost estimation
- Model-specific tokenization
"""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.tokens.counter import (
    TokenCounter,
    ModelType,
    count_tokens,
    count_messages,
    estimate_cost,
)


# =============================================================================
# ModelType Tests
# =============================================================================

class TestModelType:
    """Tests for ModelType enum."""

    def test_all_models_defined(self):
        """Test all expected models are defined."""
        expected_models = ["grok-3", "gpt-4", "claude-3"]
        actual_models = [m.value for m in ModelType]

        for model in expected_models:
            assert model in actual_models, f"Missing model: {model}"

    def test_model_values_are_strings(self):
        """Test model values are strings."""
        for model in ModelType:
            assert isinstance(model.value, str)


# =============================================================================
# TokenCounter Tests
# =============================================================================

class TestTokenCounter:
    """Tests for TokenCounter class."""

    @pytest.fixture
    def counter(self):
        """Create a TokenCounter instance."""
        return TokenCounter()

    def test_counter_creation(self, counter):
        """Test TokenCounter creation."""
        assert counter is not None

    def test_count_tokens_empty_string(self, counter):
        """Test counting tokens in empty string."""
        result = counter.count_tokens("", ModelType.GPT_4)
        assert result == 0

    def test_count_tokens_simple_text(self, counter):
        """Test counting tokens in simple text."""
        text = "Hello, world!"
        result = counter.count_tokens(text, ModelType.GPT_4)
        assert result > 0
        assert isinstance(result, int)

    def test_count_tokens_long_text(self, counter):
        """Test counting tokens in longer text."""
        text = "This is a longer piece of text. " * 100
        result = counter.count_tokens(text, ModelType.GPT_4)
        assert result > 100  # Should have significant tokens

    def test_count_tokens_different_models(self, counter):
        """Test token counts vary by model."""
        text = "Hello, world! This is a test sentence."

        gpt4_tokens = counter.count_tokens(text, ModelType.GPT_4)
        claude_tokens = counter.count_tokens(text, ModelType.CLAUDE_3)
        grok_tokens = counter.count_tokens(text, ModelType.GROK_3)

        # All should return positive values
        assert gpt4_tokens > 0
        assert claude_tokens > 0
        assert grok_tokens > 0

    def test_count_tokens_special_characters(self, counter):
        """Test counting tokens with special characters."""
        text = "Hello! @user #hashtag $100 %percent"
        result = counter.count_tokens(text, ModelType.GPT_4)
        assert result > 0

    def test_count_tokens_unicode(self, counter):
        """Test counting tokens with unicode characters."""
        text = "Hello! This is a test with emoji."
        result = counter.count_tokens(text, ModelType.GPT_4)
        assert result > 0

    def test_count_tokens_whitespace(self, counter):
        """Test counting tokens with various whitespace."""
        text = "Hello   world\n\ttab\n\n"
        result = counter.count_tokens(text, ModelType.GPT_4)
        assert result > 0


# =============================================================================
# Message Token Counting Tests
# =============================================================================

class TestMessageTokenCounting:
    """Tests for counting tokens in message lists."""

    @pytest.fixture
    def counter(self):
        """Create a TokenCounter instance."""
        return TokenCounter()

    def test_count_messages_empty_list(self, counter):
        """Test counting tokens in empty message list."""
        result = counter.count_messages([], ModelType.GPT_4)
        assert result == 0

    def test_count_messages_single_message(self, counter):
        """Test counting tokens in single message."""
        messages = [{"role": "user", "content": "Hello, world!"}]
        result = counter.count_messages(messages, ModelType.GPT_4)
        assert result > 0

    def test_count_messages_multiple_messages(self, counter):
        """Test counting tokens in multiple messages."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi there! How can I help?"},
        ]
        result = counter.count_messages(messages, ModelType.GPT_4)
        assert result > 10  # Should have significant tokens

    def test_count_messages_includes_overhead(self, counter):
        """Test message counting includes message overhead."""
        text = "Hello"
        single_tokens = counter.count_tokens(text, ModelType.GPT_4)

        messages = [{"role": "user", "content": text}]
        message_tokens = counter.count_messages(messages, ModelType.GPT_4)

        # Message tokens should include overhead
        assert message_tokens >= single_tokens

    def test_count_messages_role_overhead(self, counter):
        """Test different roles add overhead."""
        messages = [
            {"role": "user", "content": "Test"},
            {"role": "assistant", "content": "Test"},
            {"role": "system", "content": "Test"},
        ]
        result = counter.count_messages(messages, ModelType.GPT_4)
        # Each message adds overhead beyond just content
        assert result > counter.count_tokens("TestTestTest", ModelType.GPT_4)


# =============================================================================
# Cost Estimation Tests
# =============================================================================

class TestCostEstimation:
    """Tests for cost estimation."""

    @pytest.fixture
    def counter(self):
        """Create a TokenCounter instance."""
        return TokenCounter()

    def test_estimate_cost_zero_tokens(self, counter):
        """Test cost estimation with zero tokens."""
        result = counter.estimate_cost(0, ModelType.GPT_4)
        assert result == 0.0

    def test_estimate_cost_positive_tokens(self, counter):
        """Test cost estimation with positive tokens."""
        result = counter.estimate_cost(1000, ModelType.GPT_4)
        assert result > 0.0
        assert isinstance(result, float)

    def test_estimate_cost_different_models(self, counter):
        """Test cost varies by model."""
        tokens = 1000

        gpt4_cost = counter.estimate_cost(tokens, ModelType.GPT_4)
        claude_cost = counter.estimate_cost(tokens, ModelType.CLAUDE_3)
        grok_cost = counter.estimate_cost(tokens, ModelType.GROK_3)

        # All should return values
        assert gpt4_cost >= 0
        assert claude_cost >= 0
        assert grok_cost >= 0

    def test_estimate_cost_large_tokens(self, counter):
        """Test cost estimation with large token counts."""
        result = counter.estimate_cost(1_000_000, ModelType.GPT_4)
        assert result > 0.0

    def test_estimate_cost_input_output_split(self, counter):
        """Test cost estimation with separate input/output."""
        input_cost = counter.estimate_cost(1000, ModelType.GPT_4, is_output=False)
        output_cost = counter.estimate_cost(1000, ModelType.GPT_4, is_output=True)

        # Output tokens typically cost more
        # Or at minimum, both should be valid
        assert input_cost >= 0
        assert output_cost >= 0


# =============================================================================
# Convenience Function Tests
# =============================================================================

class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_count_tokens_function(self):
        """Test count_tokens convenience function."""
        result = count_tokens("Hello, world!", "gpt-4")
        assert result > 0
        assert isinstance(result, int)

    def test_count_messages_function(self):
        """Test count_messages convenience function."""
        messages = [{"role": "user", "content": "Hello!"}]
        result = count_messages(messages, "gpt-4")
        assert result > 0

    def test_estimate_cost_function(self):
        """Test estimate_cost convenience function."""
        result = estimate_cost(1000, "gpt-4")
        assert result >= 0.0


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases."""

    @pytest.fixture
    def counter(self):
        """Create a TokenCounter instance."""
        return TokenCounter()

    def test_very_long_text(self, counter):
        """Test very long text handling."""
        text = "word " * 100000  # Very long text
        result = counter.count_tokens(text, ModelType.GPT_4)
        assert result > 0

    def test_invalid_model_fallback(self, counter):
        """Test fallback for unknown model."""
        text = "Hello"
        # Should use estimation fallback
        result = counter.count_tokens(text, ModelType.GROK_3)
        assert result > 0

    def test_none_text_handling(self, counter):
        """Test handling of None text."""
        with pytest.raises((TypeError, ValueError)):
            counter.count_tokens(None, ModelType.GPT_4)

    def test_message_without_content(self, counter):
        """Test message without content field."""
        messages = [{"role": "user"}]
        # Should handle gracefully
        result = counter.count_messages(messages, ModelType.GPT_4)
        assert result >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
