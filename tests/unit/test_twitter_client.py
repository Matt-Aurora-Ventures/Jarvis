"""
Comprehensive unit tests for the Twitter Client.

Tests cover:
- TwitterCredentials loading and validation
- TweetResult dataclass
- TwitterClient connection and posting
- OAuth 2.0 token refresh
- Retry logic and circuit breaker
- Media upload
- Tweet operations (reply, quote, like, retweet)
- Error handling
"""

import pytest
import asyncio
import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
import os

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bots.twitter.twitter_client import (
    TwitterCredentials,
    TweetResult,
    TwitterClient,
    RetryablePostError,
    _is_retryable_status,
    _is_retryable_exception,
)


# =============================================================================
# TweetResult Tests
# =============================================================================

class TestTweetResult:
    """Tests for TweetResult dataclass."""

    def test_successful_result(self):
        """Test successful TweetResult creation."""
        result = TweetResult(
            success=True,
            tweet_id="123456789",
            url="https://x.com/test/status/123456789",
        )

        assert result.success is True
        assert result.tweet_id == "123456789"
        assert result.url is not None
        assert result.error is None

    def test_failed_result(self):
        """Test failed TweetResult creation."""
        result = TweetResult(
            success=False,
            error="Rate limited",
        )

        assert result.success is False
        assert result.error == "Rate limited"
        assert result.tweet_id is None

    def test_result_has_timestamp(self):
        """Test TweetResult has automatic timestamp."""
        result = TweetResult(success=True)
        assert result.timestamp is not None
        assert isinstance(result.timestamp, datetime)

    def test_result_with_explicit_timestamp(self):
        """Test TweetResult with explicit timestamp."""
        ts = datetime(2024, 1, 1, 12, 0, 0)
        result = TweetResult(success=True, timestamp=ts)
        assert result.timestamp == ts


# =============================================================================
# TwitterCredentials Tests
# =============================================================================

