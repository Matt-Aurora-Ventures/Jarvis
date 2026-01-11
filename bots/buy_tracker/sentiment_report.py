"""
Sentiment Report Generator - Automated 10-token sentiment analysis using Grok + indicators.

Posts beautiful sentiment reports to Telegram every 30 minutes.
"""

import asyncio
import logging
import os
import json
import aiohttp
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TokenSentiment:
    """Sentiment data for a single token."""
    symbol: str
    name: str
    price_usd: float
    change_1h: float
    change_24h: float
    volume_24h: float
    mcap: float
    buys_24h: int
    sells_24h: int
    liquidity: float

    # Calculated
    buy_sell_ratio: float = 0.0
    sentiment_score: float = 0.0  # -1 to 1
    sentiment_label: str = "NEUTRAL"
    grok_analysis: str = ""
    grade: str = "C"

    def calculate_sentiment(self):
        """Calculate sentiment from metrics."""
        score = 0.0

        # Price momentum (weight: 30%)
        if self.change_24h > 10:
            score += 0.3
        elif self.change_24h > 5:
            score += 0.2
        elif self.change_24h > 0:
            score += 0.1
        elif self.change_24h > -5:
            score -= 0.1
        elif self.change_24h > -10:
            score -= 0.2
        else:
            score -= 0.3

        # Buy/sell ratio (weight: 40%)
        self.buy_sell_ratio = self.buys_24h / max(self.sells_24h, 1)
        if self.buy_sell_ratio > 2:
            score += 0.4
        elif self.buy_sell_ratio > 1.5:
            score += 0.3
        elif self.buy_sell_ratio > 1.2:
            score += 0.2
        elif self.buy_sell_ratio > 1:
            score += 0.1
        elif self.buy_sell_ratio > 0.8:
            score -= 0.1
        elif self.buy_sell_ratio > 0.5:
            score -= 0.2
        else:
            score -= 0.4

        # Volume health (weight: 20%)
        vol_to_mcap = (self.volume_24h / max(self.mcap, 1)) * 100
        if vol_to_mcap > 50:
            score += 0.2
        elif vol_to_mcap > 20:
            score += 0.1
        elif vol_to_mcap < 5:
            score -= 0.1

        # Liquidity (weight: 10%)
        if self.liquidity > 100000:
            score += 0.1
        elif self.liquidity > 50000:
            score += 0.05
        elif self.liquidity < 10000:
            score -= 0.1

        self.sentiment_score = max(-1, min(1, score))

        # Label
        if self.sentiment_score > 0.3:
            self.sentiment_label = "BULLISH"
            self.grade = "A" if self.sentiment_score > 0.5 else "B+"
        elif self.sentiment_score > 0.1:
            self.sentiment_label = "SLIGHTLY BULLISH"
            self.grade = "B"
        elif self.sentiment_score > -0.1:
            self.sentiment_label = "NEUTRAL"
            self.grade = "C+"
        elif self.sentiment_score > -0.3:
            self.sentiment_label = "SLIGHTLY BEARISH"
            self.grade = "C"
        else:
            self.sentiment_label = "BEARISH"
            self.grade = "D" if self.sentiment_score > -0.5 else "F"


