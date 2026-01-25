"""
Bot Integration: Enable conversational finance on both X and Telegram bots.

Dexter ReAct agent is available to both bots for answering financial questions.
All responses are powered by Grok sentiment (1.0 weighting).

Usage:
    - X Bot: "Hey @Jarvis_lifeos what's your take on SOL?"
    - Telegram: "Is BTC looking bullish?"
"""

import logging
import asyncio
from typing import Optional, Dict, Any
from functools import wraps

from .agent import DexterAgent, ReActDecision, DecisionType
from .tools.meta_router import financial_research

logger = logging.getLogger(__name__)


def retry_with_backoff(max_retries=3, base_delay=1.0):
    """Retry with exponential backoff for rate limit errors."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if "429" in str(e) or "rate limit" in str(e).lower():
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)
                            jitter = delay * 0.1
                            import random
                            wait_time = delay + (jitter * (2 * random.random() - 1))
                            logger.warning(f"Rate limit hit, retrying in {wait_time:.2f}s (attempt {attempt + 1}/{max_retries})")
                            await asyncio.sleep(wait_time)
                            continue
                    raise
            return None
        return wrapper
    return decorator


class BotFinanceIntegration:
    """Integrates Dexter financial analysis with both X and Telegram bots."""

    def __init__(self, grok_client=None, sentiment_agg=None, position_manager=None):
        """Initialize bot integration."""
        self.grok = grok_client
        self.sentiment_agg = sentiment_agg
        self.position_manager = position_manager
        self.dexter = DexterAgent(grok_client, sentiment_agg)

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    async def process_finance_question(
        self,
        question: str,
        platform: str = "telegram"  # "telegram" or "twitter"
    ) -> str:
        """
        Process a financial question from either platform.

        Uses Dexter ReAct with heavy Grok weighting for analysis.

        Args:
            question: User's financial question
            platform: "telegram" or "twitter"

        Returns:
            Formatted response suitable for the platform
        """
        try:
            # Use meta-router for conversational analysis
            result = await financial_research(
                question,
                self.sentiment_agg,
                self.grok,
                self.position_manager
            )

            # Format response based on platform
            if platform == "twitter":
                return self._format_for_twitter(result)
            else:
                return self._format_for_telegram(result)

        except Exception as e:
            logger.error(f"Error processing finance question: {e}")
            return "❌ Error analyzing query. Please try again."

    async def analyze_trading_opportunity_for_bots(self, symbol: str) -> str:
        """
        Full ReAct analysis of a trading opportunity.

        Can be triggered by both bots for deeper analysis.

        Returns:
            Formatted trading recommendation with Grok weighting
        """
        try:
            decision = await self.dexter.analyze_trading_opportunity(symbol)

            lines = [
                f"🎯 {symbol} Trading Analysis (Grok-Powered)",
                f"Decision: {decision.decision.value}",
                f"Confidence: {decision.confidence:.1f}%",
                f"Grok Sentiment: {decision.grok_sentiment_score:.1f}/100",
                "",
                f"Reasoning: {decision.rationale}",
                "",
                f"Iterations: {decision.iterations} | Cost: ${decision.cost_usd:.4f}",
            ]

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Error in trading analysis: {e}")
            return "Could not complete trading analysis"

    def _format_for_twitter(self, result: Dict[str, Any]) -> str:
        """Format response for X/Twitter (short, tweet-friendly)."""
        response = result.get("response", "")

        # X has character limits - make it concise
        # Keep only first 280 characters for single tweet
        if len(response) > 280:
            # Try to find a good break point
            lines = response.split("\n")
            short_response = ""
            for line in lines:
                if len(short_response) + len(line) + 1 <= 280:
                    short_response += line + "\n"
                else:
                    break

            return short_response.strip() + "..."

        return response

    def _format_for_telegram(self, result: Dict[str, Any]) -> str:
        """Format response for Telegram (can be longer, more detailed)."""
        response = result.get("response", "")

        # Add source attribution
        tools_used = ", ".join(result.get("tools_used", ["analysis"]))
        grok_note = "\n\n🔹 *Grok Powered* (1.0 weighting - Primary decision driver)"

        # Telegram supports markdown
        formatted = response.replace("**", "*")  # Convert markdown ** to *
        formatted += grok_note

        return formatted

    async def handle_telegram_message(self, message: str, user_id: int) -> Optional[str]:
        """
        Handle incoming Telegram messages for financial questions.

        Integrated with the main Telegram bot responder.

        Args:
            message: User message
            user_id: Telegram user ID

        Returns:
            Response text or None if not a finance question
        """
        # Check if this looks like a finance question
        finance_keywords = [
            "token", "price", "sentiment", "bullish", "bearish",
            "buy", "sell", "position", "trade", "crypto", "sol", "btc", "eth",
            "wallet", "portfolio", "should i", "is", "trending", "moon",
            "rug", "pump", "dump", "volume", "liquidity"
        ]

        if not any(kw in message.lower() for kw in finance_keywords):
            return None  # Not a finance question

        # Use Dexter to answer
        response = await self.process_finance_question(message, platform="telegram")
        return response

    async def handle_twitter_mention(self, message: str, mentioned_user: str) -> Optional[str]:
        """
        Handle X/Twitter mentions asking financial questions.

        Integrated with the main X bot responder.

        Args:
            message: Tweet text
            mentioned_user: User who mentioned the bot

        Returns:
            Reply text or None if not appropriate to respond
        """
        # Check if question is directed at Jarvis
        if "jarvis" not in message.lower() and "@Jarvis_lifeos" not in message:
            return None

        # Check if it's a finance question
        finance_keywords = [
            "sentiment", "bullish", "bearish", "buy", "sell", "token",
            "should", "think", "what", "how", "trending", "moon"
        ]

        if not any(kw in message.lower() for kw in finance_keywords):
            return None  # Not a finance question

        # Use Dexter for analysis
        response = await self.process_finance_question(message, platform="twitter")
        return response


# Singleton instance
_bot_integration: Optional[BotFinanceIntegration] = None


def get_bot_finance_integration(
    grok_client=None,
    sentiment_agg=None,
    position_manager=None
) -> BotFinanceIntegration:
    """Get or create bot finance integration singleton."""
    global _bot_integration

    if _bot_integration is None:
        _bot_integration = BotFinanceIntegration(grok_client, sentiment_agg, position_manager)
        logger.info("Bot Finance Integration initialized with Grok-powered ReAct")

    return _bot_integration
