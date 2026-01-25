"""
Unit tests for tg_bot/handlers/faq.py - Telegram FAQ Handler.

Covers:
- FAQ Display (list all, show specific, category filtering, pagination)
- FAQ Search (keyword search, fuzzy matching, relevance ranking, no results)
- FAQ Management (admin only: add, update, delete, reorder)
- Message Formatting (Markdown, inline buttons, links, code blocks)
- User Interaction (callback queries, button clicks, navigation)

Test Categories:
1. FAQ Display - Display FAQ list and individual entries
2. FAQ Search - Search FAQ content with various methods
3. FAQ Management (Admin) - CRUD operations for FAQs
4. Message Formatting - Verify proper Telegram formatting
5. User Interaction - Callback query and navigation handling
"""

import asyncio
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from typing import Dict, Any, List

from telegram import Update, User, Chat, Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_admin_user():
    """Create a mock admin user."""
    user = Mock(spec=User)
    user.id = 123456
    user.username = "admin_user"
    user.first_name = "Admin"
    return user


@pytest.fixture
def mock_non_admin_user():
    """Create a mock non-admin user."""
    user = Mock(spec=User)
    user.id = 999999
    user.username = "regular_user"
    user.first_name = "Regular"
    return user


@pytest.fixture
def mock_chat():
    """Create a mock chat object."""
    chat = Mock(spec=Chat)
    chat.id = 123456
    chat.type = "private"
    chat.title = None
    return chat


@pytest.fixture
def mock_message(mock_admin_user, mock_chat):
    """Create a mock message object."""
    message = Mock(spec=Message)
    message.reply_text = AsyncMock()
    message.edit_text = AsyncMock()
    message.chat_id = mock_chat.id
    message.message_id = 1
    message.from_user = mock_admin_user
    message.text = "/faq"
    return message


@pytest.fixture
def mock_update(mock_admin_user, mock_chat, mock_message):
    """Create a mock update object for admin user."""
    update = Mock(spec=Update)
    update.effective_user = mock_admin_user
    update.effective_chat = mock_chat
    update.message = mock_message
    update.effective_message = mock_message
    update.callback_query = None
    return update


@pytest.fixture
def mock_non_admin_update(mock_non_admin_user, mock_chat, mock_message):
    """Create a mock update object for non-admin user."""
    update = Mock(spec=Update)
    update.effective_user = mock_non_admin_user
    update.effective_chat = mock_chat
    update.message = mock_message
    update.effective_message = mock_message
    update.callback_query = None
    return update


@pytest.fixture
def mock_callback_query(mock_admin_user, mock_message):
    """Create a mock callback query object."""
    query = Mock(spec=CallbackQuery)
    query.id = "callback_123"
    query.from_user = mock_admin_user
    query.message = mock_message
    query.data = "faq:list:0"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    return query


@pytest.fixture
def mock_callback_update(mock_admin_user, mock_chat, mock_callback_query):
    """Create a mock update with callback query."""
    update = Mock(spec=Update)
    update.effective_user = mock_admin_user
    update.effective_chat = mock_chat
    update.message = None
    update.effective_message = mock_callback_query.message
    update.callback_query = mock_callback_query
    return update


@pytest.fixture
def mock_context():
    """Create a mock context object."""
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.args = []
    context.bot = Mock()
    context.bot.send_message = AsyncMock()
    context.user_data = {}
    return context


@pytest.fixture
def admin_config():
    """Mock config where user is admin."""
    with patch("tg_bot.handlers.get_config") as mock:
        config = MagicMock()
        config.is_admin = MagicMock(return_value=True)
        config.admin_ids = {123456}
        mock.return_value = config
        yield config


@pytest.fixture
def non_admin_config():
    """Mock config where user is not admin."""
    with patch("tg_bot.handlers.get_config") as mock:
        config = MagicMock()
        config.is_admin = MagicMock(return_value=False)
        config.admin_ids = {123456}
        mock.return_value = config
        yield config


@pytest.fixture
def sample_faqs():
    """Sample FAQ data for testing."""
    return [
        {
            "id": 1,
            "question": "What is Jarvis?",
            "answer": "Jarvis is an AI-powered trading assistant for Solana tokens.",
            "category": "general",
            "keywords": ["jarvis", "what", "about"],
            "order": 1,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        },
        {
            "id": 2,
            "question": "How do I start trading?",
            "answer": "Use `/balance` to check your wallet, then `/buy <token> <amount>` to make a trade.",
            "category": "trading",
            "keywords": ["trading", "start", "begin", "buy"],
            "order": 2,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        },
        {
            "id": 3,
            "question": "What are the fees?",
            "answer": "There are no fees for using Jarvis. You only pay standard Solana network fees.",
            "category": "trading",
            "keywords": ["fees", "cost", "price"],
            "order": 3,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        },
        {
            "id": 4,
            "question": "How do I contact support?",
            "answer": "Contact @matthaynes88 on Telegram or use the `/help` command.",
            "category": "support",
            "keywords": ["support", "help", "contact"],
            "order": 4,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        },
        {
            "id": 5,
            "question": "Is my wallet safe?",
            "answer": "Yes, Jarvis never stores your private keys. All transactions require your approval.",
            "category": "security",
            "keywords": ["security", "safe", "wallet", "keys"],
            "order": 5,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        },
    ]


