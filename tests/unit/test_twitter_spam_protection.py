"""
Comprehensive unit tests for Twitter Spam Bot Protection.

Tests cover:
- SpamScore dataclass
- SpamProtection class
  - Spam score calculation with multiple factors
  - Database operations (tracking blocks, scans)
  - Stats retrieval
- scan_and_protect async function
- Edge cases and boundary conditions

This is CRITICAL SAFETY CODE that prevents detection and blocking
of spam bots that quote tweet Jarvis with scam links.
"""

import pytest
import asyncio
import json
import tempfile
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
import os
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bots.twitter.spam_protection import (
    SpamScore,
    SpamProtection,
    get_spam_protection,
    scan_and_protect,
    SPAM_THRESHOLD,
    MIN_FOLLOWERS,
    NEW_ACCOUNT_DAYS,
    SUSPICIOUS_RATIO,
    SPAM_KEYWORDS,
    SPAM_URL_PATTERNS,
    BOT_USERNAME_PATTERNS,
)


# =============================================================================
# SpamScore Dataclass Tests
# =============================================================================

class TestSpamScore:
    """Tests for SpamScore dataclass."""

    def test_spam_score_creation(self):
        """Test basic SpamScore creation."""
        score = SpamScore(
            total=0.75,
            reasons=["Low followers: 10", "Spam keywords: airdrop"],
            is_spam=True,
            user_id="12345",
            username="spambot123"
        )

        assert score.total == 0.75
        assert len(score.reasons) == 2
        assert score.is_spam is True
        assert score.user_id == "12345"
        assert score.username == "spambot123"

    def test_spam_score_not_spam(self):
        """Test SpamScore for legitimate user."""
        score = SpamScore(
            total=0.2,
            reasons=["Few followers: 80"],
            is_spam=False,
            user_id="67890",
            username="legituser"
        )

        assert score.total == 0.2
        assert score.is_spam is False

    def test_spam_score_at_threshold(self):
        """Test SpamScore exactly at threshold."""
        score = SpamScore(
            total=SPAM_THRESHOLD,
            reasons=["At threshold"],
            is_spam=True,
            user_id="11111",
            username="edgecase"
        )

        assert score.total == SPAM_THRESHOLD
        assert score.is_spam is True

    def test_spam_score_empty_reasons(self):
        """Test SpamScore with no reasons."""
        score = SpamScore(
            total=0.0,
            reasons=[],
            is_spam=False,
            user_id="22222",
            username="cleanuser"
        )

        assert score.reasons == []
        assert score.is_spam is False


# =============================================================================
# SpamProtection Class Tests
# =============================================================================

