"""
Tests for core/security/credential_loader.py

Comprehensive tests for the unified credential loader system.
Tests cover:
- XCredentials dataclass methods
- TelegramCredentials dataclass methods
- BotCredentials factory behavior
- CredentialLoader initialization and loading
- Environment file parsing
- Environment variable loading
- Credential mapping
- Async X account validation
- Singleton pattern for get_credential_loader
"""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

from core.security.credential_loader import (
    XCredentials,
    TelegramCredentials,
    BotCredentials,
    CredentialLoader,
    get_credential_loader,
    _loader,
)


# ============================================================================
# XCredentials Tests
# ============================================================================

class TestXCredentials:
    """Tests for XCredentials dataclass."""

    def test_default_values(self):
        """Test XCredentials has correct default values."""
        creds = XCredentials()

        assert creds.oauth2_client_id == ""
        assert creds.oauth2_client_secret == ""
        assert creds.oauth2_access_token == ""
        assert creds.oauth2_refresh_token == ""
        assert creds.api_key == ""
        assert creds.api_secret == ""
        assert creds.access_token == ""
        assert creds.access_token_secret == ""
        assert creds.expected_username == "jarvis_lifeos"
        assert creds.xai_api_key == ""

    def test_is_complete_with_oauth2_token(self):
        """Test is_complete returns True with oauth2 access token."""
        creds = XCredentials(oauth2_access_token="valid_token")

        assert creds.is_complete() is True

    def test_is_complete_with_api_key(self):
        """Test is_complete returns True with api_key."""
        creds = XCredentials(api_key="valid_api_key")

        assert creds.is_complete() is True

    def test_is_complete_without_tokens(self):
        """Test is_complete returns False without any tokens."""
        creds = XCredentials()

        assert creds.is_complete() is False

    def test_is_complete_with_empty_strings(self):
        """Test is_complete returns False with empty strings."""
        creds = XCredentials(oauth2_access_token="", api_key="")

        assert creds.is_complete() is False

    def test_can_upload_media_with_all_credentials(self):
        """Test can_upload_media returns True when all media credentials present."""
        creds = XCredentials(
            api_key="key",
            api_secret="secret",
            access_token="token",
            access_token_secret="token_secret"
        )

        assert creds.can_upload_media() is True

    def test_can_upload_media_missing_api_key(self):
        """Test can_upload_media returns False without api_key."""
        creds = XCredentials(
            api_secret="secret",
            access_token="token",
            access_token_secret="token_secret"
        )

        assert creds.can_upload_media() is False

    def test_can_upload_media_missing_api_secret(self):
        """Test can_upload_media returns False without api_secret."""
        creds = XCredentials(
            api_key="key",
            access_token="token",
            access_token_secret="token_secret"
        )

        assert creds.can_upload_media() is False

    def test_can_upload_media_missing_access_token(self):
        """Test can_upload_media returns False without access_token."""
        creds = XCredentials(
            api_key="key",
            api_secret="secret",
            access_token_secret="token_secret"
        )

        assert creds.can_upload_media() is False

    def test_can_upload_media_missing_access_token_secret(self):
        """Test can_upload_media returns False without access_token_secret."""
        creds = XCredentials(
            api_key="key",
            api_secret="secret",
            access_token="token"
        )

        assert creds.can_upload_media() is False

    def test_can_upload_media_empty_strings(self):
        """Test can_upload_media returns False with empty strings."""
        creds = XCredentials(
            api_key="",
            api_secret="secret",
            access_token="token",
            access_token_secret="token_secret"
        )

        assert creds.can_upload_media() is False


# ============================================================================
# TelegramCredentials Tests
# ============================================================================

