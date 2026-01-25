"""Main Bags Intel service that orchestrates monitoring, scoring, and notifications."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Set

import aiohttp
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

from .config import BagsIntelConfig, load_config
from .models import (
    TokenMetadata,
    CreatorProfile,
    BondingMetrics,
    MarketMetrics,
    GraduationEvent,
)
from .monitor import GraduationMonitor, PollingFallback
from .scorer import IntelScorer
from core.async_utils import fire_and_forget

logger = logging.getLogger("jarvis.bags_intel")


class BagsIntelService:
    """Main service for bags.fm intelligence reports."""

    def __init__(self, config: Optional[BagsIntelConfig] = None):
        self.config = config or load_config()
        self._monitor: Optional[GraduationMonitor] = None
        self._fallback: Optional[PollingFallback] = None
        self._scorer: Optional[IntelScorer] = None
        self._bot: Optional[Bot] = None
        self._http: Optional[aiohttp.ClientSession] = None
        self._running = False
        self._processed: Set[str] = set()
        self._last_report_time: Dict[str, datetime] = {}
        self._report_count = 0

    async def start(self) -> None:
        """Start the Bags Intel service."""
        if not self.config.is_configured:
            logger.warning("Bags Intel not fully configured - needs BITQUERY_API_KEY")
            # Fall back to polling if no Bitquery
            if not self.config.bitquery_api_key:
                logger.info("Using DexScreener polling fallback")

        logger.info("Starting Bags Intel service")

        # Initialize components
        self._http = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        self._scorer = IntelScorer(xai_api_key=self.config.xai_api_key)

        # Initialize Telegram bot
        if self.config.telegram_bot_token and self.config.telegram_chat_id:
            self._bot = Bot(token=self.config.telegram_bot_token)
            logger.info("Telegram notifications enabled")

        self._running = True

        # Use WebSocket if available, else polling
        if self.config.bitquery_api_key:
            self._monitor = GraduationMonitor(
                config=self.config,
                on_graduation=self._handle_graduation,
            )
            await self._monitor.run()
        else:
            self._fallback = PollingFallback(
                config=self.config,
                on_graduation=self._handle_graduation,
                poll_interval=30,
            )
            await self._fallback.run()

    async def stop(self) -> None:
        """Stop the service."""
        logger.info("Stopping Bags Intel service")
        self._running = False

        if self._monitor:
            await self._monitor.stop()
        if self._fallback:
            await self._fallback.stop()
        if self._http:
            await self._http.close()

        logger.info(f"Bags Intel stopped. Reports sent: {self._report_count}")

    async def _handle_graduation(self, event: dict) -> None:
        """Handle a graduation event."""
        mint = event.get("mint_address")
        if not mint:
            return

        # Dedupe
        if mint in self._processed:
            return

        # Rate limit
        last_time = self._last_report_time.get(mint)
        if last_time and datetime.utcnow() - last_time < timedelta(
            seconds=self.config.report_cooldown_seconds
        ):
            return

        self._processed.add(mint)
        self._last_report_time[mint] = datetime.utcnow()

        logger.info(f"Processing graduation: {mint[:12]}...")

        try:
            # Gather data
            graduation = await self._gather_data(
                mint_address=mint,
                creator_wallet=event.get("creator"),
                tx_signature=event.get("signature"),
                timestamp=event.get("timestamp"),
            )

            if not graduation:
                logger.warning(f"Failed to gather data for {mint[:12]}")
                return

            # Check thresholds
            if graduation.market.market_cap_usd < self.config.min_graduation_mcap:
                logger.info(f"Below mcap threshold: ${graduation.market.market_cap_usd:,.0f}")
                return

            if graduation.score.overall_score < self.config.min_score_to_report:
                logger.info(f"Below score threshold: {graduation.score.overall_score:.0f}")
                return

            # Send report
            await self._send_report(graduation)
            self._report_count += 1

            logger.info(
                f"Report sent: {graduation.token.symbol} "
                f"Score={graduation.score.overall_score:.0f} "
                f"MCap=${graduation.market.market_cap_usd:,.0f}"
            )

            # Store graduation outcome in memory (fire-and-forget)
            try:
                from bots.bags_intel.memory_hooks import store_graduation_outcome

                bonding_data = {
                    "duration_seconds": graduation.bonding.duration_seconds,
                    "total_volume_sol": graduation.bonding.total_volume_sol,
                    "unique_buyers": graduation.bonding.unique_buyers,
                    "unique_sellers": graduation.bonding.unique_sellers,
                    "buy_sell_ratio": graduation.bonding.buy_sell_ratio,
                }

                fire_and_forget(
                    store_graduation_outcome(
                        token_symbol=graduation.token.symbol,
                        token_mint=mint,
                        graduation_score=graduation.score.overall_score,
                        price_at_graduation=graduation.market.price_usd,
                        outcome="pending",  # Will be updated later
                        creator_twitter=graduation.creator.twitter_handle,
                        bonding_curve_data=bonding_data,
                    ),
                    name=f"store_graduation_{graduation.token.symbol}",
                )
            except Exception as e:
                logger.debug(f"Memory hook skipped: {e}")

        except Exception as e:
            logger.error(f"Error processing {mint[:12]}: {e}")

    async def _gather_data(
        self,
        mint_address: str,
        creator_wallet: Optional[str],
        tx_signature: Optional[str],
        timestamp: Optional[str],
    ) -> Optional[GraduationEvent]:
        """Gather all data for a graduated token."""
        # Parallel fetch
        token_task = self._fetch_token_metadata(mint_address)
        market_task = self._fetch_market_data(mint_address)

        results = await asyncio.gather(token_task, market_task, return_exceptions=True)

        token_meta = results[0] if not isinstance(results[0], Exception) else None
        market_data = results[1] if not isinstance(results[1], Exception) else None

        if not token_meta or not market_data:
            return None

        # Creator profile
        creator = CreatorProfile(
            wallet_address=creator_wallet or "unknown",
            twitter_handle=token_meta.twitter.lstrip("@") if token_meta.twitter else None,
        )

        # Fetch Twitter details if available
        if creator.twitter_handle and self.config.twitter_bearer_token:
            creator = await self._fetch_twitter_profile(creator)

        # Bonding metrics (estimate from available data)
        bonding = BondingMetrics(
            duration_seconds=600,  # Estimate, would need historical data
            total_volume_sol=market_data.volume_24h_usd / 200 if market_data.volume_24h_usd else 0,
            unique_buyers=market_data.buys_1h * 2 if market_data.buys_1h else 50,
            unique_sellers=market_data.sells_1h * 2 if market_data.sells_1h else 20,
            buy_sell_ratio=(market_data.buys_1h / market_data.sells_1h)
            if market_data.sells_1h
            else 2.0,
            graduation_mcap_usd=market_data.market_cap_usd,
        )

        # Calculate score
        score = await self._scorer.calculate_score(
            token=token_meta,
            creator=creator,
            bonding=bonding,
            market=market_data,
        )

        return GraduationEvent(
            token=token_meta,
            creator=creator,
            bonding=bonding,
            market=market_data,
            score=score,
            timestamp=datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if timestamp
            else datetime.utcnow(),
            tx_signature=tx_signature,
        )

    async def _fetch_token_metadata(self, mint: str) -> TokenMetadata:
        """Fetch token metadata from DexScreener."""
        url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"

        async with self._http.get(url) as resp:
            if resp.status != 200:
                raise Exception(f"DexScreener error: {resp.status}")

            data = await resp.json()
            pairs = data.get("pairs", [])

            if not pairs:
                return TokenMetadata(mint_address=mint, name="Unknown", symbol="???")

            pair = pairs[0]
            base = pair.get("baseToken", {})
            info = pair.get("info", {})
            socials = {s.get("type"): s.get("url") for s in info.get("socials", [])}

            return TokenMetadata(
                mint_address=mint,
                name=base.get("name", "Unknown"),
                symbol=base.get("symbol", "???"),
                website=info.get("websites", [{}])[0].get("url") if info.get("websites") else None,
                twitter=socials.get("twitter"),
                telegram=socials.get("telegram"),
            )

    async def _fetch_market_data(self, mint: str) -> MarketMetrics:
        """Fetch market data from DexScreener."""
        url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"

        async with self._http.get(url) as resp:
            if resp.status != 200:
                raise Exception(f"DexScreener error: {resp.status}")

            data = await resp.json()
            pairs = data.get("pairs", [])

            if not pairs:
                raise Exception("No pairs found")

            # Use highest liquidity pair
            pair = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))

            return MarketMetrics(
                price_usd=float(pair.get("priceUsd", 0) or 0),
                price_sol=float(pair.get("priceNative", 0) or 0),
                market_cap_usd=float(pair.get("marketCap", 0) or 0),
                liquidity_usd=float(pair.get("liquidity", {}).get("usd", 0) or 0),
                volume_24h_usd=float(pair.get("volume", {}).get("h24", 0) or 0),
                price_change_1h=float(pair.get("priceChange", {}).get("h1", 0) or 0),
                buys_1h=int(pair.get("txns", {}).get("h1", {}).get("buys", 0) or 0),
                sells_1h=int(pair.get("txns", {}).get("h1", {}).get("sells", 0) or 0),
            )

    async def _fetch_twitter_profile(self, creator: CreatorProfile) -> CreatorProfile:
        """Enhance creator profile with Twitter data."""
        if not creator.twitter_handle:
            return creator

        try:
            url = f"https://api.twitter.com/2/users/by/username/{creator.twitter_handle}"
            params = {"user.fields": "created_at,public_metrics"}
            headers = {"Authorization": f"Bearer {self.config.twitter_bearer_token}"}

            async with self._http.get(url, params=params, headers=headers) as resp:
                if resp.status == 200:
                    data = (await resp.json()).get("data", {})
                    metrics = data.get("public_metrics", {})

                    creator.twitter_followers = metrics.get("followers_count", 0)

                    created = data.get("created_at")
                    if created:
                        created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                        creator.twitter_account_age_days = (
                            datetime.utcnow() - created_dt.replace(tzinfo=None)
                        ).days

        except Exception as e:
            logger.debug(f"Twitter fetch error: {e}")

        return creator

    async def _send_report(self, event: GraduationEvent) -> None:
        """Send report to Telegram."""
        if not self._bot or not self.config.telegram_chat_id:
            logger.info(f"Would send report: {event.token.symbol}")
            return

        message = event.to_telegram_html()

        try:
            await self._bot.send_message(
                chat_id=self.config.telegram_chat_id,
                text=message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except TelegramError as e:
            logger.error(f"Telegram send error: {e}")


async def create_bags_intel_service() -> None:
    """Factory function for supervisor integration."""
    config = load_config()

    if not config.bitquery_api_key and not config.telegram_bot_token:
        logger.warning(
            "[bags_intel] Missing BITQUERY_API_KEY and/or TELEGRAM_BOT_TOKEN. "
            "Set at least BITQUERY_API_KEY to enable real-time monitoring."
        )
        return

    service = BagsIntelService(config)
    await service.start()
