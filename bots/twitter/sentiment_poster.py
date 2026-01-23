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
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except OSError:
        pass

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bots.twitter.twitter_client import TwitterClient, TwitterCredentials
from bots.twitter.claude_content import ClaudeContentGenerator
from bots.twitter.grok_client import GrokClient
from bots.twitter.autonomous_engine import XMemory
from core.logging.error_tracker import error_tracker

# Import structured logging for comprehensive JSON logs
try:
    from core.logging import get_structured_logger
    STRUCTURED_LOGGING_AVAILABLE = True
except ImportError:
    STRUCTURED_LOGGING_AVAILABLE = False

# Import self-correcting AI system
try:
    from core.self_correcting import (
        get_shared_memory,
        get_message_bus,
        get_ollama_router,
        LearningType,
        MessageType,
        MessagePriority,
        TaskType,
    )
    SELF_CORRECTING_AVAILABLE = True
except ImportError:
    SELF_CORRECTING_AVAILABLE = False
    get_shared_memory = None
    get_message_bus = None
    get_ollama_router = None

# Initialize structured logger if available, fallback to standard logger
if STRUCTURED_LOGGING_AVAILABLE:
    logger = get_structured_logger("jarvis.twitter.sentiment_poster", service="sentiment_poster")
else:
    logger = logging.getLogger(__name__)

# Shared memory for cross-module deduplication
_shared_memory: Optional['XMemory'] = None

def get_shared_memory() -> 'XMemory':
    """Get shared memory instance for deduplication."""
    global _shared_memory
    if _shared_memory is None:
        _shared_memory = XMemory()
    return _shared_memory

# Predictions file from sentiment_report.py
PREDICTIONS_FILE = Path(__file__).parent.parent / "buy_tracker" / "predictions_history.json"

