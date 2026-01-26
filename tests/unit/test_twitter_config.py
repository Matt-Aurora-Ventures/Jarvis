"""
Comprehensive unit tests for Twitter Bot Configuration.

Tests cover:
1. TwitterConfig - API credentials loading and validation
2. GrokConfig - xAI Grok settings
3. ScheduleConfig - Posting schedule configuration
4. EngagementConfig - Engagement settings
5. BotConfiguration - Complete bot configuration
6. Module-level functions - print_env_template, check_config

Target: 90%+ coverage with 40+ tests
"""

import pytest
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bots.twitter.config import (
    TwitterConfig,
    GrokConfig,
    ScheduleConfig,
    EngagementConfig,
    BotConfiguration,
    ENV_TEMPLATE,
    print_env_template,
    check_config,
)


# =============================================================================
# TwitterConfig Tests
# =============================================================================

class TestTwitterConfig:
    """Tests for TwitterConfig dataclass."""

    def test_twitter_config_defaults(self):
        """Test TwitterConfig default values."""
        config = TwitterConfig()

        assert config.api_key == ""
        assert config.api_secret == ""
        assert config.access_token == ""
        assert config.access_token_secret == ""
        assert config.bearer_token == ""
        assert config.oauth2_client_id == ""
        assert config.oauth2_client_secret == ""
        assert config.oauth2_access_token == ""
        assert config.oauth2_refresh_token == ""
        assert config.expected_username == ""

    def test_twitter_config_with_values(self):
        """Test TwitterConfig with explicit values."""
        config = TwitterConfig(
            api_key="test_key",
            api_secret="test_secret",
            access_token="test_token",
            access_token_secret="test_token_secret",
            bearer_token="test_bearer",
            oauth2_client_id="oauth2_client",
            oauth2_client_secret="oauth2_secret",
            oauth2_access_token="oauth2_token",
            oauth2_refresh_token="oauth2_refresh",
            expected_username="test_user"
        )

        assert config.api_key == "test_key"
        assert config.api_secret == "test_secret"
        assert config.access_token == "test_token"
        assert config.access_token_secret == "test_token_secret"
        assert config.bearer_token == "test_bearer"
        assert config.oauth2_client_id == "oauth2_client"
        assert config.oauth2_client_secret == "oauth2_secret"
        assert config.oauth2_access_token == "oauth2_token"
        assert config.oauth2_refresh_token == "oauth2_refresh"
        assert config.expected_username == "test_user"

    def test_is_valid_with_oauth1_credentials(self):
        """Test is_valid returns True with complete OAuth1 credentials."""
        config = TwitterConfig(
            api_key="key",
            api_secret="secret",
            access_token="token",
            access_token_secret="token_secret"
        )

        assert config.is_valid() is True

    def test_is_valid_with_oauth2_only(self):
        """Test is_valid returns True with OAuth2 access token only."""
        config = TwitterConfig(
            oauth2_access_token="oauth2_token"
        )

        assert config.is_valid() is True

    def test_is_valid_with_both_oauth1_and_oauth2(self):
        """Test is_valid returns True with both OAuth1 and OAuth2."""
        config = TwitterConfig(
            api_key="key",
            api_secret="secret",
            access_token="token",
            access_token_secret="token_secret",
            oauth2_access_token="oauth2_token"
        )

        assert config.is_valid() is True

    def test_is_valid_missing_api_key(self):
        """Test is_valid returns False with missing API key."""
        config = TwitterConfig(
            api_key="",
            api_secret="secret",
            access_token="token",
            access_token_secret="token_secret"
        )

        assert config.is_valid() is False

    def test_is_valid_missing_api_secret(self):
        """Test is_valid returns False with missing API secret."""
        config = TwitterConfig(
            api_key="key",
            api_secret="",
            access_token="token",
            access_token_secret="token_secret"
        )

        assert config.is_valid() is False

    def test_is_valid_missing_access_token(self):
        """Test is_valid returns False with missing access token."""
        config = TwitterConfig(
            api_key="key",
            api_secret="secret",
            access_token="",
            access_token_secret="token_secret"
        )

        assert config.is_valid() is False

    def test_is_valid_missing_access_token_secret(self):
        """Test is_valid returns False with missing access token secret."""
        config = TwitterConfig(
            api_key="key",
            api_secret="secret",
            access_token="token",
            access_token_secret=""
        )

        assert config.is_valid() is False

    def test_is_valid_empty_config(self):
        """Test is_valid returns False with empty config."""
        config = TwitterConfig()

        assert config.is_valid() is False

    def test_from_env_with_x_prefix(self):
        """Test from_env loads X_ prefixed environment variables."""
        with patch.dict(os.environ, {
            "X_API_KEY": "x_api_key",
            "X_API_SECRET": "x_api_secret",
            "X_ACCESS_TOKEN": "x_access_token",
            "X_ACCESS_TOKEN_SECRET": "x_access_token_secret",
            "X_BEARER_TOKEN": "x_bearer_token",
            "X_OAUTH2_CLIENT_ID": "x_oauth2_client",
            "X_OAUTH2_CLIENT_SECRET": "x_oauth2_secret",
            "X_OAUTH2_ACCESS_TOKEN": "x_oauth2_token",
            "X_OAUTH2_REFRESH_TOKEN": "x_oauth2_refresh",
            "X_EXPECTED_USERNAME": "x_username",
        }, clear=False):
            config = TwitterConfig.from_env()

            assert config.api_key == "x_api_key"
            assert config.api_secret == "x_api_secret"
            assert config.access_token == "x_access_token"
            assert config.access_token_secret == "x_access_token_secret"
            assert config.bearer_token == "x_bearer_token"
            assert config.oauth2_client_id == "x_oauth2_client"
            assert config.oauth2_client_secret == "x_oauth2_secret"
            assert config.oauth2_access_token == "x_oauth2_token"
            assert config.oauth2_refresh_token == "x_oauth2_refresh"
            assert config.expected_username == "x_username"

    def test_from_env_with_twitter_prefix_fallback(self):
        """Test from_env falls back to TWITTER_ prefix when X_ not set."""
        with patch.dict(os.environ, {
            "TWITTER_API_KEY": "twitter_api_key",
            "TWITTER_API_SECRET": "twitter_api_secret",
            "TWITTER_ACCESS_TOKEN": "twitter_access_token",
            "TWITTER_ACCESS_TOKEN_SECRET": "twitter_access_token_secret",
            "TWITTER_BEARER_TOKEN": "twitter_bearer_token",
            "TWITTER_EXPECTED_USERNAME": "twitter_username",
        }, clear=False):
            # Clear X_ vars if they exist
            for key in ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN",
                       "X_ACCESS_TOKEN_SECRET", "X_BEARER_TOKEN", "X_EXPECTED_USERNAME"]:
                os.environ.pop(key, None)

            config = TwitterConfig.from_env()

            assert config.api_key == "twitter_api_key"
            assert config.api_secret == "twitter_api_secret"
            assert config.access_token == "twitter_access_token"
            assert config.access_token_secret == "twitter_access_token_secret"
            assert config.bearer_token == "twitter_bearer_token"
            assert config.expected_username == "twitter_username"

    def test_from_env_x_prefix_takes_priority(self):
        """Test from_env prefers X_ prefix over TWITTER_ prefix."""
        with patch.dict(os.environ, {
            "X_API_KEY": "x_key_priority",
            "TWITTER_API_KEY": "twitter_key_ignored",
            "X_API_SECRET": "x_secret_priority",
            "TWITTER_API_SECRET": "twitter_secret_ignored",
        }, clear=False):
            config = TwitterConfig.from_env()

            assert config.api_key == "x_key_priority"
            assert config.api_secret == "x_secret_priority"

    def test_from_env_empty_environment(self):
        """Test from_env with no environment variables set."""
        # Clear all relevant env vars
        env_vars_to_clear = [
            "X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET",
            "X_BEARER_TOKEN", "X_OAUTH2_CLIENT_ID", "X_OAUTH2_CLIENT_SECRET",
            "X_OAUTH2_ACCESS_TOKEN", "X_OAUTH2_REFRESH_TOKEN", "X_EXPECTED_USERNAME",
            "TWITTER_API_KEY", "TWITTER_API_SECRET", "TWITTER_ACCESS_TOKEN",
            "TWITTER_ACCESS_TOKEN_SECRET", "TWITTER_BEARER_TOKEN", "TWITTER_EXPECTED_USERNAME"
        ]

        with patch.dict(os.environ, {k: "" for k in env_vars_to_clear}, clear=False):
            config = TwitterConfig.from_env()

            assert config.api_key == ""
            assert config.api_secret == ""
            assert config.is_valid() is False