class TestTelegramCredentials:
    """Tests for TelegramCredentials dataclass."""

    def test_default_values(self):
        """Test TelegramCredentials has correct default values."""
        creds = TelegramCredentials()

        assert creds.bot_token == ""
        assert creds.admin_ids == []
        assert creds.admin_chat_id == ""
        assert creds.buy_bot_token == ""

    def test_admin_ids_default_factory(self):
        """Test admin_ids uses a default factory (not shared list)."""
        creds1 = TelegramCredentials()
        creds2 = TelegramCredentials()

        creds1.admin_ids.append("123")

        # creds2 should not be affected
        assert creds2.admin_ids == []

    def test_is_complete_with_bot_token(self):
        """Test is_complete returns True with bot_token."""
        creds = TelegramCredentials(bot_token="valid_token")

        assert creds.is_complete() is True

    def test_is_complete_without_bot_token(self):
        """Test is_complete returns False without bot_token."""
        creds = TelegramCredentials()

        assert creds.is_complete() is False

    def test_is_complete_with_empty_bot_token(self):
        """Test is_complete returns False with empty bot_token."""
        creds = TelegramCredentials(bot_token="")

        assert creds.is_complete() is False

    def test_custom_values(self):
        """Test TelegramCredentials with custom values."""
        creds = TelegramCredentials(
            bot_token="123456:ABC",
            admin_ids=["111", "222"],
            admin_chat_id="-100123456",
            buy_bot_token="789012:DEF"
        )

        assert creds.bot_token == "123456:ABC"
        assert creds.admin_ids == ["111", "222"]
        assert creds.admin_chat_id == "-100123456"
        assert creds.buy_bot_token == "789012:DEF"


# ============================================================================
# BotCredentials Tests
# ============================================================================

class TestBotCredentials:
    """Tests for BotCredentials dataclass."""

    def test_default_factories(self):
        """Test BotCredentials uses default factories for nested objects."""
        creds = BotCredentials()

        assert isinstance(creds.x, XCredentials)
        assert isinstance(creds.telegram, TelegramCredentials)

    def test_independent_instances(self):
        """Test BotCredentials creates independent nested instances."""
        creds1 = BotCredentials()
        creds2 = BotCredentials()

        creds1.x.api_key = "key1"

        # creds2 should not be affected
        assert creds2.x.api_key == ""

    def test_custom_nested_values(self):
        """Test BotCredentials with custom nested values."""
        x_creds = XCredentials(api_key="custom_key")
        tg_creds = TelegramCredentials(bot_token="custom_token")

        creds = BotCredentials(x=x_creds, telegram=tg_creds)

        assert creds.x.api_key == "custom_key"
        assert creds.telegram.bot_token == "custom_token"


# ============================================================================
# CredentialLoader Initialization Tests
# ============================================================================

class TestCredentialLoaderInit:
    """Tests for CredentialLoader initialization."""

    def test_init_default_project_root(self):
        """Test CredentialLoader uses cwd as default project_root."""
        loader = CredentialLoader()

        assert loader.project_root == Path.cwd()
        assert loader._credentials is None
        assert loader._validated is False

    def test_init_custom_project_root(self):
        """Test CredentialLoader with custom project_root."""
        loader = CredentialLoader(project_root="/custom/path")

        assert loader.project_root == Path("/custom/path")

    def test_init_string_project_root_converted_to_path(self):
        """Test string project_root is converted to Path."""
        loader = CredentialLoader(project_root="/some/path")

        assert isinstance(loader.project_root, Path)

    def test_env_files_class_attribute(self):
        """Test ENV_FILES class attribute is correctly set."""
        assert CredentialLoader.ENV_FILES == [".env", "tg_bot/.env", "bots/twitter/.env"]


# ============================================================================
# CredentialLoader.load() Tests
# ============================================================================

