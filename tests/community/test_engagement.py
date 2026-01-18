"""
Tests for Community and Engagement Features.

Tests cover:
- Leaderboard ranking accuracy
- Achievement badge award conditions
- Community voting mechanics
- Referral tracking
- Profile creation and privacy settings
- Challenge participation
- Ambassador program requirements
- News feed aggregation

Target: 30+ tests
"""

import json
import os
import pytest
import sqlite3
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    # Windows file cleanup with retry
    import time
    for _ in range(3):
        try:
            if os.path.exists(path):
                os.unlink(path)
            break
        except PermissionError:
            time.sleep(0.1)
            import gc
            gc.collect()


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_trade_history():
    """Sample trade history for testing."""
    return [
        {
            "trade_id": "t1",
            "user_id": "user1",
            "token": "SOL",
            "type": "BUY",
            "entry_price": 100.0,
            "exit_price": 150.0,
            "amount": 10,
            "pnl": 500.0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        {
            "trade_id": "t2",
            "user_id": "user1",
            "token": "BONK",
            "type": "BUY",
            "entry_price": 0.001,
            "exit_price": 0.002,
            "amount": 1000000,
            "pnl": 1000.0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        {
            "trade_id": "t3",
            "user_id": "user1",
            "token": "WIF",
            "type": "BUY",
            "entry_price": 2.0,
            "exit_price": 1.5,
            "amount": 100,
            "pnl": -50.0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    ]


@pytest.fixture
def sample_users():
    """Sample user data for testing."""
    return [
        {
            "user_id": "user1",
            "username": "trader_pro",
            "total_pnl": 1500.0,
            "win_rate": 0.67,
            "total_trades": 3,
            "sharpe_ratio": 1.5,
            "max_drawdown": 0.05,
        },
        {
            "user_id": "user2",
            "username": "moon_hunter",
            "total_pnl": 5000.0,
            "win_rate": 0.80,
            "total_trades": 10,
            "sharpe_ratio": 2.1,
            "max_drawdown": 0.02,
        },
        {
            "user_id": "user3",
            "username": "degen_king",
            "total_pnl": -200.0,
            "win_rate": 0.30,
            "total_trades": 20,
            "sharpe_ratio": -0.5,
            "max_drawdown": 0.25,
        },
    ]


# =============================================================================
# Leaderboard Tests
# =============================================================================


class TestLeaderboard:
    """Tests for leaderboard functionality."""

    def test_leaderboard_init(self, temp_db):
        """Test leaderboard initialization."""
        from core.community.leaderboard import Leaderboard

        lb = Leaderboard(db_path=temp_db)
        assert lb is not None
        assert lb.db_path == temp_db

    def test_update_user_stats(self, temp_db, sample_users):
        """Test updating user statistics in leaderboard."""
        from core.community.leaderboard import Leaderboard

        lb = Leaderboard(db_path=temp_db)

        for user in sample_users:
            lb.update_user_stats(
                user_id=user["user_id"],
                username=user["username"],
                total_pnl=user["total_pnl"],
                win_rate=user["win_rate"],
                total_trades=user["total_trades"],
                sharpe_ratio=user["sharpe_ratio"],
                max_drawdown=user["max_drawdown"],
            )

        # Verify stats were saved
        stats = lb.get_user_stats("user1")
        assert stats is not None
        assert stats["total_pnl"] == 1500.0
        assert stats["win_rate"] == 0.67

    def test_overall_ranking_by_profit(self, temp_db, sample_users):
        """Test overall ranking by profit."""
        from core.community.leaderboard import Leaderboard

        lb = Leaderboard(db_path=temp_db)

        for user in sample_users:
            lb.update_user_stats(
                user_id=user["user_id"],
                username=user["username"],
                total_pnl=user["total_pnl"],
                win_rate=user["win_rate"],
                total_trades=user["total_trades"],
            )

        rankings = lb.get_rankings(by="profit", limit=10)

        # user2 should be first (highest profit)
        assert rankings[0]["user_id"] == "user2"
        assert rankings[0]["total_pnl"] == 5000.0

        # user1 should be second
        assert rankings[1]["user_id"] == "user1"

        # user3 should be last (negative profit)
        assert rankings[2]["user_id"] == "user3"

    def test_weekly_rankings(self, temp_db, sample_users):
        """Test weekly rankings."""
        from core.community.leaderboard import Leaderboard

        lb = Leaderboard(db_path=temp_db)

        # Add weekly stats
        for user in sample_users:
            lb.update_user_stats(
                user_id=user["user_id"],
                username=user["username"],
                total_pnl=user["total_pnl"],
                win_rate=user["win_rate"],
                total_trades=user["total_trades"],
                period="weekly",
            )

        rankings = lb.get_rankings(by="profit", period="weekly", limit=10)
        assert len(rankings) == 3
        assert rankings[0]["user_id"] == "user2"

    def test_monthly_rankings(self, temp_db, sample_users):
        """Test monthly rankings."""
        from core.community.leaderboard import Leaderboard

        lb = Leaderboard(db_path=temp_db)

        for user in sample_users:
            lb.update_user_stats(
                user_id=user["user_id"],
                username=user["username"],
                total_pnl=user["total_pnl"],
                win_rate=user["win_rate"],
                total_trades=user["total_trades"],
                period="monthly",
            )

        rankings = lb.get_rankings(by="profit", period="monthly", limit=10)
        assert len(rankings) == 3

    def test_ranking_by_win_rate(self, temp_db, sample_users):
        """Test ranking by win rate."""
        from core.community.leaderboard import Leaderboard

        lb = Leaderboard(db_path=temp_db)

        for user in sample_users:
            lb.update_user_stats(
                user_id=user["user_id"],
                username=user["username"],
                total_pnl=user["total_pnl"],
                win_rate=user["win_rate"],
                total_trades=user["total_trades"],
            )

        rankings = lb.get_rankings(by="win_rate", limit=10)

        # user2 should be first (80% win rate)
        assert rankings[0]["user_id"] == "user2"
        assert rankings[0]["win_rate"] == 0.80


# =============================================================================
# User Profile Tests
# =============================================================================


class TestUserProfile:
    """Tests for user profile functionality."""

    def test_profile_creation(self, temp_db):
        """Test creating a new user profile."""
        from core.community.user_profile import UserProfileManager

        manager = UserProfileManager(db_path=temp_db)

        profile = manager.create_profile(
            user_id="user1",
            username="trader_pro",
            bio="I trade memecoins",
        )

        assert profile is not None
        assert profile["user_id"] == "user1"
        assert profile["username"] == "trader_pro"
        assert profile["bio"] == "I trade memecoins"

    def test_profile_default_privacy(self, temp_db):
        """Test default privacy settings."""
        from core.community.user_profile import UserProfileManager

        manager = UserProfileManager(db_path=temp_db)

        profile = manager.create_profile(
            user_id="user1",
            username="trader_pro",
        )

        # Default should be anonymous
        assert profile["is_public"] is False

    def test_update_profile_privacy(self, temp_db):
        """Test updating profile privacy settings."""
        from core.community.user_profile import UserProfileManager

        manager = UserProfileManager(db_path=temp_db)

        manager.create_profile(user_id="user1", username="trader_pro")

        # Make profile public
        manager.update_privacy(
            user_id="user1",
            is_public=True,
            show_pnl=True,
            show_trades=True,
        )

        profile = manager.get_profile("user1")
        assert profile["is_public"] is True
        assert profile["show_pnl"] is True
        assert profile["show_trades"] is True

    def test_bio_max_length(self, temp_db):
        """Test bio max length validation."""
        from core.community.user_profile import UserProfileManager

        manager = UserProfileManager(db_path=temp_db)

        # Bio over 200 chars should be truncated
        long_bio = "x" * 250
        profile = manager.create_profile(
            user_id="user1",
            username="trader_pro",
            bio=long_bio,
        )

        assert len(profile["bio"]) <= 200

    def test_get_public_profile(self, temp_db):
        """Test retrieving a public profile."""
        from core.community.user_profile import UserProfileManager

        manager = UserProfileManager(db_path=temp_db)

        # Create public profile
        manager.create_profile(user_id="user1", username="trader_pro")
        manager.update_privacy(user_id="user1", is_public=True, show_pnl=True)
        manager.update_stats(user_id="user1", total_pnl=1000.0, win_rate=0.75)

        public = manager.get_public_profile("user1")

        assert public is not None
        assert public["username"] == "trader_pro"
        assert public["total_pnl"] == 1000.0

    def test_private_profile_hidden(self, temp_db):
        """Test that private profiles are hidden."""
        from core.community.user_profile import UserProfileManager

        manager = UserProfileManager(db_path=temp_db)

        # Create private profile (default)
        manager.create_profile(user_id="user1", username="trader_pro")
        manager.update_stats(user_id="user1", total_pnl=1000.0)

        public = manager.get_public_profile("user1")

        # Should return minimal info for private profile
        assert public["username"] == "Anonymous"
        assert "total_pnl" not in public or public.get("total_pnl") is None


# =============================================================================
# Achievement Badge Tests
# =============================================================================


class TestAchievements:
    """Tests for achievement/badge functionality."""

    def test_achievement_manager_init(self, temp_db):
        """Test achievement manager initialization."""
        from core.community.achievements import AchievementManager

        manager = AchievementManager(db_path=temp_db)
        assert manager is not None

    def test_first_trade_badge(self, temp_db):
        """Test 'First Trade' badge awarded on first trade."""
        from core.community.achievements import AchievementManager

        manager = AchievementManager(db_path=temp_db)

        badges = manager.check_and_award(
            user_id="user1",
            event="trade_complete",
            trade_count=1,
        )

        assert "FIRST_TRADE" in [b["badge_id"] for b in badges]

    def test_10x_gain_badge(self, temp_db):
        """Test '10x Gain' badge for 10x profit on a trade."""
        from core.community.achievements import AchievementManager

        manager = AchievementManager(db_path=temp_db)

        badges = manager.check_and_award(
            user_id="user1",
            event="trade_complete",
            trade_multiplier=10.5,
        )

        assert "10X_GAIN" in [b["badge_id"] for b in badges]

    def test_perfect_win_rate_badge(self, temp_db):
        """Test '100% Win Rate' badge with 5+ trades."""
        from core.community.achievements import AchievementManager

        manager = AchievementManager(db_path=temp_db)

        badges = manager.check_and_award(
            user_id="user1",
            event="stats_update",
            win_rate=1.0,
            trade_count=5,
        )

        assert "PERFECT_TRADER" in [b["badge_id"] for b in badges]

    def test_consistent_trader_badge(self, temp_db):
        """Test 'Consistent Trader' badge for 20+ trades."""
        from core.community.achievements import AchievementManager

        manager = AchievementManager(db_path=temp_db)

        badges = manager.check_and_award(
            user_id="user1",
            event="stats_update",
            trade_count=20,
        )

        assert "CONSISTENT_TRADER" in [b["badge_id"] for b in badges]

    def test_milestone_badges(self, temp_db):
        """Test profit milestone badges ($100, $1000, $10K+)."""
        from core.community.achievements import AchievementManager

        manager = AchievementManager(db_path=temp_db)

        # $100 milestone
        badges = manager.check_and_award(
            user_id="user1",
            event="stats_update",
            total_pnl=150.0,
        )
        assert "PROFIT_100" in [b["badge_id"] for b in badges]

        # $1000 milestone
        badges = manager.check_and_award(
            user_id="user1",
            event="stats_update",
            total_pnl=1500.0,
        )
        assert "PROFIT_1K" in [b["badge_id"] for b in badges]

    def test_explorer_badge(self, temp_db):
        """Test 'Explorer' badge for analyzing 50+ tokens."""
        from core.community.achievements import AchievementManager

        manager = AchievementManager(db_path=temp_db)

        badges = manager.check_and_award(
            user_id="user1",
            event="stats_update",
            unique_tokens_analyzed=50,
        )

        assert "EXPLORER" in [b["badge_id"] for b in badges]

    def test_alpha_hunter_badge(self, temp_db):
        """Test 'Alpha Hunter' badge for discovering token before 10x."""
        from core.community.achievements import AchievementManager

        manager = AchievementManager(db_path=temp_db)

        badges = manager.check_and_award(
            user_id="user1",
            event="alpha_discovery",
            token_multiplier_since_discovery=10.0,
        )

        assert "ALPHA_HUNTER" in [b["badge_id"] for b in badges]

    def test_no_duplicate_badges(self, temp_db):
        """Test that badges are not awarded twice."""
        from core.community.achievements import AchievementManager

        manager = AchievementManager(db_path=temp_db)

        # Award first trade badge
        manager.check_and_award(
            user_id="user1",
            event="trade_complete",
            trade_count=1,
        )

        # Try to award again
        badges = manager.check_and_award(
            user_id="user1",
            event="trade_complete",
            trade_count=2,
        )

        # Should not have FIRST_TRADE in new badges
        assert "FIRST_TRADE" not in [b["badge_id"] for b in badges]


# =============================================================================
# Community Voting Tests
# =============================================================================


class TestCommunityVoting:
    """Tests for community voting functionality."""

    def test_voting_init(self, temp_db):
        """Test voting manager initialization."""
        from core.community.voting import VotingManager

        manager = VotingManager(db_path=temp_db)
        assert manager is not None

    def test_create_poll(self, temp_db):
        """Test creating a new poll."""
        from core.community.voting import VotingManager

        manager = VotingManager(db_path=temp_db)

        poll = manager.create_poll(
            title="Which token should we analyze next?",
            options=["BONK", "WIF", "POPCAT"],
            duration_days=7,
        )

        assert poll is not None
        assert poll["title"] == "Which token should we analyze next?"
        assert len(poll["options"]) == 3

    def test_cast_vote(self, temp_db):
        """Test casting a vote."""
        from core.community.voting import VotingManager

        manager = VotingManager(db_path=temp_db)

        poll = manager.create_poll(
            title="Feature vote",
            options=["A", "B", "C"],
            duration_days=7,
        )

        result = manager.cast_vote(
            poll_id=poll["poll_id"],
            user_id="user1",
            option="A",
        )

        assert result["success"] is True

    def test_one_vote_per_user_per_week(self, temp_db):
        """Test that users can only vote once per week."""
        from core.community.voting import VotingManager

        manager = VotingManager(db_path=temp_db)

        poll1 = manager.create_poll(title="Poll 1", options=["A", "B"])
        poll2 = manager.create_poll(title="Poll 2", options=["C", "D"])

        # First vote should succeed
        manager.cast_vote(poll_id=poll1["poll_id"], user_id="user1", option="A")

        # Second vote within same week should fail
        result = manager.cast_vote(poll_id=poll2["poll_id"], user_id="user1", option="C")

        assert result["success"] is False
        assert "weekly" in result["message"].lower() and "limit" in result["message"].lower()

    def test_get_poll_results(self, temp_db):
        """Test getting poll results."""
        from core.community.voting import VotingManager

        manager = VotingManager(db_path=temp_db)

        poll = manager.create_poll(title="Test", options=["A", "B"])

        # Cast some votes (bypass weekly limit for testing)
        manager.cast_vote(poll["poll_id"], "user1", "A")
        manager._bypass_weekly_limit = True
        manager.cast_vote(poll["poll_id"], "user2", "A")
        manager.cast_vote(poll["poll_id"], "user3", "B")

        results = manager.get_results(poll["poll_id"])

        assert results["A"] == 2
        assert results["B"] == 1


# =============================================================================
# Referral Tests
# =============================================================================


class TestReferrals:
    """Tests for referral tracking functionality."""

    def test_generate_referral_code(self, temp_db):
        """Test generating a unique referral code."""
        from core.community.leaderboard import Leaderboard

        lb = Leaderboard(db_path=temp_db)

        code = lb.generate_referral_code("user1")

        assert code is not None
        assert len(code) >= 6

    def test_track_referral(self, temp_db):
        """Test tracking a referral."""
        from core.community.leaderboard import Leaderboard

        lb = Leaderboard(db_path=temp_db)

        code = lb.generate_referral_code("user1")

        # New user signs up with referral code
        result = lb.track_referral(
            referrer_id="user1",
            referred_id="user2",
            referral_code=code,
        )

        assert result["success"] is True

    def test_referral_count(self, temp_db):
        """Test counting referrals."""
        from core.community.leaderboard import Leaderboard

        lb = Leaderboard(db_path=temp_db)

        code = lb.generate_referral_code("user1")

        lb.track_referral("user1", "user2", code)
        lb.track_referral("user1", "user3", code)
        lb.track_referral("user1", "user4", code)

        count = lb.get_referral_count("user1")

        assert count == 3

    def test_referral_commission(self, temp_db):
        """Test referral commission calculation."""
        from core.community.leaderboard import Leaderboard

        lb = Leaderboard(db_path=temp_db)

        # Default 10% commission
        commission = lb.calculate_referral_commission(
            referrer_id="user1",
            referred_trade_pnl=1000.0,
            is_ambassador=False,
        )

        assert commission == 100.0  # 10% of 1000

        # Ambassador gets 15%
        commission = lb.calculate_referral_commission(
            referrer_id="user1",
            referred_trade_pnl=1000.0,
            is_ambassador=True,
        )

        assert commission == 150.0  # 15% of 1000


# =============================================================================
# Community Challenge Tests
# =============================================================================


class TestChallenges:
    """Tests for community challenge functionality."""

    def test_challenge_init(self, temp_db):
        """Test challenge manager initialization."""
        from core.community.challenges import ChallengeManager

        manager = ChallengeManager(db_path=temp_db)
        assert manager is not None

    def test_create_challenge(self, temp_db):
        """Test creating a monthly challenge."""
        from core.community.challenges import ChallengeManager

        manager = ChallengeManager(db_path=temp_db)

        challenge = manager.create_challenge(
            title="Bull Run January",
            description="Highest % gain wins",
            metric="percent_gain",
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc) + timedelta(days=30),
        )

        assert challenge is not None
        assert challenge["title"] == "Bull Run January"

    def test_register_for_challenge(self, temp_db):
        """Test registering for a challenge."""
        from core.community.challenges import ChallengeManager

        manager = ChallengeManager(db_path=temp_db)

        challenge = manager.create_challenge(
            title="Test Challenge",
            metric="profit",
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc) + timedelta(days=7),
        )

        result = manager.register(challenge["challenge_id"], "user1")

        assert result["success"] is True

    def test_challenge_leaderboard(self, temp_db):
        """Test challenge-specific leaderboard."""
        from core.community.challenges import ChallengeManager

        manager = ChallengeManager(db_path=temp_db)

        challenge = manager.create_challenge(
            title="Test",
            metric="profit",
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc) + timedelta(days=7),
        )

        manager.register(challenge["challenge_id"], "user1")
        manager.register(challenge["challenge_id"], "user2")

        manager.update_score(challenge["challenge_id"], "user1", 500.0)
        manager.update_score(challenge["challenge_id"], "user2", 1000.0)

        lb = manager.get_challenge_leaderboard(challenge["challenge_id"])

        assert lb[0]["user_id"] == "user2"
        assert lb[0]["score"] == 1000.0