class SentimentReportGenerator:
    """
    Generates and posts sentiment reports using Grok AI + technical indicators.
    """

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        xai_api_key: str,
        interval_minutes: int = 30,
    ):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.xai_api_key = xai_api_key
        self.interval_minutes = interval_minutes
        self._running = False
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self):
        """Start the sentiment report scheduler."""
        self._running = True
        self._session = aiohttp.ClientSession()

        logger.info(f"Starting sentiment report generator (every {self.interval_minutes} min)")

        # Post initial report
        await self.generate_and_post_report()

        # Schedule loop
        while self._running:
            await asyncio.sleep(self.interval_minutes * 60)
            if self._running:
                await self.generate_and_post_report()

    async def stop(self):
        """Stop the generator."""
        self._running = False
        if self._session:
            await self._session.close()

    async def generate_and_post_report(self):
        """Generate sentiment report and post to Telegram."""
        try:
            # Get top 10 tokens
            tokens = await self._get_trending_tokens(limit=10)

            if not tokens:
                logger.warning("No tokens found for sentiment report")
                return

            # Calculate sentiment for each
            for token in tokens:
                token.calculate_sentiment()

            # Get Grok analysis for top movers
            top_movers = sorted(tokens, key=lambda t: abs(t.change_24h), reverse=True)[:3]
            grok_summary = await self._get_grok_analysis(top_movers)

            # Format report
            report = self._format_report(tokens, grok_summary)

            # Post to Telegram
            await self._post_to_telegram(report)

            logger.info(f"Posted sentiment report with {len(tokens)} tokens")

        except Exception as e:
            logger.error(f"Failed to generate sentiment report: {e}")

    async def _get_trending_tokens(self, limit: int = 10) -> List[TokenSentiment]:
        """Get trending Solana tokens from DexScreener."""
        tokens = []

        try:
            # Get trending on Solana
            url = "https://api.dexscreener.com/latest/dex/tokens/solana"

            # Use search for popular tokens instead
            searches = ["SOL", "BONK", "WIF", "JUP", "PYTH", "RAY", "ORCA", "MNGO", "KR8TIV", "JTO"]

            for symbol in searches[:limit]:
                try:
                    async with self._session.get(
                        f"https://api.dexscreener.com/latest/dex/search?q={symbol}"
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            pairs = data.get("pairs", [])

                            # Find Solana pair
                            for pair in pairs:
                                if pair.get("chainId") == "solana":
                                    base = pair.get("baseToken", {})
                                    txns = pair.get("txns", {}).get("h24", {})

                                    token = TokenSentiment(
                                        symbol=base.get("symbol", symbol),
                                        name=base.get("name", symbol),
                                        price_usd=float(pair.get("priceUsd", 0)),
                                        change_1h=pair.get("priceChange", {}).get("h1", 0) or 0,
                                        change_24h=pair.get("priceChange", {}).get("h24", 0) or 0,
                                        volume_24h=pair.get("volume", {}).get("h24", 0) or 0,
                                        mcap=pair.get("marketCap", 0) or pair.get("fdv", 0) or 0,
                                        buys_24h=txns.get("buys", 0),
                                        sells_24h=txns.get("sells", 0),
                                        liquidity=pair.get("liquidity", {}).get("usd", 0) or 0,
                                    )
                                    tokens.append(token)
                                    break

                except Exception as e:
                    logger.debug(f"Failed to fetch {symbol}: {e}")

                await asyncio.sleep(0.2)  # Rate limit

        except Exception as e:
            logger.error(f"Failed to get trending tokens: {e}")

        return tokens

    async def _get_grok_analysis(self, tokens: List[TokenSentiment]) -> str:
        """Get AI analysis from Grok (xAI)."""
        if not self.xai_api_key:
            return "AI analysis unavailable"

        try:
            # Prepare context
            token_summary = "\n".join([
                f"- {t.symbol}: ${t.price_usd:.6f}, {t.change_24h:+.1f}% 24h, "
                f"B/S ratio: {t.buy_sell_ratio:.2f}, Vol: ${t.volume_24h:,.0f}"
                for t in tokens
            ])

            prompt = f"""Analyze these Solana tokens briefly (2-3 sentences total). Focus on which shows strongest momentum and any risks:

{token_summary}

Be concise and actionable. No disclaimers needed."""

            async with self._session.post(
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.xai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "grok-3",
                    "messages": [
                        {"role": "system", "content": "You are a crypto analyst. Be brief and direct."},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 150,
                    "temperature": 0.7,
                }
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    logger.error(f"Grok API error: {resp.status}")

        except Exception as e:
            logger.error(f"Grok analysis failed: {e}")

        return "AI analysis temporarily unavailable"

    def _format_report(self, tokens: List[TokenSentiment], grok_summary: str) -> str:
        """Format beautiful sentiment report."""
        now = datetime.utcnow()

        # Sort by sentiment score
        tokens_sorted = sorted(tokens, key=lambda t: t.sentiment_score, reverse=True)

        # Header
        lines = [
            "<b>========================================</b>",
            "<b>     JARVIS SENTIMENT REPORT</b>",
            "<b>========================================</b>",
            f"<i>{now.strftime('%B %d, %Y')} | {now.strftime('%H:%M')} UTC</i>",
            "",
            "<b>TOP 10 SOLANA TOKENS</b>",
            "<b>________________________________________</b>",
            "",
        ]

        # Token rows
        for i, t in enumerate(tokens_sorted, 1):
            # Sentiment emoji
            if t.sentiment_score > 0.3:
                emoji = "🟢"
            elif t.sentiment_score > 0:
                emoji = "🟡"
            elif t.sentiment_score > -0.3:
                emoji = "🟠"
            else:
                emoji = "🔴"

            # Trend arrow
            if t.change_24h > 5:
                trend = "+++"
            elif t.change_24h > 0:
                trend = "++"
            elif t.change_24h > -5:
                trend = "--"
            else:
                trend = "---"

            # Format price
            if t.price_usd >= 1:
                price_str = f"${t.price_usd:,.2f}"
            elif t.price_usd >= 0.01:
                price_str = f"${t.price_usd:.4f}"
            else:
                price_str = f"${t.price_usd:.6f}"

            lines.append(
                f"{emoji} <b>{i}. {t.symbol}</b>  {t.grade}\n"
                f"   {price_str}  <code>{t.change_24h:+.1f}%</code> {trend}\n"
                f"   B/S: <code>{t.buy_sell_ratio:.2f}x</code> | Vol: <code>${t.volume_24h/1000:.0f}K</code>"
            )
            lines.append("")

        # Summary stats
        bullish_count = sum(1 for t in tokens if t.sentiment_score > 0.1)
        bearish_count = sum(1 for t in tokens if t.sentiment_score < -0.1)
        neutral_count = len(tokens) - bullish_count - bearish_count

        avg_change = sum(t.change_24h for t in tokens) / len(tokens)

        lines.extend([
            "<b>________________________________________</b>",
            "",
            "<b>MARKET SUMMARY</b>",
            f"   🟢 Bullish:  <code>{bullish_count}</code>",
            f"   🟡 Neutral:  <code>{neutral_count}</code>",
            f"   🔴 Bearish:  <code>{bearish_count}</code>",
            f"   Avg 24h:    <code>{avg_change:+.1f}%</code>",
            "",
            "<b>________________________________________</b>",
            "",
            "<b>AI ANALYSIS (Grok)</b>",
            f"<i>{grok_summary}</i>",
            "",
            "<b>========================================</b>",
            "<i>Powered by JARVIS AI | NFA</i>",
        ])

        return "\n".join(lines)

    async def _post_to_telegram(self, report: str):
        """Post report to Telegram."""
        try:
            async with self._session.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                data={
                    "chat_id": self.chat_id,
                    "text": report,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": "true",
                }
            ) as resp:
                result = await resp.json()
                if not result.get("ok"):
                    logger.error(f"Telegram error: {result}")

        except Exception as e:
            logger.error(f"Failed to post to Telegram: {e}")


async def run_sentiment_reporter():
    """Run the sentiment report generator."""
    from pathlib import Path

    # Load env
    env_path = Path(__file__).resolve().parents[2] / "tg_bot" / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_BUY_BOT_CHAT_ID")
    xai_key = os.environ.get("XAI_API_KEY")

    if not all([bot_token, chat_id]):
        print("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_BUY_BOT_CHAT_ID")
        return

    generator = SentimentReportGenerator(
        bot_token=bot_token,
        chat_id=chat_id,
        xai_api_key=xai_key,
        interval_minutes=30,
    )

    try:
        await generator.start()
    except KeyboardInterrupt:
        await generator.stop()


if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_sentiment_reporter())
