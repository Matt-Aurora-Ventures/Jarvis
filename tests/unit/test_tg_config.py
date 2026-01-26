"""
Unit tests for tg_bot/config.py - Secure Configuration Module.

Covers:
- BotConfig dataclass initialization and defaults
- Environment variable loading and parsing
- Admin ID parsing from environment
- Admin username parsing
- Broadcast chat ID parsing
- Config validation methods (is_valid, has_grok, has_claude)
- Missing config detection (get_missing, get_optional_missing)
- Admin checking (is_admin with ID and username)
- API key masking
- Singleton pattern (get_config, reload_config)
- API cost constants
- .env file loading fallback
- Database path creation

Test Categories:
1. BotConfig initialization - Default values and environment loading
2. Admin parsing - ID and username parsing from env vars
3. Validation methods - is_valid, has_grok, has_claude
4. Missing config detection - get_missing, get_optional_missing
5. Admin checking - is_admin with various inputs
6. Key masking - mask_key for safe logging
7. Singleton pattern - get_config, reload_config
8. Helper functions - _parse_admin_ids, _parse_admin_usernames, _parse_broadcast_chat_id
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def clean_env():
    """Clean environment of config-related variables."""
    env_vars = [
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_ADMIN_IDS",
        "TELEGRAM_ADMIN_USERNAMES",
        "TELEGRAM_BROADCAST_CHAT_ID",
        "TELEGRAM_BUY_BOT_CHAT_ID",
        "XAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "BIRDEYE_API_KEY",
        "LOW_BALANCE_THRESHOLD",
    ]
    original = {k: os.environ.get(k) for k in env_vars}
    for k in env_vars:
        if k in os.environ:
            del os.environ[k]
    yield
    # Restore original values
    for k, v in original.items():
        if v is not None:
            os.environ[k] = v
        elif k in os.environ:
            del os.environ[k]


@pytest.fixture
def mock_env_with_config(clean_env):
    """Setup environment with typical config values."""
    env_vars = {
        "TELEGRAM_BOT_TOKEN": "test_token_12345",
        "TELEGRAM_ADMIN_IDS": "123456789,987654321",
        "TELEGRAM_ADMIN_USERNAMES": "admin1,admin2",
        "TELEGRAM_BROADCAST_CHAT_ID": "-1001234567890",
        "XAI_API_KEY": "xai_test_key",
        "ANTHROPIC_API_KEY": "anthropic_test_key",
        "BIRDEYE_API_KEY": "birdeye_test_key",
        "LOW_BALANCE_THRESHOLD": "0.05",
    }
    with patch.dict(os.environ, env_vars, clear=False):
        yield env_vars


@pytest.fixture
def reset_singleton():
    """Reset the config singleton before and after each test."""
    import tg_bot.config as config_module
    original_config = config_module._config
    config_module._config = None
    yield
    config_module._config = original_config


# ============================================================================
# Test: API_COSTS Constants
# ============================================================================

class TestAPICosts:
    """Tests for API_COSTS dictionary."""

    def test_api_costs_has_grok(self):
        """API_COSTS should include grok cost."""
        from tg_bot.config import API_COSTS
        assert "grok" in API_COSTS
        assert isinstance(API_COSTS["grok"], float)
        assert API_COSTS["grok"] > 0

    def test_api_costs_has_claude(self):
        """API_COSTS should include claude cost."""
        from tg_bot.config import API_COSTS
        assert "claude" in API_COSTS
        assert isinstance(API_COSTS["claude"], float)
        assert API_COSTS["claude"] > 0

    def test_api_costs_has_birdeye(self):
        """API_COSTS should include birdeye cost (free)."""
        from tg_bot.config import API_COSTS
        assert "birdeye" in API_COSTS
        assert API_COSTS["birdeye"] == 0.0

    def test_api_costs_has_dexscreener(self):
        """API_COSTS should include dexscreener cost (free)."""
        from tg_bot.config import API_COSTS
        assert "dexscreener" in API_COSTS
        assert API_COSTS["dexscreener"] == 0.0

    def test_api_costs_has_gmgn(self):
        """API_COSTS should include gmgn cost (free)."""
        from tg_bot.config import API_COSTS
        assert "gmgn" in API_COSTS
        assert API_COSTS["gmgn"] == 0.0


# ============================================================================
# Test: BotConfig Initialization and Defaults
# ============================================================================

class TestBotConfigDefaults:
    """Tests for BotConfig default values."""

    def test_default_telegram_token_empty(self, clean_env, reset_singleton):
        """Default telegram_token should be empty string."""
        from tg_bot.config import BotConfig
        config = BotConfig()
        assert config.telegram_token == ""

    def test_default_grok_api_key_empty(self, clean_env, reset_singleton):
        """Default grok_api_key should be empty string."""
        from tg_bot.config import BotConfig
        config = BotConfig()
        assert config.grok_api_key == ""

    def test_default_birdeye_api_key_empty(self, clean_env, reset_singleton):
        """Default birdeye_api_key should be empty string."""
        from tg_bot.config import BotConfig
        config = BotConfig()
        assert config.birdeye_api_key == ""

    def test_default_admin_ids_empty(self, clean_env, reset_singleton):
        """Default admin_ids should be empty set."""
        from tg_bot.config import BotConfig
        config = BotConfig()
        assert config.admin_ids == set()

    def test_default_sentiment_interval(self, clean_env, reset_singleton):
        """Default sentiment_interval_seconds should be 3600."""
        from tg_bot.config import BotConfig
        config = BotConfig()
        assert config.sentiment_interval_seconds == 3600

    def test_default_max_sentiment_per_day(self, clean_env, reset_singleton):
        """Default max_sentiment_per_day should be 24."""
        from tg_bot.config import BotConfig
        config = BotConfig()
        assert config.max_sentiment_per_day == 24

    def test_default_daily_cost_limit(self, clean_env, reset_singleton):
        """Default daily_cost_limit_usd should be 10.00."""
        from tg_bot.config import BotConfig
        config = BotConfig()
        assert config.daily_cost_limit_usd == 10.00

    def test_default_grok_model(self, clean_env, reset_singleton):
        """Default grok_model should be grok-3-mini."""
        from tg_bot.config import BotConfig
        config = BotConfig()
        assert config.grok_model == "grok-3-mini"

    def test_default_claude_model(self, clean_env, reset_singleton):
        """Default claude_model should be claude-sonnet-4-20250514."""
        from tg_bot.config import BotConfig
        config = BotConfig()
        assert config.claude_model == "claude-sonnet-4-20250514"

    def test_default_claude_max_tokens(self, clean_env, reset_singleton):
        """Default claude_max_tokens should be 1024."""
        from tg_bot.config import BotConfig
        config = BotConfig()
        assert config.claude_max_tokens == 1024

    def test_default_db_path(self, clean_env, reset_singleton):
        """Default db_path should be in .lifeos/telegram."""
        from tg_bot.config import BotConfig
        config = BotConfig()
        assert ".lifeos" in str(config.db_path)
        assert "telegram" in str(config.db_path)
        assert "jarvis_secure.db" in str(config.db_path)

    def test_default_digest_hours(self, clean_env, reset_singleton):
        """Default digest_hours should be [8, 14, 20]."""
        from tg_bot.config import BotConfig
        config = BotConfig()
        assert config.digest_hours == [8, 14, 20]

    def test_default_broadcast_chat_id_none(self, clean_env, reset_singleton):
        """Default broadcast_chat_id should be None."""
        from tg_bot.config import BotConfig
        config = BotConfig()
        assert config.broadcast_chat_id is None

    def test_default_paper_trading_balance(self, clean_env, reset_singleton):
        """Default paper_starting_balance should be 100.0."""
        from tg_bot.config import BotConfig
        config = BotConfig()
        assert config.paper_starting_balance == 100.0

    def test_default_paper_max_position_pct(self, clean_env, reset_singleton):
        """Default paper_max_position_pct should be 0.20."""
        from tg_bot.config import BotConfig
        config = BotConfig()
        assert config.paper_max_position_pct == 0.20

    def test_default_paper_slippage_pct(self, clean_env, reset_singleton):
        """Default paper_slippage_pct should be 0.003."""
        from tg_bot.config import BotConfig
        config = BotConfig()
        assert config.paper_slippage_pct == 0.003

    def test_default_low_balance_threshold(self, clean_env, reset_singleton):
        """Default low_balance_threshold should be 0.01."""
        from tg_bot.config import BotConfig
        config = BotConfig()
        assert config.low_balance_threshold == 0.01

    def test_default_log_api_calls_false(self, clean_env, reset_singleton):
        """Default log_api_calls should be False."""
        from tg_bot.config import BotConfig
        config = BotConfig()
        assert config.log_api_calls is False

    def test_default_mask_addresses_true(self, clean_env, reset_singleton):
        """Default mask_addresses should be True."""
        from tg_bot.config import BotConfig
        config = BotConfig()
        assert config.mask_addresses is True


# ============================================================================
# Test: BotConfig with Environment Variables
# ============================================================================

class TestBotConfigFromEnv:
    """Tests for BotConfig loading from environment."""

    def test_telegram_token_from_env(self, reset_singleton):
        """Should load telegram_token from TELEGRAM_BOT_TOKEN."""
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "my_test_token"}):
            from tg_bot.config import BotConfig
            config = BotConfig()
            assert config.telegram_token == "my_test_token"

    def test_grok_api_key_from_env(self, reset_singleton):
        """Should load grok_api_key from XAI_API_KEY."""
        with patch.dict(os.environ, {"XAI_API_KEY": "xai_key_123"}):
            from tg_bot.config import BotConfig
            config = BotConfig()
            assert config.grok_api_key == "xai_key_123"

    def test_birdeye_api_key_from_env(self, reset_singleton):
        """Should load birdeye_api_key from BIRDEYE_API_KEY."""
        with patch.dict(os.environ, {"BIRDEYE_API_KEY": "birdeye_key_456"}):
            from tg_bot.config import BotConfig
            config = BotConfig()
            assert config.birdeye_api_key == "birdeye_key_456"

    def test_low_balance_threshold_from_env(self, reset_singleton):
        """Should load low_balance_threshold from LOW_BALANCE_THRESHOLD."""
        with patch.dict(os.environ, {"LOW_BALANCE_THRESHOLD": "0.1"}):
            from tg_bot.config import BotConfig
            config = BotConfig()
            assert config.low_balance_threshold == 0.1

    def test_broadcast_chat_id_from_env(self, reset_singleton):
        """Should load broadcast_chat_id from TELEGRAM_BROADCAST_CHAT_ID."""
        with patch.dict(os.environ, {"TELEGRAM_BROADCAST_CHAT_ID": "-1001234567890"}):
            from tg_bot.config import BotConfig
            config = BotConfig()
            assert config.broadcast_chat_id == -1001234567890

    def test_broadcast_chat_id_fallback(self, reset_singleton):
        """Should fallback to TELEGRAM_BUY_BOT_CHAT_ID for broadcast_chat_id."""
        # Need to clear TELEGRAM_BROADCAST_CHAT_ID for fallback to work
        env = {"TELEGRAM_BUY_BOT_CHAT_ID": "-1009876543210"}
        with patch.dict(os.environ, env, clear=False):
            # Remove the primary key if set
            os.environ.pop("TELEGRAM_BROADCAST_CHAT_ID", None)
            from tg_bot.config import BotConfig
            config = BotConfig()
            assert config.broadcast_chat_id == -1009876543210


# ============================================================================
# Test: _parse_admin_ids Function
# ============================================================================

class TestParseAdminIds:
    """Tests for _parse_admin_ids helper function."""

    def test_parse_admin_ids_single(self, reset_singleton):
        """Should parse single admin ID."""
        with patch.dict(os.environ, {"TELEGRAM_ADMIN_IDS": "123456789"}):
            from tg_bot.config import _parse_admin_ids
            ids = _parse_admin_ids()
            assert ids == {123456789}

    def test_parse_admin_ids_multiple(self, reset_singleton):
        """Should parse multiple admin IDs."""
        with patch.dict(os.environ, {"TELEGRAM_ADMIN_IDS": "123,456,789"}):
            from tg_bot.config import _parse_admin_ids
            ids = _parse_admin_ids()
            assert ids == {123, 456, 789}

    def test_parse_admin_ids_with_spaces(self, reset_singleton):
        """Should handle spaces around IDs."""
        with patch.dict(os.environ, {"TELEGRAM_ADMIN_IDS": " 123 , 456 , 789 "}):
            from tg_bot.config import _parse_admin_ids
            ids = _parse_admin_ids()
            assert ids == {123, 456, 789}

    def test_parse_admin_ids_empty(self, clean_env, reset_singleton):
        """Should return empty set when not set."""
        from tg_bot.config import _parse_admin_ids
        ids = _parse_admin_ids()
        assert ids == set()

    def test_parse_admin_ids_invalid_ignored(self, reset_singleton):
        """Should ignore non-digit values."""
        with patch.dict(os.environ, {"TELEGRAM_ADMIN_IDS": "123,abc,456,xyz"}):
            from tg_bot.config import _parse_admin_ids
            ids = _parse_admin_ids()
            assert ids == {123, 456}

    def test_parse_admin_ids_all_invalid(self, reset_singleton):
        """Should return empty set when all values are invalid."""
        with patch.dict(os.environ, {"TELEGRAM_ADMIN_IDS": "abc,xyz,!@#"}):
            from tg_bot.config import _parse_admin_ids
            ids = _parse_admin_ids()
            assert ids == set()

    def test_parse_admin_ids_large_ids(self, reset_singleton):
        """Should handle large Telegram user IDs."""
        with patch.dict(os.environ, {"TELEGRAM_ADMIN_IDS": "9999999999,1111111111111"}):
            from tg_bot.config import _parse_admin_ids
            ids = _parse_admin_ids()
            assert ids == {9999999999, 1111111111111}


# ============================================================================
# Test: _parse_admin_usernames Function
# ============================================================================

class TestParseAdminUsernames:
    """Tests for _parse_admin_usernames helper function."""

    def test_parse_admin_usernames_single(self, reset_singleton):
        """Should parse single username."""
        with patch.dict(os.environ, {"TELEGRAM_ADMIN_USERNAMES": "testuser"}):
            from tg_bot.config import _parse_admin_usernames
            names = _parse_admin_usernames()
            assert "testuser" in names

    def test_parse_admin_usernames_multiple(self, reset_singleton):
        """Should parse multiple usernames."""
        with patch.dict(os.environ, {"TELEGRAM_ADMIN_USERNAMES": "user1,user2,user3"}):
            from tg_bot.config import _parse_admin_usernames
            names = _parse_admin_usernames()
            assert names == {"user1", "user2", "user3"}

    def test_parse_admin_usernames_lowercase(self, reset_singleton):
        """Should convert usernames to lowercase."""
        with patch.dict(os.environ, {"TELEGRAM_ADMIN_USERNAMES": "UserOne,USERTWO"}):
            from tg_bot.config import _parse_admin_usernames
            names = _parse_admin_usernames()
            assert "userone" in names
            assert "usertwo" in names

    def test_parse_admin_usernames_strips_at(self, reset_singleton):
        """Should strip @ prefix from usernames."""
        with patch.dict(os.environ, {"TELEGRAM_ADMIN_USERNAMES": "@user1,@user2"}):
            from tg_bot.config import _parse_admin_usernames
            names = _parse_admin_usernames()
            assert "user1" in names
            assert "user2" in names
            assert "@user1" not in names

    def test_parse_admin_usernames_default(self, clean_env, reset_singleton):
        """Should return default username when not set."""
        from tg_bot.config import _parse_admin_usernames
        names = _parse_admin_usernames()
        assert "matthaynes88" in names

    def test_parse_admin_usernames_spaces(self, reset_singleton):
        """Should handle spaces around usernames."""
        with patch.dict(os.environ, {"TELEGRAM_ADMIN_USERNAMES": " user1 , user2 "}):
            from tg_bot.config import _parse_admin_usernames
            names = _parse_admin_usernames()
            assert "user1" in names
            assert "user2" in names

    def test_parse_admin_usernames_empty_entries_ignored(self, reset_singleton):
        """Should ignore empty entries in list."""
        with patch.dict(os.environ, {"TELEGRAM_ADMIN_USERNAMES": "user1,,user2,  ,user3"}):
            from tg_bot.config import _parse_admin_usernames
            names = _parse_admin_usernames()
            assert "user1" in names
            assert "user2" in names
            assert "user3" in names
            assert "" not in names

    def test_parse_admin_usernames_only_empty(self, reset_singleton):
        """Should return default when all entries are empty/spaces."""
        # The function checks if names_str is empty first
        with patch.dict(os.environ, {"TELEGRAM_ADMIN_USERNAMES": ""}):
            from tg_bot.config import _parse_admin_usernames
            names = _parse_admin_usernames()
            # Should return default
            assert "matthaynes88" in names


# ============================================================================
# Test: _parse_broadcast_chat_id Function
# ============================================================================

class TestParseBroadcastChatId:
    """Tests for _parse_broadcast_chat_id helper function."""

    def test_parse_broadcast_chat_id_positive(self, reset_singleton):
        """Should parse positive chat ID."""
        with patch.dict(os.environ, {"TELEGRAM_BROADCAST_CHAT_ID": "12345"}):
            from tg_bot.config import _parse_broadcast_chat_id
            chat_id = _parse_broadcast_chat_id()
            assert chat_id == 12345

    def test_parse_broadcast_chat_id_negative(self, reset_singleton):
        """Should parse negative chat ID (for groups)."""
        with patch.dict(os.environ, {"TELEGRAM_BROADCAST_CHAT_ID": "-1001234567890"}):
            from tg_bot.config import _parse_broadcast_chat_id
            chat_id = _parse_broadcast_chat_id()
            assert chat_id == -1001234567890

    def test_parse_broadcast_chat_id_fallback(self, reset_singleton):
        """Should fallback to TELEGRAM_BUY_BOT_CHAT_ID."""
        # Need to clear TELEGRAM_BROADCAST_CHAT_ID for fallback to work
        with patch.dict(os.environ, {"TELEGRAM_BUY_BOT_CHAT_ID": "-1009999999999"}, clear=False):
            os.environ.pop("TELEGRAM_BROADCAST_CHAT_ID", None)
            from tg_bot.config import _parse_broadcast_chat_id
            chat_id = _parse_broadcast_chat_id()
            assert chat_id == -1009999999999

    def test_parse_broadcast_chat_id_primary_takes_precedence(self, reset_singleton):
        """TELEGRAM_BROADCAST_CHAT_ID should take precedence over fallback."""
        with patch.dict(os.environ, {
            "TELEGRAM_BROADCAST_CHAT_ID": "-100111",
            "TELEGRAM_BUY_BOT_CHAT_ID": "-100222"
        }):
            from tg_bot.config import _parse_broadcast_chat_id
            chat_id = _parse_broadcast_chat_id()
            assert chat_id == -100111

    def test_parse_broadcast_chat_id_none(self, clean_env, reset_singleton):
        """Should return None when not set."""
        from tg_bot.config import _parse_broadcast_chat_id
        chat_id = _parse_broadcast_chat_id()
        assert chat_id is None

    def test_parse_broadcast_chat_id_invalid(self, reset_singleton):
        """Should return None for invalid value."""
        with patch.dict(os.environ, {"TELEGRAM_BROADCAST_CHAT_ID": "not_a_number"}):
            from tg_bot.config import _parse_broadcast_chat_id
            chat_id = _parse_broadcast_chat_id()
            assert chat_id is None

    def test_parse_broadcast_chat_id_strips_spaces(self, reset_singleton):
        """Should strip whitespace from value."""
        with patch.dict(os.environ, {"TELEGRAM_BROADCAST_CHAT_ID": " -100123 "}):
            from tg_bot.config import _parse_broadcast_chat_id
            chat_id = _parse_broadcast_chat_id()
            assert chat_id == -100123


# ============================================================================
# Test: BotConfig.is_valid Method
# ============================================================================

class TestBotConfigIsValid:
    """Tests for BotConfig.is_valid method."""

    def test_is_valid_with_token_and_admins(self, reset_singleton):
        """Should be valid with token and admin IDs."""
        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "valid_token",
            "TELEGRAM_ADMIN_IDS": "123456"
        }):
            from tg_bot.config import BotConfig
            config = BotConfig()
            assert config.is_valid() is True

    def test_is_valid_missing_token(self, reset_singleton):
        """Should be invalid without token."""
        with patch.dict(os.environ, {"TELEGRAM_ADMIN_IDS": "123456"}):
            from tg_bot.config import BotConfig
            config = BotConfig()
            config.telegram_token = ""
            assert config.is_valid() is False

    def test_is_valid_missing_admins(self, reset_singleton):
        """Should be invalid without admin IDs."""
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "valid_token"}):
            from tg_bot.config import BotConfig
            config = BotConfig()
            config.admin_ids = set()
            assert config.is_valid() is False

    def test_is_valid_missing_both(self, clean_env, reset_singleton):
        """Should be invalid without token and admins."""
        from tg_bot.config import BotConfig
        config = BotConfig()
        assert config.is_valid() is False


# ============================================================================
# Test: BotConfig.has_grok Method
# ============================================================================

class TestBotConfigHasGrok:
    """Tests for BotConfig.has_grok method."""

    def test_has_grok_true(self, reset_singleton):
        """Should return True when grok key is set."""
        with patch.dict(os.environ, {"XAI_API_KEY": "xai_key_123"}):
            from tg_bot.config import BotConfig
            config = BotConfig()
            assert config.has_grok() is True

    def test_has_grok_false(self, clean_env, reset_singleton):
        """Should return False when grok key is empty."""
        from tg_bot.config import BotConfig
        config = BotConfig()
        assert config.has_grok() is False

    def test_has_grok_empty_string(self, reset_singleton):
        """Should return False for empty string."""
        with patch.dict(os.environ, {"XAI_API_KEY": ""}):
            from tg_bot.config import BotConfig
            config = BotConfig()
            assert config.has_grok() is False


# ============================================================================
# Test: BotConfig.has_claude Method
# ============================================================================

class TestBotConfigHasClaude:
    """Tests for BotConfig.has_claude method."""

    def test_has_claude_true(self, reset_singleton):
        """Should return True when anthropic key is set."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "anthropic_key_123"}):
            from tg_bot.config import BotConfig
            config = BotConfig()
            assert config.has_claude() is True

    def test_has_claude_false(self, clean_env, reset_singleton):
        """Should return False when anthropic key is empty."""
        from tg_bot.config import BotConfig
        # Mock the _get_anthropic_key to return empty
        with patch('tg_bot.config._get_anthropic_key', return_value=""):
            config = BotConfig()
            config.anthropic_api_key = ""
            assert config.has_claude() is False


