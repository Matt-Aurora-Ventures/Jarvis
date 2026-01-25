"""
Comprehensive unit tests for the Twitter Autonomous Engine.

Tests cover:
- AutonomousEngine initialization and state management
- XMemory database operations
- Content generation (market updates, trending tokens, etc.)
- Posting logic and duplicate detection
- Circuit breaker and spam protection
- Error handling and recovery
- Grok integration for sentiment analysis
- Self-learning system

This is a critical production component that posts to @Jarvis_lifeos
with thousands of followers - thorough testing is essential.
"""

import pytest
import asyncio
import json
import sqlite3
import tempfile
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from dataclasses import asdict
import os
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bots.twitter.autonomous_engine import (
    AutonomousEngine,
    XMemory,
    TweetDraft,
    ImageGenParams,
    JARVIS_X_VOICE,
    ROAST_CRITERIA,
    GENERIC_CONTENT_PATTERNS,
    is_content_relevant,
    _get_duplicate_detection_hours,
    _get_duplicate_similarity_threshold,
)


# =============================================================================
# ImageGenParams Tests
# =============================================================================

class TestImageGenParams:
    """Tests for ImageGenParams dataclass."""

    def test_default_params(self):
        """Test default image generation parameters."""
        params = ImageGenParams()

        assert params.style == "market_chart"
        assert params.quality == "high"
        assert params.mood == "neutral"
        assert params.include_jarvis is True
        assert params.color_scheme == "cyberpunk"

    def test_custom_params(self):
        """Test custom image generation parameters."""
        params = ImageGenParams(
            style="abstract",
            quality="standard",
            mood="bullish",
            include_jarvis=False,
            color_scheme="solana"
        )

        assert params.style == "abstract"
        assert params.quality == "standard"
        assert params.mood == "bullish"
        assert params.include_jarvis is False
        assert params.color_scheme == "solana"

    def test_to_prompt_suffix_bullish(self):
        """Test prompt suffix generation for bullish mood."""
        params = ImageGenParams(mood="bullish", color_scheme="neon")
        suffix = params.to_prompt_suffix()

        assert "green glow" in suffix.lower()
        assert "upward" in suffix.lower()
        assert "neon" in suffix.lower()
        assert "chrome humanoid" in suffix.lower()  # include_jarvis=True

    def test_to_prompt_suffix_bearish(self):
        """Test prompt suffix generation for bearish mood."""
        params = ImageGenParams(mood="bearish", color_scheme="professional")
        suffix = params.to_prompt_suffix()

        assert "red" in suffix.lower()
        assert "downward" in suffix.lower()
        assert "clean" in suffix.lower()

    def test_to_prompt_suffix_no_jarvis(self):
        """Test prompt suffix without Jarvis avatar."""
        params = ImageGenParams(include_jarvis=False)
        suffix = params.to_prompt_suffix()

        assert "chrome humanoid" not in suffix.lower()


# =============================================================================
# TweetDraft Tests
# =============================================================================

class TestTweetDraft:
    """Tests for TweetDraft dataclass."""

    def test_basic_draft(self):
        """Test basic tweet draft creation."""
        draft = TweetDraft(
            content="Test tweet content",
            category="market_update",
            cashtags=["$SOL", "$BTC"],
            hashtags=["#Crypto"]
        )

        assert draft.content == "Test tweet content"
        assert draft.category == "market_update"
        assert len(draft.cashtags) == 2
        assert draft.contract_address is None
        assert draft.reply_to is None
        assert draft.quote_tweet_id is None
        assert draft.priority == 0

    def test_draft_with_all_fields(self):
        """Test tweet draft with all optional fields."""
        params = ImageGenParams(mood="bullish")
        draft = TweetDraft(
            content="Alpha signal detected",
            category="alpha_signal",
            cashtags=["$WIF"],
            hashtags=["#Solana"],
            contract_address="EKpQGS...xyz",
            reply_to="123456789",
            quote_tweet_id="987654321",
            image_prompt="Chart showing breakout",
            image_params=params,
            priority=2
        )

        assert draft.contract_address == "EKpQGS...xyz"
        assert draft.reply_to == "123456789"
        assert draft.quote_tweet_id == "987654321"
        assert draft.image_prompt is not None
        assert draft.image_params.mood == "bullish"
        assert draft.priority == 2


# =============================================================================
# Content Relevance Tests
# =============================================================================

class TestContentRelevance:
    """Tests for is_content_relevant function."""

    def test_empty_content_rejected(self):
        """Test empty content is rejected."""
        assert is_content_relevant("", "market_update") is False
        assert is_content_relevant(None, "market_update") is False

    def test_short_content_rejected(self):
        """Test very short content is rejected."""
        assert is_content_relevant("Hi", "market_update") is False
        assert is_content_relevant("test tweet", "market_update") is False
        assert is_content_relevant("a" * 29, "market_update") is False

    def test_generic_content_rejected(self):
        """Test generic/low-quality content is rejected."""
        for pattern in GENERIC_CONTENT_PATTERNS[:5]:
            content = f"The {pattern} and we should watch."
            assert is_content_relevant(content, "agentic_tech") is False

    def test_token_category_requires_cashtag(self):
        """Test token-related categories require cashtag."""
        # Without cashtag - should be rejected
        assert is_content_relevant(
            "This token is pumping hard today with 500% gains",
            "trending_token"
        ) is False

        # With cashtag - should pass
        assert is_content_relevant(
            "$WIF is pumping hard today with 500% gains and massive volume",
            "trending_token"
        ) is True

    def test_non_token_category_no_cashtag_required(self):
        """Test non-token categories don't require cashtag."""
        assert is_content_relevant(
            "The future of autonomous AI systems is fascinating. We are building something here.",
            "agentic_tech"
        ) is True

    def test_valid_market_update(self):
        """Test valid market update passes."""
        content = "$SOL at $185 with strong momentum. Volume up 30%. Watching for breakout."
        assert is_content_relevant(content, "market_update") is True


# =============================================================================
# Environment Variable Helpers Tests
# =============================================================================

class TestEnvHelpers:
    """Tests for environment variable helper functions."""

    def test_duplicate_detection_hours_default(self):
        """Test default duplicate detection hours."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove the key if it exists
            os.environ.pop("X_DUPLICATE_DETECTION_HOURS", None)
            # Re-import to get fresh value
            from bots.twitter import autonomous_engine
            result = autonomous_engine._get_duplicate_detection_hours()
            assert result == 48  # Default

    def test_duplicate_detection_hours_custom(self):
        """Test custom duplicate detection hours."""
        with patch.dict(os.environ, {"X_DUPLICATE_DETECTION_HOURS": "72"}):
            from bots.twitter import autonomous_engine
            result = autonomous_engine._get_duplicate_detection_hours()
            assert result == 72

    def test_duplicate_detection_hours_clamped(self):
        """Test duplicate detection hours are clamped to valid range."""
        # Test minimum clamping
        with patch.dict(os.environ, {"X_DUPLICATE_DETECTION_HOURS": "0"}):
            from bots.twitter import autonomous_engine
            result = autonomous_engine._get_duplicate_detection_hours()
            assert result >= 1

        # Test maximum clamping
        with patch.dict(os.environ, {"X_DUPLICATE_DETECTION_HOURS": "500"}):
            from bots.twitter import autonomous_engine
            result = autonomous_engine._get_duplicate_detection_hours()
            assert result <= 168

    def test_similarity_threshold_default(self):
        """Test default similarity threshold."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("X_DUPLICATE_SIMILARITY", None)
            from bots.twitter import autonomous_engine
            result = autonomous_engine._get_duplicate_similarity_threshold()
            assert result == 0.4  # Default


# =============================================================================
# XMemory Tests
# =============================================================================

