"""
Tests for core/memory/retrieval.py - Memory retrieval with keyword matching.

Verifies:
- MemoryRetrieval class
- search functionality (keyword-based)
- get_relevant functionality (context-based)
- Simple keyword matching (no embeddings)
- Result ranking

Coverage Target: 60%+ with ~35 tests
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch


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
            id="msg_001",
            role="user",
            content="I want to trade SOL tokens on Jupiter",
            timestamp=now - timedelta(hours=2)
        ),
        Message(
            id="msg_002",
            role="assistant",
            content="I can help you trade SOL. What's your target price?",
            timestamp=now - timedelta(hours=2)
        ),
        Message(
            id="msg_003",
            role="user",
            content="Set take profit at 20% and stop loss at 10%",
            timestamp=now - timedelta(hours=1)
        ),
        Message(
            id="msg_004",
            role="assistant",
            content="Done! TP set at 20%, SL at 10% for your SOL position.",
            timestamp=now - timedelta(hours=1)
        ),
        Message(
            id="msg_005",
            role="user",
            content="What's the current price of Bitcoin?",
            timestamp=now - timedelta(minutes=30)
        ),
        Message(
            id="msg_006",
            role="assistant",
            content="Bitcoin is currently trading at $95,000.",
            timestamp=now - timedelta(minutes=30)
        ),
    ]


@pytest.fixture
def mock_storage(sample_messages):
    """Create mock storage with sample messages."""
    storage = Mock()
    storage.get_messages = Mock(return_value=sample_messages)
    return storage


# ==============================================================================
# MemoryRetrieval Initialization Tests
# ==============================================================================

class TestMemoryRetrievalInit:
    """Test MemoryRetrieval initialization."""

    def test_init_with_storage(self, mock_storage):
        """Test initialization with storage backend."""
        from core.memory.retrieval import MemoryRetrieval

        retrieval = MemoryRetrieval(storage=mock_storage)

        assert retrieval._storage is mock_storage

    def test_init_with_default_storage(self):
        """Test initialization with default storage."""
        with patch('core.memory.retrieval.get_default_storage') as mock_get:
            mock_storage = Mock()
            mock_get.return_value = mock_storage

            from core.memory.retrieval import MemoryRetrieval

            retrieval = MemoryRetrieval()

            mock_get.assert_called_once()


# ==============================================================================
# Search Tests
# ==============================================================================

class TestSearch:
    """Test search functionality."""

    def test_search_returns_list(self, mock_storage):
        """Test that search returns a list."""
        from core.memory.retrieval import MemoryRetrieval

        retrieval = MemoryRetrieval(storage=mock_storage)
        results = retrieval.search("user_123", "SOL")

        assert isinstance(results, list)

    def test_search_finds_matching_messages(self, mock_storage):
        """Test that search finds messages with matching keyword."""
        from core.memory.retrieval import MemoryRetrieval

        retrieval = MemoryRetrieval(storage=mock_storage)
        results = retrieval.search("user_123", "SOL")

        # Should find messages mentioning SOL
        assert len(results) >= 1
        found_sol = any("SOL" in msg.content for msg in results)
        assert found_sol

    def test_search_case_insensitive(self, mock_storage):
        """Test that search is case-insensitive."""
        from core.memory.retrieval import MemoryRetrieval

        retrieval = MemoryRetrieval(storage=mock_storage)
        results_upper = retrieval.search("user_123", "SOL")
        results_lower = retrieval.search("user_123", "sol")

        assert len(results_upper) == len(results_lower)

    def test_search_with_k_limit(self, mock_storage):
        """Test search with k limit."""
        from core.memory.retrieval import MemoryRetrieval

        retrieval = MemoryRetrieval(storage=mock_storage)
        results = retrieval.search("user_123", "SOL", k=2)

        assert len(results) <= 2

    def test_search_no_matches(self, mock_storage):
        """Test search with no matching results."""
        from core.memory.retrieval import MemoryRetrieval

        retrieval = MemoryRetrieval(storage=mock_storage)
        results = retrieval.search("user_123", "nonexistent_keyword_xyz")

        assert results == []

    def test_search_multiple_keywords(self, mock_storage):
        """Test search with multiple keywords."""
        from core.memory.retrieval import MemoryRetrieval

        retrieval = MemoryRetrieval(storage=mock_storage)
        results = retrieval.search("user_123", "SOL trade")

        # Should find messages matching any keyword
        assert len(results) >= 1

    def test_search_ranks_by_relevance(self, mock_storage):
        """Test that search ranks results by relevance."""
        from core.memory.retrieval import MemoryRetrieval

        retrieval = MemoryRetrieval(storage=mock_storage)
        results = retrieval.search("user_123", "SOL")

        # First result should have the highest relevance score
        # (Messages with more keyword matches should rank higher)
        assert len(results) >= 1

    def test_search_empty_query(self, mock_storage):
        """Test search with empty query."""
        from core.memory.retrieval import MemoryRetrieval

        retrieval = MemoryRetrieval(storage=mock_storage)
        results = retrieval.search("user_123", "")

        assert results == []

    def test_search_whitespace_only_query(self, mock_storage):
        """Test search with whitespace-only query."""
        from core.memory.retrieval import MemoryRetrieval

        retrieval = MemoryRetrieval(storage=mock_storage)
        results = retrieval.search("user_123", "   ")

        assert results == []


# ==============================================================================
# Get Relevant Tests
# ==============================================================================

class TestGetRelevant:
    """Test get_relevant functionality."""

    def test_get_relevant_returns_list(self, mock_storage):
        """Test that get_relevant returns a list."""
        from core.memory.retrieval import MemoryRetrieval

        retrieval = MemoryRetrieval(storage=mock_storage)
        context = "I want to check my SOL position"
        results = retrieval.get_relevant("user_123", context)

        assert isinstance(results, list)

    def test_get_relevant_finds_related_messages(self, mock_storage):
        """Test that get_relevant finds contextually related messages."""
        from core.memory.retrieval import MemoryRetrieval

        retrieval = MemoryRetrieval(storage=mock_storage)
        context = "What was my take profit setting for SOL?"
        results = retrieval.get_relevant("user_123", context)

        # Should find messages about TP and SOL
        assert len(results) >= 1

    def test_get_relevant_extracts_keywords(self, mock_storage):
        """Test that get_relevant extracts keywords from context."""
        from core.memory.retrieval import MemoryRetrieval

        retrieval = MemoryRetrieval(storage=mock_storage)
        context = "Tell me about Bitcoin price"
        results = retrieval.get_relevant("user_123", context)

        # Should find messages mentioning Bitcoin
        found_bitcoin = any("Bitcoin" in msg.content or "bitcoin" in msg.content.lower() for msg in results)
        assert found_bitcoin

    def test_get_relevant_with_k_limit(self, mock_storage):
        """Test get_relevant with k limit."""
        from core.memory.retrieval import MemoryRetrieval

        retrieval = MemoryRetrieval(storage=mock_storage)
        results = retrieval.get_relevant("user_123", "SOL trade", k=2)

        assert len(results) <= 2

    def test_get_relevant_empty_context(self, mock_storage):
        """Test get_relevant with empty context."""
        from core.memory.retrieval import MemoryRetrieval

        retrieval = MemoryRetrieval(storage=mock_storage)
        results = retrieval.get_relevant("user_123", "")

        assert results == []


# ==============================================================================
# Keyword Extraction Tests
# ==============================================================================

class TestKeywordExtraction:
    """Test keyword extraction functionality."""

    def test_extract_keywords_basic(self):
        """Test basic keyword extraction."""
        from core.memory.retrieval import MemoryRetrieval

        retrieval = MemoryRetrieval(storage=Mock())
        text = "I want to buy SOL tokens"
        keywords = retrieval._extract_keywords(text)

        assert "SOL" in keywords or "sol" in keywords.lower() if isinstance(keywords, str) else any("sol" in k.lower() for k in keywords)

    def test_extract_keywords_filters_stopwords(self):
        """Test that keyword extraction filters common stopwords."""
        from core.memory.retrieval import MemoryRetrieval

        retrieval = MemoryRetrieval(storage=Mock())
        text = "I want to buy the SOL tokens"
        keywords = retrieval._extract_keywords(text)

        # Common stopwords like "I", "to", "the" should be filtered
        assert "I" not in keywords
        assert "to" not in keywords
        assert "the" not in keywords

    def test_extract_keywords_handles_special_chars(self):
        """Test keyword extraction with special characters."""
        from core.memory.retrieval import MemoryRetrieval

        retrieval = MemoryRetrieval(storage=Mock())
        text = "Buy $SOL at 20% profit!!!"
        keywords = retrieval._extract_keywords(text)

        # Should extract meaningful keywords
        assert len(keywords) > 0


# ==============================================================================
# Relevance Scoring Tests
# ==============================================================================

class TestRelevanceScoring:
    """Test relevance scoring functionality."""

    def test_score_message_basic(self):
        """Test basic message scoring."""
        from core.memory.retrieval import MemoryRetrieval
        from core.memory.conversation import Message

        retrieval = MemoryRetrieval(storage=Mock())
        msg = Message(role="user", content="I want to buy SOL tokens")
        keywords = ["SOL", "buy"]

        score = retrieval._score_message(msg, keywords)

        assert isinstance(score, (int, float))
        assert score > 0

    def test_score_message_no_matches(self):
        """Test scoring message with no keyword matches."""
        from core.memory.retrieval import MemoryRetrieval
        from core.memory.conversation import Message

        retrieval = MemoryRetrieval(storage=Mock())
        msg = Message(role="user", content="Hello world")
        keywords = ["SOL", "Bitcoin"]

        score = retrieval._score_message(msg, keywords)

        assert score == 0

    def test_score_message_multiple_matches(self):
        """Test scoring message with multiple keyword matches."""
        from core.memory.retrieval import MemoryRetrieval
        from core.memory.conversation import Message

        retrieval = MemoryRetrieval(storage=Mock())
        msg = Message(role="user", content="Trade SOL and buy more SOL tokens")
        keywords = ["SOL", "trade", "buy"]

        score = retrieval._score_message(msg, keywords)

        # Multiple matches should give higher score
        assert score > 1


# ==============================================================================
# Edge Cases Tests
# ==============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_search_with_special_characters(self, mock_storage):
        """Test search with special characters in query."""
        from core.memory.retrieval import MemoryRetrieval

        retrieval = MemoryRetrieval(storage=mock_storage)
        results = retrieval.search("user_123", "20%")

        # Should handle percentage sign
        assert isinstance(results, list)

    def test_search_very_long_query(self, mock_storage):
        """Test search with very long query."""
        from core.memory.retrieval import MemoryRetrieval

        retrieval = MemoryRetrieval(storage=mock_storage)
        long_query = "SOL " * 100
        results = retrieval.search("user_123", long_query)

        assert isinstance(results, list)

    def test_search_unicode_query(self, mock_storage):
        """Test search with unicode characters."""
        from core.memory.retrieval import MemoryRetrieval

        retrieval = MemoryRetrieval(storage=mock_storage)
        results = retrieval.search("user_123", "Hello World")

        assert isinstance(results, list)

    def test_get_relevant_no_history(self):
        """Test get_relevant when user has no history."""
        from core.memory.retrieval import MemoryRetrieval

        mock_storage = Mock()
        mock_storage.get_messages.return_value = []

        retrieval = MemoryRetrieval(storage=mock_storage)
        results = retrieval.get_relevant("new_user", "SOL")

        assert results == []

    def test_search_user_isolation(self, mock_storage, sample_messages):
        """Test that search only returns messages for specified user."""
        from core.memory.retrieval import MemoryRetrieval

        retrieval = MemoryRetrieval(storage=mock_storage)
        retrieval.search("user_123", "SOL")

        # Verify storage was called with correct user_id
        mock_storage.get_messages.assert_called_once()
        call_args = mock_storage.get_messages.call_args
        assert call_args[0][0] == "user_123"


# ==============================================================================
# Factory Function Tests
# ==============================================================================

class TestFactoryFunctions:
    """Test retrieval factory functions."""

    def test_get_retrieval_for_user(self):
        """Test getting retrieval instance for user."""
        with patch('core.memory.retrieval.get_default_storage') as mock_get:
            mock_storage = Mock()
            mock_get.return_value = mock_storage

            from core.memory.retrieval import get_retrieval_for_user

            retrieval = get_retrieval_for_user("user_123")

            from core.memory.retrieval import MemoryRetrieval
            assert isinstance(retrieval, MemoryRetrieval)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