class TestTwitterCredentials:
    """Tests for TwitterCredentials."""

    def test_credentials_creation(self):
        """Test manual credential creation."""
        creds = TwitterCredentials(
            api_key="test_api_key",
            api_secret="test_api_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        assert creds.api_key == "test_api_key"
        assert creds.is_valid() is True

    def test_invalid_credentials_missing_key(self):
        """Test credentials invalid with missing API key."""
        creds = TwitterCredentials(
            api_key="",
            api_secret="test_secret",
            access_token="test_token",
            access_token_secret="test_secret",
        )

        assert creds.is_valid() is False

    def test_invalid_credentials_missing_secret(self):
        """Test credentials invalid with missing API secret."""
        creds = TwitterCredentials(
            api_key="test_key",
            api_secret="",
            access_token="test_token",
            access_token_secret="test_secret",
        )

        assert creds.is_valid() is False

    def test_invalid_credentials_missing_token(self):
        """Test credentials invalid with missing access token."""
        creds = TwitterCredentials(
            api_key="test_key",
            api_secret="test_secret",
            access_token="",
            access_token_secret="test_secret",
        )

        assert creds.is_valid() is False

    def test_has_oauth2_without_token(self):
        """Test has_oauth2 returns False without token."""
        creds = TwitterCredentials(
            api_key="test_key",
            api_secret="test_secret",
            access_token="test_token",
            access_token_secret="test_secret",
        )

        assert creds.has_oauth2() is False

    def test_has_oauth2_with_token(self):
        """Test has_oauth2 returns True with token."""
        creds = TwitterCredentials(
            api_key="test_key",
            api_secret="test_secret",
            access_token="test_token",
            access_token_secret="test_secret",
            oauth2_access_token="oauth2_test_token",
        )

        assert creds.has_oauth2() is True

    def test_from_env_loads_variables(self):
        """Test credentials loaded from environment variables."""
        with patch.dict(os.environ, {
            "X_API_KEY": "env_api_key",
            "X_API_SECRET": "env_api_secret",
            "X_ACCESS_TOKEN": "env_access_token",
            "X_ACCESS_TOKEN_SECRET": "env_access_secret",
        }, clear=False):
            # Patch the oauth2 file loading to return empty
            with patch('bots.twitter.twitter_client._load_oauth2_tokens', return_value={}):
                creds = TwitterCredentials.from_env()

                assert creds.api_key == "env_api_key"
                assert creds.api_secret == "env_api_secret"
                assert creds.is_valid() is True

    def test_jarvis_tokens_take_priority(self):
        """Test JARVIS tokens take priority over X tokens."""
        with patch.dict(os.environ, {
            "X_API_KEY": "env_api_key",
            "X_API_SECRET": "env_api_secret",
            "X_ACCESS_TOKEN": "generic_token",
            "X_ACCESS_TOKEN_SECRET": "generic_secret",
            "JARVIS_ACCESS_TOKEN": "jarvis_token",
            "JARVIS_ACCESS_TOKEN_SECRET": "jarvis_secret",
        }, clear=False):
            with patch('bots.twitter.twitter_client._load_oauth2_tokens', return_value={}):
                creds = TwitterCredentials.from_env()

                assert creds.access_token == "jarvis_token"
                assert creds.access_token_secret == "jarvis_secret"


# =============================================================================
# RetryablePostError Tests
# =============================================================================

class TestRetryablePostError:
    """Tests for RetryablePostError exception."""

    def test_error_creation(self):
        """Test RetryablePostError creation."""
        error = RetryablePostError("Rate limited", status_code=429)

        assert str(error) == "Rate limited"
        assert error.status_code == 429

    def test_error_without_status(self):
        """Test RetryablePostError without status code."""
        error = RetryablePostError("Network timeout")

        assert str(error) == "Network timeout"
        assert error.status_code is None


# =============================================================================
# Retryable Status Tests
# =============================================================================

class TestRetryableStatus:
    """Tests for retryable status code detection."""

    def test_429_is_retryable(self):
        """Test 429 Too Many Requests is retryable."""
        assert _is_retryable_status(429) is True

    def test_500_is_retryable(self):
        """Test 500 Internal Server Error is retryable."""
        assert _is_retryable_status(500) is True

    def test_502_is_retryable(self):
        """Test 502 Bad Gateway is retryable."""
        assert _is_retryable_status(502) is True

    def test_503_is_retryable(self):
        """Test 503 Service Unavailable is retryable."""
        assert _is_retryable_status(503) is True

    def test_504_is_retryable(self):
        """Test 504 Gateway Timeout is retryable."""
        assert _is_retryable_status(504) is True

    def test_400_not_retryable(self):
        """Test 400 Bad Request is not retryable."""
        assert _is_retryable_status(400) is False

    def test_401_not_retryable(self):
        """Test 401 Unauthorized is not retryable."""
        assert _is_retryable_status(401) is False

    def test_403_not_retryable(self):
        """Test 403 Forbidden is not retryable."""
        assert _is_retryable_status(403) is False

    def test_404_not_retryable(self):
        """Test 404 Not Found is not retryable."""
        assert _is_retryable_status(404) is False

    def test_none_not_retryable(self):
        """Test None status code is not retryable."""
        assert _is_retryable_status(None) is False


# =============================================================================
# Retryable Exception Tests
# =============================================================================

class TestRetryableException:
    """Tests for retryable exception detection."""

    def test_timeout_error_is_retryable(self):
        """Test TimeoutError is retryable."""
        assert _is_retryable_exception(TimeoutError()) is True

    def test_connection_error_is_retryable(self):
        """Test ConnectionError is retryable."""
        assert _is_retryable_exception(ConnectionError()) is True

    def test_os_error_is_retryable(self):
        """Test OSError is retryable."""
        assert _is_retryable_exception(OSError()) is True

    def test_asyncio_timeout_is_retryable(self):
        """Test asyncio.TimeoutError is retryable."""
        assert _is_retryable_exception(asyncio.TimeoutError()) is True

    def test_value_error_not_retryable(self):
        """Test ValueError is not retryable."""
        assert _is_retryable_exception(ValueError()) is False

    def test_key_error_not_retryable(self):
        """Test KeyError is not retryable."""
        assert _is_retryable_exception(KeyError()) is False


# =============================================================================
# TwitterClient Tests
# =============================================================================

class TestTwitterClient:
    """Tests for TwitterClient."""

    @pytest.fixture
    def mock_credentials(self):
        """Create mock credentials."""
        return TwitterCredentials(
            api_key="test_api_key",
            api_secret="test_api_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

    @pytest.fixture
    def client(self, mock_credentials):
        """Create a TwitterClient with mock credentials."""
        return TwitterClient(credentials=mock_credentials)

    def test_client_creation(self, client):
        """Test client creation."""
        assert client.credentials is not None
        assert client.credentials.is_valid() is True
        assert client.is_connected is False

    def test_client_not_connected_initially(self, client):
        """Test client is not connected initially."""
        assert client.is_connected is False
        assert client.username is None

    def test_connect_with_invalid_credentials(self):
        """Test connect fails with invalid credentials."""
        invalid_creds = TwitterCredentials(
            api_key="",
            api_secret="",
            access_token="",
            access_token_secret="",
        )
        client = TwitterClient(credentials=invalid_creds)

        result = client.connect()

        assert result is False
        assert client.is_connected is False

    @pytest.mark.asyncio
    async def test_post_tweet_not_connected(self, client):
        """Test posting fails when not connected."""
        result = await client.post_tweet("Test tweet")

        assert result.success is False
        assert "not connected" in result.error.lower()

    @pytest.mark.asyncio
    async def test_reply_to_tweet_not_connected(self, client):
        """Test replying fails when not connected."""
        result = await client.reply_to_tweet("123456", "Reply text")

        assert result.success is False
        assert "not connected" in result.error.lower()

    @pytest.mark.asyncio
    async def test_quote_tweet_not_connected(self, client):
        """Test quoting fails when not connected."""
        result = await client.quote_tweet("123456", "Quote text")

        assert result.success is False
        assert "not connected" in result.error.lower()

    @pytest.mark.asyncio
    async def test_like_tweet_not_connected(self, client):
        """Test liking fails when not connected."""
        result = await client.like_tweet("123456")

        assert result is False

    @pytest.mark.asyncio
    async def test_retweet_not_connected(self, client):
        """Test retweeting fails when not connected."""
        result = await client.retweet("123456")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_mentions_not_connected(self, client):
        """Test getting mentions fails when not connected."""
        mentions = await client.get_mentions()

        assert mentions == []

    @pytest.mark.asyncio
    async def test_get_tweet_not_connected(self, client):
        """Test getting tweet fails when not connected."""
        tweet = await client.get_tweet("123456")

        assert tweet is None

    @pytest.mark.asyncio
    async def test_search_recent_not_connected(self, client):
        """Test search fails when not connected."""
        results = await client.search_recent("test query")

        assert results == []

    @pytest.mark.asyncio
    async def test_upload_media_no_tweepy(self, client):
        """Test upload media fails without tweepy API."""
        result = await client.upload_media("/path/to/image.png")

        assert result is None

    def test_disconnect(self, client):
        """Test disconnect clears state."""
        # Simulate connected state
        client._username = "test_user"
        client._user_id = "123"

        client.disconnect()

        assert client._username is None
        assert client._user_id is None
        assert client.is_connected is False


# =============================================================================
# TwitterClient Connected State Tests
# =============================================================================

class TestTwitterClientConnected:
    """Tests for TwitterClient when connected."""

    @pytest.fixture
    def connected_client(self):
        """Create a connected mock client."""
        creds = TwitterCredentials(
            api_key="test_key",
            api_secret="test_secret",
            access_token="test_token",
            access_token_secret="test_secret",
        )
        client = TwitterClient(credentials=creds)

        # Simulate connected state
        client._username = "test_user"
        client._user_id = "123456"
        client._use_oauth2 = False

        # Mock tweepy client
        client._tweepy_client = MagicMock()

        return client

    @pytest.mark.asyncio
    async def test_post_tweet_success(self, connected_client):
        """Test successful tweet posting via tweepy."""
        mock_response = MagicMock()
        mock_response.data = {"id": "999888777"}

        connected_client._tweepy_client.create_tweet = MagicMock(
            return_value=mock_response
        )

        result = await connected_client.post_tweet(
            "Test tweet content",
            sync_to_telegram=False
        )

        assert result.success is True
        assert result.tweet_id == "999888777"

    @pytest.mark.asyncio
    async def test_post_tweet_truncation(self, connected_client):
        """Test tweet truncation for long content."""
        # Create a very long message (> 4000 chars)
        long_text = "A" * 5000

        mock_response = MagicMock()
        mock_response.data = {"id": "123"}

        connected_client._tweepy_client.create_tweet = MagicMock(
            return_value=mock_response
        )

        await connected_client.post_tweet(long_text, sync_to_telegram=False)

        # Verify the text was truncated
        call_args = connected_client._tweepy_client.create_tweet.call_args
        actual_text = call_args.kwargs.get('text', call_args.args[0] if call_args.args else None)

        # Text should be max 4000 chars (Premium) and end with ...
        assert len(actual_text) <= 4000
        assert actual_text.endswith("...")


# =============================================================================
# Username Matching Tests
# =============================================================================

class TestUsernameMatching:
    """Tests for username matching logic."""

    def test_username_matches_exact(self):
        """Test exact username match."""
        assert TwitterClient._username_matches("jarvis_lifeos", "jarvis_lifeos") is True

    def test_username_matches_case_insensitive(self):
        """Test case insensitive matching."""
        assert TwitterClient._username_matches("Jarvis_LifeOS", "jarvis_lifeos") is True

    def test_username_matches_empty_expected(self):
        """Test empty expected matches any username."""
        assert TwitterClient._username_matches("any_user", "") is True

    def test_username_matches_none_fails(self):
        """Test None username fails matching."""
        assert TwitterClient._username_matches(None, "jarvis_lifeos") is False

    def test_username_mismatch(self):
        """Test username mismatch."""
        assert TwitterClient._username_matches("wrong_user", "jarvis_lifeos") is False


# =============================================================================
# Expected Username Configuration Tests
# =============================================================================

class TestExpectedUsername:
    """Tests for expected username configuration."""

    def test_get_expected_username_from_env(self):
        """Test loading expected username from environment."""
        creds = TwitterCredentials(
            api_key="key", api_secret="secret",
            access_token="token", access_token_secret="secret"
        )
        client = TwitterClient(credentials=creds)

        with patch.dict(os.environ, {"X_EXPECTED_USERNAME": "test_user"}):
            result = client._get_expected_username()
            assert result == "test_user"

    def test_get_expected_username_strips_at(self):
        """Test expected username strips @ symbol."""
        creds = TwitterCredentials(
            api_key="key", api_secret="secret",
            access_token="token", access_token_secret="secret"
        )
        client = TwitterClient(credentials=creds)

        with patch.dict(os.environ, {"X_EXPECTED_USERNAME": "@test_user"}):
            result = client._get_expected_username()
            assert result == "test_user"

    def test_get_expected_username_default(self):
        """Test default expected username."""
        creds = TwitterCredentials(
            api_key="key", api_secret="secret",
            access_token="token", access_token_secret="secret"
        )
        client = TwitterClient(credentials=creds)

        with patch.dict(os.environ, {}, clear=True):
            # Clear the env vars
            for key in ["X_EXPECTED_USERNAME", "TWITTER_EXPECTED_USERNAME"]:
                os.environ.pop(key, None)

            result = client._get_expected_username()
            assert result == "jarvis_lifeos"  # Default

    def test_get_expected_username_wildcard(self):
        """Test wildcard expected username."""
        creds = TwitterCredentials(
            api_key="key", api_secret="secret",
            access_token="token", access_token_secret="secret"
        )
        client = TwitterClient(credentials=creds)

        with patch.dict(os.environ, {"X_EXPECTED_USERNAME": "*"}):
            result = client._get_expected_username()
            assert result == ""  # Empty means any


# =============================================================================
# OAuth2 Token Refresh Tests
# =============================================================================

class TestOAuth2TokenRefresh:
    """Tests for OAuth2 token refresh functionality."""

    @pytest.fixture
    def client_with_oauth2(self):
        """Create client with OAuth2 credentials."""
        creds = TwitterCredentials(
            api_key="key",
            api_secret="secret",
            access_token="token",
            access_token_secret="secret",
            oauth2_client_id="client_id",
            oauth2_client_secret="client_secret",
            oauth2_refresh_token="refresh_token",
        )
        return TwitterClient(credentials=creds)

    def test_refresh_without_refresh_token(self):
        """Test refresh fails without refresh token."""
        creds = TwitterCredentials(
            api_key="key",
            api_secret="secret",
            access_token="token",
            access_token_secret="secret",
            oauth2_refresh_token=None,
        )
        client = TwitterClient(credentials=creds)

        result = client._refresh_oauth2_token()

        assert result is False


# =============================================================================
# Circuit Breaker Integration Tests
# =============================================================================

class TestCircuitBreakerIntegration:
    """Tests for circuit breaker integration."""

    def test_client_has_circuit_breaker(self):
        """Test client has circuit breaker initialized."""
        creds = TwitterCredentials(
            api_key="key",
            api_secret="secret",
            access_token="token",
            access_token_secret="secret",
        )
        client = TwitterClient(credentials=creds)

        assert client._circuit_breaker is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