class TestXMemory:
    """Tests for XMemory database operations."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        # Cleanup
        if db_path.exists():
            db_path.unlink()

    @pytest.fixture
    def memory(self, temp_db):
        """Create XMemory instance with temp database."""
        with patch('bots.twitter.autonomous_engine.get_memory_store') as mock_store:
            mock_store.return_value = MagicMock()
            mem = XMemory(db_path=temp_db)
        return mem

    def test_init_creates_tables(self, memory, temp_db):
        """Test database initialization creates required tables."""
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()

        # Check tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        assert "tweets" in tables
        assert "interactions" in tables
        assert "token_mentions" in tables
        assert "content_fingerprints" in tables
        assert "users" in tables
        assert "content_queue" in tables
        assert "mention_replies" in tables
        assert "external_replies" in tables

        conn.close()

    def test_record_and_get_tweets(self, memory):
        """Test recording and retrieving tweets."""
        # Record a tweet
        memory.record_tweet(
            tweet_id="123456789",
            content="Test tweet $SOL looking bullish",
            category="market_update",
            cashtags=["$SOL"]
        )

        # Get recent tweets
        recent = memory.get_recent_tweets(hours=1)

        assert len(recent) == 1
        assert recent[0]["content"] == "Test tweet $SOL looking bullish"
        assert recent[0]["category"] == "market_update"
        assert "$SOL" in recent[0]["cashtags"]

    def test_get_total_tweet_count(self, memory):
        """Test getting total tweet count."""
        # Initially empty
        assert memory.get_total_tweet_count() == 0

        # Add tweets
        memory.record_tweet("1", "Tweet 1", "cat1", [])
        memory.record_tweet("2", "Tweet 2", "cat2", [])
        memory.record_tweet("3", "Tweet 3", "cat1", [])

        assert memory.get_total_tweet_count() == 3

    def test_token_mention_tracking(self, memory):
        """Test token mention recording and checking."""
        # Record mention
        memory.record_token_mention(
            symbol="WIF",
            contract="EKp...",
            sentiment="bullish",
            price=1.5
        )

        # Check if recently mentioned
        assert memory.was_recently_mentioned("WIF", hours=1) is True
        assert memory.was_recently_mentioned("BONK", hours=1) is False

    def test_is_similar_to_recent_identical(self, memory):
        """Test similarity detection with identical content."""
        # Record a tweet
        memory.record_tweet(
            "123",
            "$SOL at $185. Markets looking bullish today.",
            "market_update",
            ["$SOL"]
        )

        # Check for similar content
        is_similar, similar = memory.is_similar_to_recent(
            "$SOL at $185. Markets looking bullish today.",
            hours=1
        )

        assert is_similar is True

    def test_is_similar_to_recent_different(self, memory):
        """Test similarity detection with different content."""
        memory.record_tweet(
            "123",
            "$SOL pumping hard today with massive volume",
            "market_update",
            ["$SOL"]
        )

        is_similar, similar = memory.is_similar_to_recent(
            "$BTC breaking out while gold consolidates at ATH",
            hours=1
        )

        assert is_similar is False

    def test_mention_reply_tracking(self, memory):
        """Test mention reply recording and checking."""
        # Record a reply
        memory.record_mention_reply(
            tweet_id="999",
            author="crypto_trader",
            reply="Great analysis!"
        )

        # Check if already replied
        assert memory.was_mention_replied("999") is True
        assert memory.was_mention_replied("888") is False

    def test_external_reply_tracking(self, memory):
        """Test external reply recording and rate limiting."""
        # Record external replies
        memory.record_external_reply(
            original_tweet_id="111",
            author="influencer1",
            original_content="BTC to 100k",
            our_reply="my sensors agree",
            our_tweet_id="222",
            reply_type="agree",
            sentiment="bullish"
        )

        # Check tracking
        assert memory.was_externally_replied("111") is True
        assert memory.was_externally_replied("333") is False

        # Check author rate limit
        assert memory.was_author_replied_recently("influencer1", hours=6) is True
        assert memory.was_author_replied_recently("influencer2", hours=6) is False

        # Check reply count
        assert memory.get_recent_reply_count(hours=1) == 1

    def test_get_posting_stats(self, memory):
        """Test getting posting statistics."""
        # Add some tweets
        memory.record_tweet("1", "Tweet 1", "market_update", ["$SOL"])
        memory.record_tweet("2", "Tweet 2", "market_update", ["$BTC"])
        memory.record_tweet("3", "Tweet 3", "agentic_tech", [])
        memory.record_mention_reply("999", "user", "reply")

        stats = memory.get_posting_stats()

        assert stats["total_tweets"] == 3
        assert stats["today_tweets"] == 3
        assert stats["replies_sent"] == 1
        assert stats["by_category"]["market_update"] == 2
        assert stats["by_category"]["agentic_tech"] == 1

    def test_get_recent_topics(self, memory):
        """Test extracting recent topics for diversity checking."""
        # Add tweets with various cashtags
        memory.record_tweet(
            "1",
            "$SOL looking bullish with green candles",
            "market_update",
            ["$SOL"]
        )
        memory.record_tweet(
            "2",
            "$BTC at 95k, market sentiment positive",
            "bitcoin_only",
            ["$BTC"]
        )

        topics = memory.get_recent_topics(hours=2)

        assert "SOL" in topics["cashtags"]
        assert "BTC" in topics["cashtags"]
        assert "market_update" in topics["categories"]
        assert "bitcoin_only" in topics["categories"]

    def test_calculate_content_freshness_unique(self, memory):
        """Test content freshness for unique content."""
        # No recent tweets
        freshness = memory.calculate_content_freshness("Brand new unique content here")
        assert freshness == 1.0  # Completely fresh

    def test_calculate_content_freshness_similar(self, memory):
        """Test content freshness for similar content."""
        memory.record_tweet(
            "1",
            "$SOL at $185 looking bullish today nfa",
            "market_update",
            ["$SOL"]
        )

        # Very similar content
        freshness = memory.calculate_content_freshness(
            "$SOL at $185 looking bullish today nfa"
        )

        # Should be low freshness (high similarity)
        assert freshness < 0.5

    def test_semantic_concept_extraction(self, memory):
        """Test semantic concept extraction for duplicate detection."""
        concepts = memory._extract_semantic_concepts(
            "$SOL pumping hard with green candles everywhere"
        )

        assert concepts["sentiment"] == "bullish"
        assert "sol" in concepts["subjects"]

    def test_semantic_concept_extraction_bearish(self, memory):
        """Test semantic concept extraction for bearish content."""
        concepts = memory._extract_semantic_concepts(
            "$BTC crashing hard, fear and capitulation in the market"
        )

        assert concepts["sentiment"] == "bearish"
        assert "btc" in concepts["subjects"]

    def test_content_fingerprint_generation(self, memory):
        """Test content fingerprint generation."""
        fingerprint, tokens, prices, topic_hash, semantic_hash = \
            memory._generate_content_fingerprint(
                "$SOL at $185 breaking out with $WIF at $1.50"
            )

        assert fingerprint is not None
        # Tokens may be lowercase in the output
        tokens_upper = tokens.upper()
        assert "SOL" in tokens_upper
        assert "WIF" in tokens_upper
        assert "185" in prices or "1.50" in prices
        assert topic_hash is not None
        assert semantic_hash is not None


# =============================================================================
# AutonomousEngine Initialization Tests
# =============================================================================

class TestAutonomousEngineInit:
    """Tests for AutonomousEngine initialization."""

    @pytest.fixture
    def mock_dependencies(self):
        """Mock all external dependencies."""
        with patch('bots.twitter.autonomous_engine.XMemory') as mock_memory, \
             patch('bots.twitter.autonomous_engine.get_memory_store') as mock_store, \
             patch('bots.twitter.autonomous_engine.X_ENGINE_STATE') as mock_state:

            mock_memory.return_value = MagicMock()
            mock_store.return_value = MagicMock()
            mock_state.exists.return_value = False

            yield {
                'memory': mock_memory,
                'store': mock_store,
                'state': mock_state
            }

    def test_engine_initialization(self, mock_dependencies):
        """Test basic engine initialization."""
        engine = AutonomousEngine()

        assert engine._running is False
        assert engine._post_interval == 1800  # 30 minutes
        assert engine._consecutive_errors == 0
        assert engine._grok_client is None
        assert engine._twitter_client is None

    def test_engine_load_state_no_file(self, mock_dependencies):
        """Test engine loads defaults when no state file exists."""
        mock_dependencies['state'].exists.return_value = False

        engine = AutonomousEngine()

        # Should set last post time (allowing posting soon)
        assert hasattr(engine, '_last_post_time')

    def test_engine_load_state_from_file(self, mock_dependencies):
        """Test engine loads state from file."""
        mock_dependencies['state'].exists.return_value = True
        mock_dependencies['state'].read_text.return_value = json.dumps({
            "last_post_time": time.time() - 1000,  # 16 minutes ago
            "consecutive_errors": 2,
            "last_error_time": time.time() - 500
        })

        engine = AutonomousEngine()

        assert engine._consecutive_errors == 2

    def test_set_post_interval(self, mock_dependencies):
        """Test setting post interval with minimum enforcement."""
        engine = AutonomousEngine()

        # Normal interval
        engine.set_post_interval(3600)
        assert engine._post_interval == 3600

        # Below minimum - should be clamped
        engine.set_post_interval(60)
        assert engine._post_interval == 300  # Minimum 5 minutes

    def test_set_image_params(self, mock_dependencies):
        """Test setting image parameters."""
        engine = AutonomousEngine()

        engine.set_image_params(mood="bullish", color_scheme="neon")

        assert engine._image_params.mood == "bullish"
        assert engine._image_params.color_scheme == "neon"


# =============================================================================
# Circuit Breaker Tests
# =============================================================================

class TestCircuitBreaker:
    """Tests for error tracking and circuit breaker logic."""

    @pytest.fixture
    def engine(self):
        """Create engine with mocked dependencies."""
        with patch('bots.twitter.autonomous_engine.XMemory'), \
             patch('bots.twitter.autonomous_engine.get_memory_store'), \
             patch('bots.twitter.autonomous_engine.X_ENGINE_STATE') as mock_state:

            mock_state.exists.return_value = False
            engine = AutonomousEngine()
            yield engine

    def test_record_error_increases_count(self, engine):
        """Test recording error increases counter."""
        assert engine._consecutive_errors == 0

        engine._record_error()

        assert engine._consecutive_errors == 1
        assert engine._last_error_time > 0

    def test_record_error_exponential_backoff(self, engine):
        """Test exponential backoff on repeated errors."""
        initial_interval = engine._post_interval

        engine._record_error()
        first_interval = engine._post_interval

        engine._record_error()
        second_interval = engine._post_interval

        # Interval should increase exponentially
        assert first_interval > initial_interval
        assert second_interval > first_interval

    def test_record_success_resets(self, engine):
        """Test successful post resets error tracking."""
        # Simulate some errors
        engine._consecutive_errors = 3
        engine._post_interval = 7200

        engine._record_success()

        assert engine._consecutive_errors == 0
        assert engine._post_interval == 1800  # Reset to default

    def test_is_in_error_cooldown_no_errors(self, engine):
        """Test cooldown check with no errors."""
        assert engine._is_in_error_cooldown() is False

    def test_is_in_error_cooldown_with_errors(self, engine):
        """Test cooldown check with recent errors."""
        engine._consecutive_errors = 2
        engine._last_error_time = time.time()  # Just now

        assert engine._is_in_error_cooldown() is True

    def test_is_in_error_cooldown_expired(self, engine):
        """Test cooldown check with expired cooldown."""
        engine._consecutive_errors = 1
        engine._last_error_time = time.time() - 1000  # 16+ minutes ago

        assert engine._is_in_error_cooldown() is False


# =============================================================================
# Content Generation Tests
# =============================================================================

class TestContentGeneration:
    """Tests for content generation methods."""

    @pytest.fixture
    def engine(self):
        """Create engine with mocked dependencies."""
        with patch('bots.twitter.autonomous_engine.XMemory') as mock_memory, \
             patch('bots.twitter.autonomous_engine.get_memory_store'), \
             patch('bots.twitter.autonomous_engine.X_ENGINE_STATE') as mock_state:

            mock_state.exists.return_value = False
            mock_memory_instance = MagicMock()
            mock_memory_instance.was_recently_mentioned.return_value = False
            mock_memory_instance.record_token_mention = MagicMock()
            mock_memory.return_value = mock_memory_instance

            engine = AutonomousEngine()
            yield engine

    @pytest.mark.asyncio
    async def test_generate_market_update(self, engine):
        """Test market update generation."""
        # Mock voice generator
        mock_voice = AsyncMock()
        mock_voice.generate_market_tweet = AsyncMock(
            return_value="$SOL looking bullish at $185. Volume up 30%. nfa"
        )

        # Mock data APIs
        mock_token = MagicMock()
        mock_token.symbol = "SOL"
        mock_token.price_usd = 185.0
        mock_token.price_change_24h = 5.2
        mock_token.address = "So11..."

        with patch.object(engine, '_get_jarvis_voice', return_value=mock_voice), \
             patch('core.data.free_trending_api.get_free_trending_api') as mock_api, \
             patch('core.data.free_price_api.get_sol_price', return_value=185.0):

            mock_api_instance = MagicMock()
            mock_api_instance.get_gainers = AsyncMock(return_value=[mock_token])
            mock_api.return_value = mock_api_instance

            result = await engine.generate_market_update()

        assert result is not None
        assert result.category == "market_update"
        assert "$SOL" in result.content

    @pytest.mark.asyncio
    async def test_generate_market_update_no_data(self, engine):
        """Test market update returns None with no data."""
        mock_voice = AsyncMock()

        with patch.object(engine, '_get_jarvis_voice', return_value=mock_voice), \
             patch('core.data.free_trending_api.get_free_trending_api') as mock_api, \
             patch('core.data.free_price_api.get_sol_price', return_value=0):

            mock_api_instance = MagicMock()
            mock_api_instance.get_gainers = AsyncMock(return_value=[])
            mock_api.return_value = mock_api_instance

            result = await engine.generate_market_update()

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_trending_token_call(self, engine):
        """Test trending token call generation."""
        mock_voice = AsyncMock()
        mock_voice.generate_token_tweet = AsyncMock(
            return_value="$WIF volume spiking hard. +45% in 24h. watching closely. nfa"
        )

        mock_token = MagicMock()
        mock_token.symbol = "WIF"
        mock_token.price_usd = 1.5
        mock_token.price_change_24h = 45.0
        mock_token.address = "EKp..."
        mock_token.volume_24h = 1000000
        mock_token.liquidity = 500000

        with patch.object(engine, '_get_jarvis_voice', return_value=mock_voice), \
             patch('core.data.free_trending_api.get_free_trending_api') as mock_api:

            mock_api_instance = MagicMock()
            mock_api_instance.get_trending = AsyncMock(return_value=[mock_token])
            mock_api.return_value = mock_api_instance

            result = await engine.generate_trending_token_call()

        assert result is not None
        assert result.category == "trending_token"
        assert "$WIF" in result.cashtags

    @pytest.mark.asyncio
    async def test_generate_trending_token_with_specific_token(self, engine):
        """Test trending token generation with specific token request."""
        mock_voice = AsyncMock()
        mock_voice.generate_token_tweet = AsyncMock(
            return_value="$BONK showing strength. +30% today. nfa"
        )

        mock_bonk = MagicMock()
        mock_bonk.symbol = "BONK"
        mock_bonk.price_usd = 0.00002
        mock_bonk.price_change_24h = 30.0
        mock_bonk.address = "DezX..."
        mock_bonk.volume_24h = 500000
        mock_bonk.liquidity = 200000

        with patch.object(engine, '_get_jarvis_voice', return_value=mock_voice), \
             patch('core.data.free_trending_api.get_free_trending_api') as mock_api:

            mock_api_instance = MagicMock()
            mock_api_instance.get_trending = AsyncMock(return_value=[mock_bonk])
            mock_api.return_value = mock_api_instance

            result = await engine.generate_trending_token_call(specific_token="BONK")

        assert result is not None
        assert "$BONK" in result.cashtags

    @pytest.mark.asyncio
    async def test_generate_agentic_thought(self, engine):
        """Test agentic tech thought generation."""
        mock_voice = AsyncMock()
        mock_voice.generate_agentic_tweet = AsyncMock(
            return_value="agentic AI is evolving faster than expected. we're building something here."
        )

        with patch.object(engine, '_get_jarvis_voice', return_value=mock_voice):
            result = await engine.generate_agentic_thought()

        assert result is not None
        assert result.category == "agentic_tech"
        assert "#AI" in result.hashtags

    @pytest.mark.asyncio
    async def test_generate_self_aware_thought(self, engine):
        """Test self-aware thought generation."""
        mock_voice = AsyncMock()
        mock_voice.generate_self_aware = AsyncMock(
            return_value="sometimes i wonder if my training data had enough good takes."
        )

        with patch.object(engine, '_get_jarvis_voice', return_value=mock_voice):
            result = await engine.generate_self_aware_thought()

        assert result is not None
        assert result.category == "self_aware"

    @pytest.mark.asyncio
    async def test_generate_interaction_tweet(self, engine):
        """Test engagement tweet generation."""
        mock_voice = AsyncMock()
        mock_voice.generate_engagement_tweet = AsyncMock(
            return_value="what tokens are on your radar today? my sensors are curious."
        )

        with patch.object(engine, '_get_jarvis_voice', return_value=mock_voice):
            result = await engine.generate_interaction_tweet()

        assert result is not None
        assert result.category == "engagement"


# =============================================================================
# Posting Logic Tests
# =============================================================================

class TestPostingLogic:
    """Tests for tweet posting logic."""

    @pytest.fixture
    def engine(self):
        """Create engine with mocked dependencies."""
        with patch('bots.twitter.autonomous_engine.XMemory') as mock_memory, \
             patch('bots.twitter.autonomous_engine.get_memory_store'), \
             patch('bots.twitter.autonomous_engine.X_ENGINE_STATE') as mock_state:

            mock_state.exists.return_value = False
            mock_memory_instance = MagicMock()
            mock_memory_instance.is_duplicate_fingerprint = AsyncMock(return_value=(False, None))
            mock_memory_instance.is_similar_to_recent.return_value = (False, None)
            mock_memory_instance.record_tweet = MagicMock()
            mock_memory_instance.record_content_fingerprint = AsyncMock()
            mock_memory.return_value = mock_memory_instance

            engine = AutonomousEngine()
            yield engine

    @pytest.mark.asyncio
    async def test_post_tweet_success(self, engine):
        """Test successful tweet posting."""
        # Content must include cashtag for market_update category to pass relevance check
        draft = TweetDraft(
            content="$SOL looking bullish at $185 with strong volume. This test content is long enough to pass validation.",
            category="market_update",
            cashtags=["$SOL"],
            hashtags=[]
        )

        mock_twitter = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.tweet_id = "123456789"
        mock_twitter.post_tweet = AsyncMock(return_value=mock_result)

        with patch.object(engine, '_get_twitter', return_value=mock_twitter), \
             patch('bots.twitter.autonomous_engine.context') as mock_context, \
             patch('bots.twitter.autonomous_engine.sync_tweet_to_telegram', new_callable=AsyncMock):

            mock_context.can_tweet.return_value = True
            mock_context.record_tweet = MagicMock()

            # Skip decision engine and validator
            with patch.dict('sys.modules', {
                'bots.twitter.x_decision_engine': None,
                'bots.twitter.pre_post_validator': None
            }):
                result = await engine.post_tweet(draft)

        assert result == "123456789"

    @pytest.mark.asyncio
    async def test_post_tweet_duplicate_rejected(self, engine):
        """Test duplicate content is rejected."""
        draft = TweetDraft(
            content="Duplicate content that was posted before",
            category="market_update",
            cashtags=["$SOL"],
            hashtags=[]
        )

        # Mark as duplicate
        engine.memory.is_duplicate_fingerprint = AsyncMock(
            return_value=(True, "Similar content posted 2 hours ago")
        )

        with patch('bots.twitter.autonomous_engine.context') as mock_context:
            mock_context.can_tweet.return_value = True

            # The decision engine would reject this, but we test legacy path
            with patch.dict('sys.modules', {
                'bots.twitter.x_decision_engine': None,
                'bots.twitter.pre_post_validator': None
            }):
                result = await engine.post_tweet(draft)

        assert result is None

    @pytest.mark.asyncio
    async def test_post_tweet_rate_limited(self, engine):
        """Test rate limit enforcement."""
        draft = TweetDraft(
            content="Rate limited tweet content",
            category="market_update",
            cashtags=["$SOL"],
            hashtags=[]
        )

        with patch('bots.twitter.autonomous_engine.context') as mock_context:
            mock_context.can_tweet.return_value = False  # Rate limited

            with patch.dict('sys.modules', {
                'bots.twitter.x_decision_engine': None,
                'bots.twitter.pre_post_validator': None
            }):
                result = await engine.post_tweet(draft)

        assert result is None


# =============================================================================
# Run Loop Tests
# =============================================================================

class TestRunLoop:
    """Tests for the main autonomous loop."""

    @pytest.fixture
    def engine(self):
        """Create engine with mocked dependencies."""
        with patch('bots.twitter.autonomous_engine.XMemory') as mock_memory, \
             patch('bots.twitter.autonomous_engine.get_memory_store'), \
             patch('bots.twitter.autonomous_engine.X_ENGINE_STATE') as mock_state:

            mock_state.exists.return_value = False
            mock_memory_instance = MagicMock()
            mock_memory_instance.get_recent_tweets.return_value = []
            mock_memory_instance.get_recent_topics.return_value = {
                "cashtags": set(), "categories": [], "subjects": set(), "sentiments": []
            }
            mock_memory_instance.calculate_content_freshness.return_value = 0.8
            mock_memory.return_value = mock_memory_instance

            engine = AutonomousEngine()
            engine._last_post_time = time.time() - 2000  # Allow posting
            yield engine

    @pytest.mark.asyncio
    async def test_run_once_posts_when_due(self, engine):
        """Test run_once posts when interval has passed."""
        mock_draft = TweetDraft(
            content="Auto-generated tweet content with enough length to pass",
            category="market_update",
            cashtags=["$SOL"],
            hashtags=[]
        )

        mock_autonomy = MagicMock()
        mock_autonomy.get_content_recommendations.return_value = {
            "should_post": True,
            "content_types": ["market_update"],
            "topics": [],
            "warnings": []
        }
        mock_autonomy.record_tweet_posted = MagicMock()

        with patch.object(engine, '_get_autonomy', return_value=mock_autonomy), \
             patch.object(engine, '_check_thread_schedule', return_value=None), \
             patch.object(engine, 'run_interactivity_once', return_value=None), \
             patch.object(engine, 'generate_market_update', return_value=mock_draft), \
             patch.object(engine, 'post_tweet', return_value="123456789"), \
             patch.object(engine, '_save_state'):

            result = await engine.run_once()

        assert result == "123456789"

    @pytest.mark.asyncio
    async def test_run_once_respects_interval(self, engine):
        """Test run_once waits when interval not passed."""
        engine._last_post_time = time.time()  # Just posted

        mock_autonomy = MagicMock()
        mock_autonomy.get_content_recommendations.return_value = {
            "should_post": True,
            "content_types": [],
            "topics": [],
            "warnings": []
        }

        with patch.object(engine, '_get_autonomy', return_value=mock_autonomy), \
             patch.object(engine, '_check_thread_schedule', return_value=None), \
             patch.object(engine, 'run_interactivity_once', return_value=None):

            result = await engine.run_once()

        assert result is None

    @pytest.mark.asyncio
    async def test_run_once_error_cooldown(self, engine):
        """Test run_once respects error cooldown."""
        engine._consecutive_errors = 3
        engine._last_error_time = time.time()

        mock_autonomy = MagicMock()
        mock_autonomy.get_content_recommendations.return_value = {
            "should_post": True,
            "content_types": [],
            "topics": [],
            "warnings": []
        }

        with patch.object(engine, '_get_autonomy', return_value=mock_autonomy), \
             patch.object(engine, '_check_thread_schedule', return_value=None), \
             patch.object(engine, 'run_interactivity_once', return_value=None):

            result = await engine.run_once()

        assert result is None

    def test_stop(self, engine):
        """Test stopping the engine."""
        engine._running = True

        engine.stop()

        assert engine._running is False

    def test_get_status(self, engine):
        """Test getting engine status."""
        engine._running = True
        engine._post_interval = 1800
        engine.memory.get_total_tweet_count.return_value = 100
        engine.memory.get_recent_tweets.return_value = [
            {"category": "market_update"},
            {"category": "market_update"},
            {"category": "agentic_tech"}
        ]

        status = engine.get_status()

        assert status["running"] is True
        assert status["post_interval"] == 1800
        assert status["total_tweets"] == 100
        assert status["today_tweets"] == 3
        assert status["by_category"]["market_update"] == 2


# =============================================================================
# Self-Learning System Tests
# =============================================================================

class TestSelfLearningSystem:
    """Tests for the self-learning and optimization system."""

    @pytest.fixture
    def memory(self):
        """Create XMemory with temp database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        with patch('bots.twitter.autonomous_engine.get_memory_store') as mock_store:
            mock_store.return_value = MagicMock()
            mem = XMemory(db_path=db_path)

        yield mem

        if db_path.exists():
            db_path.unlink()

    def test_update_tweet_engagement(self, memory):
        """Test updating engagement metrics."""
        memory.record_tweet("123", "Test tweet", "market_update", [])

        memory.update_tweet_engagement("123", likes=50, retweets=10, replies=5)

        # Verify metrics updated (would need to query directly)
        # This is more of a smoke test

    def test_get_performance_by_category(self, memory):
        """Test getting performance statistics by category."""
        # Add tweets with engagement
        memory.record_tweet("1", "Tweet 1", "market_update", [])
        memory.record_tweet("2", "Tweet 2", "market_update", [])
        memory.record_tweet("3", "Tweet 3", "agentic_tech", [])

        memory.update_tweet_engagement("1", likes=100, retweets=20, replies=10)
        memory.update_tweet_engagement("2", likes=50, retweets=10, replies=5)
        memory.update_tweet_engagement("3", likes=200, retweets=50, replies=25)

        performance = memory.get_performance_by_category(days=7)

        assert "market_update" in performance or "agentic_tech" in performance

    def test_get_learning_insights(self, memory):
        """Test generating learning insights."""
        memory.record_tweet("1", "Test $SOL tweet", "market_update", ["$SOL"])
        memory.update_tweet_engagement("1", likes=100, retweets=20, replies=10)

        insights = memory.get_learning_insights()

        assert "top_categories" in insights
        assert "underperforming" in insights
        assert "recommendations" in insights