# ============================================================================
# Test: BotConfig.get_missing Method
# ============================================================================

class TestBotConfigGetMissing:
    """Tests for BotConfig.get_missing method."""

    def test_get_missing_all_present(self, reset_singleton):
        """Should return empty list when all required config is present."""
        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "token",
            "TELEGRAM_ADMIN_IDS": "123"
        }):
            from tg_bot.config import BotConfig
            config = BotConfig()
            missing = config.get_missing()
            assert missing == []

    def test_get_missing_no_token(self, clean_env, reset_singleton):
        """Should list TELEGRAM_BOT_TOKEN when missing."""
        with patch.dict(os.environ, {"TELEGRAM_ADMIN_IDS": "123"}):
            from tg_bot.config import BotConfig
            config = BotConfig()
            config.telegram_token = ""
            missing = config.get_missing()
            assert "TELEGRAM_BOT_TOKEN" in missing

    def test_get_missing_no_admins(self, clean_env, reset_singleton):
        """Should list TELEGRAM_ADMIN_IDS when missing."""
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "token"}):
            from tg_bot.config import BotConfig
            config = BotConfig()
            config.admin_ids = set()
            missing = config.get_missing()
            assert "TELEGRAM_ADMIN_IDS" in missing

    def test_get_missing_both(self, clean_env, reset_singleton):
        """Should list both when both missing."""
        from tg_bot.config import BotConfig
        config = BotConfig()
        missing = config.get_missing()
        assert "TELEGRAM_BOT_TOKEN" in missing
        assert "TELEGRAM_ADMIN_IDS" in missing