# Legacy state file (read-only)
SENTIMENT_STATE_FILE = Path(__file__).parent / ".sentiment_poster_state.json"


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
        self.grok = GrokClient()  # Fallback for Claude failures
        self.interval_minutes = interval_minutes
        self._running = False
        self._last_post_time: Optional[datetime] = self._load_last_post_time()

        # Initialize self-correcting AI system
        self.memory = None
        self.bus = None
        self.router = None
        if SELF_CORRECTING_AVAILABLE:
            try:
                self.memory = get_shared_memory()
                self.bus = get_message_bus()
                self.router = get_ollama_router()

                # Load past learnings about successful tweets
                past_learnings = self.memory.search_learnings(
                    component="sentiment_poster",
                    learning_type=LearningType.SUCCESS_PATTERN,
                    min_confidence=0.6
                )
                logger.info(f"Loaded {len(past_learnings)} past tweet patterns from memory")

            except Exception as e:
                logger.warning(f"Failed to initialize self-correcting AI: {e}")
                self.memory = None
                self.bus = None
                self.router = None

    def _load_last_post_time(self) -> Optional[datetime]:
        """Load last post time from state file."""
        # Prefer canonical context engine state
        try:
            from core.context_engine import context
            last = context.state.get("last_tweet")
            if last:
                return datetime.fromisoformat(last)
        except Exception:
            pass

        try:
            if SENTIMENT_STATE_FILE.exists():
                with open(SENTIMENT_STATE_FILE, 'r') as f:
                    data = json.load(f)
                    if 'last_post_time' in data:
                        return datetime.fromisoformat(data['last_post_time'])
        except Exception as e:
            error_tracker.track_error(
                e,
                context="SentimentTwitterPoster._load_last_post_time",
                component="sentiment_poster",
                metadata={"state_file": str(SENTIMENT_STATE_FILE)}
            )
            logger.warning(f"Failed to load sentiment state: {e}")
        return None

    def _save_last_post_time(self):
        """Persist last post time to canonical context state."""
        try:
            from core.context_engine import context
            context.record_tweet()
        except Exception as e:
            error_tracker.track_error(
                e,
                context="SentimentTwitterPoster._save_last_post_time",
                component="sentiment_poster"
            )
            logger.warning(f"Failed to record tweet in context state: {e}")

    async def start(self):
        """Start the sentiment poster loop."""
        self._running = True
        logger.info(f"Starting sentiment poster (every {self.interval_minutes} min)")

        # Connect to Twitter
        connected = self.twitter.connect()
        if not connected:
            logger.error("Failed to connect to Twitter")
            return

        # Check if we should skip initial post (posted recently)
        try:
            from core.context_engine import context
            if not context.can_tweet(min_interval_minutes=self.interval_minutes):
                logger.info("Recent tweet detected (context engine), skipping initial sentiment post")
            else:
                logger.info("No recent tweet, posting initial sentiment report")
                await self._post_sentiment_report()
        except Exception:
            # Fallback to local timestamp if context engine unavailable
            if self._last_post_time:
                elapsed = (datetime.now(timezone.utc) - self._last_post_time).total_seconds()
                if elapsed < self.interval_minutes * 60:
                    wait_time = self.interval_minutes * 60 - elapsed
                    logger.info(f"Recent post detected ({elapsed/60:.1f}m ago), waiting {wait_time/60:.1f}m before next")
                else:
                    logger.info("No recent post, posting initial sentiment report")
                    await self._post_sentiment_report()
            else:
                logger.info("First run, posting initial sentiment report")
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
            error_tracker.track_error(
                e,
                context="SentimentTwitterPoster._load_latest_predictions",
                component="sentiment_poster",
                metadata={"predictions_file": str(PREDICTIONS_FILE)}
            )
            logger.error(f"Failed to load predictions: {e}")
            return None

    async def _generate_grok_fallback_tweet(self, bullish: list, bearish: list, top_tokens: list) -> str:
        """Generate tweet using Grok as fallback when Claude is unavailable."""
        try:
            stats = f"{len(bullish)} bullish, {len(bearish)} bearish"
            top_symbol = top_tokens[0]['symbol'].upper() if top_tokens else "SOL"

            prompt = f"""Generate a Twitter post about this microcap sentiment scan.
Stats: {stats} tokens analyzed
Top pick: ${top_symbol}

Tone: Casual, lowercase, direct. Include NFA naturally.
Mention: t.me/kr8tiventry for full analysis
Max 280 chars (single tweet, not a thread)
Return ONLY the tweet text."""

            response = await self.grok.generate_tweet(prompt, max_tokens=100, temperature=0.8)
            if response.success:
                tweet = response.content.strip()
                # Ensure single tweet
                if len(tweet) > 280:
                    tweet = tweet[:277] + "..."
                logger.info(f"Grok fallback generated: {tweet[:80]}...")
                return tweet
        except Exception as e:
            error_tracker.track_error(
                e,
                context="SentimentTwitterPoster._generate_grok_fallback_tweet",
                component="sentiment_poster"
            )
            logger.warning(f"Grok fallback failed: {e}")

        # Ultimate fallback: static template
        return f"grok scan: {len(bullish)} bullish, {len(bearish)} bearish\n\nt.me/kr8tiventry for analysis. NFA 🤖"

    async def _post_sentiment_report(self):
        """Generate and post sentiment report tweet."""
        try:
            if os.getenv("X_BOT_ENABLED", "true").lower() == "false":
                logger.info("X_BOT_ENABLED=false - skipping sentiment post")
                return

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
- Each tweet can be up to 4,000 characters (Premium X)
- Use short contract format: first6...last4 (e.g., 8Lm6vG...pump)
- Lowercase casual energy, no periods at end
- Include NFA naturally
- NO hashtags