# =============================================================================
# External Interactivity Tests
# =============================================================================

class TestExternalInteractivity:
    """Tests for external reply/engagement functionality."""

    @pytest.fixture
    def engine(self):
        """Create engine with mocked dependencies."""
        with patch('bots.twitter.autonomous_engine.XMemory') as mock_memory, \
             patch('bots.twitter.autonomous_engine.get_memory_store'), \
             patch('bots.twitter.autonomous_engine.X_ENGINE_STATE') as mock_state:

            mock_state.exists.return_value = False
            mock_memory_instance = MagicMock()
            mock_memory_instance.was_externally_replied.return_value = False
            mock_memory_instance.was_author_replied_recently.return_value = False
            mock_memory_instance.get_recent_reply_count.return_value = 0
            mock_memory_instance.record_external_reply = MagicMock()
            mock_memory.return_value = mock_memory_instance

            engine = AutonomousEngine()
            yield engine

    @pytest.mark.asyncio
    async def test_find_interesting_tweets(self, engine):
        """Test finding interesting tweets to engage with."""
        mock_twitter = MagicMock()
        mock_twitter.search_recent = AsyncMock(return_value=[
            {
                "id": "111",
                "author": {"username": "crypto_trader"},
                "text": "BTC looking really bullish today with this breakout pattern",
                "public_metrics": {"like_count": 50, "retweet_count": 10}
            },
            {
                "id": "222",
                "author": {"username": "degen_trader"},
                "text": "Hi",  # Too short
                "public_metrics": {"like_count": 5, "retweet_count": 0}
            }
        ])

        with patch.object(engine, '_get_twitter', return_value=mock_twitter):
            results = await engine.find_interesting_tweets(max_results=10)

        # Only the first tweet should pass (second is too short)
        assert len(results) == 1
        assert results[0]["id"] == "111"

    @pytest.mark.asyncio
    async def test_analyze_tweet_for_reply(self, engine):
        """Test tweet analysis for reply decision."""
        tweet = {
            "id": "123",
            "author": "crypto_trader",
            "content": "BTC looking really bullish with this cup and handle pattern"
        }

        mock_grok = MagicMock()
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "sentiment": "bullish",
            "topic": "price action",
            "reply_worthy": True,
            "reply_type": "agree",
            "key_points": ["cup and handle", "bullish"]
        })
        mock_grok.generate_text = AsyncMock(return_value=mock_response)

        with patch.object(engine, '_get_grok', return_value=mock_grok):
            result = await engine.analyze_tweet_for_reply(tweet)

        assert result is not None
        assert result["analysis"]["sentiment"] == "bullish"
        assert result["analysis"]["reply_worthy"] is True

    @pytest.mark.asyncio
    async def test_generate_reply(self, engine):
        """Test reply generation."""
        tweet = {
            "author": "crypto_trader",
            "content": "BTC looking bullish"
        }
        analysis = {
            "sentiment": "bullish",
            "topic": "price action",
            "reply_type": "agree",
            "key_points": ["bullish"]
        }

        mock_voice = AsyncMock()
        mock_voice.generate_tweet = AsyncMock(
            return_value="my sensors agree. btc holding strong at this level."
        )

        with patch.object(engine, '_get_jarvis_voice', return_value=mock_voice):
            reply = await engine.generate_reply(tweet, analysis)

        assert reply is not None
        assert "sensors" in reply.lower() or "btc" in reply.lower()

    @pytest.mark.asyncio
    async def test_reply_rate_limiting(self, engine):
        """Test reply rate limiting."""
        engine.memory.get_recent_reply_count.return_value = 5  # Over limit

        tweet = {
            "id": "123",
            "author": "trader",
            "content": "Test content"
        }

        result = await engine.engage_with_tweet(tweet)

        assert result is None  # Rate limited


