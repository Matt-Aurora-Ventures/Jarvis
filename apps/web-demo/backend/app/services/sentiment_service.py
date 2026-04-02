"""
AI Sentiment Service - Supports both Grok (cloud) and Ollama (local).

Security: All sentiment analysis done server-side (Rule #2).
Client never sees raw API keys or model parameters.
"""
import logging
import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

import aiohttp
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# Data Models
# =============================================================================

class MarketRegime(BaseModel):
    """Market regime classification."""
    regime: str  # BULL, BEAR, NEUTRAL
    risk_level: str  # LOW, NORMAL, HIGH, EXTREME
    btc_change_24h: float
    sol_change_24h: float
    fear_greed_score: Optional[float] = None
    updated_at: datetime


class TokenSentiment(BaseModel):
    """Token sentiment analysis result."""
    token_address: str
    symbol: str
    score: float  # 0-100
    conviction: str  # LOW, MEDIUM, HIGH
    signals: List[str]
    entry_timing: str  # EARLY, OPTIMAL, LATE
    risk_factors: List[str]
    recommendation: str  # BUY, HOLD, SELL
    analysis: str
    updated_at: datetime


# =============================================================================
# AI Provider Base Class
# =============================================================================

class AIProvider:
    """Base class for AI providers."""

    async def analyze_token(self, token_data: Dict[str, Any]) -> TokenSentiment:
        """Analyze a token and return sentiment."""
        raise NotImplementedError

    async def get_market_regime(self, market_data: Dict[str, Any]) -> MarketRegime:
        """Analyze market and return regime classification."""
        raise NotImplementedError


# =============================================================================
# Grok Provider (XAI - Cloud)
# =============================================================================

class GrokProvider(AIProvider):
    """Grok AI provider via XAI API."""

    def __init__(self):
        self.api_key = settings.XAI_API_KEY
        self.model = settings.XAI_MODEL
        self.base_url = "https://api.x.ai/v1"

    async def _call_grok(self, prompt: str, system_prompt: str = None) -> str:
        """
        Call Grok API.
        Rule #1: API key never exposed to client.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1000,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Grok API error: {error_text}")
                        raise Exception(f"Grok API error: {response.status}")

                    result = await response.json()
                    return result["choices"][0]["message"]["content"]

        except Exception as e:
            logger.error(f"Grok API call failed: {e}")
            raise

    async def analyze_token(self, token_data: Dict[str, Any]) -> TokenSentiment:
        """Analyze token using Grok."""
        system_prompt = """You are a Solana trading AI analyzing token sentiment.
Return analysis in JSON format with these fields:
- score: 0-100 sentiment score
- conviction: LOW, MEDIUM, or HIGH
- signals: array of positive signals detected
- entry_timing: EARLY, OPTIMAL, or LATE
- risk_factors: array of risk factors
- recommendation: BUY, HOLD, or SELL
- analysis: brief text explanation

Use strict entry criteria:
- EARLY entry (first 100 buyers) = 67% TP rate
- Ratio requirements: 2.0x minimum for 67% TP rate
- Overconfidence penalty: scores >90 often fail
- Momentum keywords: "moon", "gem", "100x" boost score"""

        prompt = f"""Analyze this Solana token:

Symbol: {token_data.get('symbol', 'UNKNOWN')}
Address: {token_data.get('address', 'N/A')}
Price: ${token_data.get('price', 0):.8f}
Volume 24h: ${token_data.get('volume_24h', 0):,.2f}
Holders: {token_data.get('holders', 0)}
Age: {token_data.get('age_hours', 0):.1f} hours
Social signals: {token_data.get('social_signals', 0)}
Buyer count: {token_data.get('buyer_count', 0)}

Return JSON analysis."""

        try:
            response = await self._call_grok(prompt, system_prompt)

            # Parse JSON from response
            # (Grok sometimes adds text around JSON, so extract it)
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                analysis_data = json.loads(json_str)
            else:
                raise ValueError("No JSON in response")

            return TokenSentiment(
                token_address=token_data["address"],
                symbol=token_data.get("symbol", "UNKNOWN"),
                score=float(analysis_data.get("score", 50)),
                conviction=analysis_data.get("conviction", "MEDIUM"),
                signals=analysis_data.get("signals", []),
                entry_timing=analysis_data.get("entry_timing", "OPTIMAL"),
                risk_factors=analysis_data.get("risk_factors", []),
                recommendation=analysis_data.get("recommendation", "HOLD"),
                analysis=analysis_data.get("analysis", "No analysis available"),
                updated_at=datetime.utcnow(),
            )

        except Exception as e:
            logger.error(f"Token analysis failed: {e}")
            # Return default neutral sentiment on error
            return TokenSentiment(
                token_address=token_data["address"],
                symbol=token_data.get("symbol", "UNKNOWN"),
                score=50.0,
                conviction="LOW",
                signals=[],
                entry_timing="LATE",
                risk_factors=["Analysis failed"],
                recommendation="HOLD",
                analysis="AI analysis unavailable",
                updated_at=datetime.utcnow(),
            )

    async def get_market_regime(self, market_data: Dict[str, Any]) -> MarketRegime:
        """Get market regime from Grok."""
        system_prompt = """Analyze market conditions and return JSON with:
