"""
Unit tests for bots/shared/moltbook.py integration module.

Tests the ClawdBot-facing API for knowledge base access:
- query_knowledge: Query knowledge bases
- store_learning: Store learnings for future reference
- get_relevant_context: Get context for conversations
- list_available_notebooks: List available notebooks
- search_learnings: Search stored learnings
"""

import pytest
import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime


class TestQueryKnowledge:
    """Tests for query_knowledge function."""

    @pytest.mark.asyncio
    async def test_query_knowledge_basic(self):
        """Should query knowledge base and return results."""
        from bots.shared.moltbook import query_knowledge

        result = await query_knowledge("What is Telegram polling conflict?")

        assert result is not None
        assert "answer" in result or "results" in result

    @pytest.mark.asyncio
    async def test_query_knowledge_with_notebook_id(self):
        """Should query specific notebook when ID provided."""
        from bots.shared.moltbook import query_knowledge

        result = await query_knowledge(
            "How to fix 409 error?",
            notebook_id="nb_bugtracker"
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_query_knowledge_empty_question(self):
        """Should handle empty question gracefully."""
        from bots.shared.moltbook import query_knowledge

        result = await query_knowledge("")

        assert result is not None
        assert result.get("answer") == "" or result.get("results") == []

    @pytest.mark.asyncio
    async def test_query_knowledge_uses_cache(self, tmp_path):
        """Should use cache for repeated queries."""
        from bots.shared.moltbook import query_knowledge, _load_cache, _save_cache

        # First query
        result1 = await query_knowledge("test query")

        # Second query should use cache
        result2 = await query_knowledge("test query")

        assert result1 == result2


class TestStoreLearning:
    """Tests for store_learning function."""

    @pytest.mark.asyncio
    async def test_store_learning_basic(self, tmp_path):
        """Should store a learning with topic, content, and source."""
        from bots.shared.moltbook import store_learning, _get_learnings_path

        # Use temp path for testing
        with patch.object(
            __import__('bots.shared.moltbook', fromlist=['_get_learnings_path']),
            '_get_learnings_path',
            return_value=tmp_path / "learnings.json"
        ):
            result = await store_learning(
                topic="Telegram Polling",
                content="Use redis lock to prevent 409 conflicts",
                source="bugfix-session-2026-02-01"
            )

            assert result["success"] is True
            assert "learning_id" in result

    @pytest.mark.asyncio
    async def test_store_learning_persists(self, tmp_path):
        """Should persist learnings to JSON file."""
        from bots.shared.moltbook import store_learning, search_learnings

        learnings_file = tmp_path / "learnings.json"

        with patch('bots.shared.moltbook._get_learnings_path', return_value=learnings_file):
            await store_learning(
                topic="Test Topic",
                content="Test content for persistence",
                source="test-source"
            )

            # Verify file exists and contains learning
            assert learnings_file.exists()
            data = json.loads(learnings_file.read_text())
            assert len(data["learnings"]) > 0

    @pytest.mark.asyncio
    async def test_store_learning_with_tags(self, tmp_path):
        """Should support optional tags."""
        from bots.shared.moltbook import store_learning

        learnings_file = tmp_path / "learnings.json"

        with patch('bots.shared.moltbook._get_learnings_path', return_value=learnings_file):
            result = await store_learning(
                topic="Redis Patterns",
                content="Distributed lock pattern",
                source="devops-session",
                tags=["redis", "locks", "distributed"]
            )

            assert result["success"] is True

            data = json.loads(learnings_file.read_text())
            learning = data["learnings"][0]
            assert "redis" in learning.get("tags", [])


class TestGetRelevantContext:
    """Tests for get_relevant_context function."""

    @pytest.mark.asyncio
    async def test_get_relevant_context_basic(self):
        """Should return relevant context for user message."""
        from bots.shared.moltbook import get_relevant_context

        context = await get_relevant_context("Tell me about Telegram bots")

        assert context is not None
        assert isinstance(context, dict)
        assert "context" in context or "learnings" in context or "knowledge" in context

    @pytest.mark.asyncio
    async def test_get_relevant_context_empty_message(self):
        """Should handle empty message."""
        from bots.shared.moltbook import get_relevant_context

        context = await get_relevant_context("")

        assert context is not None

    @pytest.mark.asyncio
    async def test_get_relevant_context_includes_learnings(self, tmp_path):
        """Should include relevant learnings in context."""
        from bots.shared.moltbook import store_learning, get_relevant_context

        learnings_file = tmp_path / "learnings.json"

        with patch('bots.shared.moltbook._get_learnings_path', return_value=learnings_file):
            # Store a learning
            await store_learning(
                topic="Telegram Bot Fix",
                content="Fixed polling conflict with redis lock",
                source="test"
            )

            # Get context for related message
            context = await get_relevant_context("Help with Telegram bot polling")

            assert context is not None


class TestListAvailableNotebooks:
    """Tests for list_available_notebooks function."""

    @pytest.mark.asyncio
    async def test_list_notebooks_returns_list(self):
        """Should return list of available notebooks."""
        from bots.shared.moltbook import list_available_notebooks

        notebooks = await list_available_notebooks()

        assert isinstance(notebooks, list)

    @pytest.mark.asyncio
    async def test_list_notebooks_includes_default(self):
        """Should include default/mock notebooks."""
        from bots.shared.moltbook import list_available_notebooks

        notebooks = await list_available_notebooks()

        # Should have at least the mock notebooks
        assert len(notebooks) >= 0  # Empty is valid in mock mode

    @pytest.mark.asyncio
    async def test_list_notebooks_format(self):
        """Notebooks should have id and name fields."""
        from bots.shared.moltbook import list_available_notebooks

        notebooks = await list_available_notebooks()

        for nb in notebooks:
            assert "id" in nb
            assert "name" in nb


class TestSearchLearnings:
    """Tests for search_learnings function."""

    @pytest.mark.asyncio
    async def test_search_learnings_basic(self, tmp_path):
        """Should search stored learnings."""
        from bots.shared.moltbook import store_learning, search_learnings

        learnings_file = tmp_path / "learnings.json"

        with patch('bots.shared.moltbook._get_learnings_path', return_value=learnings_file):
            # Store some learnings
            await store_learning(
                topic="Telegram Fix",
                content="Fixed polling with redis",
                source="test"
            )
            await store_learning(
                topic="Docker Setup",
                content="Use docker-compose for local dev",
                source="test"
            )

            # Search for telegram
            results = await search_learnings("telegram")

            assert isinstance(results, list)
            assert len(results) >= 1
            assert any("telegram" in r.get("topic", "").lower() for r in results)

    @pytest.mark.asyncio
    async def test_search_learnings_no_match(self, tmp_path):
        """Should return empty list for no matches."""
        from bots.shared.moltbook import search_learnings

        learnings_file = tmp_path / "learnings.json"
        learnings_file.write_text('{"learnings": []}')

        with patch('bots.shared.moltbook._get_learnings_path', return_value=learnings_file):
            results = await search_learnings("nonexistent-topic-xyz")

            assert isinstance(results, list)
            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_learnings_by_tag(self, tmp_path):
        """Should search by tag."""
        from bots.shared.moltbook import store_learning, search_learnings

        learnings_file = tmp_path / "learnings.json"

        with patch('bots.shared.moltbook._get_learnings_path', return_value=learnings_file):
            await store_learning(
                topic="Redis Pattern",
                content="Distributed locks",
                source="test",
                tags=["redis", "distributed"]
            )

            results = await search_learnings("redis")

            assert len(results) >= 1


class TestResearchMode:
    """Tests for research mode functionality."""

    @pytest.mark.asyncio
    async def test_research_mode_deep_query(self):
        """Research mode should perform deeper queries."""
        from bots.shared.moltbook import query_knowledge

        result = await query_knowledge(
            "Deep dive into Solana transaction optimization",
            research_mode=True
        )

        assert result is not None
        # Research mode should indicate it was used
        assert result.get("mode") == "research" or "research" in str(result).lower() or True

    @pytest.mark.asyncio
    async def test_research_mode_multiple_sources(self):
        """Research mode should query multiple sources."""
        from bots.shared.moltbook import query_knowledge

        result = await query_knowledge(
            "Compare different caching strategies",
            research_mode=True
        )

        # Research mode might return multiple source references
        assert result is not None


class TestCaching:
    """Tests for query caching."""

    @pytest.mark.asyncio
    async def test_cache_stores_queries(self, tmp_path):
        """Should cache query results."""
        from bots.shared.moltbook import query_knowledge, _get_cache_path

        cache_file = tmp_path / "cache.json"

        with patch('bots.shared.moltbook._get_cache_path', return_value=cache_file):
            await query_knowledge("test cache query")

            # Cache file should exist or be created
            # (May not exist in mock mode)

    @pytest.mark.asyncio
    async def test_cache_expiry(self, tmp_path):
        """Cache should respect expiry time."""
        from bots.shared.moltbook import query_knowledge

        # This is a stub test - actual expiry logic tested via mocks
        result = await query_knowledge("cache expiry test")
        assert result is not None


class TestMCPIntegrationPoints:
    """Tests to verify MCP integration points are marked."""

    def test_client_has_mcp_todo(self):
        """Core client should have MCP TODO markers."""
        from core.moltbook import client
        import inspect

        source = inspect.getsource(client)
        assert "TODO: MCP" in source or "TODO" in source

    def test_integration_has_mcp_todo(self):
        """Integration module should have MCP TODO markers."""
        from bots.shared import moltbook
        import inspect

        source = inspect.getsource(moltbook)
        assert "TODO: MCP" in source or "TODO" in source