Return ONLY a JSON object: {{"tweets": ["tweet1", "tweet2", "tweet3"]}}"""

            response = await self.claude.generate_tweet(prompt, temperature=0.85)

            if not response.success:
                logger.error(f"Claude generation failed: {response.error}")
                # Try Grok fallback for tweet generation
                logger.info("Using Grok fallback for tweet generation...")
                tweet_text = await self._generate_grok_fallback_tweet(bullish, bearish, top_tokens)
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
                    # Try to fix common JSON issues (missing closing brackets)
                    try:
                        data = json.loads(content)
                    except json.JSONDecodeError:
                        # Try adding missing closing brackets
                        fixed = content.rstrip()
                        if not fixed.endswith("}"):
                            fixed += '"]}'
                        elif not fixed.endswith("]}"):
                            fixed += "]}"
                        try:
                            data = json.loads(fixed)
                        except json.JSONDecodeError:
                            # Last resort: extract tweets via regex (up to 4,000 chars for Premium X)
                            import re
                            tweet_matches = re.findall(r'"([^"]{10,4000})"', content)
                            if tweet_matches:
                                tweets = tweet_matches[:3]
                                data = None
                            else:
                                raise
                    tweets = data.get("tweets", [content]) if data else tweets
                else:
                    tweets = [content]
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse failed: {e}, using raw content")
                tweets = [response.content[:4000]]

            # Post tweets as thread
            reply_to = None
            for i, tweet in enumerate(tweets[:3]):
                # Ensure under 4,000 chars (X Premium limit) with word-boundary truncation
                max_chars = 4000
                if len(tweet) > max_chars:
                    truncated = tweet[:max_chars - 3]
                    last_space = truncated.rfind(' ')
                    if last_space > max_chars - 500:
                        tweet = tweet[:last_space] + "..."
                    else:
                        tweet = truncated + "..."
                result = await self._post_tweet(tweet, reply_to=reply_to)
                if result:
                    reply_to = result  # Chain as thread
                    logger.info(f"Posted tweet {i+1}/{len(tweets)}")
                await asyncio.sleep(1)  # Rate limit

            self._last_post_time = datetime.now(timezone.utc)
            self._save_last_post_time()

            # Broadcast sentiment changes to other bots
            if SELF_CORRECTING_AVAILABLE and self.bus and bullish:
                try:
                    for symbol in bullish[:3]:  # Top 3 bullish tokens
                        token_data_item = token_data.get(symbol, {})
                        await self.bus.publish(
                            sender="sentiment_poster",
                            message_type=MessageType.SENTIMENT_CHANGED,
                            data={
                                "token": symbol,
                                "sentiment": "bullish",
                                "score": token_data_item.get("score", 0),
                                "reason": token_data_item.get("reasoning", ""),
                                "contract": token_data_item.get("contract", ""),
                            },
                            priority=MessagePriority.HIGH
                        )
                    logger.info(f"Broadcasted {len(bullish[:3])} bullish sentiments to other bots")
                except Exception as e:
                    logger.error(f"Failed to broadcast sentiments: {e}")

            # Structured log event for sentiment post
            if STRUCTURED_LOGGING_AVAILABLE and hasattr(logger, 'log_event'):
                logger.log_event(
                    "SENTIMENT_POSTED",
                    tweet_count=len(tweets),
                    bullish_count=len(bullish),
                    bearish_count=len(bearish),
                    neutral_count=len(neutral),
                    top_tokens=[t['symbol'] for t in top_tokens[:3]],
                    generator="claude",
                )
            else:
                logger.info(f"Posted sentiment report thread ({len(tweets)} tweets)")

        except Exception as e:
            error_tracker.track_error(
                e,
                context="SentimentTwitterPoster._post_sentiment_report",
                component="sentiment_poster"
            )
            logger.error(f"Failed to post sentiment report: {e}", exc_info=True)

    async def _post_tweet(
        self,
        text: str,
        reply_to: Optional[str] = None
    ) -> Optional[str]:
        """Post a tweet and return the tweet ID."""
        try:
            # Check for duplicate content BEFORE posting (shared with autonomous_engine)
            memory = get_shared_memory()
            is_similar, similar_content = memory.is_similar_to_recent(text, hours=12, threshold=0.4)
            if is_similar and reply_to is None:  # Don't skip thread replies
                logger.warning(f"SKIPPED DUPLICATE (sentiment): Too similar to recent tweet")
                logger.info(f"New: {text[:60]}...")
                logger.info(f"Old: {similar_content[:60] if similar_content else 'N/A'}...")
                return None

            result = await self.twitter.post_tweet(text, reply_to=reply_to)
            if result and result.success:
                # Record to shared memory for cross-module deduplication
                memory.record_tweet(result.tweet_id, text, "sentiment", [])
                return result.tweet_id
            error_tracker.track_error(
                RuntimeError(result.error if result else "unknown error"),
                context="SentimentTwitterPoster._post_tweet",
                component="sentiment_poster"
            )
            logger.error(f"Tweet failed: {result.error if result else 'unknown error'}")
            return None
        except Exception as e:
            error_tracker.track_error(
                e,
                context="SentimentTwitterPoster._post_tweet",
                component="sentiment_poster"
            )
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

    # Create Twitter client using from_env() which correctly prefers JARVIS_ACCESS_TOKEN
    # for posting as @Jarvis_lifeos instead of @aurora_ventures
    twitter = TwitterClient()  # Uses TwitterCredentials.from_env() internally

    # Claude via Anthropic API (supports local Ollama via ANTHROPIC_BASE_URL)
    try:
        from core.llm.anthropic_utils import get_anthropic_api_key
        claude_key = get_anthropic_api_key()
    except Exception:
        claude_key = os.environ.get("ANTHROPIC_API_KEY")
    claude = ClaudeContentGenerator(api_key=claude_key)

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