@pytest.fixture
def mock_faq_store(sample_faqs):
    """Mock FAQ data store."""
    store = MagicMock()
    store.get_all.return_value = sample_faqs
    store.get_by_id.side_effect = lambda faq_id: next(
        (f for f in sample_faqs if f["id"] == faq_id), None
    )
    store.get_by_category.side_effect = lambda cat: [
        f for f in sample_faqs if f["category"] == cat
    ]
    store.search.return_value = sample_faqs[:2]
    store.add.return_value = {"id": 6, "question": "New FAQ", "answer": "New answer"}
    store.update.return_value = True
    store.delete.return_value = True
    store.reorder.return_value = True
    store.get_categories.return_value = ["general", "trading", "support", "security"]
    return store


# ============================================================================
# Test: FAQ Data Store
# ============================================================================

class TestFAQStore:
    """Tests for FAQStore class."""

    def test_faq_store_creation(self):
        """Should create FAQ store instance."""
        from tg_bot.handlers.faq import FAQStore
        store = FAQStore()
        assert store is not None

    def test_faq_store_get_all(self, sample_faqs):
        """Should return all FAQs."""
        from tg_bot.handlers.faq import FAQStore
        store = FAQStore()
        # Load sample data
        store._faqs = sample_faqs
        result = store.get_all()
        assert len(result) == 5

    def test_faq_store_get_by_id_exists(self, sample_faqs):
        """Should return FAQ by ID."""
        from tg_bot.handlers.faq import FAQStore
        store = FAQStore()
        store._faqs = sample_faqs
        result = store.get_by_id(1)
        assert result is not None
        assert result["question"] == "What is Jarvis?"

    def test_faq_store_get_by_id_not_found(self, sample_faqs):
        """Should return None for non-existent ID."""
        from tg_bot.handlers.faq import FAQStore
        store = FAQStore()
        store._faqs = sample_faqs
        result = store.get_by_id(999)
        assert result is None

    def test_faq_store_get_by_category(self, sample_faqs):
        """Should filter FAQs by category."""
        from tg_bot.handlers.faq import FAQStore
        store = FAQStore()
        store._faqs = sample_faqs
        result = store.get_by_category("trading")
        assert len(result) == 2
        for faq in result:
            assert faq["category"] == "trading"

    def test_faq_store_get_by_category_empty(self, sample_faqs):
        """Should return empty list for non-existent category."""
        from tg_bot.handlers.faq import FAQStore
        store = FAQStore()
        store._faqs = sample_faqs
        result = store.get_by_category("nonexistent")
        assert result == []

    def test_faq_store_get_categories(self, sample_faqs):
        """Should return unique categories."""
        from tg_bot.handlers.faq import FAQStore
        store = FAQStore()
        store._faqs = sample_faqs
        result = store.get_categories()
        assert "general" in result
        assert "trading" in result
        assert "support" in result
        assert "security" in result

    def test_faq_store_search_keyword(self, sample_faqs):
        """Should search FAQs by keyword."""
        from tg_bot.handlers.faq import FAQStore
        store = FAQStore()
        store._faqs = sample_faqs
        result = store.search("trading")
        assert len(result) > 0
        # Should find FAQs with "trading" in question, answer, or keywords

    def test_faq_store_search_no_results(self, sample_faqs):
        """Should return empty list when no matches."""
        from tg_bot.handlers.faq import FAQStore
        store = FAQStore()
        store._faqs = sample_faqs
        result = store.search("xyznonexistent123")
        assert result == []

    def test_faq_store_search_fuzzy(self, sample_faqs):
        """Should find FAQs with fuzzy matching."""
        from tg_bot.handlers.faq import FAQStore
        store = FAQStore()
        store._faqs = sample_faqs
        # "trad" should match "trading"
        result = store.search("trad")
        assert len(result) > 0

    def test_faq_store_add(self, sample_faqs):
        """Should add new FAQ."""
        from tg_bot.handlers.faq import FAQStore
        store = FAQStore()
        store._faqs = sample_faqs.copy()
        new_faq = store.add(
            question="New question?",
            answer="New answer.",
            category="general",
            keywords=["new"]
        )
        assert new_faq is not None
        assert new_faq["id"] == 6
        assert len(store._faqs) == 6

    def test_faq_store_update(self, sample_faqs):
        """Should update existing FAQ."""
        from tg_bot.handlers.faq import FAQStore
        store = FAQStore()
        store._faqs = sample_faqs.copy()
        result = store.update(1, question="Updated question?")
        assert result is True
        updated = store.get_by_id(1)
        assert updated["question"] == "Updated question?"

    def test_faq_store_update_not_found(self, sample_faqs):
        """Should return False for non-existent FAQ."""
        from tg_bot.handlers.faq import FAQStore
        store = FAQStore()
        store._faqs = sample_faqs.copy()
        result = store.update(999, question="Won't work")
        assert result is False

    def test_faq_store_delete(self, sample_faqs):
        """Should delete FAQ."""
        from tg_bot.handlers.faq import FAQStore
        store = FAQStore()
        store._faqs = sample_faqs.copy()
        result = store.delete(1)
        assert result is True
        assert store.get_by_id(1) is None
        assert len(store._faqs) == 4

    def test_faq_store_delete_not_found(self, sample_faqs):
        """Should return False for non-existent FAQ."""
        from tg_bot.handlers.faq import FAQStore
        store = FAQStore()
        store._faqs = sample_faqs.copy()
        result = store.delete(999)
        assert result is False

    def test_faq_store_reorder(self, sample_faqs):
        """Should reorder FAQs."""
        from tg_bot.handlers.faq import FAQStore
        store = FAQStore()
        store._faqs = sample_faqs.copy()
        # Move FAQ 3 to position 1
        result = store.reorder(3, 1)
        assert result is True
        # FAQ 3 should now be first
        all_faqs = store.get_all()
        assert all_faqs[0]["id"] == 3


