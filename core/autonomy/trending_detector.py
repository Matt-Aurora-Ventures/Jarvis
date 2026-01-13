"""
Trending Detector
Find trending topics before they peak using Grok and on-chain data
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TrendingTopic:
    """A detected trending topic"""
    topic: str
    category: str  # token, narrative, event, meme
    momentum: float  # 0-100, how fast it's growing
    current_mentions: int = 0
    previous_mentions: int = 0
    growth_rate: float = 0.0
    detected_at: str = ""
    peak_prediction: str = ""  # when we think it'll peak
    confidence: float = 0.5
    related_tokens: List[str] = field(default_factory=list)
    source: str = "grok"  # grok, lunarcrush, onchain


class TrendingDetector:
    """
    Detect trending topics before they peak.
    Uses Grok for social analysis + on-chain data.
    """
    
    def __init__(self):
        self.current_trends: List[TrendingTopic] = []
        self.historical_trends: List[TrendingTopic] = []
        self.last_scan = None
        self.scan_interval = timedelta(minutes=30)
        self._grok_client = None
    
    def _get_grok(self):
        """Lazy load Grok client"""
        if self._grok_client is None:
            try:
                from bots.twitter.grok_client import get_grok_client
                self._grok_client = get_grok_client()
            except Exception as e:
                logger.error(f"Could not load Grok client: {e}")
        return self._grok_client
    
    async def scan_for_trends(self) -> List[TrendingTopic]:
        """
        Scan for emerging trends using Grok.
        """
        grok = self._get_grok()
        if not grok:
            logger.warning("Grok not available for trend scanning")
            return []
        
        try:
            # Ask Grok to identify trending topics
            prompt = """Analyze current crypto Twitter trends. Identify 5 emerging topics that are gaining momentum but haven't peaked yet.

For each topic, provide:
1. Topic name
2. Category (token/narrative/event/meme)
3. Momentum score (0-100)
4. Related tokens (if any)
5. Why it's trending

Format as JSON array:
[{"topic": "...", "category": "...", "momentum": 75, "related_tokens": ["$SOL"], "reason": "..."}]

Focus on Solana ecosystem but include major crypto trends."""

            response = await grok.generate_tweet(prompt, temperature=0.3)
            if response and response.content:
                # Parse response
                trends = self._parse_trend_response(response.content)
                self.current_trends = trends
                self.last_scan = datetime.utcnow()
                logger.info(f"Detected {len(trends)} trending topics")
                return trends
                
        except Exception as e:
            logger.error(f"Error scanning for trends: {e}")
        
        return []
    
    def _parse_trend_response(self, response: str) -> List[TrendingTopic]:
        """Parse Grok's trend response"""
        import json
        trends = []
        
        try:
            # Try to extract JSON from response
            start = response.find("[")
            end = response.rfind("]") + 1
            if start >= 0 and end > start:
                data = json.loads(response[start:end])
                for item in data:
                    trend = TrendingTopic(
                        topic=item.get("topic", ""),
                        category=item.get("category", "unknown"),
                        momentum=float(item.get("momentum", 50)),
                        detected_at=datetime.utcnow().isoformat(),
                        related_tokens=item.get("related_tokens", []),
                        source="grok"
                    )
                    trends.append(trend)
        except Exception as e:
            logger.debug(f"Could not parse trend response: {e}")
        
        return trends
    
    async def get_token_buzz(self, token_symbol: str) -> Dict[str, Any]:
        """Get buzz/momentum for a specific token using Grok"""
        grok = self._get_grok()
        if not grok:
            return {"buzz": 0, "sentiment": "unknown"}
        
        try:
            response = await grok.analyze_sentiment(
                {"token": token_symbol},
                context_type="token"
            )
            if response and response.content:
                return {
                    "buzz": 50,  # Default medium
                    "sentiment": response.content,
                    "source": "grok"
                }
        except Exception as e:
            logger.debug(f"Could not get token buzz: {e}")
        
        return {"buzz": 0, "sentiment": "unknown"}
    
    async def detect_narrative_shift(self) -> Optional[str]:
        """Detect if there's a narrative shift happening"""
        grok = self._get_grok()
        if not grok:
            return None
        
        try:
            prompt = """Is there a narrative shift happening in crypto right now? 
            
Examples of narrative shifts:
- Risk-on to risk-off
- Meme season to utility focus
- L1 rotation to L2
- DeFi summer vibes

If yes, describe it briefly. If no major shift, say "stable"."""

            response = await grok.generate_tweet(prompt, temperature=0.5)
            if response and response.content:
                return response.content
        except Exception as e:
            logger.debug(f"Could not detect narrative shift: {e}")
        
        return None
    
    def get_hot_topics(self, min_momentum: float = 60) -> List[TrendingTopic]:
        """Get topics above momentum threshold"""
        return [t for t in self.current_trends if t.momentum >= min_momentum]
    
    def get_content_suggestions(self) -> List[Dict[str, Any]]:
        """Get content suggestions based on trends"""
        suggestions = []
        
        for trend in self.get_hot_topics(50):
            suggestions.append({
                "type": "trend_commentary",
                "topic": trend.topic,
                "category": trend.category,
                "momentum": trend.momentum,
                "tokens": trend.related_tokens,
                "prompt": f"Comment on the {trend.topic} trend. Momentum is {trend.momentum}/100."
            })
        
        return suggestions[:3]  # Top 3 suggestions
    
    def should_scan(self) -> bool:
        """Check if we should scan for new trends"""
        if self.last_scan is None:
            return True
        return datetime.utcnow() - self.last_scan > self.scan_interval


# Singleton
_detector: Optional[TrendingDetector] = None

def get_trending_detector() -> TrendingDetector:
    global _detector
    if _detector is None:
        _detector = TrendingDetector()
    return _detector
