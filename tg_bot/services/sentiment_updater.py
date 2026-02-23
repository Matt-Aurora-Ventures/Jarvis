"""
Sentiment Hub Updater - Background Service for US-002

Fetches and caches sentiment data every 15 minutes for the Sentiment Hub UI.

Data Sources:
- Grok Top 10 Picks (from existing sentiment report generator)
- Macro Economic Analysis (traditional markets, precious metals)
- Treasury Positions (live PnL from positions.json)
- Bags.fm Graduations (recent graduations)

Cache File: ~/.lifeos/trading/demo_sentiment_hub.json

Architecture:
- Runs as async background task in supervisor
- 15-minute update interval
- Writes all data to single JSON file
- UI reads from cache (instant load)
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import traceback

logger = logging.getLogger(__name__)

# Cache file path
SENTIMENT_HUB_FILE = Path.home() / ".lifeos" / "trading" / "demo_sentiment_hub.json"


# =============================================================================
# Data Fetchers
# =============================================================================

async def fetch_grok_top_picks(xai_api_key: str) -> List[Dict[str, Any]]:
    """
    Fetch top 10 token picks from Grok sentiment analysis.

    Returns:
        List of picks with symbol, grade, target, reasoning, sentiment
    """
    try:
        import aiohttp
        from bots.buy_tracker.sentiment_report import SentimentReportGenerator
        from dataclasses import asdict

        # Create temp session
        async with aiohttp.ClientSession() as session:
            # Create temp instance to fetch token data
            reporter = SentimentReportGenerator(
                bot_token="",  # Not needed for data fetching
                chat_id="",
                xai_api_key=xai_api_key,
                interval_minutes=15,
            )
            reporter._session = session

            # Get trending tokens
            tokens = await reporter._get_trending_tokens(limit=10)

            # Get Grok analysis for tokens
            if tokens and xai_api_key:
                await reporter._get_grok_token_scores(tokens)

            # Convert to dicts for JSON serialization
            picks = []
            for token in tokens:
                pick = {
                    "symbol": token.symbol,
                    "name": token.name,
                    "price_usd": token.price_usd,
                    "change_24h": token.change_24h,
                    "grade": token.grade,
                    "sentiment_label": token.sentiment_label,
                    "sentiment_score": token.sentiment_score,
                    "grok_reasoning": token.grok_reasoning,
                    "grok_analysis": token.grok_analysis,
                    "grok_verdict": token.grok_verdict,
                    "grok_target_safe": token.grok_target_safe,
                    "grok_target_med": token.grok_target_med,
                    "grok_target_degen": token.grok_target_degen,
                    "contract_address": token.contract_address,
                    "buy_sell_ratio": token.buy_sell_ratio,
                    "volume_24h": token.volume_24h,
                    "mcap": token.mcap,
                }
                picks.append(pick)

            return picks

    except Exception as e:
        logger.error(f"Failed to fetch Grok picks: {e}")
        logger.error(traceback.format_exc())
        return []


async def fetch_macro_analysis(xai_api_key: str) -> Dict[str, Any]:
    """
    Fetch macro economic analysis from Grok.

    Returns:
        {
            "short_term": "...",
            "medium_term": "...",
            "long_term": "...",
            "key_events": ["Event 1", "Event 2"],
        }
    """
    try:
        import aiohttp
        from bots.buy_tracker.sentiment_report import SentimentReportGenerator
        from dataclasses import asdict

        # Create temp session
        async with aiohttp.ClientSession() as session:
            # Create temp instance
            reporter = SentimentReportGenerator(
                bot_token="",
                chat_id="",
                xai_api_key=xai_api_key,
                interval_minutes=15,
            )
            reporter._session = session

            # Get macro analysis
            macro = await reporter._get_macro_analysis()

            # Convert to dict
            return {
                "short_term": macro.short_term,
                "medium_term": macro.medium_term,
                "long_term": macro.long_term,
                "key_events": macro.key_events,
            }

    except Exception as e:
        logger.error(f"Failed to fetch macro analysis: {e}")
        logger.error(traceback.format_exc())
        return {
            "short_term": "",
            "medium_term": "",
            "long_term": "",
            "key_events": [],
        }


async def fetch_treasury_positions() -> List[Dict[str, Any]]:
    """
    Fetch current treasury positions with live PnL.

    Returns:
        List of positions with symbol, entry, current, pnl, pnl_pct
    """
    try:
        # Import position loader
        from tg_bot.services.order_monitor import load_positions

        positions = load_positions()

        # Filter to only open positions
        active = [p for p in positions if p.get("status") == "open"]

        # Calculate live PnL for each
        results = []
        for pos in active:
            entry_price = float(pos.get("entry_price", 0) or 0)
            current_price = float(pos.get("current_price", 0) or 0)
            amount = float(pos.get("amount", 0) or 0)

            if entry_price > 0 and current_price > 0:
                pnl_pct = ((current_price - entry_price) / entry_price) * 100
                pnl_usd = (current_price - entry_price) * amount

                results.append({
                    "symbol": pos.get("symbol", "UNKNOWN"),
                    "address": pos.get("address"),
                    "entry_price": entry_price,
                    "current_price": current_price,
                    "amount": amount,
                    "amount_sol": pos.get("amount_sol", 0),
                    "pnl_usd": pnl_usd,
                    "pnl_pct": pnl_pct,
                    "tp_price": pos.get("tp_price", 0),
                    "sl_price": pos.get("sl_price", 0),
                })

        return results

    except Exception as e:
        logger.error(f"Failed to fetch treasury positions: {e}")
        return []


async def fetch_bags_graduations() -> List[Dict[str, Any]]:
    """
    Fetch recent bags.fm graduations via DexScreener (Meteora pairs).

    Returns:
        List of recent graduations with symbol, time, liquidity
    """
    try:
        import aiohttp
        from datetime import timedelta

        url = "https://api.dexscreener.com/latest/dex/search?q=meteora"
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        cutoff_ms = int(cutoff.timestamp() * 1000)

        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()

        pairs = data.get("pairs", []) or []
        results = []
        for pair in pairs[:30]:
            created_ms = pair.get("pairCreatedAt", 0) or 0
            if created_ms < cutoff_ms:
                continue
            base = pair.get("baseToken", {}) or {}
            symbol = base.get("symbol", "?")
            liquidity = (pair.get("liquidity", {}) or {}).get("usd", 0) or 0
            created_dt = datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc)
            results.append({
                "symbol": symbol,
                "address": base.get("address", ""),
                "liquidity_usd": round(liquidity, 2),
                "created_at": created_dt.isoformat(),
                "chain": "solana",
            })

        # Add score + time fields expected by demo_sentiment.py display
        import math
        for r in results:
            liq = r.get("liquidity_usd", 0) or 0
            # Log-scale liquidity to a 0-100 score ($10 → ~20, $10k → ~67, $1M → ~100)
            r["score"] = min(100, int(math.log10(max(liq, 1)) * 16.67))
            r["time"] = r.get("created_at", "")[:10]  # YYYY-MM-DD

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:10]

    except Exception as e:
        logger.error(f"Failed to fetch bags graduations: {e}")
        return []


# =============================================================================
# Cache Manager
# =============================================================================

def save_sentiment_hub_data(data: Dict[str, Any]):
    """Save sentiment hub data to cache file."""
    try:
        SENTIMENT_HUB_FILE.parent.mkdir(parents=True, exist_ok=True)

        with open(SENTIMENT_HUB_FILE, 'w') as f:
            json.dump(data, f, indent=2)

        logger.debug(f"Saved sentiment hub data ({len(data.get('grok_picks', []))} picks)")

    except Exception as e:
        logger.error(f"Failed to save sentiment hub data: {e}")


def load_sentiment_hub_data() -> Dict[str, Any]:
    """Load sentiment hub data from cache file."""
    if not SENTIMENT_HUB_FILE.exists():
        return {
            "grok_picks": [],
            "macro": {},
            "treasury_positions": [],
            "bags_graduations": [],
            "last_updated": None,
        }

    try:
        with open(SENTIMENT_HUB_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load sentiment hub data: {e}")
        return {
            "grok_picks": [],
            "macro": {},
            "treasury_positions": [],
            "bags_graduations": [],
            "last_updated": None,
        }


# =============================================================================
# Sentiment Updater Service
# =============================================================================

class SentimentUpdater:
    """
    Background service that updates sentiment hub data every 15 minutes.

    Usage:
        updater = SentimentUpdater()
        await updater.start()  # Runs forever
    """

    def __init__(self, update_interval: int = 15 * 60):
        """
        Initialize sentiment updater.

        Args:
            update_interval: Seconds between updates (default 15 minutes)
        """
        self.update_interval = update_interval
        self.running = False
        self.xai_api_key = os.getenv("XAI_API_KEY", "")

    async def start(self):
        """Start the update loop (runs forever)."""
        self.running = True
        logger.info(f"🔍 Sentiment updater started (updating every {self.update_interval // 60} minutes)")

        while self.running:
            try:
                await self.update_all_data()

            except Exception as e:
                logger.error(f"Sentiment updater error: {e}")
                logger.error(traceback.format_exc())

            # Wait for next update
            await asyncio.sleep(self.update_interval)

    async def update_all_data(self):
        """Fetch all sentiment hub data and save to cache."""
        logger.info("Updating sentiment hub data...")

        # Fetch all data in parallel
        grok_picks, macro, treasury, bags = await asyncio.gather(
            fetch_grok_top_picks(self.xai_api_key),
            fetch_macro_analysis(self.xai_api_key),
            fetch_treasury_positions(),
            fetch_bags_graduations(),
            return_exceptions=True,
        )

        # Handle any exceptions
        if isinstance(grok_picks, Exception):
            logger.error(f"Grok picks failed: {grok_picks}")
            grok_picks = []
        if isinstance(macro, Exception):
            logger.error(f"Macro analysis failed: {macro}")
            macro = {}
        if isinstance(treasury, Exception):
            logger.error(f"Treasury positions failed: {treasury}")
            treasury = []
        if isinstance(bags, Exception):
            logger.error(f"Bags graduations failed: {bags}")
            bags = []

        # Build sentiment hub data
        data = {
            "grok_picks": grok_picks,
            "macro": macro,
            "treasury_positions": treasury,
            "bags_graduations": bags,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

        # Save to cache
        save_sentiment_hub_data(data)

        logger.info(
            f"✅ Sentiment hub updated: "
            f"{len(grok_picks)} picks, "
            f"{len(treasury)} positions, "
            f"{len(bags)} graduations"
        )

    def stop(self):
        """Stop the update loop."""
        self.running = False
        logger.info("Sentiment updater stopped")


# =============================================================================
# Singleton Instance
# =============================================================================

_updater_instance: Optional[SentimentUpdater] = None


def get_sentiment_updater() -> SentimentUpdater:
    """Get singleton sentiment updater instance."""
    global _updater_instance
    if _updater_instance is None:
        _updater_instance = SentimentUpdater()
    return _updater_instance


async def start_sentiment_updater():
    """Start the sentiment updater service (for use in supervisor)."""
    updater = get_sentiment_updater()
    await updater.start()


# =============================================================================
# Manual Testing
# =============================================================================

if __name__ == "__main__":
    # Test the sentiment updater
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    async def test():
        """Test sentiment updater."""
        updater = SentimentUpdater(update_interval=30)  # 30 seconds for testing

        print("Starting sentiment updater test...")
        print("Press Ctrl+C to stop\n")

        try:
            await updater.start()
        except KeyboardInterrupt:
            print("\nStopping...")
            updater.stop()

    asyncio.run(test())