# =============================================================================
# GrokConfig Tests
# =============================================================================

class TestGrokConfig:
    """Tests for GrokConfig dataclass."""

    def test_grok_config_defaults(self):
        """Test GrokConfig default values."""
        config = GrokConfig()

        assert config.api_key == ""
        assert config.model == "grok-3"
        assert config.image_model == "grok-2-image"
        assert config.max_images_per_day == 6

    def test_grok_config_with_values(self):
        """Test GrokConfig with explicit values."""
        config = GrokConfig(
            api_key="xai_key",
            model="grok-2",
            image_model="grok-3-image",
            max_images_per_day=10
        )

        assert config.api_key == "xai_key"
        assert config.model == "grok-2"
        assert config.image_model == "grok-3-image"
        assert config.max_images_per_day == 10

    def test_from_env_with_api_key(self):
        """Test from_env loads XAI_API_KEY."""
        with patch.dict(os.environ, {"XAI_API_KEY": "test_xai_key"}, clear=False):
            config = GrokConfig.from_env()

            assert config.api_key == "test_xai_key"
            # Default values should be preserved
            assert config.model == "grok-3"
            assert config.image_model == "grok-2-image"
            assert config.max_images_per_day == 6

    def test_from_env_without_api_key(self):
        """Test from_env with no XAI_API_KEY set."""
        with patch.dict(os.environ, {"XAI_API_KEY": ""}, clear=False):
            config = GrokConfig.from_env()

            assert config.api_key == ""