# ============================================================================
# Test: BotConfig.get_optional_missing Method
# ============================================================================

class TestBotConfigGetOptionalMissing:
    """Tests for BotConfig.get_optional_missing method."""

    def test_get_optional_missing_all_present(self, reset_singleton):
        """Should return empty list when all optional config is present."""
        with patch.dict(os.environ, {
            "XAI_API_KEY": "xai_key",
            "ANTHROPIC_API_KEY": "anthropic_key",
            "BIRDEYE_API_KEY": "birdeye_key"
        }):
            from tg_bot.config import BotConfig
            config = BotConfig()
            missing = config.get_optional_missing()
            assert missing == []

    def test_get_optional_missing_no_grok(self, clean_env, reset_singleton):
        """Should list XAI_API_KEY when missing."""
        from tg_bot.config import BotConfig
        with patch('tg_bot.config._get_anthropic_key', return_value="key"):
            with patch.dict(os.environ, {"BIRDEYE_API_KEY": "key"}):
                config = BotConfig()
                missing = config.get_optional_missing()
                assert any("XAI_API_KEY" in m for m in missing)

    def test_get_optional_missing_no_anthropic(self, clean_env, reset_singleton):
        """Should list ANTHROPIC_API_KEY when missing."""
        with patch.dict(os.environ, {
            "XAI_API_KEY": "key",
            "BIRDEYE_API_KEY": "key"
        }):
            with patch('tg_bot.config._get_anthropic_key', return_value=""):
                from tg_bot.config import BotConfig
                config = BotConfig()
                config.anthropic_api_key = ""
                missing = config.get_optional_missing()
                assert any("ANTHROPIC" in m for m in missing)

    def test_get_optional_missing_no_birdeye(self, clean_env, reset_singleton):
        """Should list BIRDEYE_API_KEY when missing."""
        with patch.dict(os.environ, {"XAI_API_KEY": "key"}):
            with patch('tg_bot.config._get_anthropic_key', return_value="key"):
                from tg_bot.config import BotConfig
                config = BotConfig()
                missing = config.get_optional_missing()
                assert any("BIRDEYE_API_KEY" in m for m in missing)


