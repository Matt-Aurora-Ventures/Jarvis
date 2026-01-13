"""
Alpha Detector
Detect on-chain alpha: whale moves, unusual activity, anomalies
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AlphaSignal:
    """A detected alpha signal"""
    signal_id: str
    signal_type: str  # whale_move, volume_spike, liquidity_change, new_pair
    token: str
    description: str
    detected_at: str
    strength: float  # 0-100
    data: Dict[str, Any] = field(default_factory=dict)
    actioned: bool = False


class AlphaDetector:
    """
    Detect on-chain alpha using Grok and free APIs.
    Monitors whale wallets, unusual volume, liquidity changes.
    """
    
    # Known whale wallets to monitor (Solana)
    WHALE_WALLETS = [
        # Add known whale addresses here
    ]
    
    # Thresholds
    VOLUME_SPIKE_THRESHOLD = 3.0  # 3x normal volume
    LIQUIDITY_CHANGE_THRESHOLD = 0.2  # 20% change
    
    def __init__(self):
        self.recent_signals: List[AlphaSignal] = []
        self.last_scan = None
        self._grok_client = None
        self._price_api = None
    
    def _get_grok(self):
        """Lazy load Grok"""
        if self._grok_client is None:
            try:
                from bots.twitter.grok_client import get_grok_client
                self._grok_client = get_grok_client()
            except Exception as e:
                logger.debug(f"Grok not available: {e}")
        return self._grok_client
    
    def _get_price_api(self):
        """Lazy load price API"""
        if self._price_api is None:
            try:
                from core.data.free_price_api import get_free_price_api
                self._price_api = get_free_price_api()
            except Exception as e:
                logger.debug(f"Price API not available: {e}")
        return self._price_api
    
    def _generate_id(self) -> str:
        """Generate signal ID"""
        import hashlib
        return hashlib.md5(datetime.utcnow().isoformat().encode()).hexdigest()[:10]
    
    async def scan_for_alpha(self) -> List[AlphaSignal]:
        """Run all alpha detection scans"""
        signals = []
        
        # Volume spikes
        volume_signals = await self.detect_volume_spikes()
        signals.extend(volume_signals)
        
        # New pairs with potential
        new_pair_signals = await self.detect_new_pairs()
        signals.extend(new_pair_signals)
        
        # Ask Grok for alpha
        grok_signals = await self.ask_grok_for_alpha()
        signals.extend(grok_signals)
        
        self.recent_signals = signals
        self.last_scan = datetime.utcnow()
        
        logger.info(f"Alpha scan found {len(signals)} signals")
        return signals
    
    async def detect_volume_spikes(self) -> List[AlphaSignal]:
        """Detect tokens with unusual volume"""
        signals = []
        price_api = self._get_price_api()
        
        if not price_api:
            return signals
        
        try:
            # Get trending/gainers which often have volume spikes
            from core.data.free_trending_api import get_free_trending_api
            trending_api = get_free_trending_api()
            gainers = await trending_api.get_top_gainers(limit=10)
            
            for token in gainers:
                # Check if volume is unusually high
                volume_24h = token.get("volume_24h", 0)
                avg_volume = token.get("avg_volume", volume_24h)  # Fallback
                
                if avg_volume > 0 and volume_24h / avg_volume > self.VOLUME_SPIKE_THRESHOLD:
                    signal = AlphaSignal(
                        signal_id=self._generate_id(),
                        signal_type="volume_spike",
                        token=token.get("symbol", "unknown"),
                        description=f"Volume {volume_24h/avg_volume:.1f}x normal",
                        detected_at=datetime.utcnow().isoformat(),
                        strength=min(100, (volume_24h / avg_volume) * 20),
                        data=token
                    )
                    signals.append(signal)
        except Exception as e:
            logger.debug(f"Volume spike detection error: {e}")
        
        return signals
    
    async def detect_new_pairs(self) -> List[AlphaSignal]:
        """Detect promising new trading pairs"""
        signals = []
        
        try:
            from core.data.free_trending_api import get_free_trending_api
            trending_api = get_free_trending_api()
            new_pairs = await trending_api.get_new_pairs(limit=10)
            
            for pair in new_pairs:
                liquidity = pair.get("liquidity", 0)
                volume = pair.get("volume_24h", 0)
                
                # Filter: decent liquidity + volume
                if liquidity > 10000 and volume > 5000:
                    signal = AlphaSignal(
                        signal_id=self._generate_id(),
                        signal_type="new_pair",
                        token=pair.get("symbol", "unknown"),
                        description=f"New pair: ${liquidity:,.0f} liq, ${volume:,.0f} vol",
                        detected_at=datetime.utcnow().isoformat(),
                        strength=min(100, (liquidity / 1000) + (volume / 1000)),
                        data=pair
                    )
                    signals.append(signal)
        except Exception as e:
            logger.debug(f"New pairs detection error: {e}")
        
        return signals
    
    async def ask_grok_for_alpha(self) -> List[AlphaSignal]:
        """Ask Grok to identify alpha opportunities"""
        signals = []
        grok = self._get_grok()
        
        if not grok:
            return signals
        
        try:
            prompt = """Identify 3 potential alpha opportunities in Solana ecosystem right now.