- regime: BULL, BEAR, or NEUTRAL
- risk_level: LOW, NORMAL, HIGH, or EXTREME
- analysis: brief explanation"""

        prompt = f"""Analyze current market:

BTC 24h change: {market_data.get('btc_change', 0):.2f}%
SOL 24h change: {market_data.get('sol_change', 0):.2f}%
Market cap trend: {market_data.get('market_trend', 'unknown')}
Volume trend: {market_data.get('volume_trend', 'unknown')}

Return JSON analysis."""

        try:
            response = await self._call_grok(prompt, system_prompt)

            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                regime_data = json.loads(json_str)
            else:
                raise ValueError("No JSON in response")

            return MarketRegime(
                regime=regime_data.get("regime", "NEUTRAL"),
                risk_level=regime_data.get("risk_level", "NORMAL"),
                btc_change_24h=market_data.get("btc_change", 0.0),
                sol_change_24h=market_data.get("sol_change", 0.0),
                updated_at=datetime.utcnow(),
            )

        except Exception as e:
            logger.error(f"Market regime analysis failed: {e}")
            return MarketRegime(
                regime="NEUTRAL",
                risk_level="NORMAL",
                btc_change_24h=market_data.get("btc_change", 0.0),
                sol_change_24h=market_data.get("sol_change", 0.0),
                updated_at=datetime.utcnow(),
            )


# =============================================================================
# Ollama Provider (Local - Zero Cost, Privacy)
# =============================================================================

class OllamaProvider(AIProvider):
    """Ollama local AI provider."""

    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL

    async def _call_ollama(self, prompt: str, system_prompt: str = None) -> str:
        """
        Call Ollama API (local).
        Rule #1: Even though it's local, validation still applies.
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 1000,
            },
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60),  # Ollama can be slow
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Ollama API error: {error_text}")
                        raise Exception(f"Ollama API error: {response.status}")

                    result = await response.json()
                    return result["response"]

        except Exception as e:
            logger.error(f"Ollama API call failed: {e}")
            raise

    async def analyze_token(self, token_data: Dict[str, Any]) -> TokenSentiment:
        """Analyze token using local Ollama model."""
        system_prompt = """You are a cryptocurrency trading AI. Analyze tokens and return JSON."""

        prompt = f"""Analyze this token and return ONLY valid JSON (no markdown, no extra text):

{{
  "symbol": "{token_data.get('symbol', 'UNKNOWN')}",
  "price": {token_data.get('price', 0)},
  "volume_24h": {token_data.get('volume_24h', 0)},
  "holders": {token_data.get('holders', 0)},
  "age_hours": {token_data.get('age_hours', 0)}
}}

Return JSON with: score (0-100), conviction (LOW/MEDIUM/HIGH), signals (array), entry_timing (EARLY/OPTIMAL/LATE), risk_factors (array), recommendation (BUY/HOLD/SELL), analysis (string)."""

        try:
            response = await self._call_ollama(prompt, system_prompt)

            # Extract JSON from response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                analysis_data = json.loads(json_str)
            else:
                raise ValueError("No JSON in response")

            return TokenSentiment(
                token_address=token_data["address"],
                symbol=token_data.get("symbol", "UNKNOWN"),
                score=float(analysis_data.get("score", 50)),
                conviction=analysis_data.get("conviction", "MEDIUM"),
                signals=analysis_data.get("signals", []),
                entry_timing=analysis_data.get("entry_timing", "OPTIMAL"),
                risk_factors=analysis_data.get("risk_factors", []),
                recommendation=analysis_data.get("recommendation", "HOLD"),
                analysis=analysis_data.get("analysis", "No analysis"),
                updated_at=datetime.utcnow(),
            )

        except Exception as e:
            logger.error(f"Ollama token analysis failed: {e}")
            return TokenSentiment(
                token_address=token_data["address"],
                symbol=token_data.get("symbol", "UNKNOWN"),
                score=50.0,
                conviction="LOW",
                signals=[],
                entry_timing="LATE",
                risk_factors=["Analysis failed"],
                recommendation="HOLD",
                analysis="AI analysis unavailable",
                updated_at=datetime.utcnow(),
            )

    async def get_market_regime(self, market_data: Dict[str, Any]) -> MarketRegime:
        """Get market regime using Ollama."""
        system_prompt = """You are a market analyst. Return JSON analysis."""

        prompt = f"""Analyze market conditions and return ONLY valid JSON:

BTC 24h: {market_data.get('btc_change', 0):.2f}%
SOL 24h: {market_data.get('sol_change', 0):.2f}%

Return JSON with: regime (BULL/BEAR/NEUTRAL), risk_level (LOW/NORMAL/HIGH/EXTREME)."""

        try:
            response = await self._call_ollama(prompt, system_prompt)

            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                regime_data = json.loads(json_str)
            else:
                raise ValueError("No JSON in response")

            return MarketRegime(
                regime=regime_data.get("regime", "NEUTRAL"),
                risk_level=regime_data.get("risk_level", "NORMAL"),
                btc_change_24h=market_data.get("btc_change", 0.0),
                sol_change_24h=market_data.get("sol_change", 0.0),
                updated_at=datetime.utcnow(),
            )

        except Exception as e:
            logger.error(f"Ollama market regime failed: {e}")
            return MarketRegime(
                regime="NEUTRAL",
                risk_level="NORMAL",
                btc_change_24h=market_data.get("btc_change", 0.0),
                sol_change_24h=market_data.get("sol_change", 0.0),
                updated_at=datetime.utcnow(),
            )


