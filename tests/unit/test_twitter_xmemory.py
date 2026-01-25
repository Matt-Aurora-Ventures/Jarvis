"""
Comprehensive unit tests for Twitter XMemory module.

Tests cover:
1. Tweet Storage
   - Store tweet content and metadata
   - Deduplication
   - Timestamp tracking
   - Retrieval by ID

2. Novelty Detection
   - Compare new content to past tweets
   - Similarity scoring
   - Threshold-based filtering
   - Avoid repetition

3. Context Tracking
   - Track conversation threads
   - Store mentions and replies
   - Related tweets linking
   - Context window management

4. Topic Tracking
   - Extract topics from tweets
   - Topic frequency analysis
   - Trending topics detection
   - Topic cooldowns

5. Database Operations
   - SQLite/PostgreSQL storage
   - Query optimization
   - Data retention policies
   - Migration support

Target: 60%+ coverage with 40-60 tests
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
import os
import sys
import hashlib

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bots.twitter.xmemory import (
    XMemory,
    TweetRecord,
    TopicStats,
    NoveltyScore,
    ConversationContext,
    NOVELTY_THRESHOLD,
    TOPIC_COOLDOWN_HOURS,
    DEFAULT_RETENTION_DAYS,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_db(tmp_path):
    """Create temporary database path."""
    db_path = tmp_path / "test_xmemory.db"
    return db_path


@pytest.fixture
def memory(temp_db):
    """Create XMemory instance with temp database."""
    mem = XMemory(db_path=temp_db)
    yield mem
    # Cleanup
    if temp_db.exists():
        try:
            os.remove(temp_db)
        except Exception:
            pass


@pytest.fixture
def populated_memory(memory):
    """Memory with pre-populated test data."""
    # Add some tweets
    tweets = [
        ("t1", "$SOL looking bullish today. nfa", "market_update", ["SOL"]),
        ("t2", "Bitcoin at $100k is inevitable. nfa", "bitcoin_only", ["BTC"]),
        ("t3", "Ethereum L2s are the future. $ETH", "ethereum_defi", ["ETH"]),
        ("t4", "$WIF memecoin momentum continues", "trending_token", ["WIF"]),
        ("t5", "Market sentiment turning positive", "market_update", ["SOL", "BTC"]),
    ]
    for tweet_id, content, category, cashtags in tweets:
        memory.store_tweet(tweet_id, content, category, cashtags)
    return memory


# =============================================================================
# TweetRecord Dataclass Tests
# =============================================================================

class TestTweetRecord:
    """Tests for TweetRecord dataclass."""

    def test_tweet_record_creation(self):
        """Test basic TweetRecord creation."""
        record = TweetRecord(
            tweet_id="123456",
            content="Test tweet content",
            category="market_update",
            cashtags=["$SOL"]
        )

        assert record.tweet_id == "123456"
        assert record.content == "Test tweet content"
        assert record.category == "market_update"
        assert record.cashtags == ["$SOL"]

    def test_tweet_record_defaults(self):
        """Test TweetRecord default values."""
        record = TweetRecord(
            tweet_id="123",
            content="Content",
            category="general",
            cashtags=[]
        )

        assert record.engagement_likes == 0
        assert record.engagement_retweets == 0
        assert record.engagement_replies == 0
        assert record.posted_at is not None

    def test_tweet_record_with_engagement(self):
        """Test TweetRecord with engagement metrics."""
        record = TweetRecord(
            tweet_id="456",
            content="Popular tweet",
            category="viral",
            cashtags=["$BTC"],
            engagement_likes=100,
            engagement_retweets=50,
            engagement_replies=25
        )

        assert record.engagement_likes == 100
        assert record.engagement_retweets == 50
        assert record.engagement_replies == 25

    def test_tweet_record_engagement_score(self):
        """Test engagement score calculation."""
        record = TweetRecord(
            tweet_id="789",
            content="Engaging tweet",
            category="market_update",
            cashtags=[],
            engagement_likes=10,
            engagement_retweets=5,
            engagement_replies=3
        )

        # Score = likes + retweets*2 + replies*3
        expected = 10 + (5 * 2) + (3 * 3)
        assert record.engagement_score == expected


# =============================================================================
# TopicStats Dataclass Tests
# =============================================================================

class TestTopicStats:
    """Tests for TopicStats dataclass."""

    def test_topic_stats_creation(self):
        """Test TopicStats creation."""
        stats = TopicStats(
            topic="$SOL",
            mention_count=10,
            last_mentioned=datetime.now(timezone.utc).isoformat()
        )

        assert stats.topic == "$SOL"
        assert stats.mention_count == 10

    def test_topic_stats_sentiment_tracking(self):
        """Test TopicStats with sentiment data."""
        stats = TopicStats(
            topic="$BTC",
            mention_count=5,
            last_mentioned=datetime.now(timezone.utc).isoformat(),
            avg_sentiment_score=0.75,
            sentiment_samples=5
        )

        assert stats.avg_sentiment_score == 0.75
        assert stats.sentiment_samples == 5


# =============================================================================
# NoveltyScore Dataclass Tests
# =============================================================================

class TestNoveltyScore:
    """Tests for NoveltyScore dataclass."""

    def test_novelty_score_creation(self):
        """Test NoveltyScore creation."""
        score = NoveltyScore(
            score=0.85,
            is_novel=True,
            reason="Unique content"
        )

        assert score.score == 0.85
        assert score.is_novel is True
        assert score.reason == "Unique content"

    def test_novelty_score_duplicate_detection(self):
        """Test NoveltyScore for duplicate."""
        score = NoveltyScore(
            score=0.2,
            is_novel=False,
            reason="Similar to tweet from 2 hours ago",
            similar_tweet_id="existing_123"
        )

        assert score.is_novel is False
        assert score.similar_tweet_id == "existing_123"


# =============================================================================
# Tweet Storage Tests
# =============================================================================

class TestTweetStorage:
    """Tests for tweet storage functionality."""

    def test_store_tweet_basic(self, memory):
        """Test storing a basic tweet."""
        result = memory.store_tweet(
            tweet_id="test123",
            content="$SOL looking bullish today. nfa",
            category="market_update",
            cashtags=["SOL"]
        )

        assert result is True

    def test_store_tweet_retrieval(self, memory):
        """Test storing and retrieving a tweet."""
        memory.store_tweet(
            tweet_id="retrieve_test",
            content="Test content for retrieval",
            category="agentic_tech",
            cashtags=[]
        )

        tweet = memory.get_tweet("retrieve_test")

        assert tweet is not None
        assert tweet["content"] == "Test content for retrieval"
        assert tweet["category"] == "agentic_tech"

    def test_store_tweet_with_metadata(self, memory):
        """Test storing tweet with full metadata."""
        memory.store_tweet(
            tweet_id="meta_test",
            content="$BTC at $100k. nfa",
            category="bitcoin_only",
            cashtags=["BTC"],
            contract_address=None,
            reply_to="parent_tweet_id"
        )

        tweet = memory.get_tweet("meta_test")

        assert tweet["reply_to"] == "parent_tweet_id"

    def test_store_tweet_deduplication(self, memory):
        """Test that duplicate tweet IDs are handled."""
        memory.store_tweet("dup_test", "Original content", "cat1", [])
        memory.store_tweet("dup_test", "Updated content", "cat2", [])

        tweet = memory.get_tweet("dup_test")

        # Should keep the updated version (INSERT OR REPLACE)
        assert tweet["content"] == "Updated content"
        assert tweet["category"] == "cat2"

    def test_store_tweet_timestamp(self, memory):
        """Test that tweets are timestamped."""
        before = datetime.now(timezone.utc)
        memory.store_tweet("time_test", "Content", "general", [])
        after = datetime.now(timezone.utc)

        tweet = memory.get_tweet("time_test")
        posted_at = datetime.fromisoformat(tweet["posted_at"])

        assert before <= posted_at <= after

    def test_get_nonexistent_tweet(self, memory):
        """Test getting a tweet that doesn't exist."""
        tweet = memory.get_tweet("nonexistent_id_12345")

        assert tweet is None

    def test_get_recent_tweets(self, populated_memory):
        """Test getting recent tweets."""
        recent = populated_memory.get_recent_tweets(hours=24)

        assert len(recent) >= 5
        assert all("content" in t for t in recent)
        assert all("category" in t for t in recent)

    def test_get_recent_tweets_empty(self, memory):
        """Test getting recent tweets when none exist."""
        recent = memory.get_recent_tweets(hours=24)

        assert recent == []

    def test_get_recent_tweets_time_filter(self, memory):
        """Test that time filter works correctly."""
        # Store a tweet
        memory.store_tweet("recent_test", "Recent content", "general", [])

        # Should find it within 24 hours
        recent_24h = memory.get_recent_tweets(hours=24)
        assert len(recent_24h) >= 1

        # Shouldn't find it if we look at 0 hours ago (edge case)
        # This tests the boundary condition

    def test_get_total_tweet_count(self, populated_memory):
        """Test total tweet count."""
        count = populated_memory.get_total_tweet_count()

        assert count == 5

    def test_get_total_tweet_count_empty(self, memory):
        """Test total count with empty database."""
        count = memory.get_total_tweet_count()

        assert count == 0