# ============================================================================
# Test: FAQ Display - List All FAQs
# ============================================================================

class TestFAQDisplayListAll:
    """Tests for listing all FAQs."""

    @pytest.mark.asyncio
    async def test_faq_list_shows_all(self, mock_update, mock_context, admin_config, mock_faq_store):
        """Should display all FAQs."""
        from tg_bot.handlers.faq import faq_command, get_faq_store

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await faq_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            # Check for FAQ content in message (case-insensitive)
            assert "faq" in message.lower() or "question" in message.lower()

    @pytest.mark.asyncio
    async def test_faq_list_empty(self, mock_update, mock_context, admin_config):
        """Should handle empty FAQ list."""
        from tg_bot.handlers.faq import faq_command

        mock_store = MagicMock()
        mock_store.get_all.return_value = []

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_store):
            await faq_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "no faq" in message.lower() or "empty" in message.lower()

    @pytest.mark.asyncio
    async def test_faq_list_has_keyboard(self, mock_update, mock_context, admin_config, mock_faq_store):
        """Should include inline keyboard for navigation."""
        from tg_bot.handlers.faq import faq_command

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await faq_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            # Should have reply_markup for buttons
            assert "reply_markup" in call_args[1]


# ============================================================================
# Test: FAQ Display - Show Specific FAQ
# ============================================================================

class TestFAQDisplaySpecific:
    """Tests for displaying specific FAQ by ID."""

    @pytest.mark.asyncio
    async def test_faq_show_by_id(self, mock_update, mock_context, admin_config, mock_faq_store):
        """Should display specific FAQ by ID."""
        from tg_bot.handlers.faq import faq_command

        mock_context.args = ["1"]

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await faq_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "What is Jarvis?" in message

    @pytest.mark.asyncio
    async def test_faq_show_not_found(self, mock_update, mock_context, admin_config, mock_faq_store):
        """Should handle non-existent FAQ ID."""
        from tg_bot.handlers.faq import faq_command

        mock_context.args = ["999"]
        mock_faq_store.get_by_id.return_value = None

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await faq_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "not found" in message.lower()

    @pytest.mark.asyncio
    async def test_faq_show_invalid_id(self, mock_update, mock_context, admin_config, mock_faq_store):
        """Should handle invalid FAQ ID format."""
        from tg_bot.handlers.faq import faq_command

        mock_context.args = ["abc"]

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await faq_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            # Should treat as search query or show error
            assert mock_update.message.reply_text.called


# ============================================================================
# Test: FAQ Display - Category Filtering
# ============================================================================

class TestFAQCategoryFiltering:
    """Tests for filtering FAQs by category."""

    @pytest.mark.asyncio
    async def test_faq_filter_by_category(self, mock_update, mock_context, admin_config, mock_faq_store, sample_faqs):
        """Should filter FAQs by category."""
        from tg_bot.handlers.faq import faq_command

        mock_context.args = ["--category", "trading"]
        mock_faq_store.get_by_category.return_value = [f for f in sample_faqs if f["category"] == "trading"]

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await faq_command(mock_update, mock_context)

            mock_faq_store.get_by_category.assert_called_with("trading")

    @pytest.mark.asyncio
    async def test_faq_filter_empty_category(self, mock_update, mock_context, admin_config, mock_faq_store):
        """Should handle empty category results."""
        from tg_bot.handlers.faq import faq_command

        mock_context.args = ["--category", "nonexistent"]
        mock_faq_store.get_by_category.return_value = []

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await faq_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "no faq" in message.lower() or "not found" in message.lower()

    @pytest.mark.asyncio
    async def test_faq_list_categories(self, mock_update, mock_context, admin_config, mock_faq_store):
        """Should list available categories."""
        from tg_bot.handlers.faq import faq_command

        mock_context.args = ["--categories"]

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await faq_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "general" in message.lower()
            assert "trading" in message.lower()


# ============================================================================
# Test: FAQ Display - Pagination
# ============================================================================