# =============================================================================
# ScheduleConfig Tests
# =============================================================================

class TestScheduleConfig:
    """Tests for ScheduleConfig dataclass."""

    def test_schedule_config_defaults(self):
        """Test ScheduleConfig default values."""
        config = ScheduleConfig()

        assert config.timezone_offset == 0
        assert config.min_tweet_interval == 1800  # 30 minutes

    def test_schedule_config_default_schedule(self):
        """Test ScheduleConfig default posting schedule."""
        config = ScheduleConfig()

        assert 8 in config.schedule
        assert config.schedule[8] == "morning_report"
        assert 10 in config.schedule
        assert config.schedule[10] == "token_spotlight"
        assert 12 in config.schedule
        assert config.schedule[12] == "stock_picks"
        assert 14 in config.schedule
        assert config.schedule[14] == "macro_update"
        assert 16 in config.schedule
        assert config.schedule[16] == "commodities"
        assert 18 in config.schedule
        assert config.schedule[18] == "grok_insight"
        assert 20 in config.schedule
        assert config.schedule[20] == "evening_wrap"

    def test_schedule_config_custom_schedule(self):
        """Test ScheduleConfig with custom schedule."""
        custom_schedule = {
            9: "custom_morning",
            15: "custom_afternoon"
        }
        config = ScheduleConfig(schedule=custom_schedule)

        assert config.schedule == custom_schedule
        assert 9 in config.schedule
        assert config.schedule[9] == "custom_morning"

    def test_schedule_config_custom_timezone(self):
        """Test ScheduleConfig with custom timezone offset."""
        config = ScheduleConfig(timezone_offset=-5)  # EST

        assert config.timezone_offset == -5

    def test_schedule_config_custom_interval(self):
        """Test ScheduleConfig with custom tweet interval."""
        config = ScheduleConfig(min_tweet_interval=3600)  # 1 hour

        assert config.min_tweet_interval == 3600


# =============================================================================
# EngagementConfig Tests
# =============================================================================

class TestEngagementConfig:
    """Tests for EngagementConfig dataclass."""

    def test_engagement_config_defaults(self):
        """Test EngagementConfig default values."""
        config = EngagementConfig()

        assert config.auto_reply is True
        assert config.reply_probability == 0.3
        assert config.like_mentions is True
        assert config.max_replies_per_hour == 5
        assert config.check_interval == 60

    def test_engagement_config_custom_values(self):
        """Test EngagementConfig with custom values."""
        config = EngagementConfig(
            auto_reply=False,
            reply_probability=0.5,
            like_mentions=False,
            max_replies_per_hour=10,
            check_interval=120
        )

        assert config.auto_reply is False
        assert config.reply_probability == 0.5
        assert config.like_mentions is False
        assert config.max_replies_per_hour == 10
        assert config.check_interval == 120

    def test_engagement_config_reply_probability_range(self):
        """Test EngagementConfig reply probability edge cases."""
        config_zero = EngagementConfig(reply_probability=0.0)
        assert config_zero.reply_probability == 0.0

        config_full = EngagementConfig(reply_probability=1.0)
        assert config_full.reply_probability == 1.0


# =============================================================================
# BotConfiguration Tests
# =============================================================================