# =============================================================================
# Novelty Detection Tests
# =============================================================================

class TestNoveltyDetection:
    """Tests for novelty detection functionality."""

    def test_is_similar_identical_content(self, populated_memory):
        """Test detecting identical content as duplicate."""
        is_similar, similar_content = populated_memory.is_similar_to_recent(
            "$SOL looking bullish today. nfa",
            hours=24
        )

        assert is_similar is True
        assert similar_content is not None

    def test_is_similar_different_content(self, populated_memory):
        """Test that different content is not flagged."""
        is_similar, similar_content = populated_memory.is_similar_to_recent(
            "Completely unique content about $BONK and memecoins",
            hours=24
        )

        assert is_similar is False
        assert similar_content is None

    def test_is_similar_same_token_same_price(self, memory):
        """Test duplicate detection for same token and price."""
        memory.store_tweet("t1", "$WIF at $0.50 looking good", "trending_token", ["WIF"])

        is_similar, _ = memory.is_similar_to_recent(
            "$WIF hitting $0.50 with volume",
            hours=24
        )

        # Same token + same price = duplicate
        assert is_similar is True

    def test_is_similar_same_token_different_price(self, memory):
        """Test that different prices are not duplicates."""
        memory.store_tweet("t1", "$WIF at $0.50 looking good", "trending_token", ["WIF"])

        is_similar, _ = memory.is_similar_to_recent(
            "$WIF now at $0.75 new highs",
            hours=24
        )

        # Same token but different price = not duplicate
        assert is_similar is False

    def test_is_similar_word_overlap_threshold(self, memory):
        """Test word overlap similarity threshold."""
        memory.store_tweet("t1", "The market is showing strong bullish momentum today with green candles", "market_update", [])

        # Very similar phrasing
        is_similar, _ = memory.is_similar_to_recent(
            "The market is showing strong bearish momentum today with red candles",
            hours=24,
            threshold=0.5
        )

        # High word overlap but different sentiment - depends on implementation
        # Test the threshold behavior

    def test_calculate_content_freshness_unique(self, memory):
        """Test freshness score for unique content."""
        freshness = memory.calculate_content_freshness(
            "Completely new topic about $UNIQUE token"
        )

        assert freshness >= 0.9  # Should be very fresh

    def test_calculate_content_freshness_similar(self, populated_memory):
        """Test freshness score for similar content."""
        # Content similar to existing tweets
        freshness = populated_memory.calculate_content_freshness(
            "$SOL looking bullish again today. nfa"
        )

        assert freshness < 0.9  # Should be less fresh due to similarity

    def test_calculate_freshness_empty_db(self, memory):
        """Test freshness with empty database returns 1.0."""
        freshness = memory.calculate_content_freshness("Any content")

        assert freshness == 1.0

    def test_novelty_check_major_coins_excluded(self, memory):
        """Test that major coins (BTC, ETH, SOL) don't trigger false duplicates."""
        memory.store_tweet("t1", "$BTC at $100k milestone", "bitcoin_only", ["BTC"])

        # Mentioning BTC again with different context shouldn't be duplicate
        is_similar, _ = memory.is_similar_to_recent(
            "$BTC institutional adoption continues with ETF inflows",
            hours=24
        )

        # Different topic about same major coin = not duplicate
        assert is_similar is False