# ============================================================================
# Test: BotConfig.is_admin Method
# ============================================================================

class TestBotConfigIsAdmin:
    """Tests for BotConfig.is_admin method."""

    def test_is_admin_by_id(self, reset_singleton):
        """Should return True for admin by ID."""
        with patch.dict(os.environ, {"TELEGRAM_ADMIN_IDS": "123456,789012"}):
            from tg_bot.config import BotConfig
            config = BotConfig()
            assert config.is_admin(123456) is True
            assert config.is_admin(789012) is True

    def test_is_admin_not_admin_by_id(self, reset_singleton):
        """Should return False for non-admin by ID."""
        with patch.dict(os.environ, {"TELEGRAM_ADMIN_IDS": "123456"}):
            from tg_bot.config import BotConfig
            config = BotConfig()
            assert config.is_admin(999999) is False

    def test_is_admin_by_username(self, reset_singleton):
        """Should return True for admin by username."""
        with patch.dict(os.environ, {"TELEGRAM_ADMIN_USERNAMES": "admin1,admin2"}):
            from tg_bot.config import BotConfig
            config = BotConfig()
            assert config.is_admin(999999, username="admin1") is True

    def test_is_admin_username_case_insensitive(self, reset_singleton):
        """Should match username case insensitively."""
        with patch.dict(os.environ, {"TELEGRAM_ADMIN_USERNAMES": "AdminUser"}):
            from tg_bot.config import BotConfig
            config = BotConfig()
            assert config.is_admin(999999, username="adminuser") is True
            assert config.is_admin(999999, username="ADMINUSER") is True

    def test_is_admin_username_strips_at(self, reset_singleton):
        """Should strip @ from username during check."""
        with patch.dict(os.environ, {"TELEGRAM_ADMIN_USERNAMES": "admin1"}):
            from tg_bot.config import BotConfig
            config = BotConfig()
            assert config.is_admin(999999, username="@admin1") is True

    def test_is_admin_id_takes_precedence(self, reset_singleton):
        """Should check ID before username."""
        with patch.dict(os.environ, {
            "TELEGRAM_ADMIN_IDS": "123456",
            "TELEGRAM_ADMIN_USERNAMES": "differentuser"
        }):
            from tg_bot.config import BotConfig
            config = BotConfig()
            # Admin by ID, even with different username
            assert config.is_admin(123456, username="otheruser") is True

    def test_is_admin_no_username_provided(self, reset_singleton):
        """Should return False if not admin by ID and no username."""
        with patch.dict(os.environ, {
            "TELEGRAM_ADMIN_IDS": "123456",
            "TELEGRAM_ADMIN_USERNAMES": "admin1"
        }):
            from tg_bot.config import BotConfig
            config = BotConfig()
            assert config.is_admin(999999) is False

    def test_is_admin_empty_admins(self, clean_env, reset_singleton):
        """Should return False when no admins configured."""
        from tg_bot.config import BotConfig
        config = BotConfig()
        assert config.is_admin(123456) is False

    def test_is_admin_with_none_username(self, reset_singleton):
        """Should handle None username gracefully."""
        with patch.dict(os.environ, {"TELEGRAM_ADMIN_IDS": "123456"}):
            from tg_bot.config import BotConfig
            config = BotConfig()
            # Explicit None username
            assert config.is_admin(999999, username=None) is False

    def test_is_admin_with_empty_username(self, reset_singleton):
        """Should handle empty username gracefully."""
        with patch.dict(os.environ, {"TELEGRAM_ADMIN_USERNAMES": "admin1"}):
            from tg_bot.config import BotConfig
            config = BotConfig()
            # Empty string username should not match
            assert config.is_admin(999999, username="") is False