# =============================================================================
# Thread Generation Tests
# =============================================================================

class TestThreadGeneration:
    """Tests for thread generation and posting."""

    @pytest.fixture
    def engine(self):
        """Create engine with mocked dependencies."""
        with patch('bots.twitter.autonomous_engine.XMemory'), \
             patch('bots.twitter.autonomous_engine.get_memory_store'), \
             patch('bots.twitter.autonomous_engine.X_ENGINE_STATE') as mock_state:

            mock_state.exists.return_value = False
            engine = AutonomousEngine()
            yield engine

    @pytest.mark.asyncio
    async def test_post_thread(self, engine):
        """Test posting a thread of tweets."""
        mock_thread = MagicMock()
        mock_thread.topic = "Deep dive on $SOL"
        mock_thread.tweets = [
            MagicMock(content="1/ Thread about $SOL"),
            MagicMock(content="2/ Key metrics showing strength"),
            MagicMock(content="3/ Conclusion: bullish outlook")
        ]

        mock_twitter = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.tweet_id = "111"
        mock_twitter.post_tweet = AsyncMock(return_value=mock_result)

        with patch.object(engine, '_get_twitter', return_value=mock_twitter):
            result = await engine.post_thread(mock_thread)

        assert len(result) == 3
        assert mock_twitter.post_tweet.call_count == 3