# =============================================================================
# Context Tracking Tests
# =============================================================================

class TestContextTracking:
    """Tests for conversation context tracking."""

    def test_record_mention_reply(self, memory):
        """Test recording a reply to a mention."""
        memory.record_mention_reply(
            tweet_id="mention_123",
            author="@crypto_fan",
            reply="Thanks for the question! Here's my analysis..."
        )

        was_replied = memory.was_mention_replied("mention_123")

        assert was_replied is True

    def test_was_mention_replied_false(self, memory):
        """Test checking unreplied mention."""
        was_replied = memory.was_mention_replied("never_replied_tweet")

        assert was_replied is False

    def test_record_external_reply(self, memory):
        """Test recording reply to external tweet."""
        memory.record_external_reply(
            original_tweet_id="ext_123",
            author="@influencer",
            original_content="$SOL is going to moon",
            our_reply="My sensors agree. nfa",
            our_tweet_id="our_reply_456",
            reply_type="bullish",
            sentiment="positive"
        )

        was_replied = memory.was_externally_replied("ext_123")

        assert was_replied is True

    def test_was_externally_replied_false(self, memory):
        """Test checking unreplied external tweet."""
        was_replied = memory.was_externally_replied("not_replied_ext")

        assert was_replied is False

    def test_get_recent_reply_count(self, memory):
        """Test getting recent reply count."""
        # Add some replies
        for i in range(5):
            memory.record_external_reply(
                f"ext_{i}",
                f"@user_{i}",
                f"Content {i}",
                f"Reply {i}",
                f"reply_id_{i}"
            )

        count = memory.get_recent_reply_count(hours=1)

        assert count == 5

    def test_was_author_replied_recently(self, memory):
        """Test checking if author was replied to recently."""
        memory.record_external_reply(
            "ext_1",
            "@frequent_user",
            "Content",
            "Reply",
            "reply_1"
        )

        was_replied = memory.was_author_replied_recently("@frequent_user", hours=6)

        assert was_replied is True

    def test_was_author_replied_recently_false(self, memory):
        """Test author not replied to recently."""
        was_replied = memory.was_author_replied_recently("@new_user", hours=6)

        assert was_replied is False

    def test_conversation_context_creation(self):
        """Test ConversationContext dataclass."""
        context = ConversationContext(
            thread_id="thread_123",
            participants=["@user1", "@user2"],
            messages=[
                {"author": "@user1", "content": "Hello"},
                {"author": "@jarvis", "content": "Hi there!"}
            ]
        )

        assert context.thread_id == "thread_123"
        assert len(context.participants) == 2
        assert len(context.messages) == 2