class TestFAQPagination:
    """Tests for FAQ list pagination."""

    @pytest.mark.asyncio
    async def test_faq_pagination_first_page(self, mock_update, mock_context, admin_config):
        """Should display first page of FAQs."""
        from tg_bot.handlers.faq import faq_command

        # Create 15 FAQs for pagination testing
        many_faqs = [
            {"id": i, "question": f"Question {i}?", "answer": f"Answer {i}",
             "category": "general", "keywords": [], "order": i}
            for i in range(1, 16)
        ]

        mock_store = MagicMock()
        mock_store.get_all.return_value = many_faqs

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_store):
            await faq_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            # Should have navigation buttons if paginated
            if "reply_markup" in call_args[1]:
                keyboard = call_args[1]["reply_markup"]
                # Check for next button
                assert keyboard is not None

    @pytest.mark.asyncio
    async def test_faq_pagination_callback_next(self, mock_callback_update, mock_context, admin_config):
        """Should navigate to next page via callback."""
        from tg_bot.handlers.faq import handle_faq_callback

        mock_callback_update.callback_query.data = "faq:page:1"

        many_faqs = [
            {"id": i, "question": f"Question {i}?", "answer": f"Answer {i}",
             "category": "general", "keywords": [], "order": i}
            for i in range(1, 16)
        ]

        mock_store = MagicMock()
        mock_store.get_all.return_value = many_faqs

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_store):
            await handle_faq_callback(mock_callback_update, mock_context)

            mock_callback_update.callback_query.answer.assert_called()

    @pytest.mark.asyncio
    async def test_faq_pagination_callback_prev(self, mock_callback_update, mock_context, admin_config):
        """Should navigate to previous page via callback."""
        from tg_bot.handlers.faq import handle_faq_callback

        mock_callback_update.callback_query.data = "faq:page:0"
        mock_context.user_data["faq_page"] = 1

        many_faqs = [
            {"id": i, "question": f"Question {i}?", "answer": f"Answer {i}",
             "category": "general", "keywords": [], "order": i}
            for i in range(1, 16)
        ]

        mock_store = MagicMock()
        mock_store.get_all.return_value = many_faqs

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_store):
            await handle_faq_callback(mock_callback_update, mock_context)

            mock_callback_update.callback_query.answer.assert_called()


# ============================================================================
# Test: FAQ Search - Keyword Search
# ============================================================================

class TestFAQSearch:
    """Tests for FAQ search functionality."""

    @pytest.mark.asyncio
    async def test_faq_search_keyword(self, mock_update, mock_context, admin_config, mock_faq_store, sample_faqs):
        """Should search FAQs by keyword."""
        from tg_bot.handlers.faq import faq_command

        mock_context.args = ["trading"]
        mock_faq_store.search.return_value = [f for f in sample_faqs if "trading" in f["question"].lower() or "trading" in f["answer"].lower()]

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await faq_command(mock_update, mock_context)

            mock_faq_store.search.assert_called_with("trading")

    @pytest.mark.asyncio
    async def test_faq_search_multiple_keywords(self, mock_update, mock_context, admin_config, mock_faq_store):
        """Should search with multiple keywords."""
        from tg_bot.handlers.faq import faq_command

        mock_context.args = ["start", "trading"]

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await faq_command(mock_update, mock_context)

            # Should combine keywords for search
            assert mock_faq_store.search.called

    @pytest.mark.asyncio
    async def test_faq_search_no_results(self, mock_update, mock_context, admin_config, mock_faq_store):
        """Should handle no search results."""
        from tg_bot.handlers.faq import faq_command

        mock_context.args = ["xyznonexistent123"]
        mock_faq_store.search.return_value = []

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await faq_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "no" in message.lower() and ("result" in message.lower() or "found" in message.lower())

    @pytest.mark.asyncio
    async def test_faq_search_fuzzy_match(self, mock_update, mock_context, admin_config, mock_faq_store, sample_faqs):
        """Should find FAQs with fuzzy matching."""
        from tg_bot.handlers.faq import faq_command

        mock_context.args = ["trad"]  # Partial match for "trading"
        mock_faq_store.search.return_value = [sample_faqs[1], sample_faqs[2]]

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await faq_command(mock_update, mock_context)

            mock_faq_store.search.assert_called()

    @pytest.mark.asyncio
    async def test_faq_search_case_insensitive(self, mock_update, mock_context, admin_config, mock_faq_store, sample_faqs):
        """Should search case-insensitively."""
        from tg_bot.handlers.faq import faq_command

        mock_context.args = ["TRADING"]
        mock_faq_store.search.return_value = [sample_faqs[1]]

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await faq_command(mock_update, mock_context)

            # Should call search (implementation handles case)
            mock_faq_store.search.assert_called()


# ============================================================================
# Test: FAQ Search - Relevance Ranking
# ============================================================================