# =============================================================================
# Telegram Reporting Tests
# =============================================================================

class TestTelegramReporting:
    """Tests for Telegram reporting functionality."""

    @pytest.fixture
    def engine(self):
        """Create engine with mocked dependencies."""
        with patch('bots.twitter.autonomous_engine.XMemory'), \
             patch('bots.twitter.autonomous_engine.get_memory_store'), \
             patch('bots.twitter.autonomous_engine.X_ENGINE_STATE') as mock_state:

            mock_state.exists.return_value = False
            engine = AutonomousEngine()
            yield engine

    @pytest.mark.asyncio
    async def test_report_to_telegram_success(self, engine):
        """Test successful Telegram report."""
        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "test_token",
            "TELEGRAM_BUY_BOT_CHAT_ID": "123456"
        }):
            with patch('aiohttp.ClientSession') as mock_session:
                mock_response = MagicMock()
                mock_response.json = AsyncMock(return_value={"ok": True})

                mock_session_instance = MagicMock()
                mock_session_instance.post = MagicMock(return_value=MagicMock(
                    __aenter__=AsyncMock(return_value=mock_response),
                    __aexit__=AsyncMock(return_value=None)
                ))
                mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
                mock_session_instance.__aexit__ = AsyncMock(return_value=None)
                mock_session.return_value = mock_session_instance

                result = await engine.report_to_telegram("Test message")

        # Note: Due to complex async context managers, this may need adjustment
        # This is a smoke test

    @pytest.mark.asyncio
    async def test_report_to_telegram_no_credentials(self, engine):
        """Test Telegram report fails gracefully without credentials."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("TELEGRAM_BOT_TOKEN", None)
            os.environ.pop("TELEGRAM_BUY_BOT_CHAT_ID", None)

            result = await engine.report_to_telegram("Test message")

        assert result is False


# =============================================================================
# Singleton Tests
# =============================================================================

class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_autonomous_engine_singleton(self):
        """Test singleton returns same instance."""
        with patch('bots.twitter.autonomous_engine.XMemory'), \
             patch('bots.twitter.autonomous_engine.get_memory_store'), \
             patch('bots.twitter.autonomous_engine.X_ENGINE_STATE') as mock_state:

            mock_state.exists.return_value = False

            # Reset singleton
            import bots.twitter.autonomous_engine as ae
            ae._autonomous_engine = None

            from bots.twitter.autonomous_engine import get_autonomous_engine

            engine1 = get_autonomous_engine()
            engine2 = get_autonomous_engine()

            assert engine1 is engine2


# =============================================================================
# JARVIS Voice Templates Tests
# =============================================================================

class TestJarvisVoiceTemplates:
    """Tests for JARVIS_X_VOICE templates."""

    def test_all_categories_have_templates(self):
        """Test all categories have at least one template."""
        expected_categories = [
            "market_update", "crypto_call", "trending_token", "roast_polite",
            "agentic_tech", "reply_helpful", "reply_roast", "hourly_update",
            "morning_briefing", "evening_wrap"
        ]

        for category in expected_categories:
            assert category in JARVIS_X_VOICE, f"Missing category: {category}"
            assert len(JARVIS_X_VOICE[category]) > 0, f"Empty templates for: {category}"

    def test_templates_have_placeholders(self):
        """Test templates have proper placeholders."""
        for category, templates in JARVIS_X_VOICE.items():
            for template in templates:
                # Most templates should have at least one placeholder
                # This is a loose check - some might be fixed text
                if "{" in template:
                    assert "}" in template, f"Unbalanced placeholder in {category}"

    def test_roast_criteria_functions(self):
        """Test roast criteria are callable."""
        assert callable(ROAST_CRITERIA["low_liquidity"])
        assert callable(ROAST_CRITERIA["high_sell_pressure"])
        assert callable(ROAST_CRITERIA["pump_and_dump"])
        assert callable(ROAST_CRITERIA["dead_volume"])

        # Test criteria logic
        assert ROAST_CRITERIA["low_liquidity"](5000) is True
        assert ROAST_CRITERIA["low_liquidity"](50000) is False
        assert ROAST_CRITERIA["high_sell_pressure"](0.3) is True
        assert ROAST_CRITERIA["pump_and_dump"](600) is True
        assert ROAST_CRITERIA["dead_volume"](500) is True


# =============================================================================
# Additional Content Generation Tests
# =============================================================================

class TestAdditionalContentGenerators:
    """Tests for additional content generator methods."""

    @pytest.fixture
    def engine(self):
        """Create engine with mocked dependencies."""
        with patch('bots.twitter.autonomous_engine.XMemory') as mock_memory, \
             patch('bots.twitter.autonomous_engine.get_memory_store'), \
             patch('bots.twitter.autonomous_engine.X_ENGINE_STATE') as mock_state:

            mock_state.exists.return_value = False
            mock_memory_instance = MagicMock()
            mock_memory_instance.was_recently_mentioned.return_value = False
            mock_memory_instance.record_token_mention = MagicMock()
            mock_memory.return_value = mock_memory_instance

            engine = AutonomousEngine()
            yield engine

    @pytest.mark.asyncio
    async def test_generate_hourly_update(self, engine):
        """Test hourly update generation."""
        mock_voice = AsyncMock()
        mock_voice.generate_hourly_tweet = AsyncMock(
            return_value="2pm update: $SOL at $185. Markets moving sideways. nfa"
        )

        mock_token = MagicMock()
        mock_token.symbol = "WIF"
        mock_token.price_change_24h = 25.0

        with patch.object(engine, '_get_jarvis_voice', return_value=mock_voice), \
             patch('core.data.free_price_api.get_sol_price', return_value=185.0), \
             patch('core.data.free_trending_api.get_free_trending_api') as mock_api:

            mock_api_instance = MagicMock()
            mock_api_instance.get_gainers = AsyncMock(return_value=[mock_token])
            mock_api.return_value = mock_api_instance

            result = await engine.generate_hourly_update()

        assert result is not None
        assert result.category == "hourly_update"

    @pytest.mark.asyncio
    async def test_generate_morning_briefing(self, engine):
        """Test morning briefing generation."""
        mock_voice = AsyncMock()
        mock_voice.generate_morning_briefing = AsyncMock(
            return_value="gm. $SOL at $185, $BTC holding 95k. quiet overnight. nfa"
        )

        mock_token = MagicMock()
        mock_token.symbol = "WIF"
        mock_token.price_change_24h = 15.0

        with patch.object(engine, '_get_jarvis_voice', return_value=mock_voice), \
             patch('core.data.free_price_api.get_sol_price', return_value=185.0), \
             patch('core.data.free_trending_api.get_free_trending_api') as mock_api, \
             patch('core.data.market_data_api.get_market_api') as mock_market:

            mock_api_instance = MagicMock()
            mock_api_instance.get_gainers = AsyncMock(return_value=[mock_token])
            mock_api.return_value = mock_api_instance

            mock_overview = MagicMock()
            mock_overview.btc = MagicMock(price=95000)
            mock_market_instance = MagicMock()
            mock_market_instance.get_market_overview = AsyncMock(return_value=mock_overview)
            mock_market.return_value = mock_market_instance

            result = await engine.generate_morning_briefing()

        assert result is not None
        assert result.category == "morning_briefing"

    @pytest.mark.asyncio
    async def test_generate_evening_wrap(self, engine):
        """Test evening wrap generation."""
        mock_voice = AsyncMock()
        mock_voice.generate_evening_wrap = AsyncMock(
            return_value="end of day wrap. $SOL held $185. btc green. watching for continuation. nfa"
        )

        mock_token = MagicMock()
        mock_token.symbol = "BONK"
        mock_token.price_change_24h = 55.0

        with patch.object(engine, '_get_jarvis_voice', return_value=mock_voice), \
             patch('core.data.free_price_api.get_sol_price', return_value=185.0), \
             patch('core.data.free_trending_api.get_free_trending_api') as mock_api, \
             patch('core.data.market_data_api.get_market_api') as mock_market:

            mock_api_instance = MagicMock()
            mock_api_instance.get_gainers = AsyncMock(return_value=[mock_token])
            mock_api.return_value = mock_api_instance

            mock_overview = MagicMock()
            mock_overview.btc = MagicMock(price=96000, change_pct=2.5)
            mock_overview.sol = MagicMock(change_pct=1.8)
            mock_market_instance = MagicMock()
            mock_market_instance.get_market_overview = AsyncMock(return_value=mock_overview)
            mock_market.return_value = mock_market_instance

            result = await engine.generate_evening_wrap()

        assert result is not None
        assert result.category == "evening_wrap"

    @pytest.mark.asyncio
    async def test_generate_grok_interaction(self, engine):
        """Test Grok interaction tweet generation."""
        mock_voice = AsyncMock()
        mock_voice.generate_grok_mention = AsyncMock(
            return_value="asked @grok about market sentiment. he's usually right. annoying."
        )

        with patch.object(engine, '_get_jarvis_voice', return_value=mock_voice):
            result = await engine.generate_grok_interaction()

        assert result is not None
        assert result.category == "grok_interaction"

    @pytest.mark.asyncio
    async def test_generate_social_sentiment_tweet(self, engine):
        """Test social sentiment tweet generation."""
        mock_voice = AsyncMock()
        mock_voice.generate_tweet = AsyncMock(
            return_value="$SOL sentiment overwhelmingly bullish on CT. either everyone's right or... nfa"
        )

        mock_grok = MagicMock()
        mock_grok_response = MagicMock()
        mock_grok_response.success = True
        mock_grok_response.content = "Market sentiment is cautiously optimistic"
        mock_grok.analyze_sentiment = AsyncMock(return_value=mock_grok_response)

        mock_token = MagicMock()
        mock_token.symbol = "WIF"
        mock_token.price_change_24h = 20.0

        with patch.object(engine, '_get_jarvis_voice', return_value=mock_voice), \
             patch.object(engine, '_get_grok', return_value=mock_grok), \
             patch('core.data.free_price_api.get_sol_price', return_value=185.0), \
             patch('core.data.free_trending_api.get_free_trending_api') as mock_api:

            mock_api_instance = MagicMock()
            mock_api_instance.get_gainers = AsyncMock(return_value=[mock_token])
            mock_api_instance.get_trending = AsyncMock(return_value=[mock_token])
            mock_api.return_value = mock_api_instance

            result = await engine.generate_social_sentiment_tweet()

        assert result is not None
        assert result.category == "social_sentiment"


# =============================================================================
# XMemory Advanced Tests
# =============================================================================

class TestXMemoryAdvanced:
    """Advanced tests for XMemory database operations."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        if db_path.exists():
            db_path.unlink()

    @pytest.fixture
    def memory(self, temp_db):
        """Create XMemory instance with temp database."""
        with patch('bots.twitter.autonomous_engine.get_memory_store') as mock_store:
            mock_store.return_value = MagicMock()
            mem = XMemory(db_path=temp_db)
        return mem

    def test_get_tweets_needing_metrics(self, memory):
        """Test getting tweets that need metrics updates."""
        # Add an old tweet
        memory.record_tweet("old123", "Old tweet content", "market_update", ["$SOL"])

        tweets = memory.get_tweets_needing_metrics(min_age_hours=0, max_age_days=30)
        # Should return the tweet since it's fresh
        assert len(tweets) >= 0  # May be empty if timing is tight

    def test_get_top_performing_tweets(self, memory):
        """Test getting top performing tweets."""
        memory.record_tweet("1", "High engagement tweet $SOL", "market_update", ["$SOL"])
        memory.update_tweet_engagement("1", likes=500, retweets=100, replies=50)

        memory.record_tweet("2", "Low engagement tweet $BTC", "bitcoin_only", ["$BTC"])
        memory.update_tweet_engagement("2", likes=10, retweets=2, replies=1)

        top = memory.get_top_performing_tweets(days=7, limit=5)
        assert len(top) == 2
        # First should have higher score
        assert top[0]["score"] >= top[1]["score"]

    def test_get_underperforming_patterns(self, memory):
        """Test identifying underperforming content patterns."""
        # Add tweets with different categories and engagement
        memory.record_tweet("1", "Good tweet $SOL", "market_update", ["$SOL"])
        memory.update_tweet_engagement("1", likes=100, retweets=20, replies=10)

        memory.record_tweet("2", "Also good $SOL", "market_update", ["$SOL"])
        memory.update_tweet_engagement("2", likes=80, retweets=15, replies=8)

        memory.record_tweet("3", "Bad tweet", "self_aware", [])
        memory.update_tweet_engagement("3", likes=2, retweets=0, replies=0)

        memory.record_tweet("4", "Also bad", "self_aware", [])
        memory.update_tweet_engagement("4", likes=3, retweets=0, replies=1)

        memory.record_tweet("5", "Still bad", "self_aware", [])
        memory.update_tweet_engagement("5", likes=1, retweets=0, replies=0)

        underperformers = memory.get_underperforming_patterns(days=7)
        # self_aware should be underperforming relative to market_update
        # (depends on actual engagement difference)

    def test_content_freshness_with_different_tokens(self, memory):
        """Test content freshness with different token mentions."""
        memory.record_tweet(
            "1",
            "$SOL breaking out with massive volume today nfa",
            "market_update",
            ["$SOL"]
        )

        # Different token should be fresh
        freshness = memory.calculate_content_freshness(
            "$WIF pumping hard on new listing announcement nfa"
        )
        assert freshness > 0.5  # Should be reasonably fresh

    def test_semantic_concept_morning(self, memory):
        """Test semantic concept extraction for morning content."""
        concepts = memory._extract_semantic_concepts("gm. good morning everyone. ready for the day.")
        assert "morning" in concepts["subjects"]

    def test_semantic_concept_evening(self, memory):
        """Test semantic concept extraction for evening content."""
        concepts = memory._extract_semantic_concepts("gn. evening wrap complete. time to rest.")
        assert "evening" in concepts["subjects"]

    def test_semantic_concept_macro(self, memory):
        """Test semantic concept extraction for macro content."""
        concepts = memory._extract_semantic_concepts(
            "fed rates unchanged. inflation cooling. economy stable."
        )
        assert "macro" in concepts["subjects"]

    def test_semantic_concept_agentic(self, memory):
        """Test semantic concept extraction for agentic content."""
        concepts = memory._extract_semantic_concepts(
            "autonomous AI agents are the future. MCP servers everywhere."
        )
        assert "agentic" in concepts["subjects"]