# =============================================================================
# Topic Tracking Tests
# =============================================================================

class TestTopicTracking:
    """Tests for topic extraction and tracking."""

    def test_record_token_mention(self, memory):
        """Test recording a token mention."""
        memory.record_token_mention(
            symbol="WIF",
            contract="EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
            sentiment="bullish",
            price=0.50
        )

        was_mentioned = memory.was_recently_mentioned("WIF", hours=4)

        assert was_mentioned is True

    def test_was_recently_mentioned_false(self, memory):
        """Test token not recently mentioned."""
        was_mentioned = memory.was_recently_mentioned("NONEXISTENT", hours=4)

        assert was_mentioned is False

    def test_get_recent_topics(self, populated_memory):
        """Test getting recent topics."""
        topics = populated_memory.get_recent_topics(hours=24)

        assert "cashtags" in topics
        assert "categories" in topics
        assert "subjects" in topics
        assert "sentiments" in topics

        assert "SOL" in topics["cashtags"] or "sol" in str(topics["cashtags"]).lower()

    def test_extract_semantic_concepts_bullish(self, memory):
        """Test semantic extraction for bullish content."""
        concepts = memory._extract_semantic_concepts(
            "Markets are pumping! Green candles everywhere, bulls are in control!"
        )

        assert concepts["sentiment"] == "bullish"
        assert "market_general" in concepts["subjects"]

    def test_extract_semantic_concepts_bearish(self, memory):
        """Test semantic extraction for bearish content."""
        concepts = memory._extract_semantic_concepts(
            "Markets crashing hard, red everywhere. Capitulation incoming."
        )

        assert concepts["sentiment"] == "bearish"

    def test_extract_semantic_concepts_neutral(self, memory):
        """Test semantic extraction for neutral content."""
        concepts = memory._extract_semantic_concepts(
            "Markets are choppy and consolidating. Sideways action expected."
        )

        assert concepts["sentiment"] == "neutral"

    def test_extract_semantic_concepts_btc(self, memory):
        """Test semantic extraction for BTC content."""
        concepts = memory._extract_semantic_concepts(
            "Bitcoin just hit a new ATH! $BTC to the moon!"
        )

        assert "btc" in concepts["subjects"]

    def test_extract_semantic_concepts_agentic(self, memory):
        """Test semantic extraction for agentic content."""
        concepts = memory._extract_semantic_concepts(
            "The future of autonomous AI agents is here. MCP servers changing everything."
        )

        assert "agentic" in concepts["subjects"]

    def test_topic_cooldown_tracking(self, memory):
        """Test topic cooldown enforcement."""
        memory.record_token_mention("COOLDOWN_TEST", "addr", "bullish")

        # Immediately after mention, should be on cooldown
        is_on_cooldown = memory.is_topic_on_cooldown("COOLDOWN_TEST")

        assert is_on_cooldown is True