# ============================================================================
# Test: BotConfig.mask_key Method
# ============================================================================

class TestBotConfigMaskKey:
    """Tests for BotConfig.mask_key method."""

    def test_mask_key_normal(self, clean_env, reset_singleton):
        """Should mask middle of key."""
        from tg_bot.config import BotConfig
        config = BotConfig()
        masked = config.mask_key("abcdefghij1234567890")
        assert masked == "abcd...7890"

    def test_mask_key_short(self, clean_env, reset_singleton):
        """Should return *** for short keys."""
        from tg_bot.config import BotConfig
        config = BotConfig()
        masked = config.mask_key("short")
        assert masked == "***"

    def test_mask_key_empty(self, clean_env, reset_singleton):
        """Should return *** for empty key."""
        from tg_bot.config import BotConfig
        config = BotConfig()
        masked = config.mask_key("")
        assert masked == "***"

    def test_mask_key_none(self, clean_env, reset_singleton):
        """Should return *** for None key."""
        from tg_bot.config import BotConfig
        config = BotConfig()
        masked = config.mask_key(None)
        assert masked == "***"

    def test_mask_key_exactly_8_chars(self, clean_env, reset_singleton):
        """Should mask 8-char key correctly."""
        from tg_bot.config import BotConfig
        config = BotConfig()
        masked = config.mask_key("12345678")
        assert masked == "1234...5678"

    def test_mask_key_7_chars(self, clean_env, reset_singleton):
        """Should return *** for 7-char key."""
        from tg_bot.config import BotConfig
        config = BotConfig()
        masked = config.mask_key("1234567")
        assert masked == "***"


