"""
LunarCrush API - Social sentiment data for crypto tokens.

Free tier: 1000 calls/day
Docs: https://lunarcrush.com/developers/api/endpoints
"""

import os
import logging
import aiohttp
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# LunarCrush API v4 (MCP server compatible)
LUNARCRUSH_API = "https://lunarcrush.com/api4/public"


class LunarCrushAPI:
    """LunarCrush social sentiment API client."""
    
    def __init__(self):
        self.api_key = os.getenv("LUNARCRUSH_API_KEY", "")
        self._session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = 300  # 5 minutes
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _get_headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    async def _get(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make GET request to LunarCrush API."""
        cache_key = f"{endpoint}:{params}"
        
        # Check cache
        if cache_key in self._cache:
            cached, timestamp = self._cache[cache_key]
            if datetime.now().timestamp() - timestamp < self._cache_ttl:
                return cached
        
        try:
            session = await self._get_session()
            url = f"{LUNARCRUSH_API}/{endpoint}"
            
            async with session.get(url, headers=self._get_headers(), params=params, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._cache[cache_key] = (data, datetime.now().timestamp())
                    return data
                else:
                    logger.warning(f"LunarCrush API error: {resp.status}")
                    return None
        except Exception as e:
            logger.error(f"LunarCrush API error: {e}")
            return None
    
    async def get_coin_sentiment(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get social sentiment for a specific coin.
        
        Returns:
            Dict with galaxy_score, alt_rank, social_volume, sentiment, etc.
        """
        data = await self._get("coins", {"symbol": symbol.upper()})
        if data and "data" in data:
            coins = data["data"]
            if coins:
                coin = coins[0] if isinstance(coins, list) else coins
                return {
                    "symbol": coin.get("symbol", symbol),
                    "name": coin.get("name", ""),
                    "price": coin.get("price", 0),
                    "price_change_24h": coin.get("percent_change_24h", 0),
                    "galaxy_score": coin.get("galaxy_score", 0),  # 0-100 overall score
                    "alt_rank": coin.get("alt_rank", 0),  # Ranking vs other alts
                    "social_volume": coin.get("social_volume", 0),
                    "social_score": coin.get("social_score", 0),
                    "social_contributors": coin.get("social_contributors", 0),
                    "social_dominance": coin.get("social_dominance", 0),
                    "market_dominance": coin.get("market_dominance", 0),
                    "sentiment": coin.get("sentiment", 0),  # Bullish/bearish ratio
                    "categories": coin.get("categories", []),
                }
        return None
    
    async def get_trending_coins(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get trending coins by social activity.
        
        Returns:
            List of trending coins with sentiment data
        """
        data = await self._get("coins/list", {"sort": "galaxy_score", "limit": limit})
        if data and "data" in data:
            return [
                {
                    "symbol": coin.get("symbol", ""),
                    "name": coin.get("name", ""),
                    "galaxy_score": coin.get("galaxy_score", 0),
                    "social_volume": coin.get("social_volume", 0),
                    "price_change_24h": coin.get("percent_change_24h", 0),
                    "sentiment": coin.get("sentiment", 0),
                }
                for coin in data["data"][:limit]
            ]
        return []
    
    async def get_social_feed(self, symbol: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get recent social posts about a coin.
        
        Returns:
            List of recent social posts with engagement data
        """
        data = await self._get(f"coins/{symbol.lower()}/feeds", {"limit": limit})
        if data and "data" in data:
            return [
                {
                    "text": post.get("body", "")[:200],
                    "source": post.get("social_type", ""),
                    "engagement": post.get("social_score", 0),
                    "sentiment": post.get("sentiment", "neutral"),
                    "created_at": post.get("time", ""),
                }
                for post in data["data"][:limit]
            ]
        return []
    
    async def get_market_sentiment(self) -> Optional[Dict[str, Any]]:
        """
        Get overall crypto market sentiment.
        
        Returns:
            Dict with market-wide sentiment indicators
        """
        # Get top coins to gauge market sentiment
        trending = await self.get_trending_coins(20)
        if trending:
            avg_galaxy = sum(c["galaxy_score"] for c in trending) / len(trending)
            avg_sentiment = sum(c["sentiment"] for c in trending) / len(trending)
            bullish_count = sum(1 for c in trending if c["sentiment"] > 50)
            
            return {
                "avg_galaxy_score": round(avg_galaxy, 1),
                "avg_sentiment": round(avg_sentiment, 1),
                "bullish_ratio": bullish_count / len(trending),
                "market_mood": "bullish" if avg_sentiment > 55 else "bearish" if avg_sentiment < 45 else "neutral",
                "top_trending": trending[:5],
            }
        return None


# Singleton
_lunarcrush: Optional[LunarCrushAPI] = None


def get_lunarcrush() -> LunarCrushAPI:
    """Get singleton LunarCrush API instance."""
    global _lunarcrush
    if _lunarcrush is None:
        _lunarcrush = LunarCrushAPI()
    return _lunarcrush
