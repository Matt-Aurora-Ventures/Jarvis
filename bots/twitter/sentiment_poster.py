"""
Sentiment Report Twitter Poster
Posts Grok sentiment reports to Twitter every 30 minutes using Claude voice.

Flow:
1. Get sentiment data from Grok (via sentiment_report.py)
2. Use Claude (Voice Bible) to write tweet in Jarvis voice
3. Post to Twitter as @Jarvis_lifeos
"""

import os
import sys
import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

# Fix Windows encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bots.twitter.twitter_client import TwitterClient, TwitterCredentials
from bots.twitter.claude_content import ClaudeContentGenerator

logger = logging.getLogger(__name__)

# Predictions file from sentiment_report.py
PREDICTIONS_FILE = Path(__file__).parent.parent / "buy_tracker" / "predictions_history.json"


class SentimentTwitterPoster:
    """
    Posts Grok sentiment reports to Twitter using Claude voice.
    Only posts when Grok sentiment is available.
    """

    def __init__(
        self,
        twitter_client: TwitterClient,
        claude_client: ClaudeContentGenerator,
        interval_minutes: int = 30,
    ):
        self.twitter = twitter_client
        self.claude = claude_client
        self.interval_minutes = interval_minutes
        self._running = False
        self._last_post_time: Optional[datetime] = None

    async def start(self):
        """Start the sentiment poster loop."""
        self._running = True
        logger.info(f"Starting sentiment poster (every {self.interval_minutes} min)")

        # Connect to Twitter
        connected = self.twitter.connect()
        if not connected:
            logger.error("Failed to connect to Twitter")
            return

        # Initial post
        await self._post_sentiment_report()

        # Schedule loop
        while self._running:
            await asyncio.sleep(self.interval_minutes * 60)
            if self._running:
                await self._post_sentiment_report()

    async def stop(self):
        """Stop the poster."""
        self._running = False
        self.twitter.disconnect()

    def _load_latest_predictions(self) -> Optional[Dict[str, Any]]:
        """Load the latest predictions from sentiment_report.py."""
        try:
            if not PREDICTIONS_FILE.exists():
                logger.warning("No predictions file found")
                return None

            with open(PREDICTIONS_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)

            if not history:
                return None

            # Get latest prediction
            latest = history[-1]

            # Check if it has Grok sentiment data
            token_predictions = latest.get("token_predictions", {})
            if not token_predictions:
                logger.warning("No Grok token predictions in latest data")
                return None

            # Check if any tokens have verdicts
            has_verdicts = any(
                t.get("verdict") for t in token_predictions.values()
            )
            if not has_verdicts:
                logger.warning("No Grok verdicts in predictions - skipping post")
                return None

            return latest

        except Exception as e:
            logger.error(f"Failed to load predictions: {e}")
            return None

    async def _post_sentiment_report(self):
        """Generate and post sentiment report tweet."""
        try:
            # Load latest predictions
            predictions = self._load_latest_predictions()
            if not predictions:
                logger.info("No valid Grok sentiment data - skipping post")
                return

            # Build sentiment data for Claude
            token_data = predictions.get("token_predictions", {})

            # Count sentiments
            bullish = [s for s, d in token_data.items() if d.get("verdict") == "BULLISH"]
            bearish = [s for s, d in token_data.items() if d.get("verdict") == "BEARISH"]
            neutral = [s for s, d in token_data.items() if d.get("verdict") == "NEUTRAL"]

            # Get top performers with full data
            top_tokens = []
            for symbol, data in token_data.items():
                if data.get("verdict") == "BULLISH":
                    top_tokens.append({
                        "symbol": symbol,
                        "reasoning": data.get("reasoning", ""),
                        "contract": data.get("contract", ""),
                        "targets": data.get("targets", ""),
                        "score": data.get("score", 0),
                    })
            # Sort by score
            top_tokens.sort(key=lambda x: x.get("score", 0), reverse=True)

            # Build context for Claude with contract addresses
            sentiment_summary = f"""
Grok's Solana Microcap Scan:

Stats: {len(bullish)} bullish | {len(bearish)} bearish | {len(neutral)} neutral

TOP BULLISH PICKS:
"""
            for i, t in enumerate(top_tokens[:3], 1):
                contract = t['contract']
                short_ca = f"{contract[:6]}...{contract[-4:]}" if len(contract) > 10 else contract
                sentiment_summary += f"""
{i}. ${t['symbol'].upper()}
   Why: {t['reasoning']}
   CA: {short_ca}
   Targets: {t['targets']}
"""

            # Add bearish warnings
            if bearish:
                sentiment_summary += f"\nBEARISH (avoid): {', '.join(bearish[:3])}"

            # Generate tweet with Claude (Voice Bible)
            prompt = f"""Generate a Twitter thread (2-3 tweets) from this Grok sentiment analysis.

SENTIMENT DATA:
{sentiment_summary}

STRUCTURE:
Tweet 1: Hook about the market vibe + summary (X bullish, Y bearish). mention "big bro grok"
Tweet 2: Top 2 bullish picks with SHORT contract addresses (format: abc123...wxyz)
Tweet 3: Closing with NFA, telegram link (t.me/kr8tiventry) for full report

CRITICAL RULES:
- Each tweet MUST be under 280 characters
- Use short contract format: first6...last4 (e.g., 8Lm6vG...pump)
- Lowercase casual energy, no periods at end
- Include NFA naturally
- NO hashtags

Return ONLY a JSON object: {{"tweets": ["tweet1", "tweet2", "tweet3"]}}"""

            response = await self.claude.generate_tweet(prompt, temperature=0.85)

            if not response.success:
                logger.error(f"Claude generation failed: {response.error}")
                # Fallback tweet with data
                if top_tokens:
                    t = top_tokens[0]
                    ca_short = f"{t['contract'][:6]}...{t['contract'][-4:]}" if t['contract'] else ""
                    tweet_text = f"grok scan: {len(bullish)} bullish, {len(bearish)} bearish\n\nwatching ${t['symbol'].lower()}\nca: {ca_short}\n\nt.me/kr8tiventry for full. NFA 🤖"
                else:
                    tweet_text = f"grok scan: {len(bullish)} bullish, {len(bearish)} bearish\n\nt.me/kr8tiventry for full report. NFA 🤖"
                await self._post_tweet(tweet_text)
                return

            # Parse JSON response
            try:
                content = response.content.strip()
                # Remove markdown code blocks if present
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]
                    content = content.strip()

                if content.startswith("{"):
                    data = json.loads(content)
                    tweets = data.get("tweets", [content])
                else:
                    tweets = [content]
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse failed: {e}, using raw content")
                tweets = [response.content[:280]]

            # Post tweets as thread
            reply_to = None
            for i, tweet in enumerate(tweets[:3]):
                # Ensure under 280
                if len(tweet) > 280:
                    tweet = tweet[:277] + "..."
                result = await self._post_tweet(tweet, reply_to=reply_to)
                if result:
                    reply_to = result  # Chain as thread
                    logger.info(f"Posted tweet {i+1}/{len(tweets)}")
                await asyncio.sleep(1)  # Rate limit

            self._last_post_time = datetime.now(timezone.utc)
            logger.info(f"Posted sentiment report thread ({len(tweets)} tweets)")

        except Exception as e:
            logger.error(f"Failed to post sentiment report: {e}", exc_info=True)

    async def _post_tweet(
        self,
        text: str,
        reply_to: Optional[str] = None
    ) -> Optional[str]:
        """Post a tweet and return the tweet ID."""
        try:
            result = await self.twitter.post_tweet(text, reply_to_id=reply_to)
            if result.get("success"):
                return result.get("tweet_id")
            else:
                logger.error(f"Tweet failed: {result.get('error')}")
                return None
        except Exception as e:
            logger.error(f"Tweet error: {e}")
            return None