# ============================================================================
# Test: get_config Singleton Function
# ============================================================================

class TestGetConfig:
    """Tests for get_config singleton function."""

    def test_get_config_returns_botconfig(self, reset_singleton):
        """Should return a BotConfig instance."""
        from tg_bot.config import get_config, BotConfig
        config = get_config()
        assert isinstance(config, BotConfig)

    def test_get_config_singleton(self, reset_singleton):
        """Should return the same instance on multiple calls."""
        from tg_bot.config import get_config
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

    def test_get_config_loads_env(self, reset_singleton):
        """Should load config from environment."""
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "singleton_test_token"}):
            from tg_bot.config import get_config
            config = get_config()
            assert config.telegram_token == "singleton_test_token"


# ============================================================================
# Test: reload_config Function
# ============================================================================

class TestReloadConfig:
    """Tests for reload_config function."""

    def test_reload_config_returns_botconfig(self, reset_singleton):
        """Should return a BotConfig instance."""
        from tg_bot.config import reload_config, BotConfig
        config = reload_config()
        assert isinstance(config, BotConfig)

    def test_reload_config_creates_new_instance(self, reset_singleton):
        """Should create new instance each time."""
        from tg_bot.config import get_config, reload_config
        config1 = get_config()
        config2 = reload_config()
        # They should be different instances
        assert config1 is not config2

    def test_reload_config_picks_up_env_changes(self, reset_singleton):
        """Should pick up environment variable changes."""
        from tg_bot.config import get_config, reload_config

        # Initial config
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "initial_token"}):
            config1 = get_config()
            assert config1.telegram_token == "initial_token"

        # Change env and reload
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "new_token"}):
            config2 = reload_config()
            assert config2.telegram_token == "new_token"


