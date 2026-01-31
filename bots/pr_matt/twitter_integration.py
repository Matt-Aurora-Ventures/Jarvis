"""
PR Matt Twitter Integration

Hooks PR Matt bot into the Twitter posting pipeline to review all posts before publishing.

Architecture:
- Intercepts posts from autonomous_x engine and twitter_poster
- Reviews with PR Matt
- If APPROVED: Posts immediately
- If NEEDS_REVISION: Suggests alternative, waits for manual approval
- If BLOCKED: Logs and refuses to post

Usage:
    from bots.pr_matt.twitter_integration import PRMattTwitterFilter

    filter = PRMattTwitterFilter(xai_api_key)
    await filter.start()

    # Before posting
    approved, suggestion = await filter.check_post(tweet_text)
    if approved:
        await twitter_client.post(tweet_text)
    elif suggestion:
        # Use suggestion or manual review
        await twitter_client.post(suggestion)
"""

import asyncio
import logging
from typing import Optional, Tuple
from .pr_matt_bot import PRMattBot, MessageReview

logger = logging.getLogger(__name__)


class PRMattTwitterFilter:
    """Integration layer for Twitter posting with PR Matt review."""

    def __init__(
        self,
        xai_api_key: str,
        auto_approve_threshold: float = 0.9,  # Confidence needed for auto-approval
        require_manual_review: bool = False,  # If True, all posts need manual review
    ):
        self.xai_api_key = xai_api_key
        self.auto_approve_threshold = auto_approve_threshold
        self.require_manual_review = require_manual_review
        self.pr_matt: Optional[PRMattBot] = None
        self._enabled = True

    async def start(self):
        """Initialize PR Matt bot."""
        self.pr_matt = PRMattBot(self.xai_api_key)
        await self.pr_matt.start()
        logger.info("PR Matt Twitter filter started")

    async def stop(self):
        """Clean up resources."""
        if self.pr_matt:
            await self.pr_matt.stop()
        logger.info("PR Matt Twitter filter stopped")

    def enable(self):
        """Enable PR Matt filtering."""
        self._enabled = True
        logger.info("PR Matt filtering ENABLED")

    def disable(self):
        """Disable PR Matt filtering (posts go through without review)."""
        self._enabled = False
        logger.warning("PR Matt filtering DISABLED - posts will bypass review!")

    async def check_post(
        self,
        tweet_text: str,
        context: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[MessageReview]]:
        """
        Check if a tweet should be posted.

        Args:
            tweet_text: The tweet content to review
            context: Optional context about the tweet

        Returns:
            (should_post, suggested_alternative, review_result)
            - should_post: True if approved, False if blocked
            - suggested_alternative: Alternative text if needs revision
            - review_result: Full MessageReview object
        """
        if not self._enabled:
            logger.warning("PR Matt is disabled - tweet bypassing review!")
            return True, None, None

        if not self.pr_matt:
            logger.error("PR Matt not initialized - cannot review tweet")
            return False, None, None

        # Review with PR Matt
        review = await self.pr_matt.review_message(
            tweet_text,
            platform="twitter",
            context=context
        )

        # Handle decision
        if review.decision == "APPROVED":
            if review.confidence >= self.auto_approve_threshold:
                logger.info(f"PR Matt APPROVED tweet (confidence: {review.confidence:.2f})")
                return True, None, review
            else:
                logger.warning(f"PR Matt approved but confidence low ({review.confidence:.2f}) - suggesting manual review")
                return False, tweet_text, review  # Return original for manual review

        elif review.decision == "NEEDS_REVISION":
            logger.info(f"PR Matt suggests revision: {review.concerns}")
            return False, review.suggested_revision, review

        else:  # BLOCKED
            logger.warning(f"PR Matt BLOCKED tweet: {review.concerns}")
            return False, None, review

    async def check_and_post(
        self,
        tweet_text: str,
        post_func,
        context: Optional[str] = None,
        use_suggestion: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """
        Check tweet and post if approved (or use suggestion if allowed).

        Args:
            tweet_text: Original tweet text
            post_func: Async function to call to actually post (e.g., twitter_client.post)
            context: Optional context
            use_suggestion: If True and suggestion provided, post the suggestion

        Returns:
            (posted, final_text)
            - posted: True if tweet was posted
            - final_text: The actual text posted (original or suggestion)
        """
        should_post, suggestion, review = await self.check_post(tweet_text, context)

        if should_post:
            # Approved - post original
            await post_func(tweet_text)
            return True, tweet_text

        elif use_suggestion and suggestion:
            # Needs revision but suggestion available - post suggestion
            logger.info("Using PR Matt's suggested revision")
            await post_func(suggestion)
            return True, suggestion

        else:
            # Blocked or no suggestion - don't post
            logger.warning(f"Tweet not posted. Decision: {review.decision if review else 'unknown'}")
            return False, None


async def test_integration():
    """Test the Twitter integration."""
    import os

    xai_api_key = os.getenv("XAI_API_KEY", "")
    if not xai_api_key:
        print("Error: XAI_API_KEY not set")
        return

    filter = PRMattTwitterFilter(xai_api_key)
    await filter.start()

    # Mock post function
    async def mock_post(text):
        print(f"📤 POSTING: {text}")

    # Test cases
    tweets = [
        "We're shipping continuous improvements to Jarvis. GSD framework is working well.",
        "Fuck this broken code, gonna fix it anyway",
        "BEST AI TRADING BOT EVER! GUARANTEED PROFITS! TO THE MOON! 🚀",
    ]

    for tweet in tweets:
        print(f"\n{'='*80}")
        print(f"Original: {tweet}")
        posted, final_text = await filter.check_and_post(
            tweet,
            mock_post,
            use_suggestion=True
        )
        if posted:
            print(f"✅ Posted: {final_text}")
        else:
            print(f"❌ Blocked")

    await filter.stop()


if __name__ == "__main__":
    asyncio.run(test_integration())
