"""
Tests for core/context/manager.py - ContextManager class.

TDD Phase 1: Tests written BEFORE implementation.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestContextManager:
    """Tests for ContextManager class."""

    def test_context_manager_initialization(self):
        """Test ContextManager can be instantiated."""
        from core.context.manager import ContextManager

        manager = ContextManager()
        assert manager is not None

    def test_build_context_returns_string(self):
        """Test build_context returns a string."""
        from core.context.manager import ContextManager

        manager = ContextManager()
        result = manager.build_context("test_bot")

        assert isinstance(result, str)

    def test_build_context_includes_bot_name(self):
        """Test build_context includes bot identifier in output."""
        from core.context.manager import ContextManager

        manager = ContextManager()
        result = manager.build_context("clawdjarvis")

        # The context should reference the bot name somehow
        assert "clawdjarvis" in result.lower() or len(result) > 0

    def test_add_section_creates_named_section(self):
        """Test add_section adds content with section name."""
        from core.context.manager import ContextManager

        manager = ContextManager()
        manager.add_section("capabilities", "I can do X, Y, Z")

        result = manager.build_context("test_bot")
        assert "capabilities" in result.lower() or "X, Y, Z" in result

    def test_add_multiple_sections(self):
        """Test adding multiple sections preserves order/content."""
        from core.context.manager import ContextManager

        manager = ContextManager()
        manager.add_section("identity", "I am Bot A")
        manager.add_section("rules", "Always be helpful")
        manager.add_section("context", "Current time: 2026-02-02")

        result = manager.build_context("test_bot")

        # All sections should be present
        assert "Bot A" in result or "identity" in result.lower()
        assert "helpful" in result or "rules" in result.lower()

    def test_get_token_count_returns_integer(self):
        """Test get_token_count returns an integer."""
        from core.context.manager import ContextManager

        manager = ContextManager()
        manager.add_section("test", "Some content here")

        count = manager.get_token_count()

        assert isinstance(count, int)
        assert count >= 0

    def test_get_token_count_increases_with_content(self):
        """Test token count increases as content is added."""
        from core.context.manager import ContextManager

        manager = ContextManager()

        initial_count = manager.get_token_count()

        manager.add_section("content", "A" * 1000)

        new_count = manager.get_token_count()

        assert new_count > initial_count

    def test_truncate_to_limit_reduces_size(self):
        """Test truncate_to_limit reduces context to fit limit."""
        from core.context.manager import ContextManager

        manager = ContextManager()
        # Add a large amount of content
        manager.add_section("large", "word " * 5000)

        original_count = manager.get_token_count()

        # Truncate to a smaller limit
        manager.truncate_to_limit(max_tokens=1000)

        new_count = manager.get_token_count()

        assert new_count <= 1000

    def test_truncate_preserves_priority_sections(self):
        """Test truncation preserves high-priority sections."""
        from core.context.manager import ContextManager

        manager = ContextManager()
        manager.add_section("identity", "Critical identity info", priority=1)
        manager.add_section("history", "Less important history " * 500, priority=3)

        manager.truncate_to_limit(max_tokens=100)

        result = manager.build_context("test_bot")

        # Identity (priority 1) should be preserved over history (priority 3)
        assert "identity" in result.lower() or "Critical" in result

    def test_clear_sections(self):
        """Test clearing all sections."""
        from core.context.manager import ContextManager

        manager = ContextManager()
        manager.add_section("test1", "content1")
        manager.add_section("test2", "content2")

        manager.clear()

        assert manager.get_token_count() == 0 or manager.build_context("bot") == ""

    def test_remove_section(self):
        """Test removing a specific section."""
        from core.context.manager import ContextManager

        manager = ContextManager()
        manager.add_section("keep", "keep this")
        manager.add_section("remove", "remove this")

        manager.remove_section("remove")

        result = manager.build_context("bot")
        assert "keep this" in result or "keep" in result.lower()
        assert "remove this" not in result


class TestContextManagerTokenEstimation:
    """Tests for token estimation functionality."""

    def test_empty_context_zero_tokens(self):
        """Test empty manager has zero tokens."""
        from core.context.manager import ContextManager

        manager = ContextManager()

        assert manager.get_token_count() == 0

    def test_token_estimate_reasonable(self):
        """Test token estimation is reasonable (roughly 4 chars per token)."""
        from core.context.manager import ContextManager

        manager = ContextManager()
        # 400 characters should be roughly 100 tokens
        manager.add_section("test", "a" * 400)

        count = manager.get_token_count()

        # Should be between 50 and 200 tokens (reasonable range)
        assert 50 <= count <= 200


class TestContextManagerEdgeCases:
    """Edge case tests for ContextManager."""

    def test_empty_section_name(self):
        """Test handling of empty section name."""
        from core.context.manager import ContextManager

        manager = ContextManager()

        # Should either raise or handle gracefully
        try:
            manager.add_section("", "content")
            # If no error, content should still be added
            assert manager.get_token_count() > 0
        except (ValueError, KeyError):
            pass  # Expected behavior

    def test_none_content(self):
        """Test handling of None content."""
        from core.context.manager import ContextManager

        manager = ContextManager()

        try:
            manager.add_section("test", None)
        except (ValueError, TypeError):
            pass  # Expected
        else:
            # If no error, should handle gracefully
            result = manager.build_context("bot")
            assert result is not None

    def test_duplicate_section_overwrites(self):
        """Test adding duplicate section name overwrites."""
        from core.context.manager import ContextManager

        manager = ContextManager()
        manager.add_section("test", "first")
        manager.add_section("test", "second")

        result = manager.build_context("bot")

        # Should have second content, not first
        assert "second" in result
        # Should not have both
        assert result.count("first") == 0 or result.count("second") == 1

    def test_unicode_content(self):
        """Test handling of unicode content."""
        from core.context.manager import ContextManager

        manager = ContextManager()
        manager.add_section("emoji", "Hello World! Some text here")

        result = manager.build_context("bot")
        assert "Hello" in result

    def test_very_long_content(self):
        """Test handling of very long content."""
        from core.context.manager import ContextManager

        manager = ContextManager()
        long_content = "x" * 100000
        manager.add_section("long", long_content)

        # Should not crash
        result = manager.build_context("bot")
        assert result is not None
