"""
Community and Engagement Features for Jarvis.

Provides:
- Leaderboard system for ranking traders
- User profiles with privacy controls
- Achievement/badge system
- Community challenges
- Voting on features and tokens
- Ambassador program
- News feed aggregation
- Referral tracking

Usage:
    from core.community import (
        Leaderboard,
        UserProfileManager,
        AchievementManager,
        ChallengeManager,
        VotingManager,
        AmbassadorManager,
        NewsFeed,
    )

    # Get leaderboard rankings
    lb = Leaderboard()
    rankings = lb.get_rankings(by="profit", limit=10)

    # Check/award badges
    achievements = AchievementManager()
    badges = achievements.check_and_award(user_id, event="trade_complete", trade_count=1)
"""

from core.community.leaderboard import Leaderboard
from core.community.user_profile import UserProfileManager
from core.community.achievements import AchievementManager, BadgeType, BADGE_DEFINITIONS
from core.community.challenges import ChallengeManager
from core.community.voting import VotingManager
from core.community.ambassador import AmbassadorManager
from core.community.news_feed import NewsFeed

__all__ = [
    "Leaderboard",
    "UserProfileManager",
    "AchievementManager",
    "BadgeType",
    "BADGE_DEFINITIONS",
    "ChallengeManager",
    "VotingManager",
    "AmbassadorManager",
    "NewsFeed",
]