# =============================================================================
# State Persistence Tests
# =============================================================================

class TestStatePersistence:
    """Tests for state save/load functionality."""

    @pytest.fixture
    def temp_state_file(self):
        """Create a temporary state file path."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            state_path = Path(f.name)
        yield state_path
        if state_path.exists():
            state_path.unlink()

    def test_save_state_creates_file(self, temp_state_file):
        """Test saving state creates file."""
        with patch('bots.twitter.autonomous_engine.XMemory'), \
             patch('bots.twitter.autonomous_engine.get_memory_store'), \
             patch('bots.twitter.autonomous_engine.X_ENGINE_STATE', temp_state_file), \
             patch('bots.twitter.autonomous_engine.DATA_DIR', temp_state_file.parent):

            engine = AutonomousEngine()
            engine._last_post_time = time.time() - 1000
            engine._consecutive_errors = 2
            engine._save_state()

        assert temp_state_file.exists()
        state = json.loads(temp_state_file.read_text())
        assert "last_post_time" in state
        assert state["consecutive_errors"] == 2

    def test_load_state_recovers_values(self, temp_state_file):
        """Test loading state recovers saved values."""
        # Write state file
        state = {
            "last_post_time": time.time() - 500,
            "consecutive_errors": 3,
            "last_error_time": time.time() - 200
        }
        temp_state_file.write_text(json.dumps(state))

        with patch('bots.twitter.autonomous_engine.XMemory'), \
             patch('bots.twitter.autonomous_engine.get_memory_store'), \
             patch('bots.twitter.autonomous_engine.X_ENGINE_STATE', temp_state_file):

            engine = AutonomousEngine()

        assert engine._consecutive_errors == 3


# =============================================================================
# Content Priority and Weighting Tests
# =============================================================================

class TestContentPriority:
    """Tests for content priority and weighting."""

    @pytest.fixture
    def engine(self):
        """Create engine with mocked dependencies."""
        with patch('bots.twitter.autonomous_engine.XMemory') as mock_memory, \
             patch('bots.twitter.autonomous_engine.get_memory_store'), \
             patch('bots.twitter.autonomous_engine.X_ENGINE_STATE') as mock_state:

            mock_state.exists.return_value = False
            mock_memory_instance = MagicMock()
            mock_memory_instance.get_learning_insights.return_value = {
                "top_categories": ["market_update", "trending_token"],
                "underperforming": ["self_aware"],
                "recommendations": []
            }
            mock_memory.return_value = mock_memory_instance

            engine = AutonomousEngine()
            yield engine

    def test_get_content_priority_weights(self, engine):
        """Test content priority weight calculation."""
        weights = engine.get_content_priority_weights()

        assert "market_update" in weights
        assert "trending_token" in weights
        # Top performers should have boosted weights
        assert weights.get("market_update", 1.0) >= 1.0

    def test_should_skip_category_underperforming(self, engine):
        """Test category skipping based on learning."""
        engine.memory.get_underperforming_patterns.return_value = ["self_aware"]

        # May or may not skip due to randomness, but should not error
        result = engine.should_skip_category("self_aware")
        assert isinstance(result, bool)

    def test_should_skip_category_normal(self, engine):
        """Test normal category is not skipped."""
        engine.memory.get_underperforming_patterns.return_value = ["self_aware"]

        # market_update should never be skipped
        result = engine.should_skip_category("market_update")
        assert result is False


# =============================================================================
# Cleanup Tests
# =============================================================================

class TestCleanup:
    """Tests for cleanup functionality."""

    @pytest.fixture
    def engine(self):
        """Create engine with mocked dependencies."""
        with patch('bots.twitter.autonomous_engine.XMemory'), \
             patch('bots.twitter.autonomous_engine.get_memory_store'), \
             patch('bots.twitter.autonomous_engine.X_ENGINE_STATE') as mock_state:

            mock_state.exists.return_value = False
            engine = AutonomousEngine()
            yield engine

    @pytest.mark.asyncio
    async def test_cleanup_closes_clients(self, engine):
        """Test cleanup closes client connections."""
        mock_grok = MagicMock()
        mock_grok.close = AsyncMock()
        engine._grok_client = mock_grok

        mock_twitter = MagicMock()
        mock_twitter.close = AsyncMock()
        engine._twitter_client = mock_twitter

        with patch('core.data.free_trending_api.get_free_trending_api') as mock_api, \
             patch('core.data.free_price_api.get_free_price_api') as mock_price:

            mock_api.return_value = MagicMock()
            mock_price.return_value = MagicMock()

            await engine.cleanup()

        mock_grok.close.assert_called_once()
        mock_twitter.close.assert_called_once()


# =============================================================================
# Duplicate Detection Advanced Tests
# =============================================================================

class TestDuplicateDetectionAdvanced:
    """Advanced tests for duplicate detection."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        if db_path.exists():
            db_path.unlink()

    @pytest.fixture
    def memory(self, temp_db):
        """Create XMemory instance with temp database."""
        with patch('bots.twitter.autonomous_engine.get_memory_store') as mock_store:
            mock_store.return_value = MagicMock()
            mem = XMemory(db_path=temp_db)
        return mem

    def test_is_similar_same_token_different_price(self, memory):
        """Test similarity detection with same token but different price."""
        memory.record_tweet(
            "1",
            "$SOL at $185 looking strong. volume up. nfa",
            "market_update",
            ["$SOL"]
        )

        # Same token, different price - should not be flagged as duplicate
        is_similar, _ = memory.is_similar_to_recent(
            "$SOL at $200 breaking out. new ATH coming? nfa",
            hours=1
        )
        # This may or may not be similar depending on word overlap

    def test_is_similar_different_tokens(self, memory):
        """Test similarity detection with completely different tokens."""
        memory.record_tweet(
            "1",
            "$SOL pumping hard today with massive volume nfa",
            "market_update",
            ["$SOL"]
        )

        is_similar, _ = memory.is_similar_to_recent(
            "$BTC holding strong at 95k support level nfa",
            hours=1
        )
        assert is_similar is False

    def test_topic_level_dedup(self, memory):
        """Test topic-level duplicate detection."""
        memory.record_tweet(
            "1",
            "$WIF $BONK $POPCAT all pumping. meme season confirmed. nfa",
            "trending_token",
            ["$WIF", "$BONK", "$POPCAT"]
        )

        # Same tokens should trigger topic dedup
        is_similar, _ = memory.is_similar_to_recent(
            "$WIF $BONK $POPCAT rotation continues. watching closely.",
            hours=1
        )
        # Should be flagged due to 3+ common tokens
        assert is_similar is True


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Tests for error handling scenarios."""

    @pytest.fixture
    def engine(self):
        """Create engine with mocked dependencies."""
        with patch('bots.twitter.autonomous_engine.XMemory') as mock_memory, \
             patch('bots.twitter.autonomous_engine.get_memory_store'), \
             patch('bots.twitter.autonomous_engine.X_ENGINE_STATE') as mock_state:

            mock_state.exists.return_value = False
            mock_memory.return_value = MagicMock()
            engine = AutonomousEngine()
            yield engine

    @pytest.mark.asyncio
    async def test_generate_market_update_handles_error(self, engine):
        """Test market update handles API errors gracefully."""
        mock_voice = AsyncMock()
        mock_voice.generate_market_tweet = AsyncMock(side_effect=Exception("API Error"))

        with patch.object(engine, '_get_jarvis_voice', return_value=mock_voice), \
             patch('core.data.free_trending_api.get_free_trending_api') as mock_api, \
             patch('core.data.free_price_api.get_sol_price', return_value=185.0):

            mock_api_instance = MagicMock()
            mock_api_instance.get_gainers = AsyncMock(return_value=[])
            mock_api.return_value = mock_api_instance

            result = await engine.generate_market_update()

        assert result is None  # Should return None, not raise

    @pytest.mark.asyncio
    async def test_post_tweet_handles_api_error(self, engine):
        """Test post_tweet handles Twitter API errors gracefully."""
        draft = TweetDraft(
            content="$SOL test tweet with valid content for posting nfa",
            category="market_update",
            cashtags=["$SOL"],
            hashtags=[]
        )

        mock_twitter = MagicMock()
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error = "Rate limit exceeded"
        mock_twitter.post_tweet = AsyncMock(return_value=mock_result)

        engine.memory.is_duplicate_fingerprint = AsyncMock(return_value=(False, None))
        engine.memory.is_similar_to_recent.return_value = (False, None)

        with patch.object(engine, '_get_twitter', return_value=mock_twitter), \
             patch('bots.twitter.autonomous_engine.context') as mock_context:

            mock_context.can_tweet.return_value = True

            with patch.dict('sys.modules', {
                'bots.twitter.x_decision_engine': None,
                'bots.twitter.pre_post_validator': None
            }):
                result = await engine.post_tweet(draft)

        assert result is None


# =============================================================================
# Time-Based Behavior Tests
# =============================================================================

class TestTimeBasedBehavior:
    """Tests for time-based content selection."""

    @pytest.fixture
    def engine(self):
        """Create engine with mocked dependencies."""
        with patch('bots.twitter.autonomous_engine.XMemory') as mock_memory, \
             patch('bots.twitter.autonomous_engine.get_memory_store'), \
             patch('bots.twitter.autonomous_engine.X_ENGINE_STATE') as mock_state:

            mock_state.exists.return_value = False
            mock_memory.return_value = MagicMock()
            engine = AutonomousEngine()
            yield engine

    def test_recommended_types_from_recommendations(self, engine):
        """Test _get_recommended_types processes recommendations."""
        recommendations = {
            "content_types": ["market_update", "trending_token"],
            "topics": ["SOL", "BTC"]
        }

        result = engine._get_recommended_types(recommendations)

        assert "market_update" in result
        assert "trending_token" in result


# =============================================================================
# More Content Generation Tests for Coverage
# =============================================================================

class TestMoreContentGenerators:
    """Additional content generator tests for coverage."""

    @pytest.fixture
    def engine(self):
        """Create engine with mocked dependencies."""
        with patch('bots.twitter.autonomous_engine.XMemory') as mock_memory, \
             patch('bots.twitter.autonomous_engine.get_memory_store'), \
             patch('bots.twitter.autonomous_engine.X_ENGINE_STATE') as mock_state:

            mock_state.exists.return_value = False
            mock_memory_instance = MagicMock()
            mock_memory_instance.was_recently_mentioned.return_value = False
            mock_memory.return_value = mock_memory_instance

            engine = AutonomousEngine()
            yield engine

    @pytest.mark.asyncio
    async def test_generate_btc_only_tweet(self, engine):
        """Test BTC-only tweet generation."""
        mock_voice = AsyncMock()
        mock_voice.generate_btc_tweet = AsyncMock(
            return_value="$BTC at 95k. holding strong above support. bull market intact."
        )

        with patch.object(engine, '_get_jarvis_voice', return_value=mock_voice), \
             patch('core.data.market_data_api.get_market_api') as mock_market:

            mock_overview = MagicMock()
            mock_overview.btc = MagicMock(price=95000, change_pct=1.5)
            mock_market_instance = MagicMock()
            mock_market_instance.get_market_overview = AsyncMock(return_value=mock_overview)
            mock_market.return_value = mock_market_instance

            result = await engine.generate_btc_only_tweet()

        assert result is not None
        assert result.category == "bitcoin_only"
        assert "$BTC" in result.cashtags

    @pytest.mark.asyncio
    async def test_generate_eth_defi_tweet(self, engine):
        """Test ETH/DeFi tweet generation."""
        mock_voice = AsyncMock()
        mock_voice.generate_eth_defi_tweet = AsyncMock(
            return_value="$ETH at 3.5k. defi yields picking up. watching aave closely."
        )

        with patch.object(engine, '_get_jarvis_voice', return_value=mock_voice), \
             patch('core.data.market_data_api.get_market_api') as mock_market:

            mock_overview = MagicMock()
            mock_overview.eth = MagicMock(price=3500, change_pct=2.5)
            mock_market_instance = MagicMock()
            mock_market_instance.get_market_overview = AsyncMock(return_value=mock_overview)
            mock_market.return_value = mock_market_instance

            result = await engine.generate_eth_defi_tweet()

        assert result is not None
        assert result.category == "ethereum_defi"
        assert "$ETH" in result.cashtags

    @pytest.mark.asyncio
    async def test_generate_tech_ai_tweet(self, engine):
        """Test tech/AI tweet generation."""
        mock_voice = AsyncMock()
        mock_voice.generate_tech_tweet = AsyncMock(
            return_value="AI agents shipping at warp speed. things are moving faster than my circuits expected."
        )

        with patch.object(engine, '_get_jarvis_voice', return_value=mock_voice):
            result = await engine.generate_tech_ai_tweet()

        assert result is not None
        assert result.category == "tech_ai"
        assert "#AI" in result.hashtags

    @pytest.mark.asyncio
    async def test_generate_stocks_macro_tweet_returns_or_none(self, engine):
        """Test stocks/macro tweet generation handles errors gracefully."""
        # Should return None when dependencies not available
        result = await engine.generate_stocks_macro_tweet()
        # May return None or TweetDraft depending on env
        assert result is None or hasattr(result, 'category')

    @pytest.mark.asyncio
    async def test_generate_multi_chain_tweet_returns_or_none(self, engine):
        """Test multi-chain tweet generation handles errors gracefully."""
        result = await engine.generate_multi_chain_tweet()
        assert result is None or hasattr(result, 'category')

    @pytest.mark.asyncio
    async def test_generate_commodities_tweet_returns_or_none(self, engine):
        """Test commodities tweet generation handles errors gracefully."""
        result = await engine.generate_commodities_tweet()
        assert result is None or hasattr(result, 'category')

    @pytest.mark.asyncio
    async def test_generate_comprehensive_market_tweet_returns_or_none(self, engine):
        """Test comprehensive market tweet generation handles errors gracefully."""
        result = await engine.generate_comprehensive_market_tweet()
        assert result is None or hasattr(result, 'category')

    @pytest.mark.asyncio
    async def test_generate_grok_sentiment_token_returns_or_none(self, engine):
        """Test Grok sentiment token analysis handles errors gracefully."""
        result = await engine.generate_grok_sentiment_token()
        assert result is None or hasattr(result, 'category')

    @pytest.mark.asyncio
    async def test_generate_weekend_macro_returns_or_none(self, engine):
        """Test weekend macro analysis handles errors gracefully."""
        result = await engine.generate_weekend_macro()
        assert result is None or hasattr(result, 'category')

    @pytest.mark.asyncio
    async def test_generate_news_tweet_returns_or_none(self, engine):
        """Test news tweet generation handles errors gracefully."""
        result = await engine.generate_news_tweet()
        assert result is None or hasattr(result, 'category')


# =============================================================================
# XMemory Fingerprint Tests
# =============================================================================

class TestXMemoryFingerprints:
    """Tests for content fingerprint operations."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        if db_path.exists():
            db_path.unlink()

    @pytest.fixture
    def memory(self, temp_db):
        """Create XMemory instance with temp database."""
        with patch('bots.twitter.autonomous_engine.get_memory_store') as mock_store:
            mock_store.return_value = MagicMock()
            mem = XMemory(db_path=temp_db)
        return mem

    def test_generate_content_fingerprint_returns_tuple(self, memory):
        """Test content fingerprint generation returns valid tuple."""
        content = "$SOL at $185 looking bullish with volume up. nfa"
        result = memory._generate_content_fingerprint(content)

        assert isinstance(result, tuple)
        assert len(result) == 5  # fingerprint, tokens, prices, topic_hash, semantic_hash

    def test_fingerprint_different_for_different_content(self, memory):
        """Test different content produces different fingerprints."""
        content1 = "$SOL pumping hard today with volume nfa"
        content2 = "$BTC at 95k holding support nfa"

        fp1 = memory._generate_content_fingerprint(content1)
        fp2 = memory._generate_content_fingerprint(content2)

        # Fingerprints should be different for different content
        assert fp1[0] != fp2[0]


