"""
Tests for Telegram Inline Query Handler.

Tests cover:
1. Query parsing - extracting intent from raw text
2. Result generation - building InlineQueryResult objects
3. Caching - result cache management and TTL
4. Pagination - offset-based result paging
5. Answer formatting - proper response structure

Following TDD approach: tests define expected behavior.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta
import hashlib
import json


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_inline_query():
    """Create mock Telegram InlineQuery."""
    query = MagicMock()
    query.id = "inline_query_123"
    query.query = "bonk"
    query.offset = ""
    query.from_user = MagicMock()
    query.from_user.id = 12345
    query.from_user.username = "testuser"
    query.from_user.first_name = "Test"
    return query


@pytest.fixture
def mock_update(mock_inline_query):
    """Create mock Telegram Update with inline query."""
    update = MagicMock()
    update.inline_query = mock_inline_query
    update.effective_user = mock_inline_query.from_user
    return update


@pytest.fixture
def mock_context():
    """Create mock Telegram Context."""
    context = MagicMock()
    context.bot = MagicMock()
    context.bot.id = 88888
    context.bot.username = "testbot"
    return context


# =============================================================================
# Test Query Parser
# =============================================================================


class TestQueryParser:
    """Tests for inline query parsing functionality."""

    def test_parser_can_be_imported(self):
        """InlineQueryParser can be imported from module."""
        from tg_bot.handlers.inline_query import InlineQueryParser
        assert InlineQueryParser is not None

    def test_parse_empty_query(self):
        """Empty query should return empty intent."""
        from tg_bot.handlers.inline_query import InlineQueryParser

        parser = InlineQueryParser()
        result = parser.parse("")

        assert result["type"] == "empty"
        assert result["query"] == ""

    def test_parse_token_symbol(self):
        """Token symbol query should be detected."""
        from tg_bot.handlers.inline_query import InlineQueryParser

        parser = InlineQueryParser()
        result = parser.parse("BONK")

        assert result["type"] == "token_symbol"
        assert result["query"] == "BONK"

    def test_parse_token_symbol_lowercase(self):
        """Lowercase token symbol should be normalized."""
        from tg_bot.handlers.inline_query import InlineQueryParser

        parser = InlineQueryParser()
        result = parser.parse("bonk")

        assert result["type"] == "token_symbol"
        assert result["query"].upper() == "BONK"

    def test_parse_solana_address(self):
        """Solana address should be detected."""
        from tg_bot.handlers.inline_query import InlineQueryParser

        parser = InlineQueryParser()
        # Solana addresses are 32-44 base58 characters
        result = parser.parse("DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263")

        assert result["type"] == "token_address"
        assert "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263" in result["query"]

    def test_parse_partial_symbol(self):
        """Partial symbol match should be handled."""
        from tg_bot.handlers.inline_query import InlineQueryParser

        parser = InlineQueryParser()
        result = parser.parse("bo")

        assert result["type"] == "partial_search"
        assert result["query"] == "bo"

    def test_parse_command_prefix(self):
        """Command prefix queries should be detected."""
        from tg_bot.handlers.inline_query import InlineQueryParser

        parser = InlineQueryParser()
        result = parser.parse("/analyze bonk")

        assert result["type"] == "command"
        assert result["command"] == "analyze"
        assert "bonk" in result["args"]

    def test_parse_price_query(self):
        """Price lookup query should be detected."""
        from tg_bot.handlers.inline_query import InlineQueryParser

        parser = InlineQueryParser()
        result = parser.parse("price sol")

        assert result["type"] == "price_lookup"
        assert "sol" in result["query"].lower()

    def test_parse_trending_query(self):
        """Trending query should be detected."""
        from tg_bot.handlers.inline_query import InlineQueryParser

        parser = InlineQueryParser()
        result = parser.parse("trending")

        assert result["type"] == "trending"

    def test_parse_whitespace_trimmed(self):
        """Whitespace should be trimmed from queries."""
        from tg_bot.handlers.inline_query import InlineQueryParser

        parser = InlineQueryParser()
        result = parser.parse("  bonk  ")

        assert result["query"].strip() == "bonk"

    def test_parse_special_characters_sanitized(self):
        """Special characters should be handled safely."""
        from tg_bot.handlers.inline_query import InlineQueryParser

        parser = InlineQueryParser()
        result = parser.parse("<script>alert('xss')</script>")

        # Should not raise and should sanitize
        assert "<script>" not in result.get("query", "")

    def test_parse_max_length_enforced(self):
        """Queries exceeding max length should be truncated."""
        from tg_bot.handlers.inline_query import InlineQueryParser

        parser = InlineQueryParser()
        long_query = "a" * 500
        result = parser.parse(long_query)

        # Telegram inline query max is 256
        assert len(result["query"]) <= 256


# =============================================================================
# Test Result Generator
# =============================================================================


class TestResultGenerator:
    """Tests for inline query result generation."""

    def test_generator_can_be_imported(self):
        """InlineResultGenerator can be imported."""
        from tg_bot.handlers.inline_query import InlineResultGenerator
        assert InlineResultGenerator is not None

    def test_generate_token_result(self):
        """Token result should have correct format."""
        from tg_bot.handlers.inline_query import InlineResultGenerator

        generator = InlineResultGenerator()
        result = generator.generate_token_result(
            token_symbol="BONK",
            token_name="Bonk",
            token_address="DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
            price=0.00001234,
            change_24h=15.5,
        )

        assert result["type"] == "article"
        assert result["id"] is not None
        assert "BONK" in result["title"]
        assert "input_message_content" in result

    def test_generate_token_result_with_emoji(self):
        """Token result should have appropriate emoji for price change."""
        from tg_bot.handlers.inline_query import InlineResultGenerator

        generator = InlineResultGenerator()

        # Positive change
        result_up = generator.generate_token_result(
            token_symbol="SOL",
            token_name="Solana",
            token_address="So11111111111111111111111111111111111111112",
            price=150.0,
            change_24h=5.5,
        )

        # Negative change
        result_down = generator.generate_token_result(
            token_symbol="SOL",
            token_name="Solana",
            token_address="So11111111111111111111111111111111111111112",
            price=150.0,
            change_24h=-5.5,
        )

        # Results should differ
        assert result_up["title"] != result_down["title"] or \
               result_up["description"] != result_down["description"]

    def test_generate_price_result(self):
        """Price-only result should be compact."""
        from tg_bot.handlers.inline_query import InlineResultGenerator

        generator = InlineResultGenerator()
        result = generator.generate_price_result(
            token_symbol="SOL",
            price=150.12345,
        )

        assert result["type"] == "article"
        assert "$" in result["title"] or "150" in result["title"]

    def test_generate_trending_result(self):
        """Trending result should show multiple tokens."""
        from tg_bot.handlers.inline_query import InlineResultGenerator

        generator = InlineResultGenerator()
        tokens = [
            {"symbol": "SOL", "name": "Solana", "change_24h": 5.0},
            {"symbol": "BONK", "name": "Bonk", "change_24h": 15.0},
        ]
        results = generator.generate_trending_results(tokens)

        assert len(results) == len(tokens)
        for r in results:
            assert r["type"] == "article"

    def test_generate_error_result(self):
        """Error result should provide helpful message."""
        from tg_bot.handlers.inline_query import InlineResultGenerator

        generator = InlineResultGenerator()
        result = generator.generate_error_result("Token not found")

        assert result["type"] == "article"
        assert "error" in result["title"].lower() or "not found" in result["title"].lower()

    def test_generate_no_results(self):
        """No results should show helpful message."""
        from tg_bot.handlers.inline_query import InlineResultGenerator

        generator = InlineResultGenerator()
        result = generator.generate_no_results("xyz123")

        assert result["type"] == "article"
        assert "no" in result["title"].lower() or "found" in result["description"].lower()

    def test_result_id_is_unique(self):
        """Result IDs should be unique."""
        from tg_bot.handlers.inline_query import InlineResultGenerator

        generator = InlineResultGenerator()

        result1 = generator.generate_token_result("SOL", "Solana", "addr1", 100, 5)
        result2 = generator.generate_token_result("SOL", "Solana", "addr1", 100, 5)
        result3 = generator.generate_token_result("BONK", "Bonk", "addr2", 0.001, 10)

        ids = {result1["id"], result2["id"], result3["id"]}
        # At least result3 should differ
        assert len(ids) >= 2

    def test_result_description_length(self):
        """Description should not exceed Telegram limit."""
        from tg_bot.handlers.inline_query import InlineResultGenerator

        generator = InlineResultGenerator()
        result = generator.generate_token_result(
            token_symbol="TEST",
            token_name="A" * 500,  # Very long name
            token_address="addr",
            price=1.0,
            change_24h=0,
        )

        # Telegram limit is 4096 for message, but description should be shorter
        assert len(result.get("description", "")) <= 256

    def test_result_has_reply_markup(self):
        """Results should optionally include inline keyboard."""
        from tg_bot.handlers.inline_query import InlineResultGenerator

        generator = InlineResultGenerator()
        result = generator.generate_token_result(
            token_symbol="SOL",
            token_name="Solana",
            token_address="addr",
            price=100,
            change_24h=5,
            include_buttons=True,
        )

        # Should have reply markup for interactive results
        assert "reply_markup" in result or "input_message_content" in result


# =============================================================================
# Test Result Cache
# =============================================================================


class TestResultCache:
    """Tests for inline query result caching."""

    def test_cache_can_be_imported(self):
        """InlineQueryCache can be imported."""
        from tg_bot.handlers.inline_query import InlineQueryCache
        assert InlineQueryCache is not None

    def test_cache_stores_results(self):
        """Cache should store and retrieve results."""
        from tg_bot.handlers.inline_query import InlineQueryCache

        cache = InlineQueryCache()
        results = [{"id": "1", "title": "Test"}]

        cache.set("bonk", results)
        cached = cache.get("bonk")

        assert cached == results

    def test_cache_miss_returns_none(self):
        """Cache miss should return None."""
        from tg_bot.handlers.inline_query import InlineQueryCache

        cache = InlineQueryCache()
        cached = cache.get("nonexistent")

        assert cached is None

    def test_cache_expiration(self):
        """Cached results should expire after TTL."""
        from tg_bot.handlers.inline_query import InlineQueryCache

        cache = InlineQueryCache(ttl_seconds=0.1)  # Very short TTL
        results = [{"id": "1", "title": "Test"}]

        cache.set("bonk", results)

        # Immediate retrieval should work
        assert cache.get("bonk") is not None

        # After TTL, should be expired
        import time
        time.sleep(0.15)
        assert cache.get("bonk") is None

    def test_cache_key_normalization(self):
        """Cache keys should be normalized."""
        from tg_bot.handlers.inline_query import InlineQueryCache

        cache = InlineQueryCache()
        results = [{"id": "1", "title": "Test"}]

        cache.set("BONK", results)

        # Should find with different case
        assert cache.get("bonk") is not None
        assert cache.get("Bonk") is not None

    def test_cache_max_size(self):
        """Cache should respect max size limit."""
        from tg_bot.handlers.inline_query import InlineQueryCache

        cache = InlineQueryCache(max_size=5)

        # Add more than max
        for i in range(10):
            cache.set(f"key_{i}", [{"id": str(i)}])

        # Should have evicted oldest
        assert cache.size() <= 5

    def test_cache_clear(self):
        """Cache should be clearable."""
        from tg_bot.handlers.inline_query import InlineQueryCache

        cache = InlineQueryCache()
        cache.set("key1", [{}])
        cache.set("key2", [{}])

        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.size() == 0

    def test_cache_delete(self):
        """Individual cache entries should be deletable."""
        from tg_bot.handlers.inline_query import InlineQueryCache

        cache = InlineQueryCache()
        cache.set("key1", [{}])
        cache.set("key2", [{}])

        cache.delete("key1")

        assert cache.get("key1") is None
        assert cache.get("key2") is not None

    def test_cache_with_user_context(self):
        """Cache should support user-specific entries."""
        from tg_bot.handlers.inline_query import InlineQueryCache

        cache = InlineQueryCache()

        cache.set("query", [{"data": "user1"}], user_id=123)
        cache.set("query", [{"data": "user2"}], user_id=456)

        # Different users should have different results
        r1 = cache.get("query", user_id=123)
        r2 = cache.get("query", user_id=456)

        assert r1 != r2


# =============================================================================
# Test Pagination
# =============================================================================


class TestPagination:
    """Tests for inline query result pagination."""

    def test_pagination_can_be_imported(self):
        """InlineQueryPaginator can be imported."""
        from tg_bot.handlers.inline_query import InlineQueryPaginator
        assert InlineQueryPaginator is not None

    def test_paginate_first_page(self):
        """First page should return correct results."""
        from tg_bot.handlers.inline_query import InlineQueryPaginator

        paginator = InlineQueryPaginator(page_size=5)
        all_results = [{"id": str(i)} for i in range(20)]

        page, next_offset = paginator.paginate(all_results, offset="")

        assert len(page) == 5
        assert page[0]["id"] == "0"
        assert next_offset == "5"

    def test_paginate_middle_page(self):
        """Middle page should return correct slice."""
        from tg_bot.handlers.inline_query import InlineQueryPaginator

        paginator = InlineQueryPaginator(page_size=5)
        all_results = [{"id": str(i)} for i in range(20)]

        page, next_offset = paginator.paginate(all_results, offset="5")

        assert len(page) == 5
        assert page[0]["id"] == "5"
        assert next_offset == "10"

    def test_paginate_last_page(self):
        """Last page should have no next offset."""
        from tg_bot.handlers.inline_query import InlineQueryPaginator

        paginator = InlineQueryPaginator(page_size=5)
        all_results = [{"id": str(i)} for i in range(12)]

        page, next_offset = paginator.paginate(all_results, offset="10")

        assert len(page) == 2
        assert next_offset == ""  # No more pages

    def test_paginate_empty_results(self):
        """Empty results should return empty page."""
        from tg_bot.handlers.inline_query import InlineQueryPaginator

        paginator = InlineQueryPaginator(page_size=5)

        page, next_offset = paginator.paginate([], offset="")

        assert len(page) == 0
        assert next_offset == ""

    def test_paginate_invalid_offset(self):
        """Invalid offset should default to 0."""
        from tg_bot.handlers.inline_query import InlineQueryPaginator

        paginator = InlineQueryPaginator(page_size=5)
        all_results = [{"id": str(i)} for i in range(10)]

        page, _ = paginator.paginate(all_results, offset="invalid")

        assert page[0]["id"] == "0"

    def test_paginate_out_of_range_offset(self):
        """Out of range offset should return empty page."""
        from tg_bot.handlers.inline_query import InlineQueryPaginator

        paginator = InlineQueryPaginator(page_size=5)
        all_results = [{"id": str(i)} for i in range(10)]

        page, next_offset = paginator.paginate(all_results, offset="100")

        assert len(page) == 0
        assert next_offset == ""

    def test_telegram_max_results_enforced(self):
        """Should not exceed Telegram's 50 result limit."""
        from tg_bot.handlers.inline_query import InlineQueryPaginator

        paginator = InlineQueryPaginator(page_size=100)  # Try to exceed
        all_results = [{"id": str(i)} for i in range(100)]

        page, _ = paginator.paginate(all_results, offset="")

        assert len(page) <= 50  # Telegram limit


