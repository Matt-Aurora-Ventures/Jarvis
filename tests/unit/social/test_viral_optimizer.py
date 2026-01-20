"""
Viral Optimizer Tests

Tests for core/social/viral_optimizer.py:
- Hashtag generation based on sentiment
- Engagement hooks (questions, calls-to-action)
- Timing optimization (best posting times)
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestViralOptimizerImport:
    """Test that viral optimizer module imports correctly."""

    def test_viral_optimizer_import(self):
        """Test that ViralOptimizer can be imported."""
        from core.social.viral_optimizer import ViralOptimizer
        assert ViralOptimizer is not None

    def test_posting_schedule_import(self):
        """Test that PostingSchedule can be imported."""
        from core.social.viral_optimizer import PostingSchedule
        assert PostingSchedule is not None


class TestViralOptimizerInit:
    """Test ViralOptimizer initialization."""

    def test_default_init(self, temp_dir):
        """Test default initialization."""
        from core.social.viral_optimizer import ViralOptimizer
        optimizer = ViralOptimizer(data_dir=temp_dir)
        assert optimizer is not None

    def test_custom_timezone(self, temp_dir):
        """Test initialization with custom timezone."""
        from core.social.viral_optimizer import ViralOptimizer
        optimizer = ViralOptimizer(data_dir=temp_dir, timezone="US/Eastern")
        assert optimizer.timezone == "US/Eastern"


class TestHashtagGeneration:
    """Tests for sentiment-based hashtag generation."""

    def test_generate_hashtags_bullish(self, temp_dir):
        """Test hashtag generation for bullish sentiment."""
        from core.social.viral_optimizer import ViralOptimizer

        optimizer = ViralOptimizer(data_dir=temp_dir)

        sentiment_data = {
            "overall": 0.75,
            "top_token": "SOL",
            "category": "bullish"
        }

        hashtags = optimizer.generate_hashtags(sentiment_data)

        assert isinstance(hashtags, list)
        assert len(hashtags) >= 3
        assert len(hashtags) <= 5  # Max 5 hashtags
        assert any("solana" in h.lower() or "sol" in h.lower() for h in hashtags)

    def test_generate_hashtags_bearish(self, temp_dir):
        """Test hashtag generation for bearish sentiment."""
        from core.social.viral_optimizer import ViralOptimizer

        optimizer = ViralOptimizer(data_dir=temp_dir)

        sentiment_data = {
            "overall": -0.6,
            "top_token": "BTC",
            "category": "bearish"
        }

        hashtags = optimizer.generate_hashtags(sentiment_data)

        assert isinstance(hashtags, list)
        assert len(hashtags) >= 3

    def test_generate_hashtags_includes_crypto(self, temp_dir):
        """Test that crypto-related hashtags are always included."""
        from core.social.viral_optimizer import ViralOptimizer

        optimizer = ViralOptimizer(data_dir=temp_dir)

        sentiment_data = {"overall": 0.5, "category": "neutral"}

        hashtags = optimizer.generate_hashtags(sentiment_data)

        # Should include at least one core crypto hashtag
        crypto_tags = ["#crypto", "#defi", "#trading", "#nfa"]
        assert any(h.lower() in crypto_tags for h in hashtags)

    def test_generate_hashtags_token_specific(self, temp_dir):
        """Test token-specific hashtag generation."""
        from core.social.viral_optimizer import ViralOptimizer

        optimizer = ViralOptimizer(data_dir=temp_dir)

        tokens = ["SOL", "WIF", "BONK"]
        hashtags = optimizer.generate_token_hashtags(tokens)

        assert "#Solana" in hashtags or "#solana" in hashtags
        assert len(hashtags) <= 5

    def test_hashtags_no_duplicates(self, temp_dir):
        """Test that generated hashtags have no duplicates."""
        from core.social.viral_optimizer import ViralOptimizer

        optimizer = ViralOptimizer(data_dir=temp_dir)

        sentiment_data = {"overall": 0.8, "category": "bullish", "top_token": "SOL"}
        hashtags = optimizer.generate_hashtags(sentiment_data)

        # Convert to lowercase for comparison
        lowercase_tags = [h.lower() for h in hashtags]
        assert len(lowercase_tags) == len(set(lowercase_tags))


class TestEngagementHooks:
    """Tests for engagement hooks (questions, CTAs)."""

    def test_generate_question_hook(self, temp_dir):
        """Test generating question-based hooks."""
        from core.social.viral_optimizer import ViralOptimizer

        optimizer = ViralOptimizer(data_dir=temp_dir)

        hook = optimizer.generate_hook(hook_type="question", context="SOL analysis")

        assert hook is not None
        assert "?" in hook
        assert len(hook) <= 100  # Hooks should be short

    def test_generate_cta_hook(self, temp_dir):
        """Test generating call-to-action hooks."""
        from core.social.viral_optimizer import ViralOptimizer

        optimizer = ViralOptimizer(data_dir=temp_dir)

        hook = optimizer.generate_hook(hook_type="cta", context="sentiment report")

        assert hook is not None
        # CTAs often contain action words
        assert len(hook) > 0

    def test_generate_curiosity_hook(self, temp_dir):
        """Test generating curiosity-based hooks."""
        from core.social.viral_optimizer import ViralOptimizer

        optimizer = ViralOptimizer(data_dir=temp_dir)

        hook = optimizer.generate_hook(hook_type="curiosity", context="whale activity")

        assert hook is not None
        assert len(hook) <= 100

    def test_hook_pool_variety(self, temp_dir):
        """Test that hook generation provides variety."""
        from core.social.viral_optimizer import ViralOptimizer

        optimizer = ViralOptimizer(data_dir=temp_dir)

        hooks = set()
        for _ in range(10):
            hook = optimizer.generate_hook(hook_type="question", context="test")
            hooks.add(hook)

        # Should have some variety
        assert len(hooks) >= 3

    def test_append_hook_to_tweet(self, temp_dir):
        """Test appending hook to existing tweet."""
        from core.social.viral_optimizer import ViralOptimizer

        optimizer = ViralOptimizer(data_dir=temp_dir)

        tweet = "sol looking bullish today nfa"
        enhanced = optimizer.append_hook(tweet, hook_type="question")

        assert len(enhanced) > len(tweet)
        assert len(enhanced) <= 280


class TestTimingOptimization:
    """Tests for posting time optimization."""

    def test_get_optimal_posting_time(self, temp_dir):
        """Test getting optimal posting time."""
        from core.social.viral_optimizer import ViralOptimizer

        optimizer = ViralOptimizer(data_dir=temp_dir)

        optimal_time = optimizer.get_optimal_posting_time()

        assert optimal_time is not None
        assert isinstance(optimal_time, datetime)

    def test_posting_schedule_default(self, temp_dir):
        """Test default posting schedule."""
        from core.social.viral_optimizer import PostingSchedule

        schedule = PostingSchedule()

        # Should have peak hours defined
        peak_hours = schedule.get_peak_hours()
        assert len(peak_hours) >= 3
        assert all(0 <= h <= 23 for h in peak_hours)

    def test_posting_schedule_crypto_hours(self, temp_dir):
        """Test crypto-specific posting hours."""
        from core.social.viral_optimizer import PostingSchedule

        schedule = PostingSchedule(audience="crypto")

        peak_hours = schedule.get_peak_hours()
        # Crypto twitter is often active in specific windows
        assert 13 in peak_hours or 14 in peak_hours  # US market open
        assert 9 in peak_hours or 10 in peak_hours   # EU market

    def test_is_good_time_to_post(self, temp_dir):
        """Test checking if current time is good for posting."""
        from core.social.viral_optimizer import ViralOptimizer

        optimizer = ViralOptimizer(data_dir=temp_dir)

        result = optimizer.is_good_time_to_post()

        assert isinstance(result, bool)

    def test_time_until_next_peak(self, temp_dir):
        """Test calculating time until next peak hour."""
        from core.social.viral_optimizer import ViralOptimizer

        optimizer = ViralOptimizer(data_dir=temp_dir)

        minutes = optimizer.minutes_until_peak()

        assert isinstance(minutes, int)
        assert minutes >= 0
        assert minutes <= 24 * 60  # Max 24 hours


class TestTweetOptimization:
    """Tests for full tweet optimization."""

    def test_optimize_tweet_adds_hashtags(self, temp_dir):
        """Test that optimization adds hashtags."""
        from core.social.viral_optimizer import ViralOptimizer

        optimizer = ViralOptimizer(data_dir=temp_dir)

        tweet = "sol showing strong momentum today nfa"
        sentiment = {"overall": 0.7, "category": "bullish", "top_token": "SOL"}

        optimized = optimizer.optimize_tweet(tweet, sentiment)

        assert "#" in optimized
        assert len(optimized) <= 280

    def test_optimize_tweet_preserves_content(self, temp_dir):
        """Test that optimization preserves original content."""
        from core.social.viral_optimizer import ViralOptimizer

        optimizer = ViralOptimizer(data_dir=temp_dir)

        tweet = "sol showing strong momentum"
        sentiment = {"overall": 0.7}

        optimized = optimizer.optimize_tweet(tweet, sentiment)

        # Original content should be preserved at the start
        assert "sol" in optimized.lower()
        assert "momentum" in optimized.lower()

    def test_optimize_tweet_length_limit(self, temp_dir):
        """Test that optimization respects 280 char limit."""
        from core.social.viral_optimizer import ViralOptimizer

        optimizer = ViralOptimizer(data_dir=temp_dir)

        # Long tweet near limit
        tweet = "a" * 250
        sentiment = {"overall": 0.5}

        optimized = optimizer.optimize_tweet(tweet, sentiment)

        assert len(optimized) <= 280

    def test_optimize_tweet_scoring(self, temp_dir):
        """Test tweet viral score calculation."""
        from core.social.viral_optimizer import ViralOptimizer

        optimizer = ViralOptimizer(data_dir=temp_dir)

        tweet = "just scanned 50 tokens. sol leading the pack. thoughts?"

        score = optimizer.calculate_viral_score(tweet)

        assert isinstance(score, float)
        assert 0 <= score <= 100