class TestCredentialLoaderLoad:
    """Tests for CredentialLoader.load() method."""

    def test_load_returns_bot_credentials(self):
        """Test load returns BotCredentials instance."""
        loader = CredentialLoader()

        with patch.object(loader, '_load_env_file'):
            with patch.object(loader, '_load_from_environment'):
                creds = loader.load()

        assert isinstance(creds, BotCredentials)

    def test_load_caches_credentials(self):
        """Test load caches and returns same credentials on subsequent calls."""
        loader = CredentialLoader()

        with patch.object(loader, '_load_env_file'):
            with patch.object(loader, '_load_from_environment'):
                creds1 = loader.load()
                creds2 = loader.load()

        assert creds1 is creds2

    def test_load_calls_env_file_loading(self):
        """Test load calls _load_env_file for each env file in reversed order."""
        loader = CredentialLoader(project_root="/test/project")

        with patch.object(loader, '_load_env_file') as mock_load_env:
            with patch.object(loader, '_load_from_environment'):
                with patch('pathlib.Path.exists', return_value=True):
                    loader.load()

        # Should be called for each ENV_FILES in reversed order
        assert mock_load_env.call_count == 3

    def test_load_skips_nonexistent_env_files(self):
        """Test load skips env files that don't exist."""
        loader = CredentialLoader(project_root="/test/project")

        with patch.object(loader, '_load_env_file') as mock_load_env:
            with patch.object(loader, '_load_from_environment'):
                with patch('pathlib.Path.exists', return_value=False):
                    loader.load()

        # Should not be called since files don't exist
        mock_load_env.assert_not_called()

    def test_load_calls_environment_loading_last(self):
        """Test load calls _load_from_environment after env files."""
        loader = CredentialLoader()
        call_order = []

        def track_env_file(*args):
            call_order.append('env_file')

        def track_environment(*args):
            call_order.append('environment')

        with patch.object(loader, '_load_env_file', side_effect=track_env_file):
            with patch.object(loader, '_load_from_environment', side_effect=track_environment):
                with patch('pathlib.Path.exists', return_value=True):
                    loader.load()

        # Environment should be loaded after env files
        assert call_order[-1] == 'environment'


# ============================================================================
# CredentialLoader._load_env_file() Tests
# ============================================================================

class TestCredentialLoaderLoadEnvFile:
    """Tests for CredentialLoader._load_env_file() method."""

    def test_load_env_file_basic(self):
        """Test _load_env_file parses basic KEY=value format."""
        loader = CredentialLoader()
        creds = BotCredentials()

        env_content = "X_OAUTH2_ACCESS_TOKEN=test_token\n"

        with patch('builtins.open', mock_open(read_data=env_content)):
            loader._load_env_file(Path("/test/.env"), creds)

        assert creds.x.oauth2_access_token == "test_token"

    def test_load_env_file_strips_quotes(self):
        """Test _load_env_file strips quotes from values."""
        loader = CredentialLoader()
        creds = BotCredentials()

        env_content = 'X_API_KEY="my_api_key"\n'

        with patch('builtins.open', mock_open(read_data=env_content)):
            loader._load_env_file(Path("/test/.env"), creds)

        assert creds.x.api_key == "my_api_key"

    def test_load_env_file_skips_comments(self):
        """Test _load_env_file skips comment lines."""
        loader = CredentialLoader()
        creds = BotCredentials()

        env_content = "# This is a comment\nX_API_KEY=valid_key\n"

        with patch('builtins.open', mock_open(read_data=env_content)):
            loader._load_env_file(Path("/test/.env"), creds)

        assert creds.x.api_key == "valid_key"

    def test_load_env_file_skips_empty_lines(self):
        """Test _load_env_file skips empty lines."""
        loader = CredentialLoader()
        creds = BotCredentials()

        env_content = "\n\nX_API_KEY=valid_key\n\n"

        with patch('builtins.open', mock_open(read_data=env_content)):
            loader._load_env_file(Path("/test/.env"), creds)

        assert creds.x.api_key == "valid_key"

    def test_load_env_file_skips_lines_without_equals(self):
        """Test _load_env_file skips lines without '=' sign."""
        loader = CredentialLoader()
        creds = BotCredentials()

        env_content = "INVALID LINE\nX_API_KEY=valid_key\n"

        with patch('builtins.open', mock_open(read_data=env_content)):
            loader._load_env_file(Path("/test/.env"), creds)

        assert creds.x.api_key == "valid_key"

    def test_load_env_file_handles_values_with_equals(self):
        """Test _load_env_file handles values containing '=' sign."""
        loader = CredentialLoader()
        creds = BotCredentials()

        env_content = "X_API_KEY=key=with=equals\n"

        with patch('builtins.open', mock_open(read_data=env_content)):
            loader._load_env_file(Path("/test/.env"), creds)

        assert creds.x.api_key == "key=with=equals"

    def test_load_env_file_handles_whitespace(self):
        """Test _load_env_file strips whitespace from keys and values."""
        loader = CredentialLoader()
        creds = BotCredentials()

        env_content = "  X_API_KEY  =  my_key  \n"

        with patch('builtins.open', mock_open(read_data=env_content)):
            loader._load_env_file(Path("/test/.env"), creds)

        assert creds.x.api_key == "my_key"

    def test_load_env_file_handles_exception(self):
        """Test _load_env_file handles file read exceptions gracefully."""
        loader = CredentialLoader()
        creds = BotCredentials()

        with patch('builtins.open', side_effect=IOError("File not readable")):
            # Should not raise, just log warning
            loader._load_env_file(Path("/test/.env"), creds)

        # Credentials should be unchanged
        assert creds.x.api_key == ""

    def test_load_env_file_multiple_credentials(self):
        """Test _load_env_file parses multiple credentials."""
        loader = CredentialLoader()
        creds = BotCredentials()

        env_content = """
X_API_KEY=api_key_value
TELEGRAM_BOT_TOKEN=bot_token_value
XAI_API_KEY=xai_key_value
"""

        with patch('builtins.open', mock_open(read_data=env_content)):
            loader._load_env_file(Path("/test/.env"), creds)

        assert creds.x.api_key == "api_key_value"
        assert creds.telegram.bot_token == "bot_token_value"
        assert creds.x.xai_api_key == "xai_key_value"


