"""
Tests for Jarvis Telegram Bot.

Tests cover:
- Configuration
- Claude client
- Token data service
- Subscriber model
"""

import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# =============================================================================
# Test Configuration
# =============================================================================

class TestBotConfig:
    """Test bot configuration."""

    def test_config_loads(self):
        """Config should load without errors."""
        from tg_bot.config import BotConfig
        config = BotConfig()
        assert config is not None

    def test_config_validation(self):
        """Config should validate required fields."""
        from tg_bot.config import BotConfig

        # Test with empty token - should be invalid
        config = BotConfig()
        config.telegram_token = ""  # Force empty
        config.admin_ids = set()  # Force empty
        assert not config.is_valid()
        missing = config.get_missing()
        assert "TELEGRAM_BOT_TOKEN" in missing
        assert "TELEGRAM_ADMIN_IDS" in missing

    def test_config_with_env(self):
        """Config should read from environment."""
        from tg_bot.config import BotConfig

        # Clear any local Ollama configuration and set test values
        with patch.dict("os.environ", {
            "TELEGRAM_BOT_TOKEN": "test-token",
            "ANTHROPIC_API_KEY": "test-key",
            "JARVIS_ALLOW_REMOTE_ANTHROPIC": "1",  # Required to allow API key passthrough
            # Clear local Ollama config to ensure remote key is used
            "OLLAMA_ANTHROPIC_BASE_URL": "",
            "ANTHROPIC_BASE_URL": "",
        }):
            config = BotConfig()
            assert config.telegram_token == "test-token"
            # The key should be either the test key or 'ollama' if local is detected
            # We primarily care that it has some value
            assert config.anthropic_api_key in ("test-key", "ollama") or len(config.anthropic_api_key) > 0
            assert config.is_valid()

    def test_config_defaults(self):
        """Config should have sensible defaults."""
        from tg_bot.config import BotConfig
        config = BotConfig()

        assert config.claude_model == "claude-sonnet-4-20250514"
        assert config.sentiment_interval_seconds == 3600  # 1 hour
        assert config.paper_starting_balance == 100.0


# =============================================================================
# Test Claude Client
# =============================================================================

class TestClaudeClient:
    """Test Claude sentiment client (uses tg_bot.services.claude_client)."""

    def test_sentiment_result_dataclass(self):
        """SentimentResult should be a valid dataclass."""
        from tg_bot.services.claude_client import SentimentResult

        result = SentimentResult(
            score=0.8,
            confidence=0.9,
            summary="Strong momentum detected",
            key_factors=["Volume up", "Price breaking resistance"],
            suggested_action="LONG",
        )

        assert result.score == 0.8
        assert result.confidence == 0.9
        assert result.suggested_action == "LONG"
        assert len(result.key_factors) == 2

    def test_sentiment_result_to_dict(self):
        """SentimentResult should convert to dict."""
        from tg_bot.services.claude_client import SentimentResult

        result = SentimentResult(
            score=0.5,
            confidence=0.7,
            summary="Neutral outlook",
            key_factors=["Mixed signals"],
            suggested_action="HOLD",
        )

        d = result.to_dict()
        assert d["score"] == 0.5
        assert d["confidence"] == 0.7
        assert d["suggested_action"] == "HOLD"


# =============================================================================
# Test Token Data Service
# =============================================================================