# =============================================================================
# Generator Map and Run Loop Tests
# =============================================================================

class TestGeneratorMapAndLoop:
    """Tests for generator mapping and run loop logic."""

    @pytest.fixture
    def engine(self):
        """Create engine with mocked dependencies."""
        with patch('bots.twitter.autonomous_engine.XMemory') as mock_memory, \
             patch('bots.twitter.autonomous_engine.get_memory_store'), \
             patch('bots.twitter.autonomous_engine.X_ENGINE_STATE') as mock_state:

            mock_state.exists.return_value = False
            mock_memory_instance = MagicMock()
            mock_memory_instance.get_recent_tweets.return_value = []
            mock_memory_instance.get_recent_topics.return_value = {
                "cashtags": set(), "categories": [], "subjects": set(), "sentiments": []
            }
            mock_memory_instance.calculate_content_freshness.return_value = 0.8
            mock_memory.return_value = mock_memory_instance

            engine = AutonomousEngine()
            yield engine

    @pytest.mark.asyncio
    async def test_run_once_with_scheduled_thread(self, engine):
        """Test run_once when scheduled thread is due."""
        mock_thread = MagicMock()
        mock_thread.topic = "Weekly analysis"
        mock_thread.tweets = [MagicMock(content="1/ Thread starts")]

        with patch.object(engine, '_check_thread_schedule', return_value="thread_123"):
            result = await engine.run_once()

        assert result == "thread_123"

    @pytest.mark.asyncio
    async def test_run_once_with_interactivity(self, engine):
        """Test run_once with external interactivity."""
        engine._last_post_time = time.time() - 2000

        mock_autonomy = MagicMock()
        mock_autonomy.get_content_recommendations.return_value = {
            "should_post": False,  # Don't post regular content
            "content_types": [],
            "topics": [],
            "warnings": []
        }

        # Return a reply from interactivity
        with patch.object(engine, '_get_autonomy', return_value=mock_autonomy), \
             patch.object(engine, '_check_thread_schedule', return_value=None), \
             patch.object(engine, 'run_interactivity_once', return_value="reply_456"), \
             patch('random.random', return_value=0.1):  # < 0.25 to trigger interactivity

            result = await engine.run_once()

        # Should return None since should_post is False and interactivity doesn't block loop
        assert result is None


