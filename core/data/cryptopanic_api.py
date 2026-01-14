"""
CryptoPanic API - Aggregated crypto news with sentiment.

Free tier: Unlimited (with rate limits)
Docs: https://cryptopanic.com/developers/api/
"""

import os
import asyncio
import logging
import aiohttp
import time
from typing import Optional, Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# CryptoPanic API
CRYPTOPANIC_API = "https://cryptopanic.com/api/v1"


class CryptoPanicAPI:
    """CryptoPanic news and sentiment API client."""

    # Rate limiting: ~1 request per second to be safe
    MIN_REQUEST_INTERVAL = 1.0
    _last_request_time = 0.0

    def __init__(self):
        self.api_key = os.getenv("CRYPTOPANIC_API_KEY", "")
        self._session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = 180  # 3 minutes for news
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def _rate_limit(self):
        """Apply rate limiting between requests."""
        now = time.time()
        elapsed = now - CryptoPanicAPI._last_request_time
        if elapsed < self.MIN_REQUEST_INTERVAL:
            await asyncio.sleep(self.MIN_REQUEST_INTERVAL - elapsed)
        CryptoPanicAPI._last_request_time = time.time()

    async def _get(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make GET request to CryptoPanic API."""
        if not self.api_key:
            logger.warning("CRYPTOPANIC_API_KEY not set")
            return None

        cache_key = f"{endpoint}:{params}"

        # Check cache first (before rate limiting)
        if cache_key in self._cache:
            cached, timestamp = self._cache[cache_key]
            if datetime.now().timestamp() - timestamp < self._cache_ttl:
                return cached

        # Apply rate limiting
        await self._rate_limit()

        try:
            session = await self._get_session()
            url = f"{CRYPTOPANIC_API}/{endpoint}"

            # Add auth token
            params = params or {}
            params["auth_token"] = self.api_key

            async with session.get(url, params=params, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._cache[cache_key] = (data, datetime.now().timestamp())
                    return data
                elif resp.status == 429:
                    logger.warning("CryptoPanic API rate limited")
                    return None
                else:
                    logger.warning(f"CryptoPanic API error: {resp.status}")
                    return None
        except Exception as e:
            logger.error(f"CryptoPanic API error: {e}")
            return None
    
    async def get_news(
        self,
        currencies: Optional[str] = None,
        filter_type: str = "hot",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get crypto news articles.
        
        Args:
            currencies: Comma-separated currency codes (e.g., "SOL,BTC,ETH")
            filter_type: "rising", "hot", "bullish", "bearish", "important", "saved", "lol"
            limit: Number of articles to return
            
        Returns:
            List of news articles with sentiment
        """
        params = {"filter": filter_type}
        if currencies:
            params["currencies"] = currencies
        
        data = await self._get("posts/", params)
        if data and "results" in data:
            articles = []
            for post in data["results"][:limit]:
                # Determine sentiment from votes
                votes = post.get("votes", {})
                positive = votes.get("positive", 0)
                negative = votes.get("negative", 0)
                
                if positive > negative * 2:
                    sentiment = "bullish"
                elif negative > positive * 2:
                    sentiment = "bearish"
                else:
                    sentiment = "neutral"
                
                articles.append({
                    "title": post.get("title", ""),
                    "url": post.get("url", ""),
                    "source": post.get("source", {}).get("title", ""),
                    "published_at": post.get("published_at", ""),
                    "currencies": [c.get("code", "") for c in post.get("currencies", [])],
                    "sentiment": sentiment,
                    "votes_positive": positive,
                    "votes_negative": negative,
                    "is_hot": post.get("is_hot", False),
                })
            return articles
        return []
    
    async def get_bullish_news(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get bullish news articles."""
        return await self.get_news(filter_type="bullish", limit=limit)
    
    async def get_bearish_news(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get bearish news articles."""
        return await self.get_news(filter_type="bearish", limit=limit)
    
    async def get_important_news(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get important/breaking news articles."""
        return await self.get_news(filter_type="important", limit=limit)
    
    async def get_solana_news(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get Solana-specific news."""
        return await self.get_news(currencies="SOL", filter_type="hot", limit=limit)
    
    async def get_news_sentiment(self) -> Optional[Dict[str, Any]]:
        """
        Get overall news sentiment summary.
        
        Returns:
            Dict with sentiment indicators from news
        """
        try:
            hot_news = await self.get_news(filter_type="hot", limit=20)
            if not hot_news:
                return None
            
            bullish = sum(1 for n in hot_news if n["sentiment"] == "bullish")
            bearish = sum(1 for n in hot_news if n["sentiment"] == "bearish")
            neutral = len(hot_news) - bullish - bearish
            
            # Get top mentioned currencies
            currency_counts: Dict[str, int] = {}
            for article in hot_news:
                for currency in article["currencies"]:
                    currency_counts[currency] = currency_counts.get(currency, 0) + 1
            
            top_currencies = sorted(currency_counts.items(), key=lambda x: -x[1])[:5]
            
            return {
                "total_articles": len(hot_news),
                "bullish_count": bullish,
                "bearish_count": bearish,
                "neutral_count": neutral,
                "sentiment_ratio": bullish / max(bearish, 1),
                "market_mood": "bullish" if bullish > bearish * 1.5 else "bearish" if bearish > bullish * 1.5 else "mixed",
                "top_mentioned": [c[0] for c in top_currencies],
                "latest_headlines": [n["title"][:100] for n in hot_news[:3]],
            }
        except Exception as e:
            logger.error(f"News sentiment error: {e}")
            return None


# Singleton
_cryptopanic: Optional[CryptoPanicAPI] = None


def get_cryptopanic() -> CryptoPanicAPI:
    """Get singleton CryptoPanic API instance."""
    global _cryptopanic
    if _cryptopanic is None:
        _cryptopanic = CryptoPanicAPI()
    return _cryptopanic