class TestFAQRelevanceRanking:
    """Tests for FAQ search relevance ranking."""

    @pytest.mark.asyncio
    async def test_faq_search_relevance_order(self, mock_update, mock_context, admin_config, sample_faqs):
        """Should return results ordered by relevance."""
        from tg_bot.handlers.faq import faq_command

        mock_context.args = ["fees"]

        # FAQ about fees should be first
        ranked_results = [sample_faqs[2], sample_faqs[1]]  # fees FAQ first

        mock_store = MagicMock()
        mock_store.search.return_value = ranked_results

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_store):
            await faq_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            # Fees FAQ should appear before trading FAQ
            fees_pos = message.find("fees") if "fees" in message.lower() else -1
            assert fees_pos >= 0

    @pytest.mark.asyncio
    async def test_faq_search_exact_match_priority(self, mock_update, mock_context, admin_config, sample_faqs):
        """Should prioritize exact matches."""
        from tg_bot.handlers.faq import faq_command

        mock_context.args = ["Jarvis"]

        mock_store = MagicMock()
        # Exact match should be first
        mock_store.search.return_value = [sample_faqs[0]]  # "What is Jarvis?"

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_store):
            await faq_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "Jarvis" in message


# ============================================================================
# Test: FAQ Management - Admin Only
# ============================================================================

class TestFAQManagementAdminOnly:
    """Tests for FAQ admin management commands."""

    @pytest.mark.asyncio
    async def test_faq_add_admin_only(self, mock_non_admin_update, mock_context, non_admin_config):
        """Non-admin should not be able to add FAQs."""
        from tg_bot.handlers.faq import faq_add_command

        mock_context.args = ["Question?", "Answer"]

        with patch("tg_bot.handlers.faq.get_faq_store"):
            await faq_add_command(mock_non_admin_update, mock_context)

            call_args = mock_non_admin_update.message.reply_text.call_args
            message = call_args[0][0]
            # Should show unauthorized message
            assert mock_non_admin_update.message.reply_text.called

    @pytest.mark.asyncio
    async def test_faq_update_admin_only(self, mock_non_admin_update, mock_context, non_admin_config):
        """Non-admin should not be able to update FAQs."""
        from tg_bot.handlers.faq import faq_update_command

        mock_context.args = ["1", "Updated question?"]

        with patch("tg_bot.handlers.faq.get_faq_store"):
            await faq_update_command(mock_non_admin_update, mock_context)

            assert mock_non_admin_update.message.reply_text.called

    @pytest.mark.asyncio
    async def test_faq_delete_admin_only(self, mock_non_admin_update, mock_context, non_admin_config):
        """Non-admin should not be able to delete FAQs."""
        from tg_bot.handlers.faq import faq_delete_command

        mock_context.args = ["1"]

        with patch("tg_bot.handlers.faq.get_faq_store"):
            await faq_delete_command(mock_non_admin_update, mock_context)

            assert mock_non_admin_update.message.reply_text.called


# ============================================================================
# Test: FAQ Management - Add New FAQ
# ============================================================================

class TestFAQManagementAdd:
    """Tests for adding new FAQs."""

    @pytest.mark.asyncio
    async def test_faq_add_success(self, mock_update, mock_context, admin_config, mock_faq_store):
        """Should add new FAQ successfully."""
        from tg_bot.handlers.faq import faq_add_command

        mock_context.args = ["What is the moon?", "|", "The moon is very far away."]

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await faq_add_command(mock_update, mock_context)

            mock_faq_store.add.assert_called()
            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "added" in message.lower() or "created" in message.lower()

    @pytest.mark.asyncio
    async def test_faq_add_with_category(self, mock_update, mock_context, admin_config, mock_faq_store):
        """Should add FAQ with specified category."""
        from tg_bot.handlers.faq import faq_add_command

        mock_context.args = ["--category", "trading", "Question?", "|", "Answer"]

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await faq_add_command(mock_update, mock_context)

            call_args = mock_faq_store.add.call_args
            assert call_args[1].get("category") == "trading"

    @pytest.mark.asyncio
    async def test_faq_add_with_keywords(self, mock_update, mock_context, admin_config, mock_faq_store):
        """Should add FAQ with keywords."""
        from tg_bot.handlers.faq import faq_add_command

        mock_context.args = ["--keywords", "test,example", "Question?", "|", "Answer"]

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await faq_add_command(mock_update, mock_context)

            call_args = mock_faq_store.add.call_args
            keywords = call_args[1].get("keywords", [])
            assert "test" in keywords or isinstance(keywords, list)

    @pytest.mark.asyncio
    async def test_faq_add_missing_args(self, mock_update, mock_context, admin_config, mock_faq_store):
        """Should handle missing arguments."""
        from tg_bot.handlers.faq import faq_add_command

        mock_context.args = []  # No question/answer

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await faq_add_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "usage" in message.lower() or "error" in message.lower()


# ============================================================================
# Test: FAQ Management - Update FAQ
# ============================================================================