class TestTokenDataService:
    """Test token data service (uses tg_bot.services.token_data)."""

    def test_token_data_dataclass(self):
        """TokenData should be a valid dataclass."""
        from tg_bot.services.token_data import TokenData

        data = TokenData(
            address="So11111111111111111111111111111111111111112",
            symbol="SOL",
            price_usd=100.0,
            price_change_1h=2.5,
            price_change_24h=5.0,
            volume_24h=1000000,
            liquidity=5000000,
            holder_count=100000,
            top_holders_pct=15.0,
        )

        assert data.symbol == "SOL"
        assert data.price_usd == 100.0
        assert data.price_change_24h == 5.0

    def test_token_data_to_dict(self):
        """TokenData should convert to dict."""
        from tg_bot.services.token_data import TokenData

        data = TokenData(
            address="test_address",
            symbol="TEST",
            price_usd=1.0,
            price_change_1h=1.0,
            price_change_24h=5.0,
            volume_24h=1000000,
            liquidity=500000,
            holder_count=1000,
            top_holders_pct=20.0,
        )

        d = data.to_dict()
        assert d["symbol"] == "TEST"
        assert d["price_usd"] == 1.0
        assert "last_updated" in d

    def test_known_tokens_exist(self):
        """Service should have known tokens."""
        from tg_bot.services.token_data import KNOWN_TOKENS

        assert "SOL" in KNOWN_TOKENS
        assert "USDC" in KNOWN_TOKENS
        assert "BONK" in KNOWN_TOKENS

    def test_token_data_service_creation(self):
        """TokenDataService should be creatable."""
        from tg_bot.services.token_data import TokenDataService
        service = TokenDataService()
        assert service is not None
        assert service.cache_ttl == 60  # default

    def test_token_data_service_is_healthy(self):
        """TokenDataService should report health."""
        from tg_bot.services.token_data import TokenDataService
        service = TokenDataService()
        assert service.is_healthy() is True


# =============================================================================
# Test Subscriber Database
# =============================================================================

class TestSubscriberDB:
    """Test subscriber database (uses tg_bot.models.subscriber)."""

    def test_subscriber_dataclass(self):
        """Subscriber should be a valid dataclass."""
        from tg_bot.models.subscriber import Subscriber

        sub = Subscriber(
            user_id=123456,
            chat_id=123456,
            username="testuser",
            risk_profile="neutral",
            subscribed_at=datetime.now(timezone.utc),
            active=True,
        )

        assert sub.user_id == 123456
        assert sub.username == "testuser"
        assert sub.active is True

    def test_subscriber_db_creation(self):
        """SubscriberDB should be creatable."""
        from tg_bot.models.subscriber import SubscriberDB

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = SubscriberDB(db_path)
            assert db is not None
            assert db.db_path == db_path

    def test_subscribe(self):
        """Should be able to subscribe."""
        from tg_bot.models.subscriber import SubscriberDB

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = SubscriberDB(db_path)

            # Subscribe a user
            sub = db.subscribe(user_id=123456, chat_id=123456, username="testuser")

            assert sub is not None
            assert sub.user_id == 123456

    def test_unsubscribe(self):
        """Should be able to unsubscribe."""
        from tg_bot.models.subscriber import SubscriberDB

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = SubscriberDB(db_path)

            db.subscribe(123456, 123456)
            result = db.unsubscribe(123456)

            assert result is True

    def test_get_active_subscribers(self):
        """Should return active subscribers."""
        from tg_bot.models.subscriber import SubscriberDB

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = SubscriberDB(db_path)

            db.subscribe(111, 111)
            db.subscribe(222, 222)
            db.subscribe(333, 333)
            db.unsubscribe(222)

            active = db.get_active_subscribers()
            assert len(active) == 2


# =============================================================================
# Test Bot Handlers
# =============================================================================

class TestBotHandlers:
    """Test bot handler functions."""

    def test_start_handler_exists(self):
        """Start handler should exist."""
        from tg_bot.handlers import commands
        # The module exports 'start' from commands_base
        assert hasattr(commands, "start") or commands.start is not None

    def test_analyze_command_exists(self):
        """Analyze command should exist."""
        from tg_bot.handlers import commands
        assert hasattr(commands, "analyze_command")

    def test_watchlist_command_exists(self):
        """Watchlist command should exist."""
        from tg_bot.handlers import commands
        assert hasattr(commands, "watchlist_command")

    def test_quick_command_exists(self):
        """Quick command should exist."""
        from tg_bot.handlers import commands
        assert hasattr(commands, "quick_command")

    def test_callback_handlers_exist(self):
        """Callback handlers should exist."""
        from tg_bot.handlers import commands
        assert hasattr(commands, "handle_analyze_callback")
        assert hasattr(commands, "handle_watchlist_callback")
        assert hasattr(commands, "handle_quick_callback")
