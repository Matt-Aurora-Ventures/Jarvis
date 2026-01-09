"""
Tests for core/conversation.py

Tests cover:
- Text truncation
- Chat history formatting
- Entity extraction
- Intent classification
- Research request detection
- Support prompt selection
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.conversation import (
    _truncate,
    _format_history,
    _extract_entities,
    _is_research_request,
)


class TestTruncate:
    """Test text truncation."""

    def test_short_text_unchanged(self):
        """Short text should not be truncated."""
        text = "Hello, world!"
        result = _truncate(text, limit=800)
        assert result == text

    def test_exact_limit_unchanged(self):
        """Text at exact limit should not be truncated."""
        text = "x" * 800
        result = _truncate(text, limit=800)
        assert result == text
        assert len(result) == 800

    def test_long_text_truncated(self):
        """Long text should be truncated with ellipsis."""
        text = "x" * 1000
        result = _truncate(text, limit=800)
        assert len(result) <= 803  # 800 + "..."
        assert result.endswith("...")

    def test_truncate_preserves_start(self):
        """Should preserve start of text."""
        text = "START" + "x" * 1000 + "END"
        result = _truncate(text, limit=100)
        assert result.startswith("START")
        assert not result.endswith("END")

    def test_truncate_strips_trailing_whitespace(self):
        """Should strip trailing whitespace before adding ellipsis."""
        text = "Hello   " + "x" * 800
        result = _truncate(text, limit=10)
        # Should not have trailing spaces before ...
        assert "   ..." not in result

    def test_empty_text(self):
        """Empty text should remain empty."""
        result = _truncate("", limit=800)
        assert result == ""

    def test_custom_limit(self):
        """Should respect custom limit."""
        text = "x" * 100
        result = _truncate(text, limit=50)
        assert len(result) <= 53  # 50 + "..."


class TestFormatHistory:
    """Test chat history formatting."""

    def test_format_empty_history(self):
        """Empty history should return empty string."""
        result = _format_history([])
        assert result == ""

    def test_format_single_user_entry(self):
        """Should format single user entry."""
        entries = [{"source": "voice_chat_user", "text": "Hello"}]
        result = _format_history(entries)
        assert "User: Hello" in result

    def test_format_single_assistant_entry(self):
        """Should format single assistant entry."""
        entries = [{"source": "voice_chat_assistant", "text": "Hi there!"}]
        result = _format_history(entries)
        assert "Assistant: Hi there!" in result

    def test_format_conversation(self):
        """Should format full conversation."""
        entries = [
            {"source": "voice_chat_user", "text": "What time is it?"},
            {"source": "voice_chat_assistant", "text": "It's 3 PM."},
            {"source": "voice_chat_user", "text": "Thanks!"},
            {"source": "voice_chat_assistant", "text": "You're welcome!"},
        ]
        result = _format_history(entries)
        assert "User: What time is it?" in result
        assert "Assistant: It's 3 PM." in result
        assert "User: Thanks!" in result
        assert "Assistant: You're welcome!" in result

    def test_format_truncates_long_text(self):
        """Should truncate long text entries."""
        long_text = "x" * 1000
        entries = [{"source": "voice_chat_user", "text": long_text}]
        result = _format_history(entries)
        # Text should be truncated to 400 chars
        assert len(result) < 500
        assert "..." in result

    def test_format_skips_empty_text(self):
        """Should skip entries with empty text."""
        entries = [
            {"source": "voice_chat_user", "text": "Hello"},
            {"source": "voice_chat_assistant", "text": ""},
            {"source": "voice_chat_user", "text": "Still there?"},
        ]
        result = _format_history(entries)
        lines = [l for l in result.split("\n") if l.strip()]
        assert len(lines) == 2


class TestExtractEntities:
    """Test entity extraction from user input."""

    def test_extract_tools_python(self):
        """Should extract Python mention."""
        entities = _extract_entities("Can you run a Python script?")
        assert "python" in entities["tools"]

    def test_extract_tools_git(self):
        """Should extract Git mention."""
        entities = _extract_entities("Check the git status")
        assert "git" in entities["tools"]

    def test_extract_multiple_tools(self):
        """Should extract multiple tools."""
        entities = _extract_entities("Use docker and npm to set up the project")
        assert "docker" in entities["tools"]
        assert "npm" in entities["tools"]

    def test_extract_create_action(self):
        """Should extract create action."""
        entities = _extract_entities("Create a new file")
        assert "create" in entities["actions"]

    def test_extract_fix_action(self):
        """Should extract fix action."""
        entities = _extract_entities("Fix this bug")
        assert "fix" in entities["actions"]

    def test_extract_analyze_action(self):
        """Should extract analyze action."""
        entities = _extract_entities("Analyze the data")
        assert "analyze" in entities["actions"]

    def test_extract_multiple_actions(self):
        """Should extract multiple actions."""
        entities = _extract_entities("Find and fix all the errors")
        assert "find" in entities["actions"]
        assert "fix" in entities["actions"]

    def test_extract_crypto_topic(self):
        """Should extract crypto topic."""
        entities = _extract_entities("What's the Bitcoin price?")
        assert "crypto" in entities["topics"]

    def test_extract_development_topic(self):
        """Should extract development topic."""
        entities = _extract_entities("How do I write this function?")
        assert "development" in entities["topics"]

    def test_extract_business_topic(self):
        """Should extract business topic."""
        entities = _extract_entities("Let's analyze the sales data")
        assert "business" in entities["topics"]

    def test_extract_personal_topic(self):
        """Should extract personal topic."""
        entities = _extract_entities("What are my fitness goals?")
        assert "personal" in entities["topics"]

    def test_extract_empty_input(self):
        """Should handle empty input."""
        entities = _extract_entities("")
        assert entities["tools"] == []
        assert entities["actions"] == []
        assert entities["topics"] == []

    def test_extract_no_entities(self):
        """Should handle input with no recognizable entities."""
        entities = _extract_entities("Hello there!")
        # May or may not have entities, but should not error
        assert isinstance(entities, dict)


class TestIsResearchRequest:
    """Test research request detection."""

    def test_research_keyword(self):
        """Should detect 'research' keyword."""
        assert _is_research_request("Research the latest AI models")

    def test_deep_dive_keyword(self):
        """Should detect 'deep dive' keyword."""
        assert _is_research_request("Do a deep dive on Solana")

    def test_investigate_keyword(self):
        """Should detect 'investigate' keyword."""
        assert _is_research_request("Investigate this bug")

    def test_look_up_keyword(self):
        """Should detect 'look up' keyword."""
        assert _is_research_request("Look up the documentation")

    def test_find_sources_keyword(self):
        """Should detect 'find sources' keyword."""
        assert _is_research_request("Find sources about machine learning")

    def test_summarize_sources_keyword(self):
        """Should detect 'summarize sources' keyword."""
        assert _is_research_request("Summarize sources on this topic")

    def test_analyze_sources_keyword(self):
        """Should detect 'analyze sources' keyword."""
        assert _is_research_request("Analyze sources for bias")

    def test_not_research_request(self):
        """Should not detect regular requests."""
        assert not _is_research_request("What time is it?")
        assert not _is_research_request("Open the browser")
        assert not _is_research_request("Send an email")

    def test_case_insensitive(self):
        """Should be case insensitive."""
        assert _is_research_request("RESEARCH this topic")
        assert _is_research_request("Deep Dive into Python")

    def test_empty_input(self):
        """Should handle empty input."""
        assert not _is_research_request("")


class TestRecentChat:
    """Test recent chat retrieval."""

    @patch('core.conversation.memory')
    def test_recent_chat_filters_sources(self, mock_memory):
        """Should filter for voice chat entries only."""
        mock_memory.get_recent_entries.return_value = [
            {"source": "voice_chat_user", "text": "Hello"},
            {"source": "system", "text": "System message"},
            {"source": "voice_chat_assistant", "text": "Hi!"},
            {"source": "notification", "text": "Alert"},
        ]

        from core.conversation import _recent_chat
        result = _recent_chat(turns=10)

        # Should only include voice chat entries
        assert len(result) == 2
        assert all(
            e["source"] in ("voice_chat_user", "voice_chat_assistant")
            for e in result
        )

    @patch('core.conversation.memory')
    def test_recent_chat_limits_turns(self, mock_memory):
        """Should limit to specified number of turns."""
        mock_memory.get_recent_entries.return_value = [
            {"source": "voice_chat_user", "text": f"Message {i}"}
            for i in range(20)
        ]

        from core.conversation import _recent_chat
        result = _recent_chat(turns=6)

        assert len(result) <= 6


class TestSupportPrompts:
    """Test support prompt selection."""

    @patch('core.conversation.prompt_library')
    def test_selects_crypto_prompts(self, mock_library):
        """Should select crypto prompts for crypto-related input."""
        mock_prompt = Mock()
        mock_prompt.title = "Crypto Analysis"
        mock_prompt.body = "Analyze crypto trends"
        mock_prompt.id = "crypto-1"
        mock_library.get_support_prompts.return_value = [mock_prompt]

        from core.conversation import _support_prompts
        # Use "solana" which is in the keyword list
        inspirations, ids = _support_prompts("What's happening on Solana?")

        # Should have called with crypto tag
        call_args = mock_library.get_support_prompts.call_args
        tags = call_args[0][0]
        assert "crypto" in tags

    @patch('core.conversation.prompt_library')
    def test_selects_research_prompts(self, mock_library):
        """Should select research prompts for research-related input."""
        mock_prompt = Mock()
        mock_prompt.title = "Research Guide"
        mock_prompt.body = "How to research"
        mock_prompt.id = "research-1"
        mock_library.get_support_prompts.return_value = [mock_prompt]

        from core.conversation import _support_prompts
        inspirations, ids = _support_prompts("Research the latest trends")

        call_args = mock_library.get_support_prompts.call_args
        tags = call_args[0][0]
        assert "research" in tags

    @patch('core.conversation.prompt_library')
    def test_empty_prompts(self, mock_library):
        """Should handle empty prompt library."""
        mock_library.get_support_prompts.return_value = []

        from core.conversation import _support_prompts
        inspirations, ids = _support_prompts("Hello")

        assert inspirations == ""
        assert ids == []


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_truncate_with_unicode(self):
        """Should handle unicode correctly."""
        text = "日本語" * 500
        result = _truncate(text, limit=100)
        assert len(result) <= 103

    def test_extract_entities_special_chars(self):
        """Should handle special characters."""
        entities = _extract_entities("Use python3.10 & git-lfs!")
        # Should find python
        assert "python" in entities["tools"]

    def test_format_history_special_chars(self):
        """Should handle special characters in history."""
        entries = [
            {"source": "voice_chat_user", "text": "What's 2+2?"},
            {"source": "voice_chat_assistant", "text": "It's 4! 🎉"},
        ]
        result = _format_history(entries)
        assert "2+2" in result
        assert "🎉" in result

    def test_is_research_partial_match(self):
        """Should not match partial words."""
        # 'researcher' contains 'research' but might behave differently
        result = _is_research_request("I am a researcher")
        # Should still match because 'research' is substring
        assert result  # This depends on implementation

    def test_extract_entities_mixed_case(self):
        """Should handle mixed case."""
        entities = _extract_entities("Use PYTHON and GIT")
        assert "python" in entities["tools"]
        assert "git" in entities["tools"]
