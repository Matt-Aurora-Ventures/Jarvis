"""
Tests for Memory Echo Chamber Prevention (P0-1).

The echo chamber problem occurs when the LLM sees its own previous
responses as "facts" in memory, causing circular/shallow conversations.

The fix: get_factual_entries() filters out voice_chat_assistant sources.

Tests verify:
- Assistant outputs are excluded from factual memory
- User inputs are preserved
- Conversation history (for context) still includes both sides
- Memory summarization excludes assistant outputs
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import memory, safety


# =============================================================================
# Test get_factual_entries() Filtering
# =============================================================================

class TestFactualEntriesFiltering:
    """Test that get_factual_entries excludes assistant responses."""

    @pytest.fixture
    def temp_memory_dir(self, tmp_path):
        """Create temporary memory directory."""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        return memory_dir

    @pytest.fixture
    def mock_paths(self, temp_memory_dir):
        """Mock memory paths to use temp directory."""
        with patch.object(memory, 'RECENT_PATH', temp_memory_dir / "recent.jsonl"):
            with patch.object(memory, 'PENDING_PATH', temp_memory_dir / "pending.jsonl"):
                yield

    def test_user_inputs_preserved(self, mock_paths):
        """User inputs should be included in factual entries."""
        ctx = safety.SafetyContext(apply=True, dry_run=False)

        # Add user input
        memory.append_entry("What is the weather?", "voice_chat_user", ctx)

        factual = memory.get_factual_entries()
        assert len(factual) == 1
        assert factual[0]["text"] == "What is the weather?"
        assert factual[0]["source"] == "voice_chat_user"

    def test_assistant_outputs_excluded(self, mock_paths):
        """Assistant outputs should be EXCLUDED from factual entries."""
        ctx = safety.SafetyContext(apply=True, dry_run=False)

        # Add user input
        memory.append_entry("What is the weather?", "voice_chat_user", ctx)
        # Add assistant response (should be filtered out)
        memory.append_entry("The weather is sunny today.", "voice_chat_assistant", ctx)

        factual = memory.get_factual_entries()

        # Only user input should be in factual entries
        assert len(factual) == 1
        assert factual[0]["source"] == "voice_chat_user"

        # But get_recent_entries() should have both
        recent = memory.get_recent_entries()
        assert len(recent) == 2

    def test_mixed_sources_filtered_correctly(self, mock_paths):
        """Test filtering with multiple source types."""
        ctx = safety.SafetyContext(apply=True, dry_run=False)

        # Add various sources
        memory.append_entry("User message 1", "voice_chat_user", ctx)
        memory.append_entry("Assistant response 1", "voice_chat_assistant", ctx)
        memory.append_entry("CLI command", "cli_log", ctx)
        memory.append_entry("User message 2", "voice_chat_user", ctx)
        memory.append_entry("Assistant response 2", "voice_chat_assistant", ctx)
        memory.append_entry("Research finding", "research", ctx)

        factual = memory.get_factual_entries()

        # Should exclude only voice_chat_assistant
        sources = [e["source"] for e in factual]
        assert "voice_chat_assistant" not in sources
        assert "voice_chat_user" in sources
        assert "cli_log" in sources
        assert "research" in sources
        assert len(factual) == 4

    def test_empty_memory_returns_empty(self, mock_paths):
        """Empty memory should return empty list."""
        factual = memory.get_factual_entries()
        assert factual == []

    def test_only_assistant_entries_returns_empty(self, mock_paths):
        """If only assistant entries exist, factual should be empty."""
        ctx = safety.SafetyContext(apply=True, dry_run=False)

        memory.append_entry("I can help with that.", "voice_chat_assistant", ctx)
        memory.append_entry("Here's the answer.", "voice_chat_assistant", ctx)

        factual = memory.get_factual_entries()
        assert factual == []


# =============================================================================
# Test Memory Summarization
# =============================================================================

class TestMemorySummarization:
    """Test that summarization uses factual entries only."""

    @pytest.fixture
    def temp_memory_dir(self, tmp_path):
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        return memory_dir

    @pytest.fixture
    def mock_paths(self, temp_memory_dir):
        with patch.object(memory, 'RECENT_PATH', temp_memory_dir / "recent.jsonl"):
            with patch.object(memory, 'PENDING_PATH', temp_memory_dir / "pending.jsonl"):
                yield

    def test_summarize_excludes_assistant_when_using_factual(self, mock_paths):
        """Summarization of factual entries excludes assistant outputs."""
        ctx = safety.SafetyContext(apply=True, dry_run=False)

        memory.append_entry("Tell me about Python", "voice_chat_user", ctx)
        memory.append_entry("Python is a programming language.", "voice_chat_assistant", ctx)
        memory.append_entry("What about JavaScript?", "voice_chat_user", ctx)

        # Get factual entries and summarize
        factual = memory.get_factual_entries()
        summary = memory.summarize_entries(factual)

        # Summary should have user messages only
        assert "Tell me about Python" in summary
        assert "What about JavaScript" in summary
        assert "Python is a programming language" not in summary

    def test_summarize_deduplicates(self, mock_paths):
        """Summarization should deduplicate entries."""
        ctx = safety.SafetyContext(apply=True, dry_run=False)

        memory.append_entry("Same message", "voice_chat_user", ctx)
        memory.append_entry("Same message", "voice_chat_user", ctx)
        memory.append_entry("Same message", "voice_chat_user", ctx)

        factual = memory.get_factual_entries()
        summary = memory.summarize_entries(factual)

        # Should only appear once despite multiple entries
        assert summary.count("Same message") == 1


# =============================================================================
# Test Conversation Integration
# =============================================================================

class TestConversationIntegration:
    """Test that conversation.py uses factual memory correctly."""

    def test_conversation_imports_get_factual_entries(self):
        """Conversation module should use get_factual_entries."""
        from core import conversation

        # Check the function exists
        assert hasattr(memory, 'get_factual_entries')

        # The conversation module source should reference get_factual_entries
        import inspect
        source = inspect.getsource(conversation)
        assert "get_factual_entries" in source or "factual_entries" in source

    def test_factual_entries_function_signature(self):
        """get_factual_entries should have correct signature."""
        import inspect
        sig = inspect.signature(memory.get_factual_entries)

        # Should take no required arguments
        params = list(sig.parameters.values())
        assert all(p.default != inspect.Parameter.empty or p.kind == inspect.Parameter.VAR_POSITIONAL
                   for p in params), "get_factual_entries should not require arguments"


# =============================================================================
# Test Echo Prevention in Practice
# =============================================================================

class TestEchoPrevention:
    """Test that echo chamber is prevented in realistic scenarios."""

    @pytest.fixture
    def temp_memory_dir(self, tmp_path):
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        return memory_dir

    @pytest.fixture
    def mock_paths(self, temp_memory_dir):
        with patch.object(memory, 'RECENT_PATH', temp_memory_dir / "recent.jsonl"):
            with patch.object(memory, 'PENDING_PATH', temp_memory_dir / "pending.jsonl"):
                yield

    def test_multi_turn_conversation_factual_memory(self, mock_paths):
        """Multi-turn conversation should not echo assistant responses."""
        ctx = safety.SafetyContext(apply=True, dry_run=False)

        # Simulate a multi-turn conversation
        turns = [
            ("What's 2+2?", "voice_chat_user"),
            ("2+2 equals 4.", "voice_chat_assistant"),
            ("And what about 3+3?", "voice_chat_user"),
            ("3+3 equals 6.", "voice_chat_assistant"),
            ("Thanks!", "voice_chat_user"),
            ("You're welcome! Is there anything else?", "voice_chat_assistant"),
        ]

        for text, source in turns:
            memory.append_entry(text, source, ctx)

        # Factual memory should only have user turns
        factual = memory.get_factual_entries()
        user_count = sum(1 for e in factual if e["source"] == "voice_chat_user")
        assistant_count = sum(1 for e in factual if e["source"] == "voice_chat_assistant")

        assert user_count == 3
        assert assistant_count == 0

    def test_no_self_reinforcement_in_summary(self, mock_paths):
        """Summary for LLM prompt should not contain self-referential content."""
        ctx = safety.SafetyContext(apply=True, dry_run=False)

        # User asks about topic
        memory.append_entry("Tell me about machine learning", "voice_chat_user", ctx)
        # Assistant gives detailed response
        memory.append_entry(
            "Machine learning is a subset of AI that enables computers to learn from data. "
            "Key concepts include supervised learning, unsupervised learning, and neural networks.",
            "voice_chat_assistant",
            ctx
        )
        # User asks follow-up
        memory.append_entry("What are neural networks?", "voice_chat_user", ctx)

        # Get factual summary for next prompt
        factual = memory.get_factual_entries()
        summary = memory.summarize_entries(factual)

        # Summary should not contain the detailed ML explanation
        # (which would cause the LLM to see its own output as "fact")
        assert "subset of AI" not in summary
        assert "supervised learning" not in summary

        # But should contain user questions
        assert "machine learning" in summary.lower()
        assert "neural networks" in summary.lower()