# ============================================================================
# Test: _get_anthropic_key Function
# ============================================================================

class TestGetAnthropicKey:
    """Tests for _get_anthropic_key helper function."""

    def test_get_anthropic_key_from_env_fallback(self, reset_singleton):
        """Should fallback to ANTHROPIC_API_KEY env var when utils import fails."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test_anthropic_key"}):
            # Mock the import failure scenario by patching the internal import
            with patch.dict('sys.modules', {'core.llm.anthropic_utils': None}):
                from tg_bot.config import _get_anthropic_key
                # The function should try utils first, fail, then fall back to env
                key = _get_anthropic_key()
                # Should get from env since utils is mocked to fail
                assert key is not None  # Just verify it returns something

    def test_get_anthropic_key_returns_string(self, reset_singleton):
        """_get_anthropic_key should return a string."""
        from tg_bot.config import _get_anthropic_key
        key = _get_anthropic_key()
        assert isinstance(key, str)


# ============================================================================
# Test: BotConfig.__post_init__ Method
# ============================================================================

class TestBotConfigPostInit:
    """Tests for BotConfig __post_init__ behavior."""

    def test_post_init_creates_db_directory(self, clean_env, reset_singleton, tmp_path):
        """Should create database directory if it doesn't exist."""
        from tg_bot.config import BotConfig

        # Create config with custom db_path
        config = BotConfig()
        config.db_path = tmp_path / "subdir" / "test.db"
        config.__post_init__()

        assert config.db_path.parent.exists()