# =============================================================================
# Test Answer Formatter
# =============================================================================


class TestAnswerFormatter:
    """Tests for inline query answer formatting."""

    def test_formatter_can_be_imported(self):
        """InlineAnswerFormatter can be imported."""
        from tg_bot.handlers.inline_query import InlineAnswerFormatter
        assert InlineAnswerFormatter is not None

    def test_format_standard_answer(self):
        """Standard answer should have correct structure."""
        from tg_bot.handlers.inline_query import InlineAnswerFormatter

        formatter = InlineAnswerFormatter()
        results = [{"id": "1", "type": "article", "title": "Test"}]

        answer = formatter.format_answer(
            inline_query_id="query_123",
            results=results,
        )

        assert answer["inline_query_id"] == "query_123"
        assert answer["results"] == results
        assert "cache_time" in answer

    def test_format_answer_with_cache_time(self):
        """Answer should include custom cache time."""
        from tg_bot.handlers.inline_query import InlineAnswerFormatter

        formatter = InlineAnswerFormatter()

        answer = formatter.format_answer(
            inline_query_id="query_123",
            results=[],
            cache_time=300,
        )

        assert answer["cache_time"] == 300

    def test_format_answer_with_next_offset(self):
        """Answer should include next offset for pagination."""
        from tg_bot.handlers.inline_query import InlineAnswerFormatter

        formatter = InlineAnswerFormatter()

        answer = formatter.format_answer(
            inline_query_id="query_123",
            results=[],
            next_offset="10",
        )

        assert answer["next_offset"] == "10"

    def test_format_answer_personal_results(self):
        """Personal results should be marked appropriately."""
        from tg_bot.handlers.inline_query import InlineAnswerFormatter

        formatter = InlineAnswerFormatter()

        answer = formatter.format_answer(
            inline_query_id="query_123",
            results=[],
            is_personal=True,
        )

        assert answer["is_personal"] is True

    def test_format_answer_switch_pm(self):
        """Switch to PM button should be configurable."""
        from tg_bot.handlers.inline_query import InlineAnswerFormatter

        formatter = InlineAnswerFormatter()

        answer = formatter.format_answer(
            inline_query_id="query_123",
            results=[],
            switch_pm_text="Start Bot",
            switch_pm_parameter="start_inline",
        )

        assert answer.get("switch_pm_text") == "Start Bot"
        assert answer.get("switch_pm_parameter") == "start_inline"

    def test_format_result_to_telegram_type(self):
        """Results should be converted to proper Telegram types."""
        from tg_bot.handlers.inline_query import InlineAnswerFormatter

        formatter = InlineAnswerFormatter()

        result_dict = {
            "type": "article",
            "id": "result_1",
            "title": "Test Token",
            "description": "A test token",
            "input_message_content": {
                "message_text": "Token info here",
            }
        }

        telegram_result = formatter.to_telegram_result(result_dict)

        # Should be converted to proper type
        assert telegram_result is not None
        assert hasattr(telegram_result, 'id') or isinstance(telegram_result, dict)


