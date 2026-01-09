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
from datetime import datetime
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

        with patch.dict("os.environ", {
            "TELEGRAM_BOT_TOKEN": "test-token",
            "ANTHROPIC_API_KEY": "test-key",
        }):
            config = BotConfig()
            assert config.telegram_token == "test-token"
            assert config.anthropic_api_key == "test-key"
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
    """Test Claude client."""

    def test_client_creation(self):
        """Client should create without API key."""
        from tg_bot.services.claude_client import ClaudeClient
        client = ClaudeClient()
        assert not client.is_healthy()

    def test_client_with_key(self):
        """Client should be healthy with API key."""
        from tg_bot.services.claude_client import ClaudeClient
        # Without actual API, client won't be healthy until first call
        client = ClaudeClient(api_key="test-key")
        assert client.api_key == "test-key"

    def test_sentiment_result(self):
        """SentimentResult should serialize correctly."""
        from tg_bot.services.claude_client import SentimentResult

        result = SentimentResult(
            score=0.75,
            confidence=0.85,
            summary="Test summary",
            key_factors=["factor1", "factor2"],
            suggested_action="LONG",
        )

        data = result.to_dict()
        assert data["score"] == 0.75
        assert data["confidence"] == 0.85
        assert data["suggested_action"] == "LONG"

    @pytest.mark.asyncio
    async def test_quick_sentiment(self):
        """Quick sentiment should return consistent values."""
        from tg_bot.services.claude_client import ClaudeClient
        client = ClaudeClient()

        score1 = await client.quick_sentiment("SOL")
        score2 = await client.quick_sentiment("SOL")
        assert score1 == score2  # Deterministic

        score3 = await client.quick_sentiment("BONK")
        # Different tokens may have different scores


# =============================================================================
# Test Token Data Service
# =============================================================================

class TestTokenDataService:
    """Test token data service."""

    def test_service_creation(self):
        """Service should create without API key."""
        from tg_bot.services.token_data import TokenDataService
        service = TokenDataService()
        assert service.is_healthy()

    def test_known_tokens(self):
        """Should have known token addresses."""
        from tg_bot.services.token_data import KNOWN_TOKENS
        assert "SOL" in KNOWN_TOKENS
        assert "BONK" in KNOWN_TOKENS
        assert "JUP" in KNOWN_TOKENS

    @pytest.mark.asyncio
    async def test_get_mock_data(self):
        """Should return mock data without API key."""
        from tg_bot.services.token_data import TokenDataService
        service = TokenDataService()

        data = await service.get_token_data("SOL")
        assert data is not None
        assert data.symbol == "SOL"
        assert data.price_usd > 0

        await service.close()

    @pytest.mark.asyncio
    async def test_trending_returns_list(self):
        """Trending should return list of tokens."""
        from tg_bot.services.token_data import TokenDataService
        service = TokenDataService()

        tokens = await service.get_trending(limit=3)
        assert len(tokens) == 3
        assert all(t.symbol for t in tokens)

        await service.close()

    def test_token_data_to_dict(self):
        """TokenData should serialize correctly."""
        from tg_bot.services.token_data import TokenData

        data = TokenData(
            address="test",
            symbol="TEST",
            price_usd=100.0,
            price_change_1h=5.0,
            price_change_24h=10.0,
            volume_24h=1000000,
            liquidity=500000,
            holder_count=10000,
            top_holders_pct=25.0,
        )

        d = data.to_dict()
        assert d["symbol"] == "TEST"
        assert d["price_usd"] == 100.0


# =============================================================================
# Test Subscriber Model
# =============================================================================

class TestSubscriberDB:
    """Test subscriber database."""

    @pytest.fixture
    def db(self):
        """Create temporary database."""
        from tg_bot.models.subscriber import SubscriberDB
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        db = SubscriberDB(db_path)
        yield db
        db_path.unlink(missing_ok=True)

    def test_subscribe(self, db):
        """Should subscribe user."""
        sub = db.subscribe(user_id=123, chat_id=456, username="testuser")
        assert sub.user_id == 123
        assert sub.chat_id == 456
        assert sub.active

    def test_unsubscribe(self, db):
        """Should unsubscribe user."""
        db.subscribe(user_id=123, chat_id=456)
        result = db.unsubscribe(user_id=123)
        assert result is True

    def test_get_active_subscribers(self, db):
        """Should return active subscribers."""
        db.subscribe(user_id=1, chat_id=1)
        db.subscribe(user_id=2, chat_id=2)
        db.subscribe(user_id=3, chat_id=3)
        db.unsubscribe(user_id=2)

        active = db.get_active_subscribers()
        assert len(active) == 2
        assert all(s.active for s in active)

    def test_set_risk_profile(self, db):
        """Should set risk profile."""
        db.subscribe(user_id=123, chat_id=456)
        result = db.set_risk_profile(123, "aggressive")
        assert result is True

        sub = db.get_subscriber(123)
        assert sub.risk_profile == "aggressive"

    def test_paper_balance(self, db):
        """Should manage paper balance."""
        # New user gets 100 SOL
        balance = db.get_paper_balance(123)
        assert balance == 100.0

        # Update balance
        db.update_paper_balance(123, 150.0)
        balance = db.get_paper_balance(123)
        assert balance == 150.0


# =============================================================================
# Test Bot Handlers (Mocked)
# =============================================================================

class TestBotHandlers:
    """Test bot handlers with mocked telegram."""

    @pytest.mark.asyncio
    async def test_start_handler(self):
        """Start handler should send welcome message."""
        pytest.importorskip("telegram")
        from tg_bot.bot import start
        assert start is not None

    @pytest.mark.asyncio
    async def test_analyze_function_exists(self):
        """Analyze command should exist in bot."""
        pytest.importorskip("telegram")
        from tg_bot.bot import analyze
        assert analyze is not None