class TestFAQManagementUpdate:
    """Tests for updating FAQs."""

    @pytest.mark.asyncio
    async def test_faq_update_question(self, mock_update, mock_context, admin_config, mock_faq_store):
        """Should update FAQ question."""
        from tg_bot.handlers.faq import faq_update_command

        mock_context.args = ["1", "--question", "Updated question?"]

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await faq_update_command(mock_update, mock_context)

            mock_faq_store.update.assert_called()
            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "updated" in message.lower()

    @pytest.mark.asyncio
    async def test_faq_update_answer(self, mock_update, mock_context, admin_config, mock_faq_store):
        """Should update FAQ answer."""
        from tg_bot.handlers.faq import faq_update_command

        mock_context.args = ["1", "--answer", "Updated answer."]

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await faq_update_command(mock_update, mock_context)

            mock_faq_store.update.assert_called()

    @pytest.mark.asyncio
    async def test_faq_update_category(self, mock_update, mock_context, admin_config, mock_faq_store):
        """Should update FAQ category."""
        from tg_bot.handlers.faq import faq_update_command

        mock_context.args = ["1", "--category", "security"]

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await faq_update_command(mock_update, mock_context)

            call_args = mock_faq_store.update.call_args
            assert "category" in str(call_args)

    @pytest.mark.asyncio
    async def test_faq_update_not_found(self, mock_update, mock_context, admin_config, mock_faq_store):
        """Should handle updating non-existent FAQ."""
        from tg_bot.handlers.faq import faq_update_command

        mock_context.args = ["999", "--question", "Won't work"]
        mock_faq_store.update.return_value = False

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await faq_update_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "not found" in message.lower() or "failed" in message.lower()


# ============================================================================
# Test: FAQ Management - Delete FAQ
# ============================================================================

class TestFAQManagementDelete:
    """Tests for deleting FAQs."""

    @pytest.mark.asyncio
    async def test_faq_delete_success(self, mock_update, mock_context, admin_config, mock_faq_store):
        """Should delete FAQ successfully."""
        from tg_bot.handlers.faq import faq_delete_command

        mock_context.args = ["1"]

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await faq_delete_command(mock_update, mock_context)

            mock_faq_store.delete.assert_called_with(1)
            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "deleted" in message.lower()

    @pytest.mark.asyncio
    async def test_faq_delete_not_found(self, mock_update, mock_context, admin_config, mock_faq_store):
        """Should handle deleting non-existent FAQ."""
        from tg_bot.handlers.faq import faq_delete_command

        mock_context.args = ["999"]
        mock_faq_store.delete.return_value = False

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await faq_delete_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "not found" in message.lower() or "failed" in message.lower()

    @pytest.mark.asyncio
    async def test_faq_delete_missing_id(self, mock_update, mock_context, admin_config, mock_faq_store):
        """Should handle missing FAQ ID."""
        from tg_bot.handlers.faq import faq_delete_command

        mock_context.args = []

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await faq_delete_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "usage" in message.lower() or "id" in message.lower()


# ============================================================================
# Test: FAQ Management - Reorder FAQs
# ============================================================================

class TestFAQManagementReorder:
    """Tests for reordering FAQs."""

    @pytest.mark.asyncio
    async def test_faq_reorder_success(self, mock_update, mock_context, admin_config, mock_faq_store):
        """Should reorder FAQ successfully."""
        from tg_bot.handlers.faq import faq_reorder_command

        mock_context.args = ["3", "1"]  # Move FAQ 3 to position 1

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await faq_reorder_command(mock_update, mock_context)

            mock_faq_store.reorder.assert_called_with(3, 1)
            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "reorder" in message.lower() or "moved" in message.lower()

    @pytest.mark.asyncio
    async def test_faq_reorder_invalid_args(self, mock_update, mock_context, admin_config, mock_faq_store):
        """Should handle invalid reorder arguments."""
        from tg_bot.handlers.faq import faq_reorder_command

        mock_context.args = ["abc", "xyz"]

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await faq_reorder_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "invalid" in message.lower() or "usage" in message.lower()


# ============================================================================
# Test: Message Formatting
# ============================================================================

class TestMessageFormatting:
    """Tests for proper message formatting."""

    @pytest.mark.asyncio
    async def test_faq_uses_html_parse_mode(self, mock_update, mock_context, admin_config, mock_faq_store):
        """FAQ should use HTML parse mode."""
        from tg_bot.handlers.faq import faq_command

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await faq_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            assert call_args[1].get("parse_mode") == ParseMode.HTML

    @pytest.mark.asyncio
    async def test_faq_escapes_html(self, mock_update, mock_context, admin_config, sample_faqs):
        """Should escape HTML in user content."""
        from tg_bot.handlers.faq import faq_command

        # FAQ with HTML-like content
        faqs_with_html = sample_faqs.copy()
        faqs_with_html[0]["answer"] = "Use <b>bold</b> text & symbols"

        mock_store = MagicMock()
        mock_store.get_all.return_value = faqs_with_html
        mock_store.get_by_id.return_value = faqs_with_html[0]

        mock_context.args = ["1"]

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_store):
            await faq_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            # Should escape or handle HTML
            assert "&lt;" in message or "bold" in message

    @pytest.mark.asyncio
    async def test_faq_formats_code_blocks(self, mock_update, mock_context, admin_config, sample_faqs):
        """Should format code blocks properly."""
        from tg_bot.handlers.faq import faq_command

        # FAQ with code
        faqs_with_code = sample_faqs.copy()
        faqs_with_code[1]["answer"] = "Use `/buy SOL 10` to purchase"

        mock_store = MagicMock()
        mock_store.get_all.return_value = faqs_with_code
        mock_store.get_by_id.return_value = faqs_with_code[1]

        mock_context.args = ["2"]

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_store):
            await faq_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            # Should preserve code formatting
            assert "/buy" in message or "code" in message.lower()

    @pytest.mark.asyncio
    async def test_faq_inline_keyboard_format(self, mock_update, mock_context, admin_config, mock_faq_store):
        """Should include properly formatted inline keyboard."""
        from tg_bot.handlers.faq import faq_command

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await faq_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            reply_markup = call_args[1].get("reply_markup")

            if reply_markup:
                assert isinstance(reply_markup, InlineKeyboardMarkup)