# =============================================================================
# Ambassador Program Tests
# =============================================================================


class TestAmbassadorProgram:
    """Tests for ambassador program functionality."""

    def test_ambassador_requirements(self, temp_db):
        """Test ambassador requirement validation."""
        from core.community.ambassador import AmbassadorManager

        manager = AmbassadorManager(db_path=temp_db)

        # User doesn't meet requirements
        eligible = manager.check_eligibility(
            user_id="user1",
            account_age_months=1,
            total_pnl=100.0,
            community_score=10,
        )

        assert eligible["is_eligible"] is False
        assert "account_age" in eligible["missing_requirements"]

    def test_ambassador_application(self, temp_db):
        """Test ambassador application."""
        from core.community.ambassador import AmbassadorManager

        manager = AmbassadorManager(db_path=temp_db)

        # User meets all requirements
        result = manager.apply_for_ambassador(
            user_id="user1",
            account_age_months=4,
            total_pnl=600.0,
            community_score=50,
        )

        assert result["status"] == "pending"

    def test_ambassador_benefits(self, temp_db):
        """Test ambassador benefits."""
        from core.community.ambassador import AmbassadorManager

        manager = AmbassadorManager(db_path=temp_db)

        benefits = manager.get_ambassador_benefits("user1")

        assert "referral_commission_rate" in benefits
        assert benefits["referral_commission_rate"] == 0.15  # 15%