# ============================================================================
# CredentialLoader._load_from_environment() Tests
# ============================================================================

class TestCredentialLoaderLoadFromEnvironment:
    """Tests for CredentialLoader._load_from_environment() method."""

    def test_load_x_oauth2_access_token(self):
        """Test loading X_OAUTH2_ACCESS_TOKEN from environment."""
        loader = CredentialLoader()
        creds = BotCredentials()

        with patch.dict(os.environ, {"X_OAUTH2_ACCESS_TOKEN": "env_oauth_token"}):
            loader._load_from_environment(creds)

        assert creds.x.oauth2_access_token == "env_oauth_token"

    def test_load_x_api_key(self):
        """Test loading X_API_KEY from environment."""
        loader = CredentialLoader()
        creds = BotCredentials()

        with patch.dict(os.environ, {"X_API_KEY": "env_api_key"}):
            loader._load_from_environment(creds)

        assert creds.x.api_key == "env_api_key"

    def test_load_x_expected_username(self):
        """Test loading X_EXPECTED_USERNAME from environment."""
        loader = CredentialLoader()
        creds = BotCredentials()

        with patch.dict(os.environ, {"X_EXPECTED_USERNAME": "custom_user"}):
            loader._load_from_environment(creds)

        assert creds.x.expected_username == "custom_user"

    def test_load_xai_api_key(self):
        """Test loading XAI_API_KEY from environment."""
        loader = CredentialLoader()
        creds = BotCredentials()

        with patch.dict(os.environ, {"XAI_API_KEY": "xai_key"}):
            loader._load_from_environment(creds)

        assert creds.x.xai_api_key == "xai_key"

    def test_load_telegram_bot_token(self):
        """Test loading TELEGRAM_BOT_TOKEN from environment."""
        loader = CredentialLoader()
        creds = BotCredentials()

        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "tg_token"}):
            loader._load_from_environment(creds)

        assert creds.telegram.bot_token == "tg_token"

    def test_load_telegram_admin_chat_id(self):
        """Test loading TELEGRAM_ADMIN_CHAT_ID from environment."""
        loader = CredentialLoader()
        creds = BotCredentials()

        with patch.dict(os.environ, {"TELEGRAM_ADMIN_CHAT_ID": "-100123456"}):
            loader._load_from_environment(creds)

        assert creds.telegram.admin_chat_id == "-100123456"

    def test_load_multiple_environment_variables(self):
        """Test loading multiple environment variables at once."""
        loader = CredentialLoader()
        creds = BotCredentials()

        env_vars = {
            "X_OAUTH2_ACCESS_TOKEN": "oauth_token",
            "X_API_KEY": "api_key",
            "TELEGRAM_BOT_TOKEN": "bot_token",
            "XAI_API_KEY": "xai_key",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            loader._load_from_environment(creds)

        assert creds.x.oauth2_access_token == "oauth_token"
        assert creds.x.api_key == "api_key"
        assert creds.telegram.bot_token == "bot_token"
        assert creds.x.xai_api_key == "xai_key"

    def test_load_skips_missing_environment_variables(self):
        """Test that missing environment variables don't overwrite defaults."""
        loader = CredentialLoader()
        creds = BotCredentials()
        creds.x.api_key = "existing_key"

        # Ensure X_API_KEY is not in environment
        with patch.dict(os.environ, {}, clear=True):
            loader._load_from_environment(creds)

        # Should retain existing value since env var is not set
        assert creds.x.api_key == "existing_key"


# ============================================================================
# CredentialLoader._set_credential() Tests
# ============================================================================

class TestCredentialLoaderSetCredential:
    """Tests for CredentialLoader._set_credential() method."""

    def test_set_oauth2_access_token(self):
        """Test setting oauth2_access_token via OAUTH2_ACCESS key."""
        loader = CredentialLoader()
        creds = BotCredentials()

        loader._set_credential("X_OAUTH2_ACCESS_TOKEN", "oauth_value", creds)

        assert creds.x.oauth2_access_token == "oauth_value"

    def test_set_api_key(self):
        """Test setting api_key via API_KEY key."""
        loader = CredentialLoader()
        creds = BotCredentials()

        loader._set_credential("X_API_KEY", "api_key_value", creds)

        assert creds.x.api_key == "api_key_value"

    def test_set_xai_api_key(self):
        """Test setting xai_api_key via XAI_API_KEY key."""
        loader = CredentialLoader()
        creds = BotCredentials()

        loader._set_credential("XAI_API_KEY", "xai_value", creds)

        assert creds.x.xai_api_key == "xai_value"

    def test_api_key_not_set_for_xai_key(self):
        """Test that XAI_API_KEY doesn't set the regular api_key."""
        loader = CredentialLoader()
        creds = BotCredentials()

        loader._set_credential("XAI_API_KEY", "xai_value", creds)

        assert creds.x.api_key == ""
        assert creds.x.xai_api_key == "xai_value"

    def test_set_expected_username(self):
        """Test setting expected_username via EXPECTED_USERNAME key."""
        loader = CredentialLoader()
        creds = BotCredentials()

        loader._set_credential("X_EXPECTED_USERNAME", "custom_user", creds)

        assert creds.x.expected_username == "custom_user"

    def test_set_telegram_token(self):
        """Test setting telegram bot_token."""
        loader = CredentialLoader()
        creds = BotCredentials()

        loader._set_credential("TELEGRAM_BOT_TOKEN", "tg_token_value", creds)

        assert creds.telegram.bot_token == "tg_token_value"

    def test_telegram_token_not_set_for_buy_bot(self):
        """Test that TELEGRAM_BUY_BOT_TOKEN doesn't set main bot_token."""
        loader = CredentialLoader()
        creds = BotCredentials()

        loader._set_credential("TELEGRAM_BUY_BOT_TOKEN", "buy_bot_token", creds)

        # Main bot_token should not be set
        assert creds.telegram.bot_token == ""

    def test_set_admin_chat_id(self):
        """Test setting admin_chat_id."""
        loader = CredentialLoader()
        creds = BotCredentials()

        loader._set_credential("TELEGRAM_ADMIN_CHAT_ID", "-100123456", creds)

        assert creds.telegram.admin_chat_id == "-100123456"

    def test_set_credential_case_insensitive(self):
        """Test that credential keys are case insensitive."""
        loader = CredentialLoader()
        creds = BotCredentials()

        loader._set_credential("x_api_key", "lowercase_key", creds)

        assert creds.x.api_key == "lowercase_key"

    def test_set_credential_unknown_key(self):
        """Test that unknown keys don't cause errors."""
        loader = CredentialLoader()
        creds = BotCredentials()

        # Should not raise
        loader._set_credential("UNKNOWN_KEY", "some_value", creds)

        # Credentials should be unchanged
        assert creds.x.api_key == ""
        assert creds.telegram.bot_token == ""


# ============================================================================
# CredentialLoader.validate_x_account() Tests
# ============================================================================

class TestCredentialLoaderValidateXAccount:
    """Tests for CredentialLoader.validate_x_account() async method."""

    @pytest.mark.asyncio
    async def test_validate_returns_false_without_expected_username(self):
        """Test validation fails without expected_username set."""
        loader = CredentialLoader()
        loader._credentials = BotCredentials()
        loader._credentials.x.expected_username = ""
        loader._credentials.x.oauth2_access_token = "valid_token"

        success, message = await loader.validate_x_account()

        assert success is False
        assert "X_EXPECTED_USERNAME not set" in message

    @pytest.mark.asyncio
    async def test_validate_returns_false_without_oauth2_token(self):
        """Test validation fails without oauth2 token."""
        loader = CredentialLoader()
        loader._credentials = BotCredentials()
        loader._credentials.x.expected_username = "jarvis_lifeos"
        loader._credentials.x.oauth2_access_token = ""

        success, message = await loader.validate_x_account()

        assert success is False
        assert "No OAuth2 token" in message

    @pytest.mark.asyncio
    async def test_validate_success_matching_username(self):
        """Test validation succeeds when username matches."""
        loader = CredentialLoader()
        loader._credentials = BotCredentials()
        loader._credentials.x.expected_username = "jarvis_lifeos"
        loader._credentials.x.oauth2_access_token = "valid_token"

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "data": {"username": "jarvis_lifeos"}
        })

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock()
        ))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        with patch('aiohttp.ClientSession', return_value=mock_session):
            success, message = await loader.validate_x_account()

        assert success is True
        assert "Validated" in message
        assert "@jarvis_lifeos" in message
        assert loader._validated is True

    @pytest.mark.asyncio
    async def test_validate_success_case_insensitive(self):
        """Test validation is case insensitive for username."""
        loader = CredentialLoader()
        loader._credentials = BotCredentials()
        loader._credentials.x.expected_username = "Jarvis_LifeOS"
        loader._credentials.x.oauth2_access_token = "valid_token"

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "data": {"username": "jarvis_lifeos"}
        })

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock()
        ))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        with patch('aiohttp.ClientSession', return_value=mock_session):
            success, message = await loader.validate_x_account()

        assert success is True

    @pytest.mark.asyncio
    async def test_validate_failure_username_mismatch(self):
        """Test validation fails when username doesn't match."""
        loader = CredentialLoader()
        loader._credentials = BotCredentials()
        loader._credentials.x.expected_username = "jarvis_lifeos"
        loader._credentials.x.oauth2_access_token = "valid_token"

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "data": {"username": "wrong_user"}
        })

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock()
        ))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        with patch('aiohttp.ClientSession', return_value=mock_session):
            success, message = await loader.validate_x_account()

        assert success is False
        assert "Account mismatch" in message
        assert "@wrong_user" in message
        assert "@jarvis_lifeos" in message

    @pytest.mark.asyncio
    async def test_validate_failure_api_error(self):
        """Test validation handles API error response."""
        loader = CredentialLoader()
        loader._credentials = BotCredentials()
        loader._credentials.x.expected_username = "jarvis_lifeos"
        loader._credentials.x.oauth2_access_token = "valid_token"

        mock_response = AsyncMock()
        mock_response.status = 401

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock()
        ))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        with patch('aiohttp.ClientSession', return_value=mock_session):
            success, message = await loader.validate_x_account()

        assert success is False
        assert "API error: 401" in message

    @pytest.mark.asyncio
    async def test_validate_handles_exception(self):
        """Test validation handles exceptions gracefully."""
        loader = CredentialLoader()
        loader._credentials = BotCredentials()
        loader._credentials.x.expected_username = "jarvis_lifeos"
        loader._credentials.x.oauth2_access_token = "valid_token"

        with patch('aiohttp.ClientSession', side_effect=Exception("Network error")):
            success, message = await loader.validate_x_account()

        assert success is False
        assert "Network error" in message

    @pytest.mark.asyncio
    async def test_validate_calls_load_if_no_credentials(self):
        """Test validate_x_account calls load() if no cached credentials."""
        loader = CredentialLoader()

        with patch.object(loader, 'load') as mock_load:
            mock_creds = BotCredentials()
            mock_creds.x.expected_username = ""
            mock_load.return_value = mock_creds

            success, message = await loader.validate_x_account()

        mock_load.assert_called_once()