class TestBotConfiguration:
    """Tests for BotConfiguration dataclass."""

    def test_bot_configuration_defaults(self):
        """Test BotConfiguration uses default factories."""
        # Mock environment to control config creation
        with patch.dict(os.environ, {
            "X_API_KEY": "",
            "X_API_SECRET": "",
            "X_ACCESS_TOKEN": "",
            "X_ACCESS_TOKEN_SECRET": "",
            "XAI_API_KEY": ""
        }, clear=False):
            config = BotConfiguration()

            assert config.twitter is not None
            assert config.grok is not None
            assert config.schedule is not None
            assert config.engagement is not None
            assert isinstance(config.twitter, TwitterConfig)
            assert isinstance(config.grok, GrokConfig)
            assert isinstance(config.schedule, ScheduleConfig)
            assert isinstance(config.engagement, EngagementConfig)

    def test_bot_configuration_load(self):
        """Test BotConfiguration.load() classmethod."""
        with patch.dict(os.environ, {
            "X_API_KEY": "load_api_key",
            "X_API_SECRET": "load_api_secret",
            "X_ACCESS_TOKEN": "load_access_token",
            "X_ACCESS_TOKEN_SECRET": "load_access_secret",
            "XAI_API_KEY": "load_xai_key"
        }, clear=False):
            config = BotConfiguration.load()

            assert config.twitter.api_key == "load_api_key"
            assert config.grok.api_key == "load_xai_key"

    def test_validate_valid_config(self):
        """Test validate with valid configuration."""
        config = BotConfiguration(
            twitter=TwitterConfig(
                api_key="key",
                api_secret="secret",
                access_token="token",
                access_token_secret="token_secret"
            ),
            grok=GrokConfig(api_key="xai_key")
        )

        valid, errors = config.validate()

        assert valid is True
        assert errors == []

    def test_validate_invalid_twitter_credentials(self):
        """Test validate with invalid Twitter credentials."""
        config = BotConfiguration(
            twitter=TwitterConfig(),  # Empty = invalid
            grok=GrokConfig(api_key="xai_key")
        )

        valid, errors = config.validate()

        assert valid is False
        assert len(errors) == 1
        assert "Twitter credentials incomplete" in errors[0]

    def test_validate_missing_grok_api_key(self):
        """Test validate with missing Grok API key."""
        config = BotConfiguration(
            twitter=TwitterConfig(
                api_key="key",
                api_secret="secret",
                access_token="token",
                access_token_secret="token_secret"
            ),
            grok=GrokConfig(api_key="")  # Empty
        )

        valid, errors = config.validate()

        assert valid is False
        assert len(errors) == 1
        assert "XAI_API_KEY not set" in errors[0]

    def test_validate_multiple_errors(self):
        """Test validate with multiple errors."""
        config = BotConfiguration(
            twitter=TwitterConfig(),  # Empty = invalid
            grok=GrokConfig(api_key="")  # Empty
        )

        valid, errors = config.validate()

        assert valid is False
        assert len(errors) == 2
        assert any("Twitter" in e for e in errors)
        assert any("XAI_API_KEY" in e for e in errors)

    def test_validate_oauth2_only_is_valid(self):
        """Test validate accepts OAuth2-only Twitter credentials."""
        config = BotConfiguration(
            twitter=TwitterConfig(
                oauth2_access_token="oauth2_token"  # OAuth2 only
            ),
            grok=GrokConfig(api_key="xai_key")
        )

        valid, errors = config.validate()

        assert valid is True
        assert errors == []


# =============================================================================
# ENV_TEMPLATE Tests
# =============================================================================