async def run_sentiment_poster():
    """Run the sentiment Twitter poster."""
    # Load env from twitter bot folder
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())

    # Also load from tg_bot for XAI key
    tg_env = Path(__file__).parent.parent.parent / "tg_bot" / ".env"
    if tg_env.exists():
        with open(tg_env) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())

    # Create Twitter client
    creds = TwitterCredentials(
        api_key=os.environ.get("X_API_KEY", ""),
        api_secret=os.environ.get("X_API_SECRET", ""),
        access_token=os.environ.get("X_ACCESS_TOKEN", ""),
        access_token_secret=os.environ.get("X_ACCESS_TOKEN_SECRET", ""),
        bearer_token=os.environ.get("X_BEARER_TOKEN", ""),
        oauth2_client_id=os.environ.get("X_OAUTH2_CLIENT_ID", ""),
        oauth2_client_secret=os.environ.get("X_OAUTH2_CLIENT_SECRET", ""),
        oauth2_access_token=os.environ.get("X_OAUTH2_ACCESS_TOKEN", ""),
        oauth2_refresh_token=os.environ.get("X_OAUTH2_REFRESH_TOKEN", ""),
    )

    twitter = TwitterClient(creds)

    # Create Claude client
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if not anthropic_key:
        # Try to get from global env
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

    claude = ClaudeContentGenerator(api_key=anthropic_key)

    # Create and run poster
    poster = SentimentTwitterPoster(
        twitter_client=twitter,
        claude_client=claude,
        interval_minutes=30,
    )

    try:
        await poster.start()
    except KeyboardInterrupt:
        await poster.stop()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )
    asyncio.run(run_sentiment_poster())