# ============================================================================
# get_credential_loader() Tests
# ============================================================================

class TestGetCredentialLoader:
    """Tests for get_credential_loader() singleton function."""

    def test_get_credential_loader_returns_instance(self):
        """Test get_credential_loader returns a CredentialLoader instance."""
        # Reset global state
        import core.security.credential_loader as module
        module._loader = None

        loader = get_credential_loader()

        assert isinstance(loader, CredentialLoader)

    def test_get_credential_loader_singleton(self):
        """Test get_credential_loader returns same instance on subsequent calls."""
        # Reset global state
        import core.security.credential_loader as module
        module._loader = None

        loader1 = get_credential_loader()
        loader2 = get_credential_loader()

        assert loader1 is loader2

    def test_get_credential_loader_creates_new_if_none(self):
        """Test get_credential_loader creates new instance if _loader is None."""
        import core.security.credential_loader as module
        module._loader = None

        loader = get_credential_loader()

        assert module._loader is not None
        assert module._loader is loader


# ============================================================================
# Integration Tests
# ============================================================================

class TestCredentialLoaderIntegration:
    """Integration tests for CredentialLoader."""

    @pytest.fixture
    def clean_credential_env(self):
        """Fixture to clear credential-related environment variables."""
        # Keys used by the credential loader
        cred_keys = [
            "X_OAUTH2_ACCESS_TOKEN", "X_API_KEY", "X_EXPECTED_USERNAME",
            "XAI_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_ADMIN_CHAT_ID"
        ]
        # Save original values
        saved = {k: os.environ.get(k) for k in cred_keys}
        # Clear them
        for k in cred_keys:
            if k in os.environ:
                del os.environ[k]
        yield
        # Restore original values
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
            elif k in os.environ:
                del os.environ[k]

    def test_full_load_from_env_file(self, clean_credential_env):
        """Test loading credentials from an actual temp env file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text("""