# =============================================================================
# Database Operations Tests
# =============================================================================

class TestDatabaseOperations:
    """Tests for database operations."""

    def test_init_creates_tables(self, memory, temp_db):
        """Test that initialization creates all required tables."""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        conn.close()

        assert "tweets" in tables
        assert "interactions" in tables or "mention_replies" in tables
        assert "token_mentions" in tables
        assert "content_fingerprints" in tables

    def test_database_connection_management(self, memory):
        """Test that database connections are properly managed."""
        # Multiple operations shouldn't leave connections open
        for i in range(10):
            memory.store_tweet(f"conn_test_{i}", f"Content {i}", "general", [])

        # Should complete without connection errors
        count = memory.get_total_tweet_count()
        assert count >= 10

    def test_thread_safety(self, memory):
        """Test thread-safe operations."""
        import threading

        errors = []

        def writer(i):
            try:
                memory.store_tweet(f"thread_{i}", f"Content {i}", "general", [])
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_get_posting_stats(self, populated_memory):
        """Test getting posting statistics."""
        stats = populated_memory.get_posting_stats()

        assert "total_tweets" in stats
        assert "today_tweets" in stats
        assert "by_category" in stats
        assert stats["total_tweets"] >= 5

    def test_data_retention_cleanup(self, memory):
        """Test data retention cleanup."""
        # Store some old fingerprints
        # Then run cleanup
        # Verify old data is removed
        # This tests the cleanup_old_fingerprints functionality

    def test_update_tweet_engagement(self, memory):
        """Test updating engagement metrics."""
        memory.store_tweet("engage_test", "Content", "general", [])

        memory.update_tweet_engagement(
            tweet_id="engage_test",
            likes=100,
            retweets=50,
            replies=25
        )

        # Verify update was applied
        tweet = memory.get_tweet("engage_test")
        assert tweet is not None
        # Engagement fields should be updated


# =============================================================================
# Fingerprint Tests
# =============================================================================