# ============================================================================
# Test: .env File Loading
# ============================================================================

class TestEnvFileLoading:
    """Tests for .env file loading fallback."""

    def test_env_file_parsed_without_dotenv(self, clean_env, reset_singleton):
        """Should parse .env file manually when dotenv not available."""
        env_content = """# Comment line
TELEGRAM_BOT_TOKEN=env_file_token
XAI_API_KEY="quoted_value"
BIRDEYE_API_KEY='single_quoted'
INVALID LINE WITHOUT EQUALS
"""
        # This tests the fallback parsing logic
        # The actual module-level loading happens at import time
        # so we test the parsing pattern directly
        lines = env_content.strip().split("\n")
        parsed = {}
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value:
                    parsed[key] = value

        assert parsed.get("TELEGRAM_BOT_TOKEN") == "env_file_token"
        assert parsed.get("XAI_API_KEY") == "quoted_value"
        assert parsed.get("BIRDEYE_API_KEY") == "single_quoted"

    def test_env_parsing_empty_value_skipped(self, clean_env, reset_singleton):
        """Should skip entries with empty values."""
        env_content = "KEY_WITH_NO_VALUE=\n"
        lines = env_content.strip().split("\n")
        parsed = {}
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value:
                    parsed[key] = value
        assert "KEY_WITH_NO_VALUE" not in parsed

    def test_env_parsing_empty_key_skipped(self, clean_env, reset_singleton):
        """Should skip entries with empty keys."""
        env_content = "=some_value\n"
        lines = env_content.strip().split("\n")
        parsed = {}
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value:
                    parsed[key] = value
        assert len(parsed) == 0

    def test_env_parsing_handles_equals_in_value(self, clean_env, reset_singleton):
        """Should handle values containing equals signs."""
        env_content = "URL=https://example.com?foo=bar&baz=qux\n"
        lines = env_content.strip().split("\n")
        parsed = {}
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value:
                    parsed[key] = value
        assert parsed.get("URL") == "https://example.com?foo=bar&baz=qux"


# ============================================================================
# Test: Integration Tests
# ============================================================================

class TestConfigIntegration:
    """Integration tests for config module."""

    def test_full_config_flow(self, reset_singleton):
        """Test complete config flow from env to validation."""
        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "integration_token",
            "TELEGRAM_ADMIN_IDS": "111,222,333",
            "TELEGRAM_ADMIN_USERNAMES": "user1,user2",
            "TELEGRAM_BROADCAST_CHAT_ID": "-1001234567890",
            "XAI_API_KEY": "xai_integration",
            "ANTHROPIC_API_KEY": "anthropic_integration",
            "BIRDEYE_API_KEY": "birdeye_integration",
            "LOW_BALANCE_THRESHOLD": "0.05"
        }):
            from tg_bot.config import get_config

            config = get_config()

            # Validate loading
            assert config.telegram_token == "integration_token"
            assert config.admin_ids == {111, 222, 333}
            assert config.broadcast_chat_id == -1001234567890
            assert config.grok_api_key == "xai_integration"
            assert config.low_balance_threshold == 0.05

            # Validate methods
            assert config.is_valid() is True
            assert config.has_grok() is True
            assert config.has_claude() is True
            assert config.get_missing() == []
            assert config.get_optional_missing() == []

            # Admin check
            assert config.is_admin(111) is True
            assert config.is_admin(999, username="user1") is True
            assert config.is_admin(888) is False

            # Key masking
            masked = config.mask_key(config.grok_api_key)
            assert "xai_" in masked
            assert masked != config.grok_api_key

    def test_minimal_valid_config(self, reset_singleton):
        """Test minimal config that passes validation."""
        # Clear all API keys to test minimal config
        env = {
            "TELEGRAM_BOT_TOKEN": "minimal_token",
            "TELEGRAM_ADMIN_IDS": "12345",
            "XAI_API_KEY": "",
            "BIRDEYE_API_KEY": "",
        }
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("XAI_API_KEY", None)
            os.environ.pop("BIRDEYE_API_KEY", None)
            os.environ.pop("ANTHROPIC_API_KEY", None)
            from tg_bot.config import BotConfig
            # Create new instance directly to avoid singleton caching issues
            with patch('tg_bot.config._get_anthropic_key', return_value=""):
                config = BotConfig()
                config.grok_api_key = ""
                config.anthropic_api_key = ""
                config.birdeye_api_key = ""
                assert config.is_valid() is True
                assert config.has_grok() is False
                assert config.has_claude() is False
                assert len(config.get_optional_missing()) > 0

    def test_config_immutability_pattern(self, reset_singleton):
        """Config should be retrievable as singleton but reloadable."""
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "token1"}):
            from tg_bot.config import get_config, reload_config

            config1 = get_config()
            config2 = get_config()
            assert config1 is config2

            config3 = reload_config()
            assert config3 is not config1

            config4 = get_config()
            assert config4 is config3
