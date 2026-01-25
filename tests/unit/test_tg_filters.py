"""
Unit tests for tg_bot/filters.py - Custom Telegram Bot Filters.

Covers:
- Base filter classes
- Admin filters
- Chat type filters (private, group, supergroup, channel)
- Command filters
- Content pattern filters (regex, contains, starts/ends with)
- Token/address filters
- User filters
- Mention filters
- Spam detection filters
- Rate limiting filters
- Media type filters
- Composite filters (AND, OR, NOT)
- Callback filter
- Factory functions

Test Categories:
1. Message filters - Filter based on message content
2. User filters - Filter based on sender
3. Chat type filters - Filter based on chat type
4. Command filters - Filter commands
5. Custom filters - Regex, callbacks, composites
"""

import pytest
import re
import time
from unittest.mock import Mock, MagicMock, patch
from typing import Set

# Import module under test
from tg_bot.filters import (
    # Base classes
    BaseMessageFilter,
    BaseUpdateFilter,
    # Admin filters
    AdminFilter,
    AdminOrOwnerFilter,
    # Chat type filters
    PrivateChatFilter,
    GroupChatFilter,
    SupergroupFilter,
    AnyGroupFilter,
    ChannelFilter,
    SpecificChatFilter,
    # Command filters
    CommandPrefixFilter,
    SpecificCommandFilter,
    NotCommandFilter,
    # Content filters
    RegexFilter,
    ContainsTextFilter,
    StartsWithFilter,
    EndsWithFilter,
    # Token filters
    TokenAddressFilter,
    TokenTickerFilter,
    TokenMentionFilter,
    SOLANA_ADDRESS_PATTERN,
    TOKEN_TICKER_PATTERN,
    # User filters
    SpecificUserFilter,
    UsernameFilter,
    BotFilter,
    NotBotFilter,
    # Mention filters
    BotMentionFilter,
    ReplyToBotFilter,
    # Spam filters
    SpamFilter,
    NotSpamFilter,
    SpamConfig,
    # Rate limit filters
    RateLimitFilter,
    RateLimitConfig,
    # Media filters
    MediaFilter,
    PhotoFilter,
    VideoFilter,
    DocumentFilter,
    AnimationFilter,
    StickerFilter,
    VoiceFilter,
    NoMediaFilter,
    # Composite filters
    AndFilter,
    OrFilter,
    NotFilter,
    CallbackFilter,
    # Factory functions
    create_admin_filter,
    create_chat_filter,
    create_user_filter,
    create_command_filter,
    create_regex_filter,
    create_rate_limit_filter,
    # Module-level instances
    PRIVATE_CHAT,
    GROUP_CHAT,
    SUPERGROUP,
    ANY_GROUP,
    CHANNEL,
    HAS_TEXT,
    HAS_MEDIA,
    IS_COMMAND,
    NOT_COMMAND,
    FROM_BOT,
    FROM_HUMAN,
    HAS_TOKEN_ADDRESS,
    HAS_TOKEN_TICKER,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_message():
    """Create a mock Telegram Message."""
    message = Mock()
    message.text = "Hello, world!"
    message.from_user = Mock()
    message.from_user.id = 12345
    message.from_user.username = "testuser"
    message.from_user.is_bot = False
    message.chat = Mock()
    message.chat.id = 67890
    message.chat.type = "private"
    message.photo = None
    message.video = None
    message.audio = None
    message.document = None
    message.animation = None
    message.sticker = None
    message.voice = None
    message.video_note = None
    message.entities = []
    message.reply_to_message = None
    return message


@pytest.fixture
def mock_group_message(mock_message):
    """Create a mock message from a group chat."""
    mock_message.chat.type = "group"
    mock_message.chat.id = -100123456
    return mock_message


@pytest.fixture
def mock_supergroup_message(mock_message):
    """Create a mock message from a supergroup."""
    mock_message.chat.type = "supergroup"
    mock_message.chat.id = -100123456789
    return mock_message


@pytest.fixture
def mock_channel_message(mock_message):
    """Create a mock message from a channel."""
    mock_message.chat.type = "channel"
    mock_message.chat.id = -100987654321
    return mock_message


@pytest.fixture
def mock_command_message(mock_message):
    """Create a mock command message."""
    mock_message.text = "/help"
    return mock_message


@pytest.fixture
def mock_admin_message(mock_message):
    """Create a mock message from an admin user."""
    mock_message.from_user.id = 999888777
    return mock_message


@pytest.fixture
def mock_bot_message(mock_message):
    """Create a mock message from a bot."""
    mock_message.from_user.is_bot = True
    return mock_message


@pytest.fixture
def mock_photo_message(mock_message):
    """Create a mock message with a photo."""
    mock_message.photo = [Mock()]  # Photo is a list of PhotoSize
    return mock_message


@pytest.fixture
def mock_update():
    """Create a mock Telegram Update."""
    update = Mock()
    update.message = Mock()
    update.message.text = "Hello"
    update.effective_user = Mock()
    update.effective_user.id = 12345
    return update


# ============================================================================
# Test: Base Filter Classes
# ============================================================================

class TestBaseFilterClasses:
    """Tests for base filter abstract classes."""

    def test_base_message_filter_name_property(self):
        """Base filter should have name property."""
        class TestFilter(BaseMessageFilter):
            def filter(self, message):
                return True

        f = TestFilter("CustomName")
        assert f.name == "CustomName"

    def test_base_message_filter_default_name(self):
        """Base filter should use class name as default."""
        class MyCustomFilter(BaseMessageFilter):
            def filter(self, message):
                return True

        f = MyCustomFilter()
        assert f.name == "MyCustomFilter"

    def test_base_update_filter_name_property(self):
        """Base update filter should have name property."""
        class TestUpdateFilter(BaseUpdateFilter):
            def filter(self, update):
                return True

        f = TestUpdateFilter("UpdateFilter")
        assert f.name == "UpdateFilter"


# ============================================================================
# Test: Admin Filters
# ============================================================================

class TestAdminFilter:
    """Tests for AdminFilter."""

    def test_admin_filter_allows_admin(self, mock_message):
        """Admin filter should allow admin users."""
        admin_filter = AdminFilter(admin_ids={12345})
        mock_message.from_user.id = 12345
        assert admin_filter.filter(mock_message) is True

    def test_admin_filter_blocks_non_admin(self, mock_message):
        """Admin filter should block non-admin users."""
        admin_filter = AdminFilter(admin_ids={999})
        mock_message.from_user.id = 12345
        assert admin_filter.filter(mock_message) is False

    def test_admin_filter_handles_no_user(self, mock_message):
        """Admin filter should handle missing user."""
        admin_filter = AdminFilter(admin_ids={12345})
        mock_message.from_user = None
        assert admin_filter.filter(mock_message) is False

    def test_admin_filter_multiple_admins(self, mock_message):
        """Admin filter should support multiple admin IDs."""
        admin_filter = AdminFilter(admin_ids={111, 222, 333})
        mock_message.from_user.id = 222
        assert admin_filter.filter(mock_message) is True

    def test_admin_filter_empty_admin_set(self, mock_message):
        """Admin filter with empty set should block all."""
        admin_filter = AdminFilter(admin_ids=set())
        assert admin_filter.filter(mock_message) is False

    def test_admin_filter_admin_ids_property(self):
        """Admin filter should expose admin_ids property."""
        admin_filter = AdminFilter(admin_ids={1, 2, 3})
        assert admin_filter.admin_ids == {1, 2, 3}

    def test_admin_filter_add_admin(self):
        """Should be able to add admin at runtime."""
        admin_filter = AdminFilter(admin_ids={1})
        admin_filter.add_admin(2)
        assert 2 in admin_filter.admin_ids

    def test_admin_filter_remove_admin(self):
        """Should be able to remove admin at runtime."""
        admin_filter = AdminFilter(admin_ids={1, 2})
        admin_filter.remove_admin(1)
        assert 1 not in admin_filter.admin_ids

    def test_admin_filter_loads_from_env(self):
        """Admin filter should load from environment."""
        with patch.dict('os.environ', {'TELEGRAM_ADMIN_IDS': '123,456,789'}):
            admin_filter = AdminFilter()
            assert 123 in admin_filter.admin_ids
            assert 456 in admin_filter.admin_ids
            assert 789 in admin_filter.admin_ids

    def test_admin_filter_handles_invalid_env(self):
        """Admin filter should handle invalid env values."""
        with patch.dict('os.environ', {'TELEGRAM_ADMIN_IDS': 'invalid,123,abc'}):
            admin_filter = AdminFilter()
            assert 123 in admin_filter.admin_ids
            assert len(admin_filter.admin_ids) == 1


class TestAdminOrOwnerFilter:
    """Tests for AdminOrOwnerFilter."""

    def test_admin_or_owner_allows_admin(self, mock_message):
        """Should allow admin users."""
        f = AdminOrOwnerFilter(admin_ids={12345})
        mock_message.from_user.id = 12345
        assert f.filter(mock_message) is True

    def test_admin_or_owner_blocks_non_admin(self, mock_message):
        """Should block non-admin in private chat."""
        f = AdminOrOwnerFilter(admin_ids={999})
        mock_message.from_user.id = 12345
        assert f.filter(mock_message) is False


# ============================================================================
# Test: Chat Type Filters
# ============================================================================

class TestChatTypeFilters:
    """Tests for chat type filters."""

    def test_private_chat_filter_passes_private(self, mock_message):
        """Private chat filter should pass private chats."""
        f = PrivateChatFilter()
        mock_message.chat.type = "private"
        assert f.filter(mock_message) is True

    def test_private_chat_filter_blocks_group(self, mock_group_message):
        """Private chat filter should block group chats."""
        f = PrivateChatFilter()
        assert f.filter(mock_group_message) is False

    def test_private_chat_filter_handles_no_chat(self, mock_message):
        """Private chat filter should handle missing chat."""
        f = PrivateChatFilter()
        mock_message.chat = None
        assert f.filter(mock_message) is False

    def test_group_chat_filter_passes_group(self, mock_group_message):
        """Group chat filter should pass group chats."""
        f = GroupChatFilter()
        assert f.filter(mock_group_message) is True

    def test_group_chat_filter_blocks_supergroup(self, mock_supergroup_message):
        """Group chat filter should block supergroups."""
        f = GroupChatFilter()
        assert f.filter(mock_supergroup_message) is False

    def test_group_chat_filter_blocks_private(self, mock_message):
        """Group chat filter should block private chats."""
        f = GroupChatFilter()
        assert f.filter(mock_message) is False

    def test_supergroup_filter_passes_supergroup(self, mock_supergroup_message):
        """Supergroup filter should pass supergroups."""
        f = SupergroupFilter()
        assert f.filter(mock_supergroup_message) is True

    def test_supergroup_filter_blocks_group(self, mock_group_message):
        """Supergroup filter should block regular groups."""
        f = SupergroupFilter()
        assert f.filter(mock_group_message) is False

    def test_any_group_filter_passes_group(self, mock_group_message):
        """Any group filter should pass regular groups."""
        f = AnyGroupFilter()
        assert f.filter(mock_group_message) is True

    def test_any_group_filter_passes_supergroup(self, mock_supergroup_message):
        """Any group filter should pass supergroups."""
        f = AnyGroupFilter()
        assert f.filter(mock_supergroup_message) is True

    def test_any_group_filter_blocks_private(self, mock_message):
        """Any group filter should block private chats."""
        f = AnyGroupFilter()
        assert f.filter(mock_message) is False

    def test_channel_filter_passes_channel(self, mock_channel_message):
        """Channel filter should pass channels."""
        f = ChannelFilter()
        assert f.filter(mock_channel_message) is True

    def test_channel_filter_blocks_group(self, mock_group_message):
        """Channel filter should block groups."""
        f = ChannelFilter()
        assert f.filter(mock_group_message) is False


class TestSpecificChatFilter:
    """Tests for SpecificChatFilter."""

    def test_specific_chat_single_id(self, mock_message):
        """Should filter by single chat ID."""
        f = SpecificChatFilter(67890)
        assert f.filter(mock_message) is True

    def test_specific_chat_set_of_ids(self, mock_message):
        """Should filter by set of chat IDs."""
        f = SpecificChatFilter({67890, 11111, 22222})
        assert f.filter(mock_message) is True

    def test_specific_chat_list_of_ids(self, mock_message):
        """Should filter by list of chat IDs."""
        f = SpecificChatFilter([67890, 11111])
        assert f.filter(mock_message) is True

    def test_specific_chat_blocks_unknown(self, mock_message):
        """Should block chats not in list."""
        f = SpecificChatFilter({11111, 22222})
        assert f.filter(mock_message) is False

    def test_specific_chat_add_chat(self):
        """Should add chat at runtime."""
        f = SpecificChatFilter({1})
        f.add_chat(2)
        assert 2 in f.chat_ids

    def test_specific_chat_remove_chat(self):
        """Should remove chat at runtime."""
        f = SpecificChatFilter({1, 2})
        f.remove_chat(1)
        assert 1 not in f.chat_ids

    def test_specific_chat_handles_no_chat(self, mock_message):
        """Should handle missing chat."""
        f = SpecificChatFilter({67890})
        mock_message.chat = None
        assert f.filter(mock_message) is False


# ============================================================================
# Test: Command Filters
# ============================================================================

class TestCommandFilters:
    """Tests for command filters."""

    def test_command_prefix_filter_default(self, mock_command_message):
        """Command prefix filter should detect / commands."""
        f = CommandPrefixFilter()
        assert f.filter(mock_command_message) is True

    def test_command_prefix_filter_non_command(self, mock_message):
        """Command prefix filter should reject non-commands."""
        f = CommandPrefixFilter()
        mock_message.text = "hello"
        assert f.filter(mock_message) is False

    def test_command_prefix_filter_custom_prefix(self, mock_message):
        """Should support custom prefix."""
        f = CommandPrefixFilter(prefix="!")
        mock_message.text = "!help"
        assert f.filter(mock_message) is True

    def test_command_prefix_filter_handles_no_text(self, mock_message):
        """Should handle messages without text."""
        f = CommandPrefixFilter()
        mock_message.text = None
        assert f.filter(mock_message) is False

    def test_command_prefix_property(self):
        """Should expose prefix property."""
        f = CommandPrefixFilter(prefix="!")
        assert f.prefix == "!"


class TestSpecificCommandFilter:
    """Tests for SpecificCommandFilter."""

    def test_specific_command_single(self, mock_command_message):
        """Should match single command."""
        f = SpecificCommandFilter("help")
        assert f.filter(mock_command_message) is True

    def test_specific_command_list(self, mock_command_message):
        """Should match from list of commands."""
        f = SpecificCommandFilter(["help", "start", "info"])
        assert f.filter(mock_command_message) is True

    def test_specific_command_case_insensitive(self, mock_message):
        """Should be case insensitive by default."""
        f = SpecificCommandFilter("HELP")
        mock_message.text = "/help"
        assert f.filter(mock_message) is True

    def test_specific_command_case_sensitive(self, mock_message):
        """Should support case sensitive matching."""
        f = SpecificCommandFilter("Help", case_sensitive=True)
        mock_message.text = "/help"
        assert f.filter(mock_message) is False

    def test_specific_command_with_args(self, mock_message):
        """Should match command with arguments."""
        f = SpecificCommandFilter("analyze")
        mock_message.text = "/analyze SOL"
        assert f.filter(mock_message) is True

    def test_specific_command_with_bot_mention(self, mock_message):
        """Should match command with @botname."""
        f = SpecificCommandFilter("help")
        mock_message.text = "/help@JarvisBot"
        assert f.filter(mock_message) is True

    def test_specific_command_no_match(self, mock_message):
        """Should not match different command."""
        f = SpecificCommandFilter("help")
        mock_message.text = "/start"
        assert f.filter(mock_message) is False

    def test_specific_command_not_a_command(self, mock_message):
        """Should not match non-command text."""
        f = SpecificCommandFilter("help")
        mock_message.text = "help me"
        assert f.filter(mock_message) is False

    def test_specific_command_commands_property(self):
        """Should expose commands property."""
        f = SpecificCommandFilter(["help", "start"])
        assert "help" in f.commands
        assert "start" in f.commands


class TestNotCommandFilter:
    """Tests for NotCommandFilter."""

    def test_not_command_passes_text(self, mock_message):
        """Should pass regular text messages."""
        f = NotCommandFilter()
        mock_message.text = "Hello world"
        assert f.filter(mock_message) is True

    def test_not_command_blocks_command(self, mock_command_message):
        """Should block command messages."""
        f = NotCommandFilter()
        assert f.filter(mock_command_message) is False

    def test_not_command_handles_no_text(self, mock_message):
        """Should pass messages without text."""
        f = NotCommandFilter()
        mock_message.text = None
        assert f.filter(mock_message) is True


# ============================================================================
# Test: Content Pattern Filters
# ============================================================================

class TestRegexFilter:
    """Tests for RegexFilter."""

    def test_regex_filter_matches(self, mock_message):
        """Should match regex pattern."""
        f = RegexFilter(r"Hello.*world")
        mock_message.text = "Hello, beautiful world!"
        assert f.filter(mock_message) is True

    def test_regex_filter_no_match(self, mock_message):
        """Should not match when pattern absent."""
        f = RegexFilter(r"goodbye")
        mock_message.text = "Hello world"
        assert f.filter(mock_message) is False

    def test_regex_filter_with_flags(self, mock_message):
        """Should support regex flags."""
        f = RegexFilter(r"HELLO", re.IGNORECASE)
        mock_message.text = "hello"
        assert f.filter(mock_message) is True

    def test_regex_filter_compiled_pattern(self, mock_message):
        """Should accept compiled patterns."""
        pattern = re.compile(r"test\d+")
        f = RegexFilter(pattern)
        mock_message.text = "test123"
        assert f.filter(mock_message) is True

    def test_regex_filter_handles_no_text(self, mock_message):
        """Should handle missing text."""
        f = RegexFilter(r"test")
        mock_message.text = None
        assert f.filter(mock_message) is False

    def test_regex_filter_pattern_property(self):
        """Should expose pattern property."""
        f = RegexFilter(r"test")
        assert f.pattern.pattern == "test"


class TestContainsTextFilter:
    """Tests for ContainsTextFilter."""

    def test_contains_text_matches(self, mock_message):
        """Should match contained text."""
        f = ContainsTextFilter("world")
        mock_message.text = "Hello world"
        assert f.filter(mock_message) is True

    def test_contains_text_case_insensitive(self, mock_message):
        """Should be case insensitive by default."""
        f = ContainsTextFilter("HELLO")
        mock_message.text = "hello there"
        assert f.filter(mock_message) is True

    def test_contains_text_case_sensitive(self, mock_message):
        """Should support case sensitive matching."""
        f = ContainsTextFilter("Hello", case_sensitive=True)
        mock_message.text = "hello there"
        assert f.filter(mock_message) is False

    def test_contains_text_no_match(self, mock_message):
        """Should not match when text absent."""
        f = ContainsTextFilter("goodbye")
        mock_message.text = "Hello world"
        assert f.filter(mock_message) is False

    def test_contains_text_handles_no_text(self, mock_message):
        """Should handle missing text."""
        f = ContainsTextFilter("test")
        mock_message.text = None
        assert f.filter(mock_message) is False

    def test_contains_text_search_text_property(self):
        """Should expose search_text property."""
        f = ContainsTextFilter("test")
        assert f.search_text == "test"


class TestStartsWithFilter:
    """Tests for StartsWithFilter."""

    def test_starts_with_matches(self, mock_message):
        """Should match starting text."""
        f = StartsWithFilter("Hello")
        mock_message.text = "Hello, world!"
        assert f.filter(mock_message) is True

    def test_starts_with_case_insensitive(self, mock_message):
        """Should be case insensitive by default."""
        f = StartsWithFilter("HELLO")
        mock_message.text = "hello there"
        assert f.filter(mock_message) is True

    def test_starts_with_case_sensitive(self, mock_message):
        """Should support case sensitive matching."""
        f = StartsWithFilter("Hello", case_sensitive=True)
        mock_message.text = "hello there"
        assert f.filter(mock_message) is False

    def test_starts_with_no_match(self, mock_message):
        """Should not match when text doesn't start with prefix."""
        f = StartsWithFilter("Goodbye")
        mock_message.text = "Hello world"
        assert f.filter(mock_message) is False

    def test_starts_with_prefix_property(self):
        """Should expose prefix property."""
        f = StartsWithFilter("test")
        assert f.prefix == "test"


class TestEndsWithFilter:
    """Tests for EndsWithFilter."""

    def test_ends_with_matches(self, mock_message):
        """Should match ending text."""
        f = EndsWithFilter("world!")
        mock_message.text = "Hello, world!"
        assert f.filter(mock_message) is True

    def test_ends_with_case_insensitive(self, mock_message):
        """Should be case insensitive by default."""
        f = EndsWithFilter("WORLD")
        mock_message.text = "Hello world"
        assert f.filter(mock_message) is True

    def test_ends_with_case_sensitive(self, mock_message):
        """Should support case sensitive matching."""
        f = EndsWithFilter("World", case_sensitive=True)
        mock_message.text = "Hello world"
        assert f.filter(mock_message) is False

    def test_ends_with_no_match(self, mock_message):
        """Should not match when text doesn't end with suffix."""
        f = EndsWithFilter("goodbye")
        mock_message.text = "Hello world"
        assert f.filter(mock_message) is False


# ============================================================================
# Test: Token/Address Filters
# ============================================================================

class TestTokenAddressFilter:
    """Tests for TokenAddressFilter."""

    def test_token_address_matches_32_char(self, mock_message):
        """Should match 32-char base58 address."""
        f = TokenAddressFilter()
        mock_message.text = "Check out 11111111111111111111111111111112"
        assert f.filter(mock_message) is True

    def test_token_address_matches_44_char(self, mock_message):
        """Should match 44-char base58 address."""
        f = TokenAddressFilter()
        mock_message.text = "So11111111111111111111111111111111111111111112"
        assert f.filter(mock_message) is True

    def test_token_address_no_match(self, mock_message):
        """Should not match text without addresses."""
        f = TokenAddressFilter()
        mock_message.text = "Hello world"
        assert f.filter(mock_message) is False

    def test_token_address_extract_addresses(self, mock_message):
        """Should extract multiple addresses."""
        f = TokenAddressFilter()
        mock_message.text = "Compare 11111111111111111111111111111112 with 22222222222222222222222222222223"
        addresses = f.extract_addresses(mock_message)
        assert len(addresses) == 2

    def test_token_address_handles_no_text(self, mock_message):
        """Should handle missing text."""
        f = TokenAddressFilter()
        mock_message.text = None
        assert f.filter(mock_message) is False

    def test_solana_pattern_rejects_invalid(self):
        """Pattern should reject invalid characters."""
        # 0, O, I, l are not in base58
        assert SOLANA_ADDRESS_PATTERN.search("0" * 32) is None


class TestTokenTickerFilter:
    """Tests for TokenTickerFilter."""

    def test_token_ticker_matches_dollar_symbol(self, mock_message):
        """Should match $SYMBOL format."""
        f = TokenTickerFilter()
        mock_message.text = "Buy $SOL now!"
        assert f.filter(mock_message) is True

    def test_token_ticker_matches_various_lengths(self, mock_message):
        """Should match tickers 2-10 chars."""
        f = TokenTickerFilter()
        mock_message.text = "$BTC and $ETHEREUM"
        assert f.filter(mock_message) is True

    def test_token_ticker_no_match(self, mock_message):
        """Should not match text without tickers."""
        f = TokenTickerFilter()
        mock_message.text = "Hello world"
        assert f.filter(mock_message) is False

    def test_token_ticker_extract_tickers(self, mock_message):
        """Should extract multiple tickers."""
        f = TokenTickerFilter()
        mock_message.text = "Compare $SOL with $ETH and $BTC"
        tickers = f.extract_tickers(mock_message)
        assert len(tickers) == 3
        assert "$SOL" in tickers


class TestTokenMentionFilter:
    """Tests for TokenMentionFilter."""

    def test_token_mention_matches_address(self, mock_message):
        """Should match token addresses."""
        f = TokenMentionFilter()
        mock_message.text = "Check 11111111111111111111111111111112"
        assert f.filter(mock_message) is True

    def test_token_mention_matches_ticker(self, mock_message):
        """Should match token tickers."""
        f = TokenMentionFilter()
        mock_message.text = "Buy $SOL"
        assert f.filter(mock_message) is True

    def test_token_mention_matches_both(self, mock_message):
        """Should match when both present."""
        f = TokenMentionFilter()
        mock_message.text = "$SOL is 11111111111111111111111111111112"
        assert f.filter(mock_message) is True

    def test_token_mention_no_match(self, mock_message):
        """Should not match regular text."""
        f = TokenMentionFilter()
        mock_message.text = "Hello world"
        assert f.filter(mock_message) is False


# ============================================================================
# Test: User Filters
# ============================================================================

class TestSpecificUserFilter:
    """Tests for SpecificUserFilter."""

    def test_specific_user_single_id(self, mock_message):
        """Should filter by single user ID."""
        f = SpecificUserFilter(12345)
        assert f.filter(mock_message) is True

    def test_specific_user_set_of_ids(self, mock_message):
        """Should filter by set of user IDs."""
        f = SpecificUserFilter({12345, 11111, 22222})
        assert f.filter(mock_message) is True

    def test_specific_user_blocks_unknown(self, mock_message):
        """Should block users not in list."""
        f = SpecificUserFilter({11111, 22222})
        assert f.filter(mock_message) is False

    def test_specific_user_add_user(self):
        """Should add user at runtime."""
        f = SpecificUserFilter({1})
        f.add_user(2)
        assert 2 in f.user_ids

    def test_specific_user_remove_user(self):
        """Should remove user at runtime."""
        f = SpecificUserFilter({1, 2})
        f.remove_user(1)
        assert 1 not in f.user_ids

    def test_specific_user_handles_no_user(self, mock_message):
        """Should handle missing user."""
        f = SpecificUserFilter({12345})
        mock_message.from_user = None
        assert f.filter(mock_message) is False


class TestUsernameFilter:
    """Tests for UsernameFilter."""

    def test_username_filter_matches(self, mock_message):
        """Should match username."""
        f = UsernameFilter("testuser")
        assert f.filter(mock_message) is True

    def test_username_filter_strips_at(self, mock_message):
        """Should strip @ prefix."""
        f = UsernameFilter("@testuser")
        assert f.filter(mock_message) is True

    def test_username_filter_case_insensitive(self, mock_message):
        """Should be case insensitive by default."""
        f = UsernameFilter("TESTUSER")
        assert f.filter(mock_message) is True

    def test_username_filter_case_sensitive(self, mock_message):
        """Should support case sensitive matching."""
        f = UsernameFilter("TESTUSER", case_sensitive=True)
        assert f.filter(mock_message) is False

    def test_username_filter_multiple(self, mock_message):
        """Should filter by multiple usernames."""
        f = UsernameFilter(["testuser", "admin", "mod"])
        assert f.filter(mock_message) is True

    def test_username_filter_no_username(self, mock_message):
        """Should handle user without username."""
        f = UsernameFilter("testuser")
        mock_message.from_user.username = None
        assert f.filter(mock_message) is False


class TestBotFilter:
    """Tests for BotFilter."""

    def test_bot_filter_allows_bots(self, mock_bot_message):
        """Should pass bot messages when configured."""
        f = BotFilter(allow_bots=True)
        assert f.filter(mock_bot_message) is True

    def test_bot_filter_blocks_humans(self, mock_message):
        """Should block human messages when allow_bots=True."""
        f = BotFilter(allow_bots=True)
        assert f.filter(mock_message) is False

    def test_bot_filter_inverted(self, mock_message):
        """Should pass humans when allow_bots=False."""
        f = BotFilter(allow_bots=False)
        assert f.filter(mock_message) is True

    def test_bot_filter_inverted_blocks_bots(self, mock_bot_message):
        """Should block bots when allow_bots=False."""
        f = BotFilter(allow_bots=False)
        assert f.filter(mock_bot_message) is False


class TestNotBotFilter:
    """Tests for NotBotFilter."""

    def test_not_bot_filter_passes_humans(self, mock_message):
        """Should pass human messages."""
        f = NotBotFilter()
        assert f.filter(mock_message) is True

    def test_not_bot_filter_blocks_bots(self, mock_bot_message):
        """Should block bot messages."""
        f = NotBotFilter()
        assert f.filter(mock_bot_message) is False


# ============================================================================
# Test: Mention Filters
# ============================================================================

class TestBotMentionFilter:
    """Tests for BotMentionFilter."""

    def test_bot_mention_matches(self, mock_message):
        """Should match @botname mention."""
        f = BotMentionFilter("JarvisBot")
        mock_message.text = "Hey @JarvisBot help me"
        assert f.filter(mock_message) is True

    def test_bot_mention_case_insensitive(self, mock_message):
        """Should match case insensitively."""
        f = BotMentionFilter("JarvisBot")
        mock_message.text = "Hey @jarvisbot help me"
        assert f.filter(mock_message) is True

    def test_bot_mention_no_match(self, mock_message):
        """Should not match when bot not mentioned."""
        f = BotMentionFilter("JarvisBot")
        mock_message.text = "Hello world"
        assert f.filter(mock_message) is False

    def test_bot_mention_empty_username(self, mock_message):
        """Should return False if no bot username set."""
        f = BotMentionFilter("")
        mock_message.text = "@JarvisBot help"
        assert f.filter(mock_message) is False

    def test_bot_mention_set_username(self):
        """Should allow setting username at runtime."""
        f = BotMentionFilter()
        f.set_bot_username("@NewBot")
        assert f.bot_username == "NewBot"


class TestReplyToBotFilter:
    """Tests for ReplyToBotFilter."""

    def test_reply_to_bot_matches(self, mock_message):
        """Should match replies to bot."""
        f = ReplyToBotFilter(bot_id=999)
        mock_message.reply_to_message = Mock()
        mock_message.reply_to_message.from_user = Mock()
        mock_message.reply_to_message.from_user.id = 999
        assert f.filter(mock_message) is True

    def test_reply_to_bot_no_reply(self, mock_message):
        """Should not match non-reply messages."""
        f = ReplyToBotFilter(bot_id=999)
        mock_message.reply_to_message = None
        assert f.filter(mock_message) is False

    def test_reply_to_bot_reply_to_other(self, mock_message):
        """Should not match replies to other users."""
        f = ReplyToBotFilter(bot_id=999)
        mock_message.reply_to_message = Mock()
        mock_message.reply_to_message.from_user = Mock()
        mock_message.reply_to_message.from_user.id = 123
        assert f.filter(mock_message) is False

    def test_reply_to_bot_no_bot_id(self, mock_message):
        """Should return False if no bot ID set."""
        f = ReplyToBotFilter()
        mock_message.reply_to_message = Mock()
        mock_message.reply_to_message.from_user = Mock()
        mock_message.reply_to_message.from_user.id = 999
        assert f.filter(mock_message) is False

    def test_reply_to_bot_set_id(self):
        """Should allow setting bot ID at runtime."""
        f = ReplyToBotFilter()
        f.set_bot_id(123)
        assert f.bot_id == 123


# ============================================================================
# Test: Spam Detection Filters
# ============================================================================

class TestSpamFilter:
    """Tests for SpamFilter."""

    def test_spam_filter_detects_emoji_spam(self, mock_message):
        """Should detect excessive emojis."""
        f = SpamFilter(SpamConfig(max_emojis=5))
        mock_message.text = "Check this out!!!"
        assert f.filter(mock_message) is True

    def test_spam_filter_allows_few_emojis(self, mock_message):
        """Should allow reasonable emoji count."""
        f = SpamFilter(SpamConfig(max_emojis=10))
        mock_message.text = "Great job!"
        assert f.filter(mock_message) is False

    def test_spam_filter_detects_caps(self, mock_message):
        """Should detect excessive caps."""
        f = SpamFilter(SpamConfig(max_caps_ratio=0.5, min_caps_length=10))
        mock_message.text = "THIS IS ALL CAPS MESSAGE"
        assert f.filter(mock_message) is True

    def test_spam_filter_allows_normal_caps(self, mock_message):
        """Should allow normal capitalization."""
        f = SpamFilter(SpamConfig(max_caps_ratio=0.7, min_caps_length=20))
        mock_message.text = "Hello World"
        assert f.filter(mock_message) is False

    def test_spam_filter_detects_blocked_pattern(self, mock_message):
        """Should detect blocked patterns."""
        f = SpamFilter(SpamConfig(blocked_patterns=["free money"]))
        mock_message.text = "Get free money now!"
        assert f.filter(mock_message) is True

    def test_spam_filter_detects_suspicious_url(self, mock_message):
        """Should detect suspicious URLs."""
        f = SpamFilter(SpamConfig(suspicious_urls=["bit.ly"]))
        mock_message.text = "Check out bit.ly/abc123"
        assert f.filter(mock_message) is True

    def test_spam_filter_allows_normal_message(self, mock_message):
        """Should allow normal messages."""
        f = SpamFilter()
        mock_message.text = "Hello, how are you doing today?"
        assert f.filter(mock_message) is False

    def test_spam_filter_handles_no_text(self, mock_message):
        """Should handle missing text."""
        f = SpamFilter()
        mock_message.text = None
        assert f.filter(mock_message) is False

    def test_spam_filter_config_property(self):
        """Should expose config property."""
        config = SpamConfig(max_emojis=20)
        f = SpamFilter(config)
        assert f.config.max_emojis == 20


class TestNotSpamFilter:
    """Tests for NotSpamFilter."""

    def test_not_spam_passes_normal(self, mock_message):
        """Should pass normal messages."""
        f = NotSpamFilter()
        mock_message.text = "Hello world"
        assert f.filter(mock_message) is True

    def test_not_spam_blocks_spam(self, mock_message):
        """Should block spam messages."""
        f = NotSpamFilter(SpamConfig(blocked_patterns=["spam"]))
        mock_message.text = "This is spam content"
        assert f.filter(mock_message) is False


# ============================================================================
# Test: Rate Limiting Filters
# ============================================================================

class TestRateLimitFilter:
    """Tests for RateLimitFilter."""

    def test_rate_limit_allows_first_message(self, mock_message):
        """Should allow first message."""
        f = RateLimitFilter(RateLimitConfig(messages_per_window=5, window_seconds=60))
        assert f.filter(mock_message) is True

    def test_rate_limit_allows_within_limit(self, mock_message):
        """Should allow messages within limit."""
        f = RateLimitFilter(RateLimitConfig(messages_per_window=3, window_seconds=60))
        assert f.filter(mock_message) is True
        assert f.filter(mock_message) is True
        assert f.filter(mock_message) is True

    def test_rate_limit_blocks_over_limit(self, mock_message):
        """Should block messages over limit."""
        f = RateLimitFilter(RateLimitConfig(messages_per_window=2, window_seconds=60))
        assert f.filter(mock_message) is True
        assert f.filter(mock_message) is True
        assert f.filter(mock_message) is False  # Over limit

    def test_rate_limit_per_user(self, mock_message):
        """Should track per user when configured."""
        f = RateLimitFilter(RateLimitConfig(messages_per_window=1, window_seconds=60, per_user=True))
        assert f.filter(mock_message) is True
        assert f.filter(mock_message) is False

        # Different user should be allowed
        mock_message.from_user.id = 99999
        assert f.filter(mock_message) is True

    def test_rate_limit_per_chat(self, mock_message):
        """Should track per chat when configured."""
        f = RateLimitFilter(RateLimitConfig(messages_per_window=1, window_seconds=60, per_user=False, per_chat=True))
        assert f.filter(mock_message) is True
        assert f.filter(mock_message) is False

        # Different chat should be allowed
        mock_message.chat.id = 99999
        assert f.filter(mock_message) is True

    def test_rate_limit_reset(self, mock_message):
        """Should reset rate limit tracking."""
        f = RateLimitFilter(RateLimitConfig(messages_per_window=1, window_seconds=60))
        assert f.filter(mock_message) is True
        assert f.filter(mock_message) is False
        f.reset()
        assert f.filter(mock_message) is True

    def test_rate_limit_config_property(self):
        """Should expose config property."""
        config = RateLimitConfig(messages_per_window=10)
        f = RateLimitFilter(config)
        assert f.config.messages_per_window == 10


# ============================================================================
# Test: Media Type Filters
# ============================================================================

class TestMediaFilter:
    """Tests for MediaFilter."""

    def test_media_filter_detects_photo(self, mock_photo_message):
        """Should detect photo messages."""
        f = MediaFilter()
        assert f.filter(mock_photo_message) is True

    def test_media_filter_detects_video(self, mock_message):
        """Should detect video messages."""
        f = MediaFilter()
        mock_message.video = Mock()
        assert f.filter(mock_message) is True

    def test_media_filter_detects_document(self, mock_message):
        """Should detect document messages."""
        f = MediaFilter()
        mock_message.document = Mock()
        assert f.filter(mock_message) is True

    def test_media_filter_detects_sticker(self, mock_message):
        """Should detect sticker messages."""
        f = MediaFilter()
        mock_message.sticker = Mock()
        assert f.filter(mock_message) is True

    def test_media_filter_detects_animation(self, mock_message):
        """Should detect animation messages."""
        f = MediaFilter()
        mock_message.animation = Mock()
        assert f.filter(mock_message) is True

    def test_media_filter_no_media(self, mock_message):
        """Should not match text-only messages."""
        f = MediaFilter()
        assert f.filter(mock_message) is False

    def test_media_filter_selective(self, mock_message):
        """Should filter specific media types."""
        f = MediaFilter(photos=True, videos=False, documents=False, stickers=False, animations=False, audio=False, voice=False, video_notes=False)
        mock_message.video = Mock()
        assert f.filter(mock_message) is False

        mock_message.video = None
        mock_message.photo = [Mock()]
        assert f.filter(mock_message) is True


class TestSpecificMediaFilters:
    """Tests for specific media type filters."""

    def test_photo_filter(self, mock_photo_message, mock_message):
        """PhotoFilter should only match photos."""
        f = PhotoFilter()
        assert f.filter(mock_photo_message) is True
        assert f.filter(mock_message) is False

    def test_video_filter(self, mock_message):
        """VideoFilter should only match videos."""
        f = VideoFilter()
        assert f.filter(mock_message) is False
        mock_message.video = Mock()
        assert f.filter(mock_message) is True

    def test_document_filter(self, mock_message):
        """DocumentFilter should only match documents."""
        f = DocumentFilter()
        assert f.filter(mock_message) is False
        mock_message.document = Mock()
        assert f.filter(mock_message) is True

    def test_animation_filter(self, mock_message):
        """AnimationFilter should only match animations."""
        f = AnimationFilter()
        assert f.filter(mock_message) is False
        mock_message.animation = Mock()
        assert f.filter(mock_message) is True

    def test_sticker_filter(self, mock_message):
        """StickerFilter should only match stickers."""
        f = StickerFilter()
        assert f.filter(mock_message) is False
        mock_message.sticker = Mock()
        assert f.filter(mock_message) is True

    def test_voice_filter(self, mock_message):
        """VoiceFilter should only match voice messages."""
        f = VoiceFilter()
        assert f.filter(mock_message) is False
        mock_message.voice = Mock()
        assert f.filter(mock_message) is True


class TestNoMediaFilter:
    """Tests for NoMediaFilter."""

    def test_no_media_passes_text(self, mock_message):
        """Should pass text-only messages."""
        f = NoMediaFilter()
        assert f.filter(mock_message) is True

    def test_no_media_blocks_photo(self, mock_photo_message):
        """Should block photo messages."""
        f = NoMediaFilter()
        assert f.filter(mock_photo_message) is False

    def test_no_media_blocks_video(self, mock_message):
        """Should block video messages."""
        f = NoMediaFilter()
        mock_message.video = Mock()
        assert f.filter(mock_message) is False


# ============================================================================
# Test: Composite Filters
# ============================================================================

class TestAndFilter:
    """Tests for AndFilter."""

    def test_and_filter_all_pass(self, mock_message):
        """Should pass when all filters pass."""
        f1 = ContainsTextFilter("Hello")
        f2 = ContainsTextFilter("world")
        and_filter = AndFilter(f1, f2)
        mock_message.text = "Hello, world!"
        assert and_filter.filter(mock_message) is True

    def test_and_filter_one_fails(self, mock_message):
        """Should fail when any filter fails."""
        f1 = ContainsTextFilter("Hello")
        f2 = ContainsTextFilter("goodbye")
        and_filter = AndFilter(f1, f2)
        mock_message.text = "Hello, world!"
        assert and_filter.filter(mock_message) is False

    def test_and_filter_add_filter(self, mock_message):
        """Should support adding filters."""
        f1 = ContainsTextFilter("Hello")
        and_filter = AndFilter(f1)
        and_filter.add_filter(ContainsTextFilter("world"))
        mock_message.text = "Hello, world!"
        assert and_filter.filter(mock_message) is True

    def test_and_filter_empty(self, mock_message):
        """Empty AND filter should pass (vacuous truth)."""
        and_filter = AndFilter()
        assert and_filter.filter(mock_message) is True

    def test_and_filter_filters_property(self):
        """Should expose filters property."""
        f1 = ContainsTextFilter("test")
        and_filter = AndFilter(f1)
        assert len(and_filter.filters) == 1


class TestOrFilter:
    """Tests for OrFilter."""

    def test_or_filter_one_passes(self, mock_message):
        """Should pass when any filter passes."""
        f1 = ContainsTextFilter("Hello")
        f2 = ContainsTextFilter("goodbye")
        or_filter = OrFilter(f1, f2)
        mock_message.text = "Hello, world!"
        assert or_filter.filter(mock_message) is True

    def test_or_filter_all_fail(self, mock_message):
        """Should fail when all filters fail."""
        f1 = ContainsTextFilter("foo")
        f2 = ContainsTextFilter("bar")
        or_filter = OrFilter(f1, f2)
        mock_message.text = "Hello, world!"
        assert or_filter.filter(mock_message) is False

    def test_or_filter_add_filter(self, mock_message):
        """Should support adding filters."""
        f1 = ContainsTextFilter("foo")
        or_filter = OrFilter(f1)
        or_filter.add_filter(ContainsTextFilter("Hello"))
        mock_message.text = "Hello, world!"
        assert or_filter.filter(mock_message) is True

    def test_or_filter_empty(self, mock_message):
        """Empty OR filter should fail (vacuous false)."""
        or_filter = OrFilter()
        assert or_filter.filter(mock_message) is False


class TestNotFilter:
    """Tests for NotFilter."""

    def test_not_filter_inverts_true(self, mock_message):
        """Should invert True to False."""
        inner = ContainsTextFilter("Hello")
        not_filter = NotFilter(inner)
        mock_message.text = "Hello, world!"
        assert not_filter.filter(mock_message) is False

    def test_not_filter_inverts_false(self, mock_message):
        """Should invert False to True."""
        inner = ContainsTextFilter("goodbye")
        not_filter = NotFilter(inner)
        mock_message.text = "Hello, world!"
        assert not_filter.filter(mock_message) is True

    def test_not_filter_inner_property(self):
        """Should expose inner_filter property."""
        inner = ContainsTextFilter("test")
        not_filter = NotFilter(inner)
        assert not_filter.inner_filter is inner


# ============================================================================
# Test: Callback Filter
# ============================================================================

class TestCallbackFilter:
    """Tests for CallbackFilter."""

    def test_callback_filter_returns_true(self, mock_message):
        """Should call callback and return result."""
        f = CallbackFilter(lambda m: True)
        assert f.filter(mock_message) is True

    def test_callback_filter_returns_false(self, mock_message):
        """Should call callback and return result."""
        f = CallbackFilter(lambda m: False)
        assert f.filter(mock_message) is False

    def test_callback_filter_receives_message(self, mock_message):
        """Callback should receive message object."""
        received = []
        def callback(m):
            received.append(m)
            return True

        f = CallbackFilter(callback)
        f.filter(mock_message)
        assert received[0] is mock_message

    def test_callback_filter_custom_logic(self, mock_message):
        """Should support custom filtering logic."""
        def callback(m):
            return m.text and len(m.text) > 10

        f = CallbackFilter(callback)
        mock_message.text = "Hello"
        assert f.filter(mock_message) is False

        mock_message.text = "Hello, this is a longer message"
        assert f.filter(mock_message) is True

    def test_callback_filter_custom_name(self, mock_message):
        """Should support custom name."""
        f = CallbackFilter(lambda m: True, name="MyCallback")
        assert f.name == "MyCallback"

    def test_callback_filter_callback_property(self):
        """Should expose callback property."""
        cb = lambda m: True
        f = CallbackFilter(cb)
        assert f.callback is cb


# ============================================================================
# Test: Factory Functions
# ============================================================================

class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_admin_filter(self):
        """Should create admin filter."""
        f = create_admin_filter({1, 2, 3})
        assert isinstance(f, AdminFilter)
        assert f.admin_ids == {1, 2, 3}

    def test_create_chat_filter(self):
        """Should create chat filter."""
        f = create_chat_filter({100, 200})
        assert isinstance(f, SpecificChatFilter)
        assert f.chat_ids == {100, 200}

    def test_create_user_filter(self):
        """Should create user filter."""
        f = create_user_filter([1, 2, 3])
        assert isinstance(f, SpecificUserFilter)
        assert f.user_ids == {1, 2, 3}

    def test_create_command_filter(self):
        """Should create command filter."""
        f = create_command_filter(["help", "start"])
        assert isinstance(f, SpecificCommandFilter)
        assert "help" in f.commands

    def test_create_regex_filter(self):
        """Should create regex filter."""
        f = create_regex_filter(r"test\d+")
        assert isinstance(f, RegexFilter)
        assert f.pattern.pattern == r"test\d+"

    def test_create_rate_limit_filter(self):
        """Should create rate limit filter."""
        f = create_rate_limit_filter(messages=10, seconds=30)
        assert isinstance(f, RateLimitFilter)
        assert f.config.messages_per_window == 10
        assert f.config.window_seconds == 30


# ============================================================================
# Test: Module-Level Filter Instances
# ============================================================================

class TestModuleLevelFilters:
    """Tests for module-level filter instances."""

    def test_private_chat_instance(self, mock_message):
        """PRIVATE_CHAT should be a PrivateChatFilter."""
        assert isinstance(PRIVATE_CHAT, PrivateChatFilter)
        mock_message.chat.type = "private"
        assert PRIVATE_CHAT.filter(mock_message) is True

    def test_group_chat_instance(self, mock_group_message):
        """GROUP_CHAT should be a GroupChatFilter."""
        assert isinstance(GROUP_CHAT, GroupChatFilter)
        assert GROUP_CHAT.filter(mock_group_message) is True

    def test_supergroup_instance(self, mock_supergroup_message):
        """SUPERGROUP should be a SupergroupFilter."""
        assert isinstance(SUPERGROUP, SupergroupFilter)
        assert SUPERGROUP.filter(mock_supergroup_message) is True

    def test_any_group_instance(self, mock_group_message):
        """ANY_GROUP should be an AnyGroupFilter."""
        assert isinstance(ANY_GROUP, AnyGroupFilter)
        assert ANY_GROUP.filter(mock_group_message) is True

    def test_channel_instance(self, mock_channel_message):
        """CHANNEL should be a ChannelFilter."""
        assert isinstance(CHANNEL, ChannelFilter)
        assert CHANNEL.filter(mock_channel_message) is True

    def test_is_command_instance(self, mock_command_message):
        """IS_COMMAND should be a CommandPrefixFilter."""
        assert isinstance(IS_COMMAND, CommandPrefixFilter)
        assert IS_COMMAND.filter(mock_command_message) is True

    def test_not_command_instance(self, mock_message):
        """NOT_COMMAND should be a NotCommandFilter."""
        assert isinstance(NOT_COMMAND, NotCommandFilter)
        mock_message.text = "Hello"
        assert NOT_COMMAND.filter(mock_message) is True

    def test_from_bot_instance(self, mock_bot_message):
        """FROM_BOT should be a BotFilter allowing bots."""
        assert isinstance(FROM_BOT, BotFilter)
        assert FROM_BOT.filter(mock_bot_message) is True

    def test_from_human_instance(self, mock_message):
        """FROM_HUMAN should be a NotBotFilter."""
        assert isinstance(FROM_HUMAN, NotBotFilter)
        assert FROM_HUMAN.filter(mock_message) is True

    def test_has_token_address_instance(self, mock_message):
        """HAS_TOKEN_ADDRESS should be a TokenAddressFilter."""
        assert isinstance(HAS_TOKEN_ADDRESS, TokenAddressFilter)
        mock_message.text = "Check 11111111111111111111111111111112"
        assert HAS_TOKEN_ADDRESS.filter(mock_message) is True

    def test_has_token_ticker_instance(self, mock_message):
        """HAS_TOKEN_TICKER should be a TokenTickerFilter."""
        assert isinstance(HAS_TOKEN_TICKER, TokenTickerFilter)
        mock_message.text = "Buy $SOL"
        assert HAS_TOKEN_TICKER.filter(mock_message) is True


# ============================================================================
# Test: Integration - Complex Filter Chains
# ============================================================================

class TestComplexFilterChains:
    """Integration tests for complex filter combinations."""

    def test_admin_in_private_chat(self, mock_message):
        """Should filter admin messages in private chat."""
        admin_filter = AdminFilter(admin_ids={12345})
        private_filter = PrivateChatFilter()
        combined = AndFilter(admin_filter, private_filter)

        mock_message.from_user.id = 12345
        mock_message.chat.type = "private"
        assert combined.filter(mock_message) is True

        mock_message.chat.type = "group"
        assert combined.filter(mock_message) is False

    def test_command_or_token_mention(self, mock_message):
        """Should filter commands or token mentions."""
        command_filter = CommandPrefixFilter()
        token_filter = TokenMentionFilter()
        combined = OrFilter(command_filter, token_filter)

        mock_message.text = "/help"
        assert combined.filter(mock_message) is True

        mock_message.text = "Check $SOL"
        assert combined.filter(mock_message) is True

        mock_message.text = "Hello world"
        assert combined.filter(mock_message) is False

    def test_not_spam_from_human(self, mock_message):
        """Should filter non-spam messages from humans."""
        not_spam = NotSpamFilter()
        from_human = NotBotFilter()
        combined = AndFilter(not_spam, from_human)

        mock_message.text = "Hello, how are you?"
        mock_message.from_user.is_bot = False
        assert combined.filter(mock_message) is True

    def test_media_in_group_from_admin(self, mock_photo_message):
        """Should filter media in groups from admins."""
        admin_filter = AdminFilter(admin_ids={12345})
        group_filter = AnyGroupFilter()
        media_filter = MediaFilter()
        combined = AndFilter(admin_filter, group_filter, media_filter)

        mock_photo_message.from_user.id = 12345
        mock_photo_message.chat.type = "group"
        assert combined.filter(mock_photo_message) is True

        mock_photo_message.from_user.id = 99999
        assert combined.filter(mock_photo_message) is False

    def test_rate_limited_commands(self, mock_command_message):
        """Should rate limit commands per user."""
        command_filter = CommandPrefixFilter()
        rate_filter = RateLimitFilter(RateLimitConfig(messages_per_window=2, window_seconds=60))
        combined = AndFilter(command_filter, rate_filter)

        assert combined.filter(mock_command_message) is True
        assert combined.filter(mock_command_message) is True
        assert combined.filter(mock_command_message) is False  # Rate limited