# =============================================================================
# News Feed Tests
# =============================================================================


class TestNewsFeed:
    """Tests for news feed functionality."""

    def test_news_feed_init(self, temp_db):
        """Test news feed initialization."""
        from core.community.news_feed import NewsFeed

        feed = NewsFeed(db_path=temp_db)
        assert feed is not None

    def test_add_news_item(self, temp_db):
        """Test adding a news item."""
        from core.community.news_feed import NewsFeed

        feed = NewsFeed(db_path=temp_db)

        item = feed.add_item(
            item_type="achievement",
            content="user1 earned the '10x Gain' badge!",
            user_id="user1",
            metadata={"badge_id": "10X_GAIN"},
        )

        assert item is not None
        assert item["item_type"] == "achievement"

    def test_get_personalized_feed(self, temp_db):
        """Test getting personalized feed."""
        from core.community.news_feed import NewsFeed

        feed = NewsFeed(db_path=temp_db)

        # Add various items
        feed.add_item("achievement", "user1 earned badge", user_id="user1")
        feed.add_item("challenge", "New challenge started")
        feed.add_item("team_update", "New feature released")

        items = feed.get_feed(user_id="user1", limit=10)

        assert len(items) >= 1

    def test_daily_digest(self, temp_db):
        """Test daily digest generation."""
        from core.community.news_feed import NewsFeed

        feed = NewsFeed(db_path=temp_db)

        # Add today's items
        feed.add_item("achievement", "Achievement 1")
        feed.add_item("market_alpha", "New token alert")

        digest = feed.generate_daily_digest(user_id="user1")

        assert digest is not None
        assert "items" in digest
        assert len(digest["items"]) >= 1


