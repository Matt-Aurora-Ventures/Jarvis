"""
Tests for core/memory/summarizer.py - Conversation summarization.

Verifies:
- Summarizer class
- summarize_conversation functionality
- extract_key_points functionality
- LLM integration for summarization
- Fallback behavior

Coverage Target: 60%+ with ~30 tests
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock


# ==============================================================================
# Test Fixtures
# ==============================================================================

@pytest.fixture
def sample_messages():
    """Create sample messages for testing."""
    from core.memory.conversation import Message

    now = datetime.utcnow()
    return [
        Message(
            role="user",
            content="Hello, I want to buy some SOL tokens.",
            timestamp=now - timedelta(minutes=10)
        ),
        Message(
            role="assistant",
            content="I can help you with that. How much SOL would you like to purchase?",
            timestamp=now - timedelta(minutes=9)
        ),
        Message(
            role="user",
            content="I'd like to buy 5 SOL and set a take profit at 20%.",
            timestamp=now - timedelta(minutes=8)
        ),
        Message(
            role="assistant",
            content="Perfect. I'll place an order for 5 SOL with a 20% take profit.",
            timestamp=now - timedelta(minutes=7)
        ),
    ]


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = Mock()
    client.messages = Mock()
    client.messages.create = Mock()
    return client


# ==============================================================================
# Summarizer Initialization Tests
# ==============================================================================

class TestSummarizerInit:
    """Test Summarizer initialization."""

    def test_init_default(self):
        """Test default initialization."""
        from core.memory.summarizer import Summarizer

        summarizer = Summarizer()

        assert summarizer is not None

    def test_init_with_custom_model(self):
        """Test initialization with custom model."""
        from core.memory.summarizer import Summarizer

        summarizer = Summarizer(model="claude-3-haiku-20240307")

        assert summarizer.model == "claude-3-haiku-20240307"

    def test_init_with_max_tokens(self):
        """Test initialization with max tokens."""
        from core.memory.summarizer import Summarizer

        summarizer = Summarizer(max_tokens=500)

        assert summarizer.max_tokens == 500


# ==============================================================================
# Summarize Conversation Tests
# ==============================================================================

class TestSummarizeConversation:
    """Test summarize_conversation functionality."""

    def test_summarize_returns_string(self, sample_messages):
        """Test that summarize returns a string."""
        with patch('core.memory.summarizer.anthropic') as mock_anthropic:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.content = [Mock(text="User wants to buy 5 SOL with 20% TP.")]
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.Anthropic.return_value = mock_client

            from core.memory.summarizer import Summarizer

            summarizer = Summarizer()
            result = summarizer.summarize_conversation(sample_messages)

            assert isinstance(result, str)
            assert len(result) > 0

    def test_summarize_empty_list(self):
        """Test summarizing empty message list."""
        from core.memory.summarizer import Summarizer

        summarizer = Summarizer()
        result = summarizer.summarize_conversation([])

        assert result == ""

    def test_summarize_single_message(self):
        """Test summarizing single message."""
        from core.memory.summarizer import Summarizer
        from core.memory.conversation import Message

        with patch('core.memory.summarizer.anthropic') as mock_anthropic:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.content = [Mock(text="User greeted.")]
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.Anthropic.return_value = mock_client

            summarizer = Summarizer()
            messages = [Message(role="user", content="Hello")]
            result = summarizer.summarize_conversation(messages)

            assert isinstance(result, str)

    def test_summarize_calls_llm_with_correct_prompt(self, sample_messages):
        """Test that summarize calls LLM with correct prompt."""
        with patch('core.memory.summarizer.anthropic') as mock_anthropic:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.content = [Mock(text="Summary")]
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.Anthropic.return_value = mock_client

            from core.memory.summarizer import Summarizer

            summarizer = Summarizer()
            summarizer.summarize_conversation(sample_messages)

            # Verify LLM was called
            mock_client.messages.create.assert_called_once()
            call_args = mock_client.messages.create.call_args
            assert "messages" in call_args.kwargs

    def test_summarize_handles_llm_error(self, sample_messages):
        """Test that summarize handles LLM errors gracefully."""
        with patch('core.memory.summarizer.anthropic') as mock_anthropic:
            mock_client = Mock()
            mock_client.messages.create.side_effect = Exception("API Error")
            mock_anthropic.Anthropic.return_value = mock_client

            from core.memory.summarizer import Summarizer

            summarizer = Summarizer()
            result = summarizer.summarize_conversation(sample_messages)

            # Should return fallback summary
            assert "Error" in result or len(result) > 0

    def test_summarize_respects_max_tokens(self, sample_messages):
        """Test that summarize respects max_tokens setting."""
        with patch('core.memory.summarizer.anthropic') as mock_anthropic:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.content = [Mock(text="Summary")]
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.Anthropic.return_value = mock_client

            from core.memory.summarizer import Summarizer

            summarizer = Summarizer(max_tokens=100)
            summarizer.summarize_conversation(sample_messages)

            call_args = mock_client.messages.create.call_args
            assert call_args.kwargs["max_tokens"] == 100


# ==============================================================================
# Extract Key Points Tests
# ==============================================================================

class TestExtractKeyPoints:
    """Test extract_key_points functionality."""

    def test_extract_returns_list(self, sample_messages):
        """Test that extract_key_points returns a list."""
        with patch('core.memory.summarizer.anthropic') as mock_anthropic:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.content = [Mock(text="- User wants 5 SOL\n- 20% take profit")]
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.Anthropic.return_value = mock_client

            from core.memory.summarizer import Summarizer

            summarizer = Summarizer()
            result = summarizer.extract_key_points(sample_messages)

            assert isinstance(result, list)

    def test_extract_empty_list(self):
        """Test extracting key points from empty messages."""
        from core.memory.summarizer import Summarizer

        summarizer = Summarizer()
        result = summarizer.extract_key_points([])

        assert result == []

    def test_extract_parses_bullet_points(self, sample_messages):
        """Test that extract parses bullet points correctly."""
        with patch('core.memory.summarizer.anthropic') as mock_anthropic:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.content = [Mock(text="- Point 1\n- Point 2\n- Point 3")]
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.Anthropic.return_value = mock_client

            from core.memory.summarizer import Summarizer

            summarizer = Summarizer()
            result = summarizer.extract_key_points(sample_messages)

            assert len(result) == 3
            assert "Point 1" in result[0]

    def test_extract_handles_numbered_list(self, sample_messages):
        """Test that extract handles numbered lists."""
        with patch('core.memory.summarizer.anthropic') as mock_anthropic:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.content = [Mock(text="1. Point 1\n2. Point 2")]
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.Anthropic.return_value = mock_client

            from core.memory.summarizer import Summarizer

            summarizer = Summarizer()
            result = summarizer.extract_key_points(sample_messages)

            assert len(result) == 2

    def test_extract_handles_llm_error(self, sample_messages):
        """Test that extract handles LLM errors."""
        with patch('core.memory.summarizer.anthropic') as mock_anthropic:
            mock_client = Mock()
            mock_client.messages.create.side_effect = Exception("API Error")
            mock_anthropic.Anthropic.return_value = mock_client

            from core.memory.summarizer import Summarizer

            summarizer = Summarizer()
            result = summarizer.extract_key_points(sample_messages)

            # Should return empty list on error
            assert result == []


# ==============================================================================
# Fallback Summarization Tests
# ==============================================================================

class TestFallbackSummarization:
    """Test fallback summarization when LLM is unavailable."""

    def test_fallback_summarize_basic(self, sample_messages):
        """Test basic fallback summarization."""
        from core.memory.summarizer import Summarizer

        summarizer = Summarizer()
        result = summarizer._fallback_summarize(sample_messages)

        assert isinstance(result, str)
        assert "messages" in result.lower() or len(result) > 0

    def test_fallback_summarize_shows_message_count(self, sample_messages):
        """Test that fallback shows message count."""
        from core.memory.summarizer import Summarizer

        summarizer = Summarizer()
        result = summarizer._fallback_summarize(sample_messages)

        assert "4" in result  # 4 messages

    def test_fallback_summarize_empty_list(self):
        """Test fallback with empty list."""
        from core.memory.summarizer import Summarizer

        summarizer = Summarizer()
        result = summarizer._fallback_summarize([])

        assert result == "" or "no messages" in result.lower()


# ==============================================================================
# Factory Function Tests
# ==============================================================================

class TestFactoryFunctions:
    """Test summarizer factory functions."""

    def test_get_default_summarizer(self):
        """Test getting default summarizer."""
        from core.memory.summarizer import get_default_summarizer

        summarizer = get_default_summarizer()

        from core.memory.summarizer import Summarizer
        assert isinstance(summarizer, Summarizer)

    def test_get_default_summarizer_cached(self):
        """Test that default summarizer is cached."""
        from core.memory.summarizer import get_default_summarizer

        s1 = get_default_summarizer()
        s2 = get_default_summarizer()

        assert s1 is s2


# ==============================================================================
# Edge Cases Tests
# ==============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_long_conversation(self):
        """Test summarizing very long conversation."""
        from core.memory.conversation import Message
        from core.memory.summarizer import Summarizer

        # Create 100 messages
        messages = []
        for i in range(100):
            messages.append(Message(
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message number {i} with some content"
            ))

        with patch('core.memory.summarizer.anthropic') as mock_anthropic:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.content = [Mock(text="Long conversation summary")]
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.Anthropic.return_value = mock_client

            summarizer = Summarizer()
            result = summarizer.summarize_conversation(messages)

            assert isinstance(result, str)

    def test_messages_with_special_characters(self):
        """Test messages with special characters."""
        from core.memory.conversation import Message
        from core.memory.summarizer import Summarizer

        messages = [
            Message(role="user", content="Hello <script>alert('xss')</script>"),
            Message(role="assistant", content="I'll help with that & more"),
        ]

        with patch('core.memory.summarizer.anthropic') as mock_anthropic:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.content = [Mock(text="Summary")]
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.Anthropic.return_value = mock_client

            summarizer = Summarizer()
            result = summarizer.summarize_conversation(messages)

            assert isinstance(result, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