# X API Credentials
X_OAUTH2_ACCESS_TOKEN=test_oauth_token
X_API_KEY=test_api_key
X_EXPECTED_USERNAME=test_user
XAI_API_KEY=test_xai_key

# Telegram Credentials
TELEGRAM_BOT_TOKEN=123456:ABCDEF
TELEGRAM_ADMIN_CHAT_ID=-100123456789
""")

            loader = CredentialLoader(project_root=tmpdir)
            creds = loader.load()

            assert creds.x.oauth2_access_token == "test_oauth_token"
            assert creds.x.api_key == "test_api_key"
            assert creds.x.expected_username == "test_user"
            assert creds.x.xai_api_key == "test_xai_key"
            assert creds.telegram.bot_token == "123456:ABCDEF"
            assert creds.telegram.admin_chat_id == "-100123456789"

    def test_env_vars_override_file_values(self):
        """Test environment variables override .env file values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text("X_API_KEY=file_value\n")

            loader = CredentialLoader(project_root=tmpdir)

            with patch.dict(os.environ, {"X_API_KEY": "env_value"}):
                creds = loader.load()

            # Environment variable should win
            assert creds.x.api_key == "env_value"

    def test_multiple_env_files_priority(self):
        """Test that later env files override earlier ones."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create root .env
            root_env = Path(tmpdir) / ".env"
            root_env.write_text("X_API_KEY=root_value\n")

            # Create tg_bot/.env
            tg_bot_dir = Path(tmpdir) / "tg_bot"
            tg_bot_dir.mkdir()
            tg_env = tg_bot_dir / ".env"
            tg_env.write_text("X_API_KEY=tg_value\n")

            loader = CredentialLoader(project_root=tmpdir)

            # Clear environment to isolate test
            with patch.dict(os.environ, {}, clear=True):
                creds = loader.load()

            # Files are loaded in reversed order, so .env is loaded last
            # and should have final value
            assert creds.x.api_key == "root_value"

    def test_credentials_is_complete_check(self, clean_credential_env):
        """Test using is_complete after loading credentials."""
        loader = CredentialLoader()

        with patch.object(loader, '_load_env_file'):
            with patch.dict(os.environ, {"X_OAUTH2_ACCESS_TOKEN": "token"}, clear=False):
                creds = loader.load()

        assert creds.x.is_complete() is True
        # Telegram won't be complete without bot_token
        assert creds.telegram.is_complete() is False


# ============================================================================
# Edge Cases
# ============================================================================

class TestCredentialLoaderEdgeCases:
    """Edge case tests for CredentialLoader."""

    @pytest.fixture
    def clean_credential_env(self):
        """Fixture to clear credential-related environment variables."""
        cred_keys = [
            "X_OAUTH2_ACCESS_TOKEN", "X_API_KEY", "X_EXPECTED_USERNAME",
            "XAI_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_ADMIN_CHAT_ID"
        ]
        saved = {k: os.environ.get(k) for k in cred_keys}
        for k in cred_keys:
            if k in os.environ:
                del os.environ[k]
        yield
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
            elif k in os.environ:
                del os.environ[k]

    def test_empty_env_file(self, clean_credential_env):
        """Test handling of empty .env file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text("")

            loader = CredentialLoader(project_root=tmpdir)
            creds = loader.load()

            # Should return empty credentials without error
            assert creds.x.api_key == ""
            assert creds.telegram.bot_token == ""

    def test_env_file_with_only_comments(self, clean_credential_env):
        """Test handling of .env file with only comments."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text("# Just a comment\n# Another comment\n")

            loader = CredentialLoader(project_root=tmpdir)
            creds = loader.load()

            assert creds.x.api_key == ""

    def test_env_file_with_special_characters_in_value(self, clean_credential_env):
        """Test handling of special characters in credential values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text('X_API_KEY="key!@#$%^&*()"\n')

            loader = CredentialLoader(project_root=tmpdir)
            creds = loader.load()

            assert creds.x.api_key == "key!@#$%^&*()"

    def test_env_file_with_multiline_ignored(self):
        """Test that multiline values are handled (only first line used)."""
        loader = CredentialLoader()
        creds = BotCredentials()

        # Simulate a file read with multiline content
        env_content = "X_API_KEY=first_line\nX_EXPECTED_USERNAME=second_line\n"

        with patch('builtins.open', mock_open(read_data=env_content)):
            loader._load_env_file(Path("/test/.env"), creds)

        assert creds.x.api_key == "first_line"
        assert creds.x.expected_username == "second_line"

    def test_repeated_loads_use_cache(self):
        """Test that repeated load() calls return cached credentials."""
        loader = CredentialLoader()

        with patch.object(loader, '_load_env_file') as mock_env:
            with patch.object(loader, '_load_from_environment') as mock_from_env:
                loader.load()
                loader.load()
                loader.load()

        # Should only be called once due to caching
        mock_from_env.assert_called_once()

    def test_logger_exists(self):
        """Test that module logger is properly configured."""
        import core.security.credential_loader as module

        assert module.logger is not None
        assert module.logger.name == "jarvis.security.credentials"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