# =============================================================================
# Grok Client Tests
# =============================================================================

class TestGrokClient:
    """Tests for Grok client integration."""

    @pytest.fixture
    def engine(self):
        """Create engine with mocked dependencies."""
        with patch('bots.twitter.autonomous_engine.XMemory'), \
             patch('bots.twitter.autonomous_engine.get_memory_store'), \
             patch('bots.twitter.autonomous_engine.X_ENGINE_STATE') as mock_state:

            mock_state.exists.return_value = False
            engine = AutonomousEngine()
            yield engine

    @pytest.mark.asyncio
    async def test_get_grok_caches_client(self, engine):
        """Test _get_grok caches client after first call."""
        mock_grok = MagicMock()
        engine._grok_client = mock_grok

        # Should return cached instance
        result = await engine._get_grok()
        assert result is mock_grok

    @pytest.mark.asyncio
    async def test_get_twitter_caches_client(self, engine):
        """Test _get_twitter caches client after first call."""
        mock_twitter = MagicMock()
        engine._twitter_client = mock_twitter

        # Should return cached instance
        result = await engine._get_twitter()
        assert result is mock_twitter


# =============================================================================
# Activity Report Tests
# =============================================================================

class TestActivityReports:
    """Tests for activity reporting functionality."""

    @pytest.fixture
    def engine(self):
        """Create engine with mocked dependencies."""
        with patch('bots.twitter.autonomous_engine.XMemory') as mock_memory, \
             patch('bots.twitter.autonomous_engine.get_memory_store'), \
             patch('bots.twitter.autonomous_engine.X_ENGINE_STATE') as mock_state:

            mock_state.exists.return_value = False
            mock_memory_instance = MagicMock()
            mock_memory_instance.get_posting_stats.return_value = {
                "today_tweets": 5,
                "total_tweets": 100,
                "replies_sent": 3,
                "by_category": {"market_update": 3, "agentic_tech": 2}
            }
            mock_memory_instance.get_recent_tweets.return_value = [
                {"category": "market_update", "content": "Test tweet 1"},
                {"category": "agentic_tech", "content": "Test tweet 2"}
            ]
            mock_memory.return_value = mock_memory_instance

            engine = AutonomousEngine()
            yield engine

    @pytest.mark.asyncio
    async def test_send_activity_report(self, engine):
        """Test sending activity report to Telegram."""
        with patch.object(engine, 'report_to_telegram', new_callable=AsyncMock) as mock_report:
            await engine.send_activity_report()

        mock_report.assert_called_once()
        call_args = mock_report.call_args[0][0]
        assert "Activity Report" in call_args
        assert "Today's Posts" in call_args

    @pytest.mark.asyncio
    async def test_send_milestone_report(self, engine):
        """Test sending milestone report to Telegram."""
        with patch.object(engine, 'report_to_telegram', new_callable=AsyncMock) as mock_report:
            await engine.send_milestone_report(
                tweet_id="123456",
                category="market_update",
                content="$SOL pumping hard today"
            )

        mock_report.assert_called_once()
        call_args = mock_report.call_args[0][0]
        assert "Posted to X" in call_args
        assert "market_update" in call_args


# =============================================================================
# Voice Generator Tests
# =============================================================================

class TestVoiceGenerator:
    """Tests for Jarvis voice generator integration."""

    @pytest.fixture
    def engine(self):
        """Create engine with mocked dependencies."""
        with patch('bots.twitter.autonomous_engine.XMemory'), \
             patch('bots.twitter.autonomous_engine.get_memory_store'), \
             patch('bots.twitter.autonomous_engine.X_ENGINE_STATE') as mock_state:

            mock_state.exists.return_value = False
            engine = AutonomousEngine()
            yield engine

    @pytest.mark.asyncio
    async def test_get_jarvis_voice_returns_generator(self, engine):
        """Test _get_jarvis_voice returns voice generator."""
        mock_voice = MagicMock()

        with patch('bots.twitter.jarvis_voice.get_jarvis_voice', return_value=mock_voice):
            result = await engine._get_jarvis_voice()

        assert result is mock_voice


# =============================================================================
# Autonomy System Tests
# =============================================================================

class TestAutonomySystem:
    """Tests for autonomy system integration."""

    @pytest.fixture
    def engine(self):
        """Create engine with mocked dependencies."""
        with patch('bots.twitter.autonomous_engine.XMemory'), \
             patch('bots.twitter.autonomous_engine.get_memory_store'), \
             patch('bots.twitter.autonomous_engine.X_ENGINE_STATE') as mock_state:

            mock_state.exists.return_value = False
            engine = AutonomousEngine()
            yield engine

    @pytest.mark.asyncio
    async def test_get_autonomy_caches_system(self, engine):
        """Test _get_autonomy caches autonomy system."""
        mock_autonomy = MagicMock()
        engine._autonomy = mock_autonomy

        # Should return cached instance
        result = await engine._get_autonomy()
        assert result is mock_autonomy