Look for:
- Tokens with unusual social activity
- Projects with upcoming catalysts
- Undervalued narratives

Format each as JSON:
{"token": "$SYMBOL", "reason": "brief reason", "strength": 1-100}

Return JSON array only."""

            response = await grok.generate_tweet(prompt, temperature=0.5)
            if response and response.content:
                import json
                try:
                    start = response.content.find("[")
                    end = response.content.rfind("]") + 1
                    if start >= 0 and end > start:
                        data = json.loads(response.content[start:end])
                        for item in data:
                            signal = AlphaSignal(
                                signal_id=self._generate_id(),
                                signal_type="grok_alpha",
                                token=item.get("token", ""),
                                description=item.get("reason", ""),
                                detected_at=datetime.utcnow().isoformat(),
                                strength=float(item.get("strength", 50)),
                                data={"source": "grok"}
                            )
                            signals.append(signal)
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Grok alpha detection error: {e}")
        
        return signals
    
    async def analyze_token(self, token_address: str) -> Dict[str, Any]:
        """Deep analysis of a specific token"""
        grok = self._get_grok()
        price_api = self._get_price_api()
        
        analysis = {
            "token": token_address,
            "price_data": None,
            "sentiment": None,
            "alpha_score": 0,
            "risks": [],
            "opportunities": []
        }
        
        # Get price data
        if price_api:
            try:
                price_data = await price_api.get_token_price(token_address)
                analysis["price_data"] = price_data
            except Exception:
                pass
        
        # Get Grok sentiment
        if grok:
            try:
                response = await grok.analyze_sentiment(
                    {"token": token_address, "price_data": analysis["price_data"]},
                    context_type="token"
                )
                if response:
                    analysis["sentiment"] = response.content
            except Exception:
                pass
        
        return analysis
    
    def get_actionable_signals(self, min_strength: float = 60) -> List[AlphaSignal]:
        """Get signals strong enough to act on"""
        return [s for s in self.recent_signals 
                if s.strength >= min_strength and not s.actioned]
    
    def mark_actioned(self, signal_id: str):
        """Mark a signal as actioned"""
        for signal in self.recent_signals:
            if signal.signal_id == signal_id:
                signal.actioned = True
                break
    
    def get_content_from_signals(self) -> List[Dict[str, Any]]:
        """Generate content suggestions from signals"""
        suggestions = []
        
        for signal in self.get_actionable_signals(50):
            if signal.signal_type == "volume_spike":
                suggestions.append({
                    "type": "alpha_alert",
                    "topic": f"Volume spike on {signal.token}",
                    "signal": signal,
                    "prompt": f"{signal.token} volume is {signal.description}. Worth watching."
                })
            elif signal.signal_type == "new_pair":
                suggestions.append({
                    "type": "new_pair_alert",
                    "topic": f"New pair: {signal.token}",
                    "signal": signal,
                    "prompt": f"Spotted new pair {signal.token}. {signal.description}"
                })
            elif signal.signal_type == "grok_alpha":
                suggestions.append({
                    "type": "grok_alpha",
                    "topic": signal.token,
                    "signal": signal,
                    "prompt": f"Grok spotted {signal.token}: {signal.description}"
                })
        
        return suggestions[:3]


# Singleton
_detector: Optional[AlphaDetector] = None

def get_alpha_detector() -> AlphaDetector:
    global _detector
    if _detector is None:
        _detector = AlphaDetector()
    return _detector