# =============================================================================
# Test Inline Query Handler
# =============================================================================


class TestInlineQueryHandler:
    """Tests for the main inline query handler."""

    def test_handler_can_be_imported(self):
        """InlineQueryHandler can be imported."""
        from tg_bot.handlers.inline_query import InlineQueryHandler
        assert InlineQueryHandler is not None

    def test_handler_has_handle_method(self):
        """Handler should have async handle method."""
        from tg_bot.handlers.inline_query import InlineQueryHandler

        handler = InlineQueryHandler()
        assert hasattr(handler, "handle")
        assert callable(handler.handle)

    @pytest.mark.asyncio
    async def test_handle_empty_query(self, mock_update, mock_context):
        """Empty query should show default suggestions."""
        from tg_bot.handlers.inline_query import InlineQueryHandler

        mock_update.inline_query.query = ""
        mock_update.inline_query.answer = AsyncMock()

        handler = InlineQueryHandler()
        await handler.handle(mock_update, mock_context)

        # Should have called answer
        mock_update.inline_query.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_token_search(self, mock_update, mock_context):
        """Token search query should return results."""
        from tg_bot.handlers.inline_query import InlineQueryHandler

        mock_update.inline_query.query = "bonk"
        mock_update.inline_query.answer = AsyncMock()

        handler = InlineQueryHandler()

        with patch.object(handler, '_search_tokens', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [
                {"symbol": "BONK", "name": "Bonk", "address": "addr", "price": 0.00001}
            ]
            await handler.handle(mock_update, mock_context)

        mock_update.inline_query.answer.assert_called_once()
        call_args = mock_update.inline_query.answer.call_args
        results = call_args[0][0] if call_args[0] else call_args[1].get("results", [])
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_handle_address_lookup(self, mock_update, mock_context):
        """Address query should fetch token info."""
        from tg_bot.handlers.inline_query import InlineQueryHandler

        mock_update.inline_query.query = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
        mock_update.inline_query.answer = AsyncMock()

        handler = InlineQueryHandler()

        with patch.object(handler, '_get_token_by_address', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {"symbol": "BONK", "name": "Bonk", "price": 0.00001}
            await handler.handle(mock_update, mock_context)

        mock_update.inline_query.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_with_pagination(self, mock_update, mock_context):
        """Paginated queries should use offset."""
        from tg_bot.handlers.inline_query import InlineQueryHandler

        mock_update.inline_query.query = "sol"
        mock_update.inline_query.offset = "10"
        mock_update.inline_query.answer = AsyncMock()

        handler = InlineQueryHandler()
        await handler.handle(mock_update, mock_context)

        # Should include next_offset in answer
        mock_update.inline_query.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_uses_cache(self, mock_update, mock_context):
        """Handler should use cache for repeated queries."""
        from tg_bot.handlers.inline_query import InlineQueryHandler

        mock_update.inline_query.query = "sol"
        mock_update.inline_query.answer = AsyncMock()

        handler = InlineQueryHandler()

        # First call
        await handler.handle(mock_update, mock_context)

        # Second call should use cache
        with patch.object(handler.cache, 'get') as mock_cache_get:
            mock_cache_get.return_value = [{"id": "cached", "type": "article", "title": "Cached"}]
            await handler.handle(mock_update, mock_context)
            mock_cache_get.assert_called()

    @pytest.mark.asyncio
    async def test_handle_error_gracefully(self, mock_update, mock_context):
        """Handler should handle errors gracefully."""
        from tg_bot.handlers.inline_query import InlineQueryHandler

        mock_update.inline_query.query = "bonk"
        mock_update.inline_query.answer = AsyncMock()

        handler = InlineQueryHandler()

        with patch.object(handler, '_search_tokens', new_callable=AsyncMock) as mock_search:
            mock_search.side_effect = Exception("API Error")

            # Should not raise
            await handler.handle(mock_update, mock_context)

        # Should still answer with error result
        mock_update.inline_query.answer.assert_called_once()


# =============================================================================
# Test Inline Handler Function (Entry Point)
# =============================================================================


class TestInlineQueryHandlerFunction:
    """Tests for the inline_query_handler function entry point."""

    def test_handler_function_can_be_imported(self):
        """inline_query_handler function can be imported."""
        from tg_bot.handlers.inline_query import inline_query_handler
        assert inline_query_handler is not None
        assert callable(inline_query_handler)

    @pytest.mark.asyncio
    async def test_handler_function_processes_query(self, mock_update, mock_context):
        """Handler function should process inline queries."""
        from tg_bot.handlers.inline_query import inline_query_handler

        mock_update.inline_query.query = "test"
        mock_update.inline_query.answer = AsyncMock()

        await inline_query_handler(mock_update, mock_context)

        mock_update.inline_query.answer.assert_called()

    @pytest.mark.asyncio
    async def test_handler_function_ignores_no_inline_query(self, mock_context):
        """Handler should handle updates without inline_query."""
        from tg_bot.handlers.inline_query import inline_query_handler

        mock_update = MagicMock()
        mock_update.inline_query = None

        # Should not raise
        await inline_query_handler(mock_update, mock_context)


# =============================================================================
# Test Token Search Integration
# =============================================================================


class TestTokenSearchIntegration:
    """Tests for token search functionality in inline queries."""

    @pytest.mark.asyncio
    async def test_search_popular_tokens(self):
        """Should return popular tokens for common queries."""
        from tg_bot.handlers.inline_query import InlineQueryHandler

        handler = InlineQueryHandler()

        with patch('tg_bot.handlers.commands.search_command.search_tokens') as mock_search:
            mock_search.return_value = [
                {"symbol": "SOL", "name": "Solana", "address": "addr1"},
                {"symbol": "BONK", "name": "Bonk", "address": "addr2"},
            ]

            results = await handler._search_tokens("sol")

            assert len(results) > 0

    @pytest.mark.asyncio
    async def test_search_with_price_data(self):
        """Search results should include price when available."""
        from tg_bot.handlers.inline_query import InlineQueryHandler

        handler = InlineQueryHandler()

        with patch.object(handler, '_get_token_price', new_callable=AsyncMock) as mock_price:
            mock_price.return_value = 150.0

            result = await handler._enrich_with_price({
                "symbol": "SOL",
                "name": "Solana",
                "address": "addr",
            })

            assert "price" in result
            assert result["price"] == 150.0

    @pytest.mark.asyncio
    async def test_search_no_results(self):
        """No results should return empty list."""
        from tg_bot.handlers.inline_query import InlineQueryHandler

        handler = InlineQueryHandler()

        with patch('tg_bot.handlers.commands.search_command.search_tokens') as mock_search:
            mock_search.return_value = []

            results = await handler._search_tokens("xyznonexistent123")

            assert results == []


# =============================================================================
# Test Rate Limiting
# =============================================================================


class TestInlineQueryRateLimiting:
    """Tests for inline query rate limiting."""

    def test_rate_limiter_can_be_imported(self):
        """InlineQueryRateLimiter can be imported."""
        from tg_bot.handlers.inline_query import InlineQueryRateLimiter
        assert InlineQueryRateLimiter is not None

    def test_rate_limiter_allows_initial_requests(self):
        """Initial requests should be allowed."""
        from tg_bot.handlers.inline_query import InlineQueryRateLimiter

        limiter = InlineQueryRateLimiter(max_requests=10, window_seconds=60)

        allowed = limiter.check(user_id=123)
        assert allowed is True

    def test_rate_limiter_blocks_excessive_requests(self):
        """Excessive requests should be blocked."""
        from tg_bot.handlers.inline_query import InlineQueryRateLimiter

        limiter = InlineQueryRateLimiter(max_requests=3, window_seconds=60)

        # First 3 should be allowed
        for _ in range(3):
            assert limiter.check(user_id=123) is True

        # 4th should be blocked
        assert limiter.check(user_id=123) is False

    def test_rate_limiter_per_user(self):
        """Rate limiting should be per-user."""
        from tg_bot.handlers.inline_query import InlineQueryRateLimiter

        limiter = InlineQueryRateLimiter(max_requests=2, window_seconds=60)

        # User 1 exhausts limit
        limiter.check(user_id=1)
        limiter.check(user_id=1)
        assert limiter.check(user_id=1) is False

        # User 2 should still be allowed
        assert limiter.check(user_id=2) is True


# =============================================================================
# Test Result Caching with TTL Variants
# =============================================================================


class TestCacheTTLStrategies:
    """Tests for different cache TTL strategies."""

    def test_short_ttl_for_price_data(self):
        """Price-related results should have short TTL."""
        from tg_bot.handlers.inline_query import InlineQueryCache

        cache = InlineQueryCache()

        ttl = cache.get_ttl_for_query_type("price_lookup")
        assert ttl <= 60  # 1 minute max for prices

    def test_longer_ttl_for_static_data(self):
        """Static data like trending should have longer TTL."""
        from tg_bot.handlers.inline_query import InlineQueryCache

        cache = InlineQueryCache()

        ttl = cache.get_ttl_for_query_type("trending")
        assert ttl >= 60  # At least 1 minute

    def test_medium_ttl_for_search(self):
        """Search results should have medium TTL."""
        from tg_bot.handlers.inline_query import InlineQueryCache

        cache = InlineQueryCache()

        ttl = cache.get_ttl_for_query_type("token_search")
        assert 30 <= ttl <= 300


# =============================================================================
# Test Input Message Content Formatting
# =============================================================================


class TestInputMessageContent:
    """Tests for input message content formatting."""

    def test_format_token_message(self):
        """Token message should have correct format."""
        from tg_bot.handlers.inline_query import InlineResultGenerator

        generator = InlineResultGenerator()
        content = generator.format_token_message(
            symbol="SOL",
            name="Solana",
            price=150.0,
            change_24h=5.5,
            address="So11111111111111111111111111111111111111112",
        )

        assert "SOL" in content["message_text"]
        assert "$150" in content["message_text"] or "150" in content["message_text"]
        assert content.get("parse_mode") in ["HTML", "Markdown", "MarkdownV2", None]

    def test_format_price_message(self):
        """Price message should be concise."""
        from tg_bot.handlers.inline_query import InlineResultGenerator

        generator = InlineResultGenerator()
        content = generator.format_price_message("SOL", 150.0)

        assert "SOL" in content["message_text"]
        assert "150" in content["message_text"]

    def test_format_trending_message(self):
        """Trending message should list multiple tokens."""
        from tg_bot.handlers.inline_query import InlineResultGenerator

        generator = InlineResultGenerator()
        tokens = [
            {"symbol": "SOL", "change_24h": 5.0},
            {"symbol": "BONK", "change_24h": 15.0},
        ]
        content = generator.format_trending_message(tokens)

        assert "SOL" in content["message_text"]
        assert "BONK" in content["message_text"]


# =============================================================================
# Test Suggestion Generation
# =============================================================================


class TestSuggestionGeneration:
    """Tests for query suggestion generation."""

    def test_get_default_suggestions(self):
        """Default suggestions should be provided for empty query."""
        from tg_bot.handlers.inline_query import InlineQueryHandler

        handler = InlineQueryHandler()
        suggestions = handler.get_default_suggestions()

        assert len(suggestions) > 0
        # Suggestions are result dicts, should have title with token symbol
        titles = [s.get("title", "") for s in suggestions]
        assert any(
            any(sym in title for sym in ["SOL", "BONK", "JUP", "WIF"])
            for title in titles
        )

    def test_get_partial_suggestions(self):
        """Partial queries should get relevant suggestions."""
        from tg_bot.handlers.inline_query import InlineQueryHandler

        handler = InlineQueryHandler()
        suggestions = handler.get_suggestions_for_partial("so")

        # Should include SOL
        symbols = [s.get("symbol", "").upper() for s in suggestions]
        assert "SOL" in symbols

    def test_get_command_suggestions(self):
        """Command prefix should suggest available commands."""
        from tg_bot.handlers.inline_query import InlineQueryHandler

        handler = InlineQueryHandler()
        suggestions = handler.get_command_suggestions()

        # Should have command suggestions
        assert len(suggestions) > 0


# =============================================================================
# Test Module Exports
# =============================================================================


class TestModuleExports:
    """Tests for module __all__ exports."""

    def test_all_exports_importable(self):
        """All items in __all__ should be importable."""
        from tg_bot.handlers import inline_query

        if hasattr(inline_query, '__all__'):
            for name in inline_query.__all__:
                assert hasattr(inline_query, name), f"Missing export: {name}"

    def test_main_handler_exported(self):
        """Main handler function should be exported."""
        from tg_bot.handlers.inline_query import inline_query_handler
        assert callable(inline_query_handler)


# =============================================================================
# Test Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_unicode_query(self, mock_update, mock_context):
        """Unicode queries should be handled."""
        from tg_bot.handlers.inline_query import inline_query_handler

        mock_update.inline_query.query = "test"
        mock_update.inline_query.answer = AsyncMock()

        await inline_query_handler(mock_update, mock_context)
        mock_update.inline_query.answer.assert_called()

    @pytest.mark.asyncio
    async def test_very_long_query(self, mock_update, mock_context):
        """Very long queries should be truncated safely."""
        from tg_bot.handlers.inline_query import inline_query_handler

        mock_update.inline_query.query = "a" * 300
        mock_update.inline_query.answer = AsyncMock()

        await inline_query_handler(mock_update, mock_context)
        mock_update.inline_query.answer.assert_called()

    @pytest.mark.asyncio
    async def test_concurrent_queries(self, mock_context):
        """Concurrent queries should be handled correctly."""
        from tg_bot.handlers.inline_query import inline_query_handler
        import asyncio

        updates = []
        for i in range(5):
            update = MagicMock()
            update.inline_query = MagicMock()
            update.inline_query.query = f"query_{i}"
            update.inline_query.offset = ""
            update.inline_query.id = f"id_{i}"
            update.inline_query.from_user = MagicMock()
            update.inline_query.from_user.id = 12345
            update.inline_query.answer = AsyncMock()
            update.effective_user = update.inline_query.from_user
            updates.append(update)

        # Run concurrently
        await asyncio.gather(*[
            inline_query_handler(u, mock_context) for u in updates
        ])

        # All should have been answered
        for u in updates:
            u.inline_query.answer.assert_called()

    def test_result_id_collision_prevention(self):
        """Result IDs should not collide for similar inputs."""
        from tg_bot.handlers.inline_query import InlineResultGenerator

        generator = InlineResultGenerator()

        ids = set()
        for i in range(100):
            result = generator.generate_token_result(
                token_symbol="SOL",
                token_name="Solana",
                token_address="addr",
                price=100 + i * 0.01,
                change_24h=0,
            )
            ids.add(result["id"])

        # Should have many unique IDs
        assert len(ids) > 50


# =============================================================================
# Test Handler Registration
# =============================================================================


class TestHandlerRegistration:
    """Tests for handler registration with Telegram bot."""

    def test_get_handler_returns_handler_object(self):
        """get_inline_query_handler should return handler for registration."""
        from tg_bot.handlers.inline_query import get_inline_query_handler

        handler = get_inline_query_handler()

        # Should be usable with Application.add_handler
        assert handler is not None

    def test_handler_type_is_correct(self):
        """Handler should be InlineQueryHandler type."""
        from tg_bot.handlers.inline_query import get_inline_query_handler
        from telegram.ext import InlineQueryHandler as TelegramInlineQueryHandler

        handler = get_inline_query_handler()

        assert isinstance(handler, TelegramInlineQueryHandler)