class TestEnvTemplate:
    """Tests for ENV_TEMPLATE constant."""

    def test_env_template_contains_twitter_vars(self):
        """Test ENV_TEMPLATE includes Twitter variables."""
        assert "X_API_KEY" in ENV_TEMPLATE
        assert "X_API_SECRET" in ENV_TEMPLATE
        assert "X_ACCESS_TOKEN" in ENV_TEMPLATE
        assert "X_ACCESS_TOKEN_SECRET" in ENV_TEMPLATE
        assert "X_BEARER_TOKEN" in ENV_TEMPLATE
        assert "X_EXPECTED_USERNAME" in ENV_TEMPLATE

    def test_env_template_contains_oauth2_vars(self):
        """Test ENV_TEMPLATE includes OAuth2 variables."""
        assert "X_OAUTH2_CLIENT_ID" in ENV_TEMPLATE
        assert "X_OAUTH2_CLIENT_SECRET" in ENV_TEMPLATE
        assert "X_OAUTH2_ACCESS_TOKEN" in ENV_TEMPLATE
        assert "X_OAUTH2_REFRESH_TOKEN" in ENV_TEMPLATE
        assert "X_OAUTH2_REDIRECT_URI" in ENV_TEMPLATE

    def test_env_template_contains_xai_vars(self):
        """Test ENV_TEMPLATE includes xAI variables."""
        assert "XAI_API_KEY" in ENV_TEMPLATE

    def test_env_template_is_string(self):
        """Test ENV_TEMPLATE is a string."""
        assert isinstance(ENV_TEMPLATE, str)

    def test_env_template_has_comments(self):
        """Test ENV_TEMPLATE contains helpful comments."""
        assert "# JARVIS Twitter Bot" in ENV_TEMPLATE or "Twitter Bot" in ENV_TEMPLATE
        assert "#" in ENV_TEMPLATE  # Has comments


# =============================================================================
# print_env_template Tests
# =============================================================================

class TestPrintEnvTemplate:
    """Tests for print_env_template function."""

    def test_print_env_template_outputs_template(self):
        """Test print_env_template prints the template."""
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            print_env_template()
            output = mock_stdout.getvalue()

            assert "X_API_KEY" in output
            assert "XAI_API_KEY" in output


# =============================================================================
# check_config Tests
# =============================================================================

class TestCheckConfig:
    """Tests for check_config function."""

    def test_check_config_returns_true_when_valid(self):
        """Test check_config returns True for valid config."""
        with patch.dict(os.environ, {
            "X_API_KEY": "valid_key",
            "X_API_SECRET": "valid_secret",
            "X_ACCESS_TOKEN": "valid_token",
            "X_ACCESS_TOKEN_SECRET": "valid_token_secret",
            "XAI_API_KEY": "valid_xai_key"
        }, clear=False):
            with patch('sys.stdout', new_callable=StringIO):
                result = check_config()

                assert result is True

    def test_check_config_returns_false_when_invalid(self):
        """Test check_config returns False for invalid config."""
        with patch.dict(os.environ, {
            "X_API_KEY": "",
            "X_API_SECRET": "",
            "X_ACCESS_TOKEN": "",
            "X_ACCESS_TOKEN_SECRET": "",
            "XAI_API_KEY": ""
        }, clear=False):
            # Clear TWITTER_ fallbacks too
            for key in ["TWITTER_API_KEY", "TWITTER_API_SECRET",
                       "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_TOKEN_SECRET"]:
                os.environ.pop(key, None)

            with patch('sys.stdout', new_callable=StringIO):
                result = check_config()

                assert result is False

    def test_check_config_prints_valid_message(self):
        """Test check_config prints 'Configuration valid' when valid."""
        with patch.dict(os.environ, {
            "X_API_KEY": "key",
            "X_API_SECRET": "secret",
            "X_ACCESS_TOKEN": "token",
            "X_ACCESS_TOKEN_SECRET": "token_secret",
            "XAI_API_KEY": "xai_key"
        }, clear=False):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                check_config()
                output = mock_stdout.getvalue()

                assert "Configuration valid" in output

    def test_check_config_prints_errors_when_invalid(self):
        """Test check_config prints errors when invalid."""
        with patch.dict(os.environ, {
            "X_API_KEY": "",
            "X_API_SECRET": "",
            "X_ACCESS_TOKEN": "",
            "X_ACCESS_TOKEN_SECRET": "",
            "X_OAUTH2_ACCESS_TOKEN": "",
            "XAI_API_KEY": ""
        }, clear=False):
            # Clear fallbacks
            for key in ["TWITTER_API_KEY", "TWITTER_API_SECRET",
                       "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_TOKEN_SECRET"]:
                os.environ.pop(key, None)

            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                check_config()
                output = mock_stdout.getvalue()

                assert "Configuration errors" in output
                assert "-" in output  # Error bullets


# =============================================================================
# Module Load / dotenv Tests
# =============================================================================

class TestModuleLoad:
    """Tests for module-level loading behavior."""

    def test_module_import_succeeds(self):
        """Test module can be imported without errors."""
        import importlib
        import bots.twitter.config as config_module

        # Re-import to test loading
        importlib.reload(config_module)

        assert config_module.TwitterConfig is not None
        assert config_module.BotConfiguration is not None

    def test_module_handles_missing_dotenv(self):
        """Test module handles missing python-dotenv gracefully."""
        # The module already handles ImportError for dotenv
        # This test verifies the import doesn't fail
        import bots.twitter.config as config_module

        # Module should be loaded regardless of dotenv availability
        assert hasattr(config_module, 'TwitterConfig')
        assert hasattr(config_module, 'BotConfiguration')