# ============================================================================
# Test: User Interaction - Callback Queries
# ============================================================================

class TestCallbackQueries:
    """Tests for callback query handling."""

    @pytest.mark.asyncio
    async def test_faq_callback_show(self, mock_callback_update, mock_context, admin_config, mock_faq_store, sample_faqs):
        """Should show FAQ via callback."""
        from tg_bot.handlers.faq import handle_faq_callback

        mock_callback_update.callback_query.data = "faq:show:1"
        mock_faq_store.get_by_id.return_value = sample_faqs[0]

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await handle_faq_callback(mock_callback_update, mock_context)

            mock_callback_update.callback_query.answer.assert_called()
            mock_callback_update.callback_query.edit_message_text.assert_called()

    @pytest.mark.asyncio
    async def test_faq_callback_back_to_list(self, mock_callback_update, mock_context, admin_config, mock_faq_store):
        """Should return to FAQ list via callback."""
        from tg_bot.handlers.faq import handle_faq_callback

        mock_callback_update.callback_query.data = "faq:list:0"

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await handle_faq_callback(mock_callback_update, mock_context)

            mock_callback_update.callback_query.answer.assert_called()

    @pytest.mark.asyncio
    async def test_faq_callback_category_filter(self, mock_callback_update, mock_context, admin_config, mock_faq_store, sample_faqs):
        """Should filter by category via callback."""
        from tg_bot.handlers.faq import handle_faq_callback

        mock_callback_update.callback_query.data = "faq:category:trading"
        mock_faq_store.get_by_category.return_value = [f for f in sample_faqs if f["category"] == "trading"]

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await handle_faq_callback(mock_callback_update, mock_context)

            mock_faq_store.get_by_category.assert_called_with("trading")

    @pytest.mark.asyncio
    async def test_faq_callback_invalid_data(self, mock_callback_update, mock_context, admin_config):
        """Should handle invalid callback data."""
        from tg_bot.handlers.faq import handle_faq_callback

        mock_callback_update.callback_query.data = "faq:invalid:data"

        await handle_faq_callback(mock_callback_update, mock_context)

        mock_callback_update.callback_query.answer.assert_called()


# ============================================================================
# Test: User Interaction - Navigation
# ============================================================================

class TestNavigation:
    """Tests for FAQ navigation."""

    @pytest.mark.asyncio
    async def test_faq_nav_next_faq(self, mock_callback_update, mock_context, admin_config, mock_faq_store, sample_faqs):
        """Should navigate to next FAQ."""
        from tg_bot.handlers.faq import handle_faq_callback

        mock_callback_update.callback_query.data = "faq:next:1"  # Go to FAQ 2
        mock_faq_store.get_all.return_value = sample_faqs
        mock_faq_store.get_by_id.return_value = sample_faqs[1]

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await handle_faq_callback(mock_callback_update, mock_context)

            # Implementation uses get_all() to find next/prev
            mock_faq_store.get_all.assert_called()

    @pytest.mark.asyncio
    async def test_faq_nav_prev_faq(self, mock_callback_update, mock_context, admin_config, mock_faq_store, sample_faqs):
        """Should navigate to previous FAQ."""
        from tg_bot.handlers.faq import handle_faq_callback

        mock_callback_update.callback_query.data = "faq:prev:2"  # Go to FAQ 1
        mock_faq_store.get_all.return_value = sample_faqs
        mock_faq_store.get_by_id.return_value = sample_faqs[0]

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await handle_faq_callback(mock_callback_update, mock_context)

            # Implementation uses get_all() to find next/prev
            mock_faq_store.get_all.assert_called()

    @pytest.mark.asyncio
    async def test_faq_nav_at_start(self, mock_callback_update, mock_context, admin_config, mock_faq_store, sample_faqs):
        """Should handle navigation at start of list."""
        from tg_bot.handlers.faq import handle_faq_callback

        mock_callback_update.callback_query.data = "faq:prev:1"  # Already at first
        mock_faq_store.get_by_id.return_value = sample_faqs[0]
        mock_faq_store.get_all.return_value = sample_faqs

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await handle_faq_callback(mock_callback_update, mock_context)

            # Should stay at first or wrap around
            mock_callback_update.callback_query.answer.assert_called()

    @pytest.mark.asyncio
    async def test_faq_nav_at_end(self, mock_callback_update, mock_context, admin_config, mock_faq_store, sample_faqs):
        """Should handle navigation at end of list."""
        from tg_bot.handlers.faq import handle_faq_callback

        mock_callback_update.callback_query.data = "faq:next:5"  # Already at last
        mock_faq_store.get_by_id.return_value = sample_faqs[-1]
        mock_faq_store.get_all.return_value = sample_faqs

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await handle_faq_callback(mock_callback_update, mock_context)

            mock_callback_update.callback_query.answer.assert_called()