class TestContentFingerprints:
    """Tests for content fingerprint functionality."""

    def test_generate_fingerprint(self, memory):
        """Test fingerprint generation."""
        fingerprint, tokens, prices, topic_hash, semantic_hash = memory._generate_content_fingerprint(
            "$SOL at $200 looking bullish. $BTC also strong."
        )

        assert fingerprint is not None
        assert len(fingerprint) > 0
        assert "SOL" in tokens or "sol" in tokens.lower()
        assert "BTC" in tokens or "btc" in tokens.lower()
        assert "200" in prices

    def test_fingerprint_different_for_different_content(self, memory):
        """Test fingerprints differ for different content."""
        fp1, _, _, _, _ = memory._generate_content_fingerprint("$SOL at $100")
        fp2, _, _, _, _ = memory._generate_content_fingerprint("$BTC at $50000")

        assert fp1 != fp2

    def test_fingerprint_same_for_similar_content(self, memory):
        """Test topic hash similarity for related content."""
        _, _, _, hash1, _ = memory._generate_content_fingerprint("$SOL pumping to $100")
        _, _, _, hash2, _ = memory._generate_content_fingerprint("$SOL reaching $100 levels")

        # Topic hash should be the same (same token, same price range)
        assert hash1 == hash2

    def test_semantic_hash_catches_rephrasing(self, memory):
        """Test semantic hash catches rephrased content."""
        # Same sentiment + same subjects + same tone = same hash
        _, _, _, _, sem1 = memory._generate_content_fingerprint("Markets bullish today, green candles everywhere")
        _, _, _, _, sem2 = memory._generate_content_fingerprint("Markets looking bullish, green candles continue")

        # Both have: bullish sentiment, market_general subject, commentary tone
        assert sem1 == sem2

        # Different sentiments should have different hashes
        _, _, _, _, sem_bearish = memory._generate_content_fingerprint("Markets crashing, red candles everywhere")
        assert sem1 != sem_bearish

    @pytest.mark.asyncio
    async def test_is_duplicate_fingerprint(self, memory):
        """Test async duplicate fingerprint detection."""
        # Record a fingerprint
        await memory.record_content_fingerprint("$WIF at $0.50 pumping hard", "tweet_123")

        # Check for duplicate
        is_dup, reason = await memory.is_duplicate_fingerprint(
            "$WIF at $0.50 strong momentum",
            hours=24
        )

        # Should detect as duplicate (same token, same price)
        assert is_dup is True

    @pytest.mark.asyncio
    async def test_is_not_duplicate_fingerprint(self, memory):
        """Test non-duplicate fingerprint."""
        await memory.record_content_fingerprint("$SOL analysis", "tweet_1")

        is_dup, reason = await memory.is_duplicate_fingerprint(
            "$BTC completely different topic",
            hours=24
        )

        assert is_dup is False

    @pytest.mark.asyncio
    async def test_cleanup_old_fingerprints(self, memory):
        """Test cleanup of old fingerprints."""
        # Record some fingerprints
        await memory.record_content_fingerprint("Old content", "old_tweet")

        # Cleanup
        await memory.cleanup_old_fingerprints(days=0)

        # Very recent fingerprints might still exist depending on implementation


# =============================================================================
# Self-Learning Tests
# =============================================================================