# =============================================================================
# Edge Cases and Integration Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_twitter_config_partial_oauth1(self):
        """Test TwitterConfig with partial OAuth1 credentials."""
        # Missing one field
        config = TwitterConfig(
            api_key="key",
            api_secret="secret",
            access_token="token"
            # Missing access_token_secret
        )

        assert config.is_valid() is False

    def test_schedule_config_empty_schedule(self):
        """Test ScheduleConfig with empty schedule."""
        config = ScheduleConfig(schedule={})

        assert config.schedule == {}
        assert len(config.schedule) == 0

    def test_engagement_config_extreme_values(self):
        """Test EngagementConfig with extreme values."""
        config = EngagementConfig(
            reply_probability=0.0,
            max_replies_per_hour=0,
            check_interval=1
        )

        assert config.reply_probability == 0.0
        assert config.max_replies_per_hour == 0
        assert config.check_interval == 1

    def test_bot_configuration_with_custom_subconfigs(self):
        """Test BotConfiguration with custom sub-configurations."""
        custom_twitter = TwitterConfig(api_key="custom_key")
        custom_grok = GrokConfig(api_key="custom_grok")
        custom_schedule = ScheduleConfig(timezone_offset=-8)
        custom_engagement = EngagementConfig(auto_reply=False)

        config = BotConfiguration(
            twitter=custom_twitter,
            grok=custom_grok,
            schedule=custom_schedule,
            engagement=custom_engagement
        )

        assert config.twitter.api_key == "custom_key"
        assert config.grok.api_key == "custom_grok"
        assert config.schedule.timezone_offset == -8
        assert config.engagement.auto_reply is False

    def test_twitter_config_from_env_empty_string_fallback(self):
        """Test from_env handles empty X_ with non-empty TWITTER_ fallback."""
        with patch.dict(os.environ, {
            "X_API_KEY": "",
            "TWITTER_API_KEY": "fallback_key"
        }, clear=False):
            config = TwitterConfig.from_env()

            # Empty X_ should fall back to TWITTER_
            assert config.api_key == "fallback_key"

    def test_grok_config_preserves_custom_models(self):
        """Test GrokConfig preserves custom model names."""
        config = GrokConfig(
            api_key="key",
            model="grok-4-turbo",
            image_model="grok-4-vision"
        )

        assert config.model == "grok-4-turbo"
        assert config.image_model == "grok-4-vision"


# =============================================================================
# Dataclass Behavior Tests
# =============================================================================

class TestDataclassBehavior:
    """Tests for dataclass-specific behavior."""

    def test_twitter_config_is_dataclass(self):
        """Test TwitterConfig is a proper dataclass."""
        from dataclasses import fields, is_dataclass

        assert is_dataclass(TwitterConfig)

        field_names = [f.name for f in fields(TwitterConfig)]
        assert "api_key" in field_names
        assert "api_secret" in field_names

    def test_grok_config_is_dataclass(self):
        """Test GrokConfig is a proper dataclass."""
        from dataclasses import fields, is_dataclass

        assert is_dataclass(GrokConfig)

        field_names = [f.name for f in fields(GrokConfig)]
        assert "api_key" in field_names
        assert "model" in field_names

    def test_schedule_config_is_dataclass(self):
        """Test ScheduleConfig is a proper dataclass."""
        from dataclasses import is_dataclass

        assert is_dataclass(ScheduleConfig)

    def test_engagement_config_is_dataclass(self):
        """Test EngagementConfig is a proper dataclass."""
        from dataclasses import is_dataclass

        assert is_dataclass(EngagementConfig)

    def test_bot_configuration_is_dataclass(self):
        """Test BotConfiguration is a proper dataclass."""
        from dataclasses import is_dataclass

        assert is_dataclass(BotConfiguration)

    def test_schedule_config_schedule_is_mutable_default(self):
        """Test ScheduleConfig schedule uses field factory for mutable default."""
        config1 = ScheduleConfig()
        config2 = ScheduleConfig()

        # Modifying one should not affect the other
        config1.schedule[9] = "custom_9am"

        assert 9 not in config2.schedule or config2.schedule.get(9) != "custom_9am"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