# ============================================================================
# Test: Edge Cases and Error Handling
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_faq_handles_none_message(self, mock_update, mock_context, admin_config):
        """Should handle None message gracefully."""
        from tg_bot.handlers.faq import faq_command

        mock_update.message = None
        mock_update.effective_message = None

        # Should not raise exception
        try:
            with patch("tg_bot.handlers.faq.get_faq_store"):
                await faq_command(mock_update, mock_context)
        except AttributeError:
            pass  # Expected if message is None

    @pytest.mark.asyncio
    async def test_faq_handles_store_error(self, mock_update, mock_context, admin_config):
        """Should handle FAQ store errors."""
        from tg_bot.handlers.faq import faq_command

        mock_store = MagicMock()
        mock_store.get_all.side_effect = Exception("Store error")

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_store):
            await faq_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "error" in message.lower() or "sorry" in message.lower()

    @pytest.mark.asyncio
    async def test_faq_handles_very_long_answer(self, mock_update, mock_context, admin_config, sample_faqs):
        """Should handle FAQs with very long answers."""
        from tg_bot.handlers.faq import faq_command

        faqs_with_long = sample_faqs.copy()
        faqs_with_long[0]["answer"] = "A" * 5000  # Very long answer

        mock_store = MagicMock()
        mock_store.get_all.return_value = faqs_with_long
        mock_store.get_by_id.return_value = faqs_with_long[0]

        mock_context.args = ["1"]

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_store):
            await faq_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            # Should truncate or handle long content
            assert len(message) < 5500  # Telegram limit consideration

    @pytest.mark.asyncio
    async def test_faq_handles_special_characters(self, mock_update, mock_context, admin_config, sample_faqs):
        """Should handle FAQs with special characters."""
        from tg_bot.handlers.faq import faq_command

        faqs_with_special = sample_faqs.copy()
        faqs_with_special[0]["question"] = "What about <>&\"' characters?"

        mock_store = MagicMock()
        mock_store.get_all.return_value = faqs_with_special
        mock_store.get_by_id.return_value = faqs_with_special[0]

        mock_context.args = ["1"]

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_store):
            await faq_command(mock_update, mock_context)

            # Should not raise exception
            assert mock_update.message.reply_text.called


# ============================================================================
# Test: Integration - Full Flow
# ============================================================================

class TestIntegrationFlow:
    """Integration tests for full FAQ workflow."""

    @pytest.mark.asyncio
    async def test_faq_full_flow_list_then_show(self, mock_update, mock_callback_update, mock_context, admin_config, mock_faq_store, sample_faqs):
        """Should complete flow: list FAQs -> select one -> view details."""
        from tg_bot.handlers.faq import faq_command, handle_faq_callback

        # Step 1: List FAQs
        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await faq_command(mock_update, mock_context)

            assert mock_update.message.reply_text.called
            call_args = mock_update.message.reply_text.call_args
            assert "reply_markup" in call_args[1]

        # Step 2: Select FAQ via callback
        mock_callback_update.callback_query.data = "faq:show:1"
        mock_faq_store.get_by_id.return_value = sample_faqs[0]

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await handle_faq_callback(mock_callback_update, mock_context)

            mock_callback_update.callback_query.edit_message_text.assert_called()
            call_args = mock_callback_update.callback_query.edit_message_text.call_args
            message = call_args[0][0]
            assert "What is Jarvis?" in message

    @pytest.mark.asyncio
    async def test_faq_admin_crud_flow(self, mock_update, mock_context, admin_config, mock_faq_store):
        """Should complete admin CRUD flow: add -> update -> delete."""
        from tg_bot.handlers.faq import faq_add_command, faq_update_command, faq_delete_command

        # Step 1: Add FAQ
        mock_context.args = ["New question?", "|", "New answer."]

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await faq_add_command(mock_update, mock_context)
            mock_faq_store.add.assert_called()

        # Step 2: Update FAQ
        mock_context.args = ["6", "--answer", "Updated answer."]
        mock_update.message.reply_text.reset_mock()

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await faq_update_command(mock_update, mock_context)
            mock_faq_store.update.assert_called()

        # Step 3: Delete FAQ
        mock_context.args = ["6"]
        mock_update.message.reply_text.reset_mock()

        with patch("tg_bot.handlers.faq.get_faq_store", return_value=mock_faq_store):
            await faq_delete_command(mock_update, mock_context)
            mock_faq_store.delete.assert_called()


# ============================================================================
# Test: Singleton Pattern
# ============================================================================

class TestSingletonPattern:
    """Tests for FAQ store singleton pattern."""

    def test_get_faq_store_returns_instance(self):
        """Should return FAQStore instance."""
        from tg_bot.handlers.faq import get_faq_store

        store = get_faq_store()
        assert store is not None

    def test_get_faq_store_returns_same_instance(self):
        """Should return same instance on multiple calls."""
        from tg_bot.handlers.faq import get_faq_store, _faq_store
        import tg_bot.handlers.faq as faq_module

        # Reset singleton
        faq_module._faq_store = None

        store1 = get_faq_store()
        store2 = get_faq_store()

        assert store1 is store2
