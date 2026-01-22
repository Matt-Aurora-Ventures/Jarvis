"""
Raid Service - Business logic for Twitter raid campaigns.

Handles verification, raid management, participation tracking, and weekly resets.
"""

import re
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Tuple, Any

from tg_bot.services.raid_database import RaidDatabase, get_raid_db

logger = logging.getLogger(__name__)


class RaidService:
    """Business logic for raid campaigns."""

    def __init__(self, db: RaidDatabase = None):
        self.db = db or get_raid_db()
        self._twitter_client = None
        self._twitter_client_initialized = False

    async def _get_twitter_client(self):
        """Lazy load Twitter client."""
        if not self._twitter_client_initialized:
            try:
                from bots.twitter.twitter_client import TwitterClient
                self._twitter_client = TwitterClient()
                if self._twitter_client.connect():
                    self._twitter_client_initialized = True
                    logger.info("Twitter client connected for raid service")
                else:
                    logger.warning("Twitter client failed to connect")
                    self._twitter_client = None
            except Exception as e:
                logger.error(f"Failed to init Twitter client: {e}")
                self._twitter_client = None
                self._twitter_client_initialized = True  # Don't retry
        return self._twitter_client

    def parse_tweet_url(self, url: str) -> Optional[str]:
        """Extract tweet ID from URL."""
        # Patterns: twitter.com/user/status/ID, x.com/user/status/ID
        patterns = [
            r'(?:twitter|x)\.com/\w+/status/(\d+)',
            r'(?:twitter|x)\.com/\w+/statuses/(\d+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        # Maybe just a tweet ID was provided
        if url.isdigit() and len(url) > 10:
            return url
        return None

    # =========================================================================
    # USER VERIFICATION
    # =========================================================================

    async def verify_twitter_handle(self, handle: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Verify a Twitter handle exists and get user info.

        Args:
            handle: Twitter handle (with or without @)

        Returns:
            (success, user_data) where user_data contains twitter_id, username, is_blue, followers
        """
        client = await self._get_twitter_client()
        if not client:
            return False, {"error": "Twitter client unavailable. Try again later."}

        handle = handle.lstrip("@")

        try:
            user_data = await client.get_user(handle)

            if not user_data:
                return False, {"error": f"User @{handle} not found on Twitter"}

            return True, {
                "twitter_id": user_data.get("id", ""),
                "username": user_data.get("username", handle),
                "is_blue": user_data.get("verified", False),
                "followers": user_data.get("followers_count", 0),
                "following": user_data.get("following_count", 0),
            }
        except Exception as e:
            logger.error(f"Error verifying Twitter handle {handle}: {e}")
            return False, {"error": f"Failed to verify @{handle}: {str(e)[:100]}"}

    def register_user(
        self,
        telegram_id: int,
        telegram_username: str,
        twitter_handle: str,
        twitter_id: str = "",
        is_blue: bool = False
    ) -> int:
        """Register or update a user. Returns user ID."""
        return self.db.register_user(
            telegram_id=telegram_id,
            telegram_username=telegram_username,
            twitter_handle=twitter_handle,
            twitter_id=twitter_id,
            is_blue=is_blue
        )

    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict]:
        """Get user by Telegram ID."""
        return self.db.get_user_by_telegram_id(telegram_id)

    # =========================================================================
    # RAID MANAGEMENT
    # =========================================================================

    async def start_raid(
        self,
        tweet_url: str,
        announcement_msg_id: int = None,
        announcement_chat_id: int = None
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        Start a new raid on a tweet.

        Args:
            tweet_url: Full URL or tweet ID
            announcement_msg_id: Telegram message ID for the announcement
            announcement_chat_id: Telegram chat ID where announcement was posted

        Returns:
            (success, message, raid_data)
        """
        # Check for existing active raid
        active = self.db.get_active_raid()
        if active:
            return False, f"A raid is already active! End it first with /endraid", None

        # Parse tweet ID
        tweet_id = self.parse_tweet_url(tweet_url)
        if not tweet_id:
            return False, "Invalid tweet URL. Use format: x.com/user/status/ID", None

        # Check if this tweet was already raided
        existing = self.db.get_raid_by_tweet_id(tweet_id)
        if existing:
            return False, f"This tweet was already raided on {existing['started_at'][:10]}", None

        # Verify tweet exists and get info
        tweet_author = ""
        tweet_text = ""
        client = await self._get_twitter_client()
        if client:
            try:
                tweet = await client.get_tweet(tweet_id)
                if not tweet:
                    return False, "Tweet not found or inaccessible", None
                tweet_author = tweet.get("author_username", "")
                tweet_text = tweet.get("text", "")[:280]
            except Exception as e:
                logger.warning(f"Could not fetch tweet info: {e}")
                # Continue anyway - raid can still work

        # Normalize URL
        if not tweet_url.startswith("http"):
            tweet_url = f"https://x.com/i/status/{tweet_id}"

        # Create raid
        raid_id = self.db.create_raid(
            tweet_id=tweet_id,
            tweet_url=tweet_url,
            tweet_author=tweet_author,
            tweet_text=tweet_text,
            announcement_message_id=announcement_msg_id,
            announcement_chat_id=announcement_chat_id
        )

        raid = self.db.get_raid_by_id(raid_id)
        logger.info(f"Raid started: ID={raid_id}, tweet={tweet_id}, author={tweet_author}")

        return True, f"Raid started!", raid

    async def end_raid(self) -> Tuple[bool, str, Optional[Dict]]:
        """
        End the current active raid and calculate final scores.

        Returns:
            (success, message, summary_data)
        """
        active = self.db.get_active_raid()
        if not active:
            return False, "No active raid to end", None

        # Get participants before ending
        participants = self.db.get_raid_participants(active["id"])

        # End the raid in DB
        self.db.end_raid(active["id"])

        # Calculate duration
        duration_minutes = self._calculate_duration(active["started_at"])

        # Build summary
        summary = {
            "raid_id": active["id"],
            "tweet_id": active["tweet_id"],
            "tweet_url": active["tweet_url"],
            "tweet_author": active.get("tweet_author", ""),
            "duration_minutes": duration_minutes,
            "total_participants": len(participants),
            "total_points": sum(p["points_earned"] for p in participants),
            "total_likes": sum(1 for p in participants if p.get("liked")),
            "total_retweets": sum(1 for p in participants if p.get("retweeted")),
            "total_comments": sum(1 for p in participants if p.get("commented")),
            "top_participants": participants[:5],
        }

        logger.info(f"Raid ended: ID={active['id']}, participants={len(participants)}, points={summary['total_points']}")

        return True, "Raid ended!", summary

    def cancel_raid(self) -> Tuple[bool, str]:
        """Cancel the active raid without awarding points."""
        active = self.db.get_active_raid()
        if not active:
            return False, "No active raid to cancel"

        self.db.cancel_raid(active["id"])
        logger.info(f"Raid cancelled: ID={active['id']}")
        return True, "Raid cancelled"

    def get_active_raid(self) -> Optional[Dict]:
        """Get the currently active raid."""
        return self.db.get_active_raid()

    def update_raid_announcement(self, raid_id: int, message_id: int, chat_id: int) -> None:
        """Update raid with announcement message details."""
        self.db.update_raid_announcement(raid_id, message_id, chat_id)

    def _calculate_duration(self, started_at: str) -> int:
        """Calculate raid duration in minutes."""
        try:
            start = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            return int((now - start).total_seconds() / 60)
        except Exception:
            return 0

    # =========================================================================
    # PARTICIPATION CHECKING
    # =========================================================================

    async def check_participation(self, telegram_id: int) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Check a user's participation in the active raid.
        Verifies likes, retweets, and comments on Twitter.

        Args:
            telegram_id: Telegram user ID

        Returns:
            (success, message, participation_data)
        """
        # Get user
        user = self.db.get_user_by_telegram_id(telegram_id)
        if not user:
            return False, "You need to verify your Twitter handle first. Use /verify @handle", {}

        if not user.get("is_verified"):
            return False, "Your account isn't verified. Use /verify @handle", {}

        # Get active raid
        active = self.db.get_active_raid()
        if not active:
            return False, "No active raid right now", {}

        # Check if already participated in this raid
        existing = self.db.get_participation(active["id"], user["id"])
        if existing and existing.get("points_earned", 0) > 0:
            return True, "Already checked", {
                "liked": bool(existing.get("liked")),
                "retweeted": bool(existing.get("retweeted")),
                "commented": bool(existing.get("commented")),
                "points_earned": existing["points_earned"],
                "is_blue": user.get("is_blue", False),
                "already_checked": True,
            }

        client = await self._get_twitter_client()
        if not client:
            return False, "Twitter API unavailable. Try again later.", {}

        twitter_handle = user["twitter_handle"]
        twitter_id = user.get("twitter_id", "")
        is_blue = bool(user.get("is_blue", False))
        tweet_id = active["tweet_id"]

        # Check engagement on tweet
        liked = await self._check_user_liked(client, tweet_id, twitter_handle, twitter_id)
        retweeted = await self._check_user_retweeted(client, tweet_id, twitter_handle, twitter_id)
        commented = await self._check_user_commented(client, tweet_id, twitter_handle)

        # Calculate points
        point_values = self.db.get_point_values()
        points = 0
        if liked:
            points += point_values["like"]
        if retweeted:
            points += point_values["retweet"]
        if commented:
            points += point_values["comment"]

        # Apply blue bonus if user did at least one action
        blue_bonus = 0
        if is_blue and points > 0:
            blue_bonus = point_values["blue_bonus"]
            points += blue_bonus

        # Record participation if they did something
        if points > 0:
            self.db.record_participation(
                raid_id=active["id"],
                user_id=user["id"],
                liked=liked,
                retweeted=retweeted,
                commented=commented,
                points=points
            )
            # Update user's total points
            self.db.update_user_points(user["id"], points)

            logger.info(f"Participation recorded: user={user['id']}, raid={active['id']}, points={points}")

        return True, "Participation checked", {
            "liked": liked,
            "retweeted": retweeted,
            "commented": commented,
            "points_earned": points,
            "is_blue": is_blue,
            "blue_bonus": blue_bonus,
            "already_checked": False,
        }

    async def _check_user_liked(self, client, tweet_id: str, handle: str, twitter_id: str) -> bool:
        """Check if user liked the tweet."""
        try:
            likers = await client.get_liking_users(tweet_id)
            if not likers:
                return False
            handle_lower = handle.lower()
            for user in likers:
                if user.get("username", "").lower() == handle_lower:
                    return True
                if twitter_id and user.get("id") == twitter_id:
                    return True
            return False
        except Exception as e:
            logger.warning(f"Error checking likes: {e}")
            return False

    async def _check_user_retweeted(self, client, tweet_id: str, handle: str, twitter_id: str) -> bool:
        """Check if user retweeted the tweet."""
        try:
            retweeters = await client.get_retweeters(tweet_id)
            if not retweeters:
                return False
            handle_lower = handle.lower()
            for user in retweeters:
                if user.get("username", "").lower() == handle_lower:
                    return True
                if twitter_id and user.get("id") == twitter_id:
                    return True
            return False
        except Exception as e:
            logger.warning(f"Error checking retweets: {e}")
            return False

    async def _check_user_commented(self, client, tweet_id: str, handle: str) -> bool:
        """Check if user replied to the tweet."""
        try:
            replies = await client.get_tweet_replies(tweet_id)
            if not replies:
                return False
            handle_lower = handle.lower()
            for reply in replies:
                if reply.get("author_username", "").lower() == handle_lower:
                    return True
            return False
        except Exception as e:
            logger.warning(f"Error checking replies: {e}")
            return False

    # =========================================================================
    # LEADERBOARD & POINTS
    # =========================================================================

    def get_leaderboard(self, limit: int = 10, weekly: bool = True) -> List[Dict]:
        """Get top raiders by points."""
        return self.db.get_leaderboard(limit=limit, weekly=weekly)

    def get_user_points(self, telegram_id: int) -> Optional[Dict]:
        """Get user's points and rank."""
        user = self.db.get_user_by_telegram_id(telegram_id)
        if not user:
            return None

        rank = self.db.get_user_rank(user["id"], weekly=True)
        total_rank = self.db.get_user_rank(user["id"], weekly=False)

        return {
            "twitter_handle": user["twitter_handle"],
            "is_blue": user.get("is_blue", False),
            "weekly_points": user["weekly_points"],
            "total_points": user["total_points"],
            "weekly_rank": rank,
            "total_rank": total_rank,
        }

    # =========================================================================
    # CONFIGURATION
    # =========================================================================

    def get_point_values(self) -> Dict[str, int]:
        """Get current point values."""
        return self.db.get_point_values()

    def set_point_value(self, key: str, value: int) -> bool:
        """Set a point value. Key: like, retweet, comment, blue_bonus."""
        valid_keys = {"like": "points_like", "retweet": "points_retweet",
                      "comment": "points_comment", "blue_bonus": "blue_bonus"}
        if key not in valid_keys:
            return False
        self.db.set_config(valid_keys[key], str(value))
        return True

    def get_reward_config(self) -> Dict[str, Any]:
        """Get weekly reward configuration."""
        return {
            "amount": float(self.db.get_config("weekly_reward_amount") or 0),
            "token": self.db.get_config("weekly_reward_token") or "SOL",
        }

    def set_reward_config(self, amount: float, token: str = None) -> None:
        """Set weekly reward configuration."""
        self.db.set_config("weekly_reward_amount", str(amount))
        if token:
            self.db.set_config("weekly_reward_token", token.upper())

    # =========================================================================
    # WEEKLY RESET
    # =========================================================================

    async def weekly_reset(self) -> Dict[str, Any]:
        """
        Reset weekly points and return winners.
        Called by weekly scheduler.

        Returns:
            {winners: List[Dict], reward_amount: float, week_end: str}
        """
        # Get top 10 before reset
        winners = self.db.get_leaderboard(limit=10, weekly=True)

        # Record history
        now = datetime.now(timezone.utc)
        week_end = now.isoformat()
        week_start = (now - timedelta(days=7)).isoformat()

        reward_amount = float(self.db.get_config("weekly_reward_amount") or 0)

        if winners:
            self.db.record_weekly_winners(week_start, week_end, winners, reward_amount)
            logger.info(f"Weekly winners recorded: {len(winners)} winners")

        # Reset points
        self.db.reset_weekly_points()
        logger.info("Weekly points reset completed")

        return {
            "winners": winners,
            "reward_amount": reward_amount,
            "reward_token": self.db.get_config("weekly_reward_token") or "SOL",
            "week_end": week_end,
        }

    # =========================================================================
    # STATS
    # =========================================================================

    def get_raid_stats(self) -> Dict[str, Any]:
        """Get overall raid statistics."""
        recent_raids = self.db.get_recent_raids(limit=100)
        total_users = self.db.get_total_verified_users()

        return {
            "total_raids": len(recent_raids),
            "total_verified_users": total_users,
            "recent_raids": recent_raids[:5],
        }


# Singleton instance
_raid_service: Optional[RaidService] = None


def get_raid_service() -> RaidService:
    """Get or create raid service singleton."""
    global _raid_service
    if _raid_service is None:
        _raid_service = RaidService()
    return _raid_service