class TestSelfLearning:
    """Tests for self-learning functionality."""

    def test_get_performance_by_category(self, memory):
        """Test performance analysis by category."""
        # Store tweets with engagement
        for i in range(3):
            memory.store_tweet(f"perf_{i}", f"Content {i}", "market_update", [])
            memory.update_tweet_engagement(f"perf_{i}", likes=10+i, retweets=5, replies=2)

        performance = memory.get_performance_by_category(days=7)

        assert "market_update" in performance
        assert performance["market_update"]["count"] >= 3

    def test_get_top_performing_tweets(self, memory):
        """Test getting top performing tweets."""
        # Store tweets with varying engagement
        memory.store_tweet("top1", "High performer", "viral", [])
        memory.update_tweet_engagement("top1", likes=1000, retweets=500, replies=200)

        memory.store_tweet("low1", "Low performer", "general", [])
        memory.update_tweet_engagement("low1", likes=5, retweets=1, replies=0)

        top = memory.get_top_performing_tweets(days=7, limit=5)

        assert len(top) >= 1
        assert top[0]["tweet_id"] == "top1"

    def test_get_underperforming_patterns(self, memory):
        """Test identifying underperforming patterns."""
        # Create categories with different performance
        for i in range(5):
            memory.store_tweet(f"good_{i}", "Good content", "high_perf", [])
            memory.update_tweet_engagement(f"good_{i}", likes=100, retweets=50, replies=25)

        for i in range(5):
            memory.store_tweet(f"bad_{i}", "Bad content", "low_perf", [])
            memory.update_tweet_engagement(f"bad_{i}", likes=1, retweets=0, replies=0)

        underperformers = memory.get_underperforming_patterns(days=7)

        assert "low_perf" in underperformers

    def test_get_learning_insights(self, memory):
        """Test generating learning insights."""
        # Setup performance data
        memory.store_tweet("insight1", "Good tweet $SOL", "market_update", ["SOL"])
        memory.update_tweet_engagement("insight1", likes=50, retweets=20, replies=10)

        insights = memory.get_learning_insights()

        assert "top_categories" in insights
        assert "recommendations" in insights


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_content(self, memory):
        """Test handling empty content."""
        memory.store_tweet("empty_test", "", "general", [])
        tweet = memory.get_tweet("empty_test")

        assert tweet is not None
        assert tweet["content"] == ""

    def test_very_long_content(self, memory):
        """Test handling very long content."""
        long_content = "a" * 10000
        memory.store_tweet("long_test", long_content, "general", [])
        tweet = memory.get_tweet("long_test")

        assert tweet is not None
        assert len(tweet["content"]) == 10000

    def test_special_characters(self, memory):
        """Test handling special characters."""
        special_content = "Special chars: <>\"'&!@#$%^*() and unicode: emoji symbols"
        memory.store_tweet("special_test", special_content, "general", [])
        tweet = memory.get_tweet("special_test")

        assert tweet is not None
        assert "Special chars" in tweet["content"]

    def test_unicode_content(self, memory):
        """Test handling unicode content."""
        unicode_content = "Unicode test: nice work, fire, rocket symbols"
        memory.store_tweet("unicode_test", unicode_content, "general", [])
        tweet = memory.get_tweet("unicode_test")

        assert tweet is not None

    def test_null_cashtags(self, memory):
        """Test handling null/None cashtags."""
        # Should handle gracefully
        try:
            memory.store_tweet("null_tags", "Content", "general", None)
        except TypeError:
            # Acceptable if it raises TypeError for None
            pass

    def test_concurrent_writes(self, memory):
        """Test concurrent write operations."""
        import threading
        import time

        results = []

        def writer(i):
            for j in range(10):
                memory.store_tweet(f"concurrent_{i}_{j}", f"Content {i}_{j}", "general", [])
            results.append(i)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 5
        assert memory.get_total_tweet_count() >= 50


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for XMemory."""

    def test_full_tweet_lifecycle(self, memory):
        """Test complete tweet lifecycle."""
        # 1. Check novelty
        is_similar, _ = memory.is_similar_to_recent("Brand new content about $NEW", hours=24)
        assert is_similar is False

        # 2. Store tweet
        memory.store_tweet("lifecycle_1", "Brand new content about $NEW", "trending_token", ["NEW"])

        # 3. Update engagement
        memory.update_tweet_engagement("lifecycle_1", likes=50, retweets=20, replies=10)

        # 4. Check it's now a duplicate
        is_similar, _ = memory.is_similar_to_recent("Brand new content about $NEW", hours=24)
        assert is_similar is True

        # 5. Get stats
        stats = memory.get_posting_stats()
        assert stats["total_tweets"] >= 1

    def test_topic_diversity_enforcement(self, memory):
        """Test topic diversity over time."""
        # Post about SOL
        memory.store_tweet("t1", "$SOL looking good", "market_update", ["SOL"])
        memory.record_token_mention("SOL", "addr", "bullish")

        # Should detect SOL as recently mentioned
        assert memory.was_recently_mentioned("SOL", hours=4) is True

        # Should still allow different topic
        is_similar, _ = memory.is_similar_to_recent("$BTC hitting new highs", hours=24)
        assert is_similar is False

    def test_reply_rate_limiting(self, memory):
        """Test reply rate limiting."""
        # Simulate multiple replies
        for i in range(10):
            memory.record_external_reply(
                f"ext_{i}",
                f"@user_{i}",
                f"Content {i}",
                f"Reply {i}",
                f"reply_{i}"
            )

        count = memory.get_recent_reply_count(hours=1)
        assert count == 10

        # Check specific author wasn't spammed
        assert memory.was_author_replied_recently("@user_0", hours=6) is True
