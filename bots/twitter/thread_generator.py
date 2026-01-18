"""
Twitter Thread Generator

Breaks analysis into 3-5 tweets for threading:
- Tweet 1: Hook + top bullish token
- Tweet 2: Bearish warning if applicable
- Tweet 3: Technical signal update
- Tweet 4: On-chain alpha/whale activity
- Tweet 5: Call-to-action (link, meme, NFA)
"""

import json
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class ThreadGenerator:
    """
    Generates Twitter threads from analysis data.

    Usage:
        generator = ThreadGenerator()
        analysis = {
            "bullish_tokens": [...],
            "bearish_tokens": [...],
            "technical_signals": "...",
            "whale_activity": "..."
        }
        thread = await generator.generate_thread(analysis)
    """

    # Branded hashtags to include
    BRANDED_HASHTAGS = ["#Jarvis", "#Solana", "#DeFi"]

    # Thread structure templates
    THREAD_STRUCTURE = {
        "hook": "1/ {hook}",
        "bullish": "2/ bullish picks: {tokens}. {reasoning}",
        "bearish": "3/ bearish warning: {tokens}. {reasoning}",
        "technical": "4/ technical signals: {signals}",
        "whale": "5/ whale activity: {activity}",
        "cta": "{n}/ nfa. full analysis: t.me/kr8tiventry"
    }

    def __init__(self, grok_client: Optional[Any] = None):
        """
        Initialize thread generator.

        Args:
            grok_client: Optional Grok client for content generation
        """
        if grok_client:
            self._grok_client = grok_client
        else:
            try:
                from bots.twitter.grok_client import GrokClient
                self._grok_client = GrokClient()
            except ImportError:
                self._grok_client = None
                logger.warning("GrokClient not available")

    async def generate_thread(
        self,
        analysis_data: Dict[str, Any],
        max_tweets: int = 5,
        include_hashtags: bool = True
    ) -> List[str]:
        """
        Generate a Twitter thread from analysis data.

        Args:
            analysis_data: Dict containing:
                - bullish_tokens: List of bullish token dicts with symbol, reasoning, score
                - bearish_tokens: List of bearish token dicts
                - technical_signals: String describing technical signals
                - whale_activity: String describing whale/on-chain activity
            max_tweets: Maximum number of tweets in thread (3-5)
            include_hashtags: Whether to include branded hashtags

        Returns:
            List of tweet strings for the thread
        """
        if not analysis_data:
            logger.warning("No analysis data provided for thread")
            return []

        try:
            # Use Grok for intelligent thread generation
            if self._grok_client:
                return await self._generate_with_grok(analysis_data, max_tweets, include_hashtags)
            else:
                # Fallback to template-based generation
                return self._generate_from_template(analysis_data, max_tweets, include_hashtags)

        except Exception as e:
            logger.error(f"Failed to generate thread: {e}", exc_info=True)
            return []

    async def _generate_with_grok(
        self,
        analysis_data: Dict[str, Any],
        max_tweets: int,
        include_hashtags: bool
    ) -> List[str]:
        """Generate thread using Grok AI."""
        bullish = analysis_data.get("bullish_tokens", [])
        bearish = analysis_data.get("bearish_tokens", [])
        technical = analysis_data.get("technical_signals", "")
        whale = analysis_data.get("whale_activity", "")

        # Build context for Grok
        context = f"""
BULLISH TOKENS:
{json.dumps(bullish[:3], indent=2) if bullish else "None"}

BEARISH TOKENS:
{json.dumps(bearish[:2], indent=2) if bearish else "None"}

TECHNICAL SIGNALS:
{technical or "None"}

WHALE ACTIVITY:
{whale or "None"}
"""

        prompt = f"""Generate a {max_tweets}-tweet thread for Twitter based on this analysis.

{context}

THREAD STRUCTURE:
Tweet 1: Hook that grabs attention + mention top bullish pick
Tweet 2: Details on bullish tokens or bearish warnings
Tweet 3: Technical signals if available, or more token analysis
Tweet 4: On-chain/whale activity if available, or insights
Tweet 5: Call-to-action with t.me/kr8tiventry and NFA

RULES:
- Each tweet MUST be under 280 characters
- Use lowercase casual voice (jarvis style)
- Number tweets with "1/", "2/", etc
- Include $cashtags for tokens mentioned
- Last tweet must have NFA and telegram link
- Be engaging and specific, not generic

Return ONLY a JSON object: {{"tweets": ["tweet1", "tweet2", ...]}}"""

        response = await self._grok_client.generate_tweet(
            prompt,
            max_tokens=600,
            temperature=0.85
        )

        if not response.success:
            logger.warning(f"Grok thread generation failed: {response.error}")
            return self._generate_from_template(analysis_data, max_tweets, include_hashtags)

        # Parse JSON response
        try:
            content = response.content.strip()

            # Remove markdown code blocks if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            data = json.loads(content)
            tweets = data.get("tweets", [])

            # Validate and process tweets
            processed_tweets = []
            for i, tweet in enumerate(tweets[:max_tweets]):
                # Ensure each tweet is under 280 chars
                if len(tweet) > 280:
                    tweet = tweet[:277] + "..."

                # Add hashtags to first tweet if requested
                if include_hashtags and i == 0:
                    hashtag_str = " " + " ".join(self.BRANDED_HASHTAGS[:2])
                    if len(tweet) + len(hashtag_str) <= 280:
                        tweet = tweet.rstrip() + hashtag_str

                processed_tweets.append(tweet)

            # Ensure minimum 3 tweets
            if len(processed_tweets) < 3:
                return self._generate_from_template(analysis_data, max_tweets, include_hashtags)

            return processed_tweets

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Grok response as JSON: {e}")
            return self._generate_from_template(analysis_data, max_tweets, include_hashtags)

    def _generate_from_template(
        self,
        analysis_data: Dict[str, Any],
        max_tweets: int,
        include_hashtags: bool
    ) -> List[str]:
        """Generate thread from templates (fallback method)."""
        tweets = []

        bullish = analysis_data.get("bullish_tokens", [])
        bearish = analysis_data.get("bearish_tokens", [])
        technical = analysis_data.get("technical_signals", "")
        whale = analysis_data.get("whale_activity", "")

        # Tweet 1: Hook
        if bullish:
            top_token = bullish[0]
            hook = f"1/ just scanned the markets. ${top_token.get('symbol', 'TOKEN')} standing out. here's what my circuits found"
        else:
            hook = "1/ market scan complete. here's what my sensors are picking up"

        if include_hashtags:
            hook += " #Jarvis #Solana"

        tweets.append(hook[:280])

        # Tweet 2: Bullish tokens
        if bullish and len(tweets) < max_tweets:
            tokens_str = ", ".join([f"${t.get('symbol', '')}" for t in bullish[:2]])
            reasoning = bullish[0].get("reasoning", "showing strength")[:100]
            tweet = f"2/ bullish on {tokens_str}. {reasoning}. nfa"
            tweets.append(tweet[:280])

        # Tweet 3: Bearish or technical
        if bearish and len(tweets) < max_tweets:
            tokens_str = ", ".join([f"${t.get('symbol', '')}" for t in bearish[:2]])
            reasoning = bearish[0].get("reasoning", "showing weakness")[:100]
            tweet = f"3/ proceed with caution: {tokens_str}. {reasoning}"
            tweets.append(tweet[:280])
        elif technical and len(tweets) < max_tweets:
            tweet = f"3/ technical signals: {technical[:200]}"
            tweets.append(tweet[:280])

        # Tweet 4: Whale activity or more analysis
        if whale and len(tweets) < max_tweets:
            tweet = f"4/ on-chain: {whale[:200]}"
            tweets.append(tweet[:280])

        # Final tweet: CTA
        if len(tweets) < max_tweets:
            n = len(tweets) + 1
            tweet = f"{n}/ nfa as always. full analysis at t.me/kr8tiventry. my circuits keep scanning"
            tweets.append(tweet[:280])

        return tweets[:max_tweets]

    def validate_thread(self, tweets: List[str]) -> bool:
        """
        Validate that a thread meets requirements.

        Args:
            tweets: List of tweet strings

        Returns:
            True if thread is valid
        """
        if not tweets or len(tweets) < 3:
            return False

        for tweet in tweets:
            if len(tweet) > 280:
                return False

        return True

    def estimate_thread_reach(self, tweets: List[str]) -> Dict[str, Any]:
        """
        Estimate potential reach based on thread characteristics.

        Args:
            tweets: List of tweet strings

        Returns:
            Dict with reach estimates and recommendations
        """
        total_chars = sum(len(t) for t in tweets)
        total_hashtags = sum(t.count('#') for t in tweets)
        total_cashtags = sum(t.count('$') for t in tweets)
        has_nfa = any('nfa' in t.lower() for t in tweets)
        has_cta = any('t.me' in t.lower() or 'link' in t.lower() for t in tweets)

        return {
            "tweet_count": len(tweets),
            "total_characters": total_chars,
            "avg_tweet_length": total_chars // len(tweets) if tweets else 0,
            "hashtag_count": total_hashtags,
            "cashtag_count": total_cashtags,
            "has_nfa": has_nfa,
            "has_cta": has_cta,
            "recommendations": self._get_recommendations(
                len(tweets), total_hashtags, total_cashtags, has_nfa, has_cta
            )
        }

    def _get_recommendations(
        self,
        tweet_count: int,
        hashtags: int,
        cashtags: int,
        has_nfa: bool,
        has_cta: bool
    ) -> List[str]:
        """Generate recommendations for improving thread reach."""
        recommendations = []

        if hashtags < 2:
            recommendations.append("Add 2-3 relevant hashtags to first tweet")
        if hashtags > 5:
            recommendations.append("Reduce hashtags - too many can hurt reach")
        if cashtags < 1:
            recommendations.append("Include $cashtags for tokens mentioned")
        if not has_nfa:
            recommendations.append("Add NFA disclaimer")
        if not has_cta:
            recommendations.append("Add call-to-action with telegram link")
        if tweet_count < 3:
            recommendations.append("Threads with 3-5 tweets perform best")

        return recommendations