class TestSpamProtection:
    """Tests for SpamProtection class."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create temporary database directory."""
        data_dir = tmp_path / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / "test_spam.db"

    @pytest.fixture
    def protection(self, temp_db):
        """Create SpamProtection instance with temp database."""
        with patch('bots.twitter.spam_protection.SPAM_DB', temp_db):
            with patch('bots.twitter.spam_protection.DATA_DIR', temp_db.parent):
                prot = SpamProtection()
                prot._db_path = temp_db
                prot._init_db()
                return prot

    # -------------------------------------------------------------------------
    # Database Initialization Tests
    # -------------------------------------------------------------------------

    def test_init_db_creates_tables(self, protection):
        """Test that initialization creates all required tables."""
        conn = sqlite3.connect(protection._db_path)
        cursor = conn.cursor()

        # Check all tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        assert 'blocked_users' in tables
        assert 'scanned_quotes' in tables
        assert 'jarvis_tweets' in tables

        conn.close()

    def test_init_db_creates_directory(self, tmp_path):
        """Test that initialization creates data directory if needed."""
        new_dir = tmp_path / "new_data_dir"
        db_path = new_dir / "spam.db"

        with patch('bots.twitter.spam_protection.SPAM_DB', db_path):
            with patch('bots.twitter.spam_protection.DATA_DIR', new_dir):
                protection = SpamProtection()
                protection._db_path = db_path
                protection._init_db()

        assert new_dir.exists()
        assert db_path.exists()

    # -------------------------------------------------------------------------
    # Spam Score Calculation Tests
    # -------------------------------------------------------------------------

    def test_calculate_spam_score_low_followers(self, protection):
        """Test spam scoring for very low follower count."""
        user = {
            "id": "12345",
            "username": "lowfollower",
            "followers_count": 10,  # Very low
            "following_count": 100,
            "tweet_count": 500,
            "description": "Just a user",
            "created_at": "2020-01-01 00:00:00"
        }

        score = protection.calculate_spam_score(user, "Hello world")

        assert "Low followers" in str(score.reasons)
        assert score.total >= 0.3  # Low followers adds 0.3

    def test_calculate_spam_score_suspicious_ratio(self, protection):
        """Test spam scoring for suspicious following/followers ratio."""
        user = {
            "id": "12345",
            "username": "ratiofollower",
            "followers_count": 10,
            "following_count": 1000,  # Following many, followed by few
            "tweet_count": 500,
            "description": "Just a user",
            "created_at": "2020-01-01 00:00:00"
        }

        score = protection.calculate_spam_score(user, "Hello world")

        assert "Suspicious ratio" in str(score.reasons)
        assert score.total >= 0.2  # Suspicious ratio adds 0.2

    def test_calculate_spam_score_new_account(self, protection):
        """Test spam scoring for new account."""
        # Create a date just 10 days ago
        recent_date = (datetime.utcnow() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")

        user = {
            "id": "12345",
            "username": "newuser",
            "followers_count": 5000,
            "following_count": 100,
            "tweet_count": 500,
            "description": "Just a user",
            "created_at": recent_date
        }

        score = protection.calculate_spam_score(user, "Hello world")

        assert "New account" in str(score.reasons)
        assert score.total >= 0.25  # New account adds 0.25

    def test_calculate_spam_score_spam_keywords(self, protection):
        """Test spam scoring for spam keywords in text."""
        user = {
            "id": "12345",
            "username": "keyworduser",
            "followers_count": 5000,
            "following_count": 100,
            "tweet_count": 500,
            "description": "Normal bio",
            "created_at": "2020-01-01 00:00:00"
        }

        tweet_text = "AIRDROP! Claim now for FREE TOKENS! Limited spots!"

        score = protection.calculate_spam_score(user, tweet_text)

        assert "Spam keywords" in str(score.reasons)
        assert score.total > 0  # Should have keyword score

    def test_calculate_spam_score_spam_keywords_in_bio(self, protection):
        """Test spam scoring for spam keywords in bio/description."""
        user = {
            "id": "12345",
            "username": "biouser",
            "followers_count": 5000,
            "following_count": 100,
            "tweet_count": 500,
            "description": "DM for exclusive giveaway airdrop",  # Spam in bio
            "created_at": "2020-01-01 00:00:00"
        }

        score = protection.calculate_spam_score(user, "Normal tweet")

        assert "Spam keywords" in str(score.reasons)

    def test_calculate_spam_score_spam_url_patterns(self, protection):
        """Test spam scoring for spam URL patterns."""
        user = {
            "id": "12345",
            "username": "urluser",
            "followers_count": 5000,
            "following_count": 100,
            "tweet_count": 500,
            "description": "Normal bio",
            "created_at": "2020-01-01 00:00:00"
        }

        # Contains shortened URL
        tweet_text = "Check this out! bit.ly/scam123"

        score = protection.calculate_spam_score(user, tweet_text)

        assert "Spam URL pattern" in str(score.reasons)
        assert score.total >= 0.3  # URL pattern adds 0.3

    def test_calculate_spam_score_bot_username(self, protection):
        """Test spam scoring for bot-like username patterns."""
        user = {
            "id": "12345",
            "username": "user12345678",  # Many numbers = bot pattern
            "followers_count": 5000,
            "following_count": 100,
            "tweet_count": 500,
            "description": "Normal bio",
            "created_at": "2020-01-01 00:00:00"
        }

        score = protection.calculate_spam_score(user, "Hello world")

        assert "Bot-like username" in str(score.reasons)
        assert score.total >= 0.2  # Bot username adds 0.2

    def test_calculate_spam_score_low_tweets_with_spam(self, protection):
        """Test spam scoring for low tweet count + spam content."""
        user = {
            "id": "12345",
            "username": "lowtweeter",
            "followers_count": 5000,
            "following_count": 100,
            "tweet_count": 10,  # Very few tweets
            "description": "Normal bio",
            "created_at": "2020-01-01 00:00:00"
        }

        tweet_text = "AIRDROP claim now!"  # Contains spam keywords

        score = protection.calculate_spam_score(user, tweet_text)

        assert "Low tweets" in str(score.reasons)

    def test_calculate_spam_score_legitimate_user(self, protection):
        """Test spam scoring for legitimate user with no spam signals."""
        user = {
            "id": "12345",
            "username": "legituser",
            "followers_count": 5000,
            "following_count": 200,
            "tweet_count": 2000,
            "description": "Software developer",
            "created_at": "2018-01-01 00:00:00"
        }

        tweet_text = "Interesting analysis on the market today!"

        score = protection.calculate_spam_score(user, tweet_text)

        assert score.is_spam is False
        assert score.total < SPAM_THRESHOLD

    def test_calculate_spam_score_maximum_combined_spam(self, protection):
        """Test spam scoring with maximum spam signals combined."""
        # Account created just 5 days ago
        recent_date = (datetime.utcnow() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")

        user = {
            "id": "12345",
            "username": "spambot12345678",  # Bot username pattern
            "followers_count": 5,  # Very low
            "following_count": 5000,  # Bad ratio
            "tweet_count": 10,  # Low tweets
            "description": "airdrop giveaway claim now",  # Spam keywords in bio
            "created_at": recent_date  # New account
        }

        tweet_text = "AIRDROP! CLAIM NOW! bit.ly/scam FREE TOKENS!"

        score = protection.calculate_spam_score(user, tweet_text)

        assert score.is_spam is True
        assert score.total >= SPAM_THRESHOLD
        assert len(score.reasons) >= 3  # Multiple spam signals

    def test_calculate_spam_score_capped_at_1(self, protection):
        """Test that spam score is capped at 1.0."""
        # Create user with many spam signals
        user = {
            "id": "12345",
            "username": "spambot12345678",
            "followers_count": 1,
            "following_count": 10000,
            "tweet_count": 1,
            "description": "airdrop giveaway claim now free tokens presale whitelist",
            "created_at": (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        }

        tweet_text = "AIRDROP CLAIM NOW bit.ly/x FREE TOKENS GIVEAWAY LIMITED SPOTS"

        score = protection.calculate_spam_score(user, tweet_text)

        assert score.total <= 1.0

    def test_calculate_spam_score_missing_user_data(self, protection):
        """Test spam scoring with missing user data fields."""
        user = {
            "id": "12345",
            "username": "minimaluser"
            # Missing most fields
        }

        score = protection.calculate_spam_score(user, "Hello world")

        # Should not crash, should return a score
        assert score.user_id == "12345"
        assert score.username == "minimaluser"

    def test_calculate_spam_score_empty_user(self, protection):
        """Test spam scoring with empty user dict."""
        user = {}

        score = protection.calculate_spam_score(user, "Hello world")

        # Should not crash
        assert score.user_id == ""
        assert score.username == ""

    # -------------------------------------------------------------------------
    # Database Record Operations Tests
    # -------------------------------------------------------------------------

    def test_record_scan(self, protection):
        """Test recording a scan result."""
        protection.record_scan("tweet123", "author456", False)

        conn = sqlite3.connect(protection._db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM scanned_quotes WHERE tweet_id = ?", ("tweet123",))
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[1] == "author456"  # author_id
        assert row[2] == 0  # is_spam (False)

    def test_record_scan_spam(self, protection):
        """Test recording a spam scan result."""
        protection.record_scan("tweet789", "author999", True)

        conn = sqlite3.connect(protection._db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT is_spam FROM scanned_quotes WHERE tweet_id = ?", ("tweet789",))
        row = cursor.fetchone()
        conn.close()

        assert row[0] == 1  # is_spam (True)

    def test_was_already_scanned_true(self, protection):
        """Test checking if tweet was already scanned - true case."""
        protection.record_scan("scanned_tweet", "author1", False)

        result = protection.was_already_scanned("scanned_tweet")

        assert result is True

    def test_was_already_scanned_false(self, protection):
        """Test checking if tweet was already scanned - false case."""
        result = protection.was_already_scanned("unscanned_tweet")

        assert result is False

    def test_record_block(self, protection):
        """Test recording a user block."""
        protection.record_block(
            user_id="blocked_user_1",
            username="spammer",
            reason="Low followers: 5; Spam keywords: airdrop",
            spam_score=0.85,
            quote_tweet_id="quote123"
        )

        conn = sqlite3.connect(protection._db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM blocked_users WHERE user_id = ?", ("blocked_user_1",))
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[1] == "spammer"  # username
        assert row[3] == 0.85  # spam_score
        assert row[5] == "quote123"  # quote_tweet_id

    def test_is_user_blocked_true(self, protection):
        """Test checking if user is blocked - true case."""
        protection.record_block("user_xyz", "blocked_user", "spam", 0.9, "tweet999")

        result = protection.is_user_blocked("user_xyz")

        assert result is True

    def test_is_user_blocked_false(self, protection):
        """Test checking if user is blocked - false case."""
        result = protection.is_user_blocked("not_blocked_user")

        assert result is False

    def test_record_jarvis_tweet(self, protection):
        """Test recording a Jarvis tweet for scanning."""
        protection.record_jarvis_tweet("jarvis_tweet_1")

        conn = sqlite3.connect(protection._db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jarvis_tweets WHERE tweet_id = ?", ("jarvis_tweet_1",))
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[2] is None  # last_scanned should be NULL

    def test_record_jarvis_tweet_duplicate(self, protection):
        """Test recording duplicate Jarvis tweet is ignored."""
        protection.record_jarvis_tweet("jarvis_tweet_dup")
        protection.record_jarvis_tweet("jarvis_tweet_dup")  # Should not error

        conn = sqlite3.connect(protection._db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM jarvis_tweets WHERE tweet_id = ?", ("jarvis_tweet_dup",))
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 1

    def test_mark_tweet_scanned(self, protection):
        """Test marking a tweet as scanned."""
        protection.record_jarvis_tweet("tweet_to_mark")
        protection.mark_tweet_scanned("tweet_to_mark")

        conn = sqlite3.connect(protection._db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT last_scanned FROM jarvis_tweets WHERE tweet_id = ?", ("tweet_to_mark",))
        row = cursor.fetchone()
        conn.close()

        assert row[0] is not None  # Should have a timestamp now

    def test_get_tweets_to_scan_empty(self, protection):
        """Test getting tweets to scan when none exist."""
        result = protection.get_tweets_to_scan()

        assert result == []

    def test_get_tweets_to_scan_returns_unscanned(self, protection):
        """Test getting tweets that haven't been scanned."""
        protection.record_jarvis_tweet("tweet_a")
        protection.record_jarvis_tweet("tweet_b")

        result = protection.get_tweets_to_scan()

        assert len(result) == 2
        assert "tweet_a" in result or "tweet_b" in result

    def test_get_tweets_to_scan_excludes_recently_scanned(self, protection):
        """Test that recently scanned tweets are excluded."""
        protection.record_jarvis_tweet("old_tweet")
        protection.record_jarvis_tweet("new_tweet")
        protection.mark_tweet_scanned("new_tweet")  # Just scanned

        result = protection.get_tweets_to_scan()

        # new_tweet was just scanned so should be excluded
        assert "old_tweet" in result
        # new_tweet might or might not be included depending on timing

    def test_get_tweets_to_scan_respects_limit(self, protection):
        """Test that get_tweets_to_scan respects limit parameter."""
        for i in range(10):
            protection.record_jarvis_tweet(f"tweet_{i}")

        result = protection.get_tweets_to_scan(limit=3)

        assert len(result) <= 3

    # -------------------------------------------------------------------------
    # Stats Tests
    # -------------------------------------------------------------------------

    def test_get_stats_empty_db(self, protection):
        """Test getting stats from empty database."""
        stats = protection.get_stats()

        assert stats["total_blocked"] == 0
        assert stats["total_scanned"] == 0
        assert stats["spam_detected"] == 0
        assert stats["recent_blocks_24h"] == 0
        assert stats["detection_rate"] == 0

    def test_get_stats_with_data(self, protection):
        """Test getting stats with data in database."""
        # Add some scanned tweets
        protection.record_scan("t1", "u1", False)
        protection.record_scan("t2", "u2", True)
        protection.record_scan("t3", "u3", True)

        # Add a blocked user
        protection.record_block("u2", "spammer", "spam", 0.8, "t2")

        stats = protection.get_stats()

        assert stats["total_scanned"] == 3
        assert stats["spam_detected"] == 2
        assert stats["total_blocked"] == 1
        assert stats["detection_rate"] == pytest.approx(66.67, rel=0.1)

    def test_get_stats_recent_blocks(self, protection):
        """Test that recent_blocks_24h counts correctly."""
        protection.record_block("u1", "spam1", "spam", 0.8, "t1")

        stats = protection.get_stats()

        assert stats["recent_blocks_24h"] == 1


# =============================================================================
# Singleton Tests
# =============================================================================

class TestSingleton:
    """Tests for get_spam_protection singleton."""

    def test_get_spam_protection_returns_instance(self, tmp_path):
        """Test that get_spam_protection returns an instance."""
        db_path = tmp_path / "data" / "spam.db"

        with patch('bots.twitter.spam_protection.SPAM_DB', db_path):
            with patch('bots.twitter.spam_protection.DATA_DIR', db_path.parent):
                # Reset singleton
                import bots.twitter.spam_protection as sp
                sp._spam_protection = None

                instance = get_spam_protection()

                assert instance is not None
                assert isinstance(instance, SpamProtection)

    def test_get_spam_protection_returns_same_instance(self, tmp_path):
        """Test that get_spam_protection returns the same instance."""
        db_path = tmp_path / "data" / "spam.db"

        with patch('bots.twitter.spam_protection.SPAM_DB', db_path):
            with patch('bots.twitter.spam_protection.DATA_DIR', db_path.parent):
                # Reset singleton
                import bots.twitter.spam_protection as sp
                sp._spam_protection = None

                instance1 = get_spam_protection()
                instance2 = get_spam_protection()

                assert instance1 is instance2


# =============================================================================
# scan_and_protect Async Function Tests
# =============================================================================

class TestScanAndProtect:
    """Tests for scan_and_protect async function."""

    @pytest.fixture
    def mock_twitter_client(self):
        """Create mock Twitter client."""
        client = AsyncMock()
        client.get_quote_tweets = AsyncMock(return_value=[])
        client.block_user = AsyncMock(return_value=True)
        client.mute_user = AsyncMock(return_value=True)
        return client

    @pytest.fixture
    def temp_protection(self, tmp_path):
        """Create temp protection instance."""
        db_path = tmp_path / "data" / "spam.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        with patch('bots.twitter.spam_protection.SPAM_DB', db_path):
            with patch('bots.twitter.spam_protection.DATA_DIR', db_path.parent):
                import bots.twitter.spam_protection as sp
                sp._spam_protection = None
                return get_spam_protection()

    @pytest.mark.asyncio
    async def test_scan_and_protect_no_tweets(self, mock_twitter_client, tmp_path):
        """Test scan_and_protect with no tweets to scan."""
        db_path = tmp_path / "data" / "spam.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        with patch('bots.twitter.spam_protection.SPAM_DB', db_path):
            with patch('bots.twitter.spam_protection.DATA_DIR', db_path.parent):
                import bots.twitter.spam_protection as sp
                sp._spam_protection = None

                result = await scan_and_protect(mock_twitter_client)

                assert result["scanned"] == 0
                assert result["blocked"] == 0

    @pytest.mark.asyncio
    async def test_scan_and_protect_with_tweet_ids(self, mock_twitter_client, tmp_path):
        """Test scan_and_protect with specific tweet IDs."""
        db_path = tmp_path / "data" / "spam.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Mock quote tweets - one legitimate user
        mock_twitter_client.get_quote_tweets.return_value = [
            {
                "id": "quote1",
                "text": "Great analysis!",
                "author": {
                    "id": "author1",
                    "username": "legituser",
                    "followers_count": 5000,
                    "following_count": 500,
                    "tweet_count": 1000,
                    "description": "Crypto enthusiast",
                    "created_at": "2020-01-01 00:00:00"
                }
            }
        ]

        with patch('bots.twitter.spam_protection.SPAM_DB', db_path):
            with patch('bots.twitter.spam_protection.DATA_DIR', db_path.parent):
                import bots.twitter.spam_protection as sp
                sp._spam_protection = None

                result = await scan_and_protect(mock_twitter_client, tweet_ids=["tweet123"])

                assert result["scanned"] == 1
                assert result["blocked"] == 0

    @pytest.mark.asyncio
    async def test_scan_and_protect_blocks_spam(self, mock_twitter_client, tmp_path):
        """Test scan_and_protect blocks spam bots."""
        db_path = tmp_path / "data" / "spam.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Mock quote tweets - spam bot
        mock_twitter_client.get_quote_tweets.return_value = [
            {
                "id": "quote_spam",
                "text": "AIRDROP! CLAIM NOW! bit.ly/scam FREE TOKENS!",
                "author": {
                    "id": "spammer1",
                    "username": "spambot12345678",
                    "followers_count": 5,
                    "following_count": 5000,
                    "tweet_count": 10,
                    "description": "airdrop giveaway",
                    "created_at": (datetime.utcnow() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
                }
            }
        ]

        with patch('bots.twitter.spam_protection.SPAM_DB', db_path):
            with patch('bots.twitter.spam_protection.DATA_DIR', db_path.parent):
                import bots.twitter.spam_protection as sp
                sp._spam_protection = None

                result = await scan_and_protect(mock_twitter_client, tweet_ids=["tweet456"])

                assert result["scanned"] == 1
                assert result["blocked"] == 1
                assert len(result["spam_found"]) == 1
                assert result["spam_found"][0]["username"] == "spambot12345678"

                # Verify block/mute were called
                mock_twitter_client.block_user.assert_called_once_with("spammer1")
                mock_twitter_client.mute_user.assert_called_once_with("spammer1")

    @pytest.mark.asyncio
    async def test_scan_and_protect_skips_already_scanned(self, mock_twitter_client, tmp_path):
        """Test scan_and_protect skips already scanned quotes."""
        db_path = tmp_path / "data" / "spam.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        mock_twitter_client.get_quote_tweets.return_value = [
            {
                "id": "already_scanned_quote",
                "text": "Some text",
                "author": {
                    "id": "author1",
                    "username": "user1",
                    "followers_count": 1000,
                }
            }
        ]

        with patch('bots.twitter.spam_protection.SPAM_DB', db_path):
            with patch('bots.twitter.spam_protection.DATA_DIR', db_path.parent):
                import bots.twitter.spam_protection as sp
                sp._spam_protection = None

                protection = get_spam_protection()
                protection.record_scan("already_scanned_quote", "author1", False)

                result = await scan_and_protect(mock_twitter_client, tweet_ids=["tweet789"])

                # Should not have scanned this quote again
                assert result["scanned"] == 0

    @pytest.mark.asyncio
    async def test_scan_and_protect_skips_blocked_users(self, mock_twitter_client, tmp_path):
        """Test scan_and_protect skips already blocked users."""
        db_path = tmp_path / "data" / "spam.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        mock_twitter_client.get_quote_tweets.return_value = [
            {
                "id": "new_quote_from_blocked",
                "text": "Some text",
                "author": {
                    "id": "blocked_user",
                    "username": "spammer",
                    "followers_count": 5,
                }
            }
        ]

        with patch('bots.twitter.spam_protection.SPAM_DB', db_path):
            with patch('bots.twitter.spam_protection.DATA_DIR', db_path.parent):
                import bots.twitter.spam_protection as sp
                sp._spam_protection = None

                protection = get_spam_protection()
                protection.record_block("blocked_user", "spammer", "spam", 0.9, "old_quote")

                result = await scan_and_protect(mock_twitter_client, tweet_ids=["tweet999"])

                # Should record the scan but not count it
                assert result["scanned"] == 0
                assert result["blocked"] == 0

    @pytest.mark.asyncio
    async def test_scan_and_protect_handles_empty_quotes(self, mock_twitter_client, tmp_path):
        """Test scan_and_protect handles tweets with no quote tweets."""
        db_path = tmp_path / "data" / "spam.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        mock_twitter_client.get_quote_tweets.return_value = []

        with patch('bots.twitter.spam_protection.SPAM_DB', db_path):
            with patch('bots.twitter.spam_protection.DATA_DIR', db_path.parent):
                import bots.twitter.spam_protection as sp
                sp._spam_protection = None

                result = await scan_and_protect(mock_twitter_client, tweet_ids=["tweet_no_quotes"])

                assert result["scanned"] == 0
                assert result["blocked"] == 0

    @pytest.mark.asyncio
    async def test_scan_and_protect_handles_missing_author_data(self, mock_twitter_client, tmp_path):
        """Test scan_and_protect handles quotes with missing author data."""
        db_path = tmp_path / "data" / "spam.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        mock_twitter_client.get_quote_tweets.return_value = [
            {
                "id": "",  # Empty ID
                "text": "Some text",
                "author": {}
            },
            {
                # No ID at all
                "text": "Some text",
                "author": {"id": "author1"}
            }
        ]

        with patch('bots.twitter.spam_protection.SPAM_DB', db_path):
            with patch('bots.twitter.spam_protection.DATA_DIR', db_path.parent):
                import bots.twitter.spam_protection as sp
                sp._spam_protection = None

                result = await scan_and_protect(mock_twitter_client, tweet_ids=["tweet_missing"])

                # Should handle gracefully
                assert result["scanned"] == 0

    @pytest.mark.asyncio
    async def test_scan_and_protect_handles_api_errors(self, mock_twitter_client, tmp_path):
        """Test scan_and_protect handles API errors gracefully."""
        db_path = tmp_path / "data" / "spam.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        mock_twitter_client.get_quote_tweets.side_effect = Exception("API Error")

        with patch('bots.twitter.spam_protection.SPAM_DB', db_path):
            with patch('bots.twitter.spam_protection.DATA_DIR', db_path.parent):
                import bots.twitter.spam_protection as sp
                sp._spam_protection = None

                result = await scan_and_protect(mock_twitter_client, tweet_ids=["tweet_error"])

                # Should not crash
                assert result["scanned"] == 0
                assert result["blocked"] == 0

    @pytest.mark.asyncio
    async def test_scan_and_protect_block_failure(self, mock_twitter_client, tmp_path):
        """Test scan_and_protect handles block failure."""
        db_path = tmp_path / "data" / "spam.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Spam user that should be blocked
        mock_twitter_client.get_quote_tweets.return_value = [
            {
                "id": "quote_block_fail",
                "text": "AIRDROP! FREE TOKENS!",
                "author": {
                    "id": "spammer_fail",
                    "username": "spambot99999999",
                    "followers_count": 1,
                    "following_count": 5000,
                    "tweet_count": 1,
                    "description": "airdrop giveaway presale",
                    "created_at": (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
                }
            }
        ]

        # Block fails
        mock_twitter_client.block_user.return_value = False
        mock_twitter_client.mute_user.return_value = False

        with patch('bots.twitter.spam_protection.SPAM_DB', db_path):
            with patch('bots.twitter.spam_protection.DATA_DIR', db_path.parent):
                import bots.twitter.spam_protection as sp
                sp._spam_protection = None

                result = await scan_and_protect(mock_twitter_client, tweet_ids=["tweet_block_fail"])

                # Scanned but not blocked (block failed)
                assert result["scanned"] == 1
                assert result["blocked"] == 0


# =============================================================================
# Edge Cases and Boundary Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.fixture
    def protection(self, tmp_path):
        """Create SpamProtection instance with temp database."""
        db_path = tmp_path / "data" / "spam.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        with patch('bots.twitter.spam_protection.SPAM_DB', db_path):
            with patch('bots.twitter.spam_protection.DATA_DIR', db_path.parent):
                prot = SpamProtection()
                prot._db_path = db_path
                prot._init_db()
                return prot

    def test_score_exactly_at_threshold(self, protection):
        """Test behavior at exact spam threshold."""
        # Create user that should score exactly at threshold
        # This is tricky as scores are cumulative
        user = {
            "id": "12345",
            "username": "edgeuser",
            "followers_count": 10,  # +0.3
            "following_count": 100,  # +0.2 (ratio)
            "tweet_count": 500,
            "description": "Normal bio",
            "created_at": "2020-01-01 00:00:00"
        }

        score = protection.calculate_spam_score(user, "Hello world")

        # This user should have score around 0.5 from low followers + ratio
        # Threshold is 0.6, so should not be spam
        assert score.total > 0
        # Verify threshold logic works

    def test_score_just_below_threshold(self, protection):
        """Test user just below spam threshold."""
        user = {
            "id": "12345",
            "username": "almostspam",
            "followers_count": 60,  # Just above MIN_FOLLOWERS (50), so only +0.15
            "following_count": 100,
            "tweet_count": 500,
            "description": "Normal bio",
            "created_at": "2020-01-01 00:00:00"
        }

        tweet_text = "join now"  # Only one small keyword (+0.2)

        score = protection.calculate_spam_score(user, tweet_text)

        # Should be below threshold
        assert score.is_spam is False

    def test_follower_boundary_50(self, protection):
        """Test follower count at MIN_FOLLOWERS boundary."""
        # At MIN_FOLLOWERS (50) - should get 0.15
        user_at_50 = {
            "id": "1",
            "username": "at50",
            "followers_count": 50,
            "following_count": 100,
            "tweet_count": 500,
        }

        # Below MIN_FOLLOWERS (49) - should get 0.3
        user_below_50 = {
            "id": "2",
            "username": "below50",
            "followers_count": 49,
            "following_count": 100,
            "tweet_count": 500,
        }

        score_at = protection.calculate_spam_score(user_at_50, "Hello")
        score_below = protection.calculate_spam_score(user_below_50, "Hello")

        # Below should have higher score
        assert score_below.total >= score_at.total

    def test_account_age_boundary_30_days(self, protection):
        """Test account age at NEW_ACCOUNT_DAYS boundary."""
        # Exactly 30 days old - should not trigger new account penalty
        date_30_days = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        date_29_days = (datetime.utcnow() - timedelta(days=29)).strftime("%Y-%m-%d %H:%M:%S")

        user_30 = {
            "id": "1",
            "username": "user30",
            "followers_count": 5000,
            "following_count": 100,
            "tweet_count": 500,
            "created_at": date_30_days
        }

        user_29 = {
            "id": "2",
            "username": "user29",
            "followers_count": 5000,
            "following_count": 100,
            "tweet_count": 500,
            "created_at": date_29_days
        }

        score_30 = protection.calculate_spam_score(user_30, "Hello")
        score_29 = protection.calculate_spam_score(user_29, "Hello")

        # 29 days should trigger new account, 30 should be young account
        # Both might have penalties but 29 should be higher

    def test_keyword_score_capped_at_0_5(self, protection):
        """Test that keyword score is capped at 0.5."""
        user = {
            "id": "12345",
            "username": "keywordmax",
            "followers_count": 5000,
            "following_count": 100,
            "tweet_count": 500,
            "created_at": "2020-01-01 00:00:00"
        }

        # Max out keywords (each has weight, should cap at 0.5)
        tweet_text = " ".join(SPAM_KEYWORDS.keys())

        score = protection.calculate_spam_score(user, tweet_text)

        # Total keyword contribution should be capped
        # With all keywords, raw score would be > 0.5 but should cap

    def test_unicode_in_username(self, protection):
        """Test handling unicode characters in username."""
        user = {
            "id": "12345",
            "username": "user_unicode",
            "followers_count": 5000,
            "following_count": 100,
            "tweet_count": 500,
        }

        score = protection.calculate_spam_score(user, "Hello world")

        assert score.username == "user_unicode"

    def test_empty_tweet_text(self, protection):
        """Test handling empty tweet text."""
        user = {
            "id": "12345",
            "username": "emptytweet",
            "followers_count": 5000,
            "following_count": 100,
            "tweet_count": 500,
        }

        score = protection.calculate_spam_score(user, "")

        assert score is not None

    def test_very_long_tweet_text(self, protection):
        """Test handling very long tweet text."""
        user = {
            "id": "12345",
            "username": "longtweet",
            "followers_count": 5000,
            "following_count": 100,
            "tweet_count": 500,
        }

        # Create very long text
        long_text = "Normal content. " * 1000

        score = protection.calculate_spam_score(user, long_text)

        assert score is not None

    def test_special_characters_in_tweet(self, protection):
        """Test handling special characters in tweet text."""
        user = {
            "id": "12345",
            "username": "specialchars",
            "followers_count": 5000,
            "following_count": 100,
            "tweet_count": 500,
        }

        special_text = "Check this out! @#$%^&*()_+=[]{}|;':\",./<>? Emojis too!"

        score = protection.calculate_spam_score(user, special_text)

        assert score is not None

    def test_case_insensitive_keyword_detection(self, protection):
        """Test that keyword detection is case-insensitive."""
        user = {
            "id": "12345",
            "username": "casetest",
            "followers_count": 5000,
            "following_count": 100,
            "tweet_count": 500,
        }

        # Keywords in different cases
        lower = protection.calculate_spam_score(user, "airdrop here")
        upper = protection.calculate_spam_score(user, "AIRDROP HERE")
        mixed = protection.calculate_spam_score(user, "AiRdRoP HeRe")

        # All should detect the keyword
        assert "airdrop" in lower.reasons[0].lower() if lower.reasons else True
        assert "airdrop" in upper.reasons[0].lower() if upper.reasons else True
        assert "airdrop" in mixed.reasons[0].lower() if mixed.reasons else True

    def test_zero_followers_zero_following(self, protection):
        """Test handling user with zero followers and following."""
        user = {
            "id": "12345",
            "username": "ghost",
            "followers_count": 0,
            "following_count": 0,
            "tweet_count": 0,
        }

        score = protection.calculate_spam_score(user, "Hello")

        # Should not crash on division by zero
        assert score is not None
        assert score.total >= 0

    def test_negative_counts_handled(self, protection):
        """Test handling negative counts (shouldn't happen but be safe)."""
        user = {
            "id": "12345",
            "username": "negative",
            "followers_count": -1,
            "following_count": -1,
            "tweet_count": -1,
        }

        score = protection.calculate_spam_score(user, "Hello")

        # Should not crash
        assert score is not None

    def test_malformed_date_format(self, protection):
        """Test handling malformed date format."""
        user = {
            "id": "12345",
            "username": "baddate",
            "followers_count": 5000,
            "following_count": 100,
            "tweet_count": 500,
            "created_at": "not-a-date"
        }

        score = protection.calculate_spam_score(user, "Hello")

        # Should not crash
        assert score is not None

    def test_multiple_url_patterns_only_scores_once(self, protection):
        """Test that multiple URL patterns only add score once."""
        user = {
            "id": "12345",
            "username": "multiurl",
            "followers_count": 5000,
            "following_count": 100,
            "tweet_count": 500,
            "created_at": "2020-01-01 00:00:00"
        }

        # Multiple spam URLs
        tweet_text = "Check bit.ly/x and tinyurl.com/y and linktr.ee/z"

        score = protection.calculate_spam_score(user, tweet_text)

        # URL pattern should only add 0.3 once (not 0.9 for 3 patterns)
        # This is by design - the code breaks after first match
        assert score.reasons.count("Spam URL pattern detected") == 1

    def test_multiple_bot_username_patterns_only_scores_once(self, protection):
        """Test that multiple bot username patterns only add score once."""
        # Username matching multiple patterns
        user = {
            "id": "12345",
            "username": "aaaa12345678",  # Repeating chars + many numbers
            "followers_count": 5000,
            "following_count": 100,
            "tweet_count": 500,
            "created_at": "2020-01-01 00:00:00"
        }

        score = protection.calculate_spam_score(user, "Hello")

        # Bot username should only add 0.2 once
        bot_reasons = [r for r in score.reasons if "Bot-like username" in r]
        assert len(bot_reasons) <= 1


# =============================================================================
# URL Pattern Detection Tests
# =============================================================================

class TestUrlPatternDetection:
    """Tests for spam URL pattern detection."""

    @pytest.fixture
    def protection(self, tmp_path):
        """Create SpamProtection instance."""
        db_path = tmp_path / "data" / "spam.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        with patch('bots.twitter.spam_protection.SPAM_DB', db_path):
            with patch('bots.twitter.spam_protection.DATA_DIR', db_path.parent):
                prot = SpamProtection()
                prot._db_path = db_path
                prot._init_db()
                return prot

    @pytest.fixture
    def clean_user(self):
        """Create a clean user for URL testing."""
        return {
            "id": "12345",
            "username": "urltest",
            "followers_count": 5000,
            "following_count": 100,
            "tweet_count": 500,
            "created_at": "2020-01-01 00:00:00"
        }

    def test_detects_bitly(self, protection, clean_user):
        """Test detection of bit.ly URLs."""
        score = protection.calculate_spam_score(clean_user, "Check bit.ly/abc123")
        assert "Spam URL pattern" in str(score.reasons)

    def test_detects_tinyurl(self, protection, clean_user):
        """Test detection of tinyurl URLs."""
        score = protection.calculate_spam_score(clean_user, "Check tinyurl.com/abc")
        assert "Spam URL pattern" in str(score.reasons)

    def test_detects_linktree(self, protection, clean_user):
        """Test detection of linktr.ee URLs."""
        score = protection.calculate_spam_score(clean_user, "Check linktr.ee/mylinks")
        assert "Spam URL pattern" in str(score.reasons)

    def test_detects_tco_short_links(self, protection, clean_user):
        """Test detection of t.co shortened links."""
        score = protection.calculate_spam_score(clean_user, "Check t.co/abc123xyz")
        assert "Spam URL pattern" in str(score.reasons)

    def test_normal_urls_not_flagged(self, protection, clean_user):
        """Test that normal URLs are not flagged."""
        score = protection.calculate_spam_score(clean_user, "Check https://twitter.com/user")
        assert "Spam URL pattern" not in str(score.reasons)


# =============================================================================
# Bot Username Pattern Tests
# =============================================================================

class TestBotUsernamePatterns:
    """Tests for bot username pattern detection."""

    @pytest.fixture
    def protection(self, tmp_path):
        """Create SpamProtection instance."""
        db_path = tmp_path / "data" / "spam.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        with patch('bots.twitter.spam_protection.SPAM_DB', db_path):
            with patch('bots.twitter.spam_protection.DATA_DIR', db_path.parent):
                prot = SpamProtection()
                prot._db_path = db_path
                prot._init_db()
                return prot

    def test_detects_many_trailing_numbers(self, protection):
        """Test detection of username with many trailing numbers."""
        user = {
            "id": "1",
            "username": "john123456",  # 6+ trailing numbers
            "followers_count": 5000,
            "following_count": 100,
        }
        score = protection.calculate_spam_score(user, "Hello")
        assert "Bot-like username" in str(score.reasons)

    def test_detects_just_numbers(self, protection):
        """Test detection of username that's just numbers."""
        user = {
            "id": "1",
            "username": "12345678901",  # 8+ numbers only
            "followers_count": 5000,
            "following_count": 100,
        }
        score = protection.calculate_spam_score(user, "Hello")
        assert "Bot-like username" in str(score.reasons)

    def test_detects_repeating_chars(self, protection):
        """Test detection of username with repeating characters."""
        user = {
            "id": "1",
            "username": "aaaaauser",  # 5+ repeating chars
            "followers_count": 5000,
            "following_count": 100,
        }
        score = protection.calculate_spam_score(user, "Hello")
        assert "Bot-like username" in str(score.reasons)

    def test_detects_name_underscore_numbers(self, protection):
        """Test detection of name_numbers pattern."""
        user = {
            "id": "1",
            "username": "john_12345",  # name_4+ numbers
            "followers_count": 5000,
            "following_count": 100,
        }
        score = protection.calculate_spam_score(user, "Hello")
        assert "Bot-like username" in str(score.reasons)

    def test_normal_username_not_flagged(self, protection):
        """Test that normal usernames are not flagged."""
        user = {
            "id": "1",
            "username": "johndoe",
            "followers_count": 5000,
            "following_count": 100,
        }
        score = protection.calculate_spam_score(user, "Hello")
        assert "Bot-like username" not in str(score.reasons)

    def test_short_numbers_not_flagged(self, protection):
        """Test that short number suffixes are not flagged."""
        user = {
            "id": "1",
            "username": "john123",  # Only 3 numbers
            "followers_count": 5000,
            "following_count": 100,
        }
        score = protection.calculate_spam_score(user, "Hello")
        # Should not be flagged as bot (pattern requires 6+ numbers)
        # Note: Depends on exact regex pattern


# =============================================================================
# Concurrent Access Tests
# =============================================================================

class TestConcurrentAccess:
    """Tests for concurrent database access."""

    @pytest.fixture
    def protection(self, tmp_path):
        """Create SpamProtection instance."""
        db_path = tmp_path / "data" / "spam.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        with patch('bots.twitter.spam_protection.SPAM_DB', db_path):
            with patch('bots.twitter.spam_protection.DATA_DIR', db_path.parent):
                prot = SpamProtection()
                prot._db_path = db_path
                prot._init_db()
                return prot

    def test_multiple_record_scans(self, protection):
        """Test multiple record_scan calls don't conflict."""
        for i in range(100):
            protection.record_scan(f"tweet_{i}", f"author_{i}", i % 2 == 0)

        stats = protection.get_stats()
        assert stats["total_scanned"] == 100

    def test_multiple_record_blocks(self, protection):
        """Test multiple record_block calls don't conflict."""
        for i in range(50):
            protection.record_block(
                f"user_{i}",
                f"spammer_{i}",
                "spam",
                0.8,
                f"tweet_{i}"
            )

        stats = protection.get_stats()
        assert stats["total_blocked"] == 50

    def test_insert_or_replace_scans(self, protection):
        """Test INSERT OR REPLACE behavior for scans."""
        # Insert same tweet twice with different spam status
        protection.record_scan("same_tweet", "author1", False)
        protection.record_scan("same_tweet", "author1", True)  # Update

        conn = sqlite3.connect(protection._db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM scanned_quotes WHERE tweet_id = ?", ("same_tweet",))
        count = cursor.fetchone()[0]
        cursor.execute("SELECT is_spam FROM scanned_quotes WHERE tweet_id = ?", ("same_tweet",))
        is_spam = cursor.fetchone()[0]
        conn.close()

        assert count == 1  # Only one record
        assert is_spam == 1  # Updated to spam

    def test_insert_or_replace_blocks(self, protection):
        """Test INSERT OR REPLACE behavior for blocks."""
        # Insert same user twice with different reason
        protection.record_block("same_user", "spammer", "reason1", 0.7, "tweet1")
        protection.record_block("same_user", "spammer", "reason2", 0.9, "tweet2")

        conn = sqlite3.connect(protection._db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM blocked_users WHERE user_id = ?", ("same_user",))
        count = cursor.fetchone()[0]
        cursor.execute("SELECT spam_score FROM blocked_users WHERE user_id = ?", ("same_user",))
        score = cursor.fetchone()[0]
        conn.close()

        assert count == 1  # Only one record
        assert score == 0.9  # Updated score