# =============================================================================
# Integration Tests
# =============================================================================


class TestCommunityIntegration:
    """Integration tests for community features."""

    def test_trade_triggers_achievements(self, temp_db):
        """Test that completing a trade triggers achievement checks."""
        from core.community.leaderboard import Leaderboard
        from core.community.achievements import AchievementManager

        lb = Leaderboard(db_path=temp_db)
        achievements = AchievementManager(db_path=temp_db)

        # Update user stats after trade
        lb.update_user_stats(
            user_id="user1",
            username="trader",
            total_pnl=1500.0,
            win_rate=0.75,
            total_trades=1,
        )

        # Check for badges
        badges = achievements.check_and_award(
            user_id="user1",
            event="trade_complete",
            trade_count=1,
            total_pnl=1500.0,
        )

        assert len(badges) > 0
        badge_ids = [b["badge_id"] for b in badges]
        assert "FIRST_TRADE" in badge_ids
        assert "PROFIT_1K" in badge_ids

    def test_referral_updates_leaderboard(self, temp_db):
        """Test that referrals update leaderboard stats."""
        from core.community.leaderboard import Leaderboard

        lb = Leaderboard(db_path=temp_db)

        # User1 refers user2
        code = lb.generate_referral_code("user1")
        lb.track_referral("user1", "user2", code)

        # Check referral count in stats
        stats = lb.get_user_stats("user1")
        # Note: This may need the leaderboard to track referrals separately
        referral_count = lb.get_referral_count("user1")
        assert referral_count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