# =============================================================================
# Sentiment Service (Main Interface)
# =============================================================================

class SentimentService:
    """
    Main sentiment service that routes to appropriate AI provider.
    Rule #2: All AI selection logic server-side - client has no control.
    """

    def __init__(self):
        self.provider = self._initialize_provider()

    def _initialize_provider(self) -> Optional[AIProvider]:
        """Initialize AI provider based on config."""
        if settings.OLLAMA_ENABLED:
            logger.info("Initializing Ollama AI provider (local)")
            return OllamaProvider()
        elif settings.XAI_ENABLED and settings.XAI_API_KEY:
            logger.info("Initializing Grok AI provider (cloud)")
            return GrokProvider()
        else:
            logger.warning("No AI provider configured")
            return None

    async def analyze_token(self, token_data: Dict[str, Any]) -> TokenSentiment:
        """
        Analyze token sentiment.
        Rule #1: Client provides token data, server does analysis.
        """
        if not self.provider:
            # Return neutral sentiment if no AI provider
            return TokenSentiment(
                token_address=token_data.get("address", "unknown"),
                symbol=token_data.get("symbol", "UNKNOWN"),
                score=50.0,
                conviction="LOW",
                signals=[],
                entry_timing="LATE",
                risk_factors=["AI provider not configured"],
                recommendation="HOLD",
                analysis="AI sentiment analysis not available",
                updated_at=datetime.utcnow(),
            )

        return await self.provider.analyze_token(token_data)

    async def get_market_regime(self, market_data: Optional[Dict[str, Any]] = None) -> MarketRegime:
        """
        Get current market regime.
        Rule #2: Server fetches market data and analyzes it.
        """
        if market_data is None:
            # Fetch market data server-side (would call price APIs)
            market_data = {
                "btc_change": 0.0,  # TODO: Fetch from CoinGecko/Binance
                "sol_change": 0.0,
                "market_trend": "unknown",
                "volume_trend": "unknown",
            }

        if not self.provider:
            return MarketRegime(
                regime="NEUTRAL",
                risk_level="NORMAL",
                btc_change_24h=market_data.get("btc_change", 0.0),
                sol_change_24h=market_data.get("sol_change", 0.0),
                updated_at=datetime.utcnow(),
            )

        return await self.provider.get_market_regime(market_data)

    async def batch_analyze_tokens(
        self,
        tokens: List[Dict[str, Any]],
        max_concurrent: int = 5,
    ) -> List[TokenSentiment]:
        """
        Analyze multiple tokens in parallel.
        Rule #2: Server controls concurrency - client can't DOS the AI API.
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_with_limit(token_data):
            async with semaphore:
                return await self.analyze_token(token_data)

        tasks = [analyze_with_limit(token) for token in tokens]
        return await asyncio.gather(*tasks, return_exceptions=True)


# Singleton instance
_sentiment_service: Optional[SentimentService] = None


def get_sentiment_service() -> SentimentService:
    """Get sentiment service singleton."""
    global _sentiment_service
    if _sentiment_service is None:
        _sentiment_service = SentimentService()
    return _sentiment_service


# Export
__all__ = [
    "MarketRegime",
    "TokenSentiment",
    "SentimentService",
    "get_sentiment_service",
]
