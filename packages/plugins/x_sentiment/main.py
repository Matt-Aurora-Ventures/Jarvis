"""
X/Twitter Sentiment Plugin for LifeOS.

Wraps the x_sentiment module as a plugin with:
- PAE Providers: Sentiment data, trend analysis
- PAE Actions: Analyze text, analyze crypto, analyze trend
- Event integration for sentiment alerts
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from lifeos.plugins.base import Plugin
from lifeos.pae.base import EvaluationResult

logger = logging.getLogger(__name__)


class AnalyzeSentimentAction:
    """Action to analyze sentiment of text."""

    name = "x.analyze_sentiment"
    description = "Analyze sentiment of X/Twitter text"
    requires_confirmation = False

    def __init__(self, plugin_id: str, config: Dict[str, Any]):
        self._plugin_id = plugin_id
        self._config = config
        self._analyzer = None

    def set_analyzer(self, module) -> None:
        """Set the analyzer module."""
        self._analyzer = module

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute sentiment analysis."""
        text = params.get("text")
        focus = params.get("focus", self._config.get("default_focus", "general"))
        context = params.get("context")

        if not text:
            raise ValueError("text is required")

        if not self._analyzer:
            return {
                "success": False,
                "error": "Analyzer not initialized",
            }

        try:
            result = self._analyzer.analyze_sentiment(text, context, focus)
            if result:
                return {
                    "success": True,
                    "sentiment": result.sentiment,
                    "confidence": result.confidence,
                    "key_topics": result.key_topics,
                    "emotional_tone": result.emotional_tone,
                    "market_relevance": result.market_relevance,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            else:
                return {
                    "success": False,
                    "error": "Analysis returned no result",
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }


class AnalyzeCryptoAction:
    """Action to analyze crypto sentiment on X."""

    name = "x.analyze_crypto"
    description = "Analyze X sentiment for a cryptocurrency"
    requires_confirmation = False

    def __init__(self, plugin_id: str, config: Dict[str, Any]):
        self._plugin_id = plugin_id
        self._config = config
        self._analyzer = None

    def set_analyzer(self, module) -> None:
        """Set the analyzer module."""
        self._analyzer = module

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute crypto sentiment analysis."""
        symbol = params.get("symbol")
        sample_size = params.get("sample_size", 10)

        if not symbol:
            raise ValueError("symbol is required")

        if not self._analyzer:
            return {
                "success": False,
                "error": "Analyzer not initialized",
            }

        try:
            result = self._analyzer.analyze_crypto_sentiment(symbol, sample_size)
            if result:
                return {
                    "success": True,
                    "symbol": symbol,
                    "data": result,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            else:
                return {
                    "success": False,
                    "error": "Analysis returned no result",
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }


class AnalyzeTrendAction:
    """Action to analyze X trends for a topic."""

    name = "x.analyze_trend"
    description = "Analyze X trends for a topic"
    requires_confirmation = False

    def __init__(self, plugin_id: str, config: Dict[str, Any]):
        self._plugin_id = plugin_id
        self._config = config
        self._analyzer = None

    def set_analyzer(self, module) -> None:
        """Set the analyzer module."""
        self._analyzer = module

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute trend analysis."""
        topic = params.get("topic")
        timeframe = params.get("timeframe", "24h")

        if not topic:
            raise ValueError("topic is required")

        if not self._analyzer:
            return {
                "success": False,
                "error": "Analyzer not initialized",
            }

        try:
            result = self._analyzer.analyze_trend(topic, timeframe)
            if result:
                return {
                    "success": True,
                    "topic": result.topic,
                    "sentiment": result.sentiment,
                    "volume": result.volume,
                    "key_drivers": result.key_drivers,
                    "notable_voices": result.notable_voices,
                    "market_impact": result.market_impact,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            else:
                return {
                    "success": False,
                    "error": "Trend analysis unavailable",
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }


class SentimentProvider:
    """Provider for sentiment data."""

    name = "x.sentiment"
    description = "Get X sentiment for text or crypto"

    def __init__(self, plugin_id: str, config: Dict[str, Any]):
        self._plugin_id = plugin_id
        self._config = config
        self._analyzer = None

    def set_analyzer(self, module) -> None:
        """Set the analyzer module."""
        self._analyzer = module

    async def provide(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Provide sentiment data."""
        text = query.get("text")
        symbol = query.get("symbol")

        if not self._analyzer:
            return {
                "available": False,
                "error": "Analyzer not initialized",
            }

        result = {}

        if text:
            focus = query.get("focus", "general")
            sentiment = self._analyzer.analyze_sentiment(text, focus=focus)
            if sentiment:
                result["text_sentiment"] = {
                    "sentiment": sentiment.sentiment,
                    "confidence": sentiment.confidence,
                    "key_topics": sentiment.key_topics,
                }

        if symbol:
            crypto = self._analyzer.analyze_crypto_sentiment(symbol)
            if crypto:
                result["crypto_sentiment"] = crypto

        result["timestamp"] = datetime.now(timezone.utc).isoformat()
        result["available"] = bool(result.get("text_sentiment") or result.get("crypto_sentiment"))

        return result


class TrendProvider:
    """Provider for trend data."""

    name = "x.trends"
    description = "Get X trend analysis"

    def __init__(self, plugin_id: str, config: Dict[str, Any]):
        self._plugin_id = plugin_id
        self._config = config
        self._analyzer = None

    def set_analyzer(self, module) -> None:
        """Set the analyzer module."""
        self._analyzer = module

    async def provide(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Provide trend data."""
        topic = query.get("topic")
        timeframe = query.get("timeframe", "24h")

        if not topic:
            return {
                "available": False,
                "error": "topic is required",
            }

        if not self._analyzer:
            return {
                "available": False,
                "error": "Analyzer not initialized",
            }

        result = self._analyzer.analyze_trend(topic, timeframe)
        if result:
            return {
                "available": True,
                "topic": result.topic,
                "sentiment": result.sentiment,
                "volume": result.volume,
                "key_drivers": result.key_drivers,
                "notable_voices": result.notable_voices,
                "market_impact": result.market_impact,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        else:
            return {
                "available": False,
                "error": "Trend analysis unavailable",
            }


class SentimentEvaluator:
    """Evaluator for sentiment-based decisions."""

    name = "x.sentiment_evaluator"
    description = "Evaluate if sentiment supports an action"

    def __init__(self, plugin_id: str, config: Dict[str, Any]):
        self._plugin_id = plugin_id
        self._config = config
        self._analyzer = None

    def set_analyzer(self, module) -> None:
        """Set the analyzer module."""
        self._analyzer = module

    async def evaluate(self, context: Dict[str, Any]) -> EvaluationResult:
        """Evaluate sentiment for decision support."""
        symbol = context.get("symbol")
        required_sentiment = context.get("required_sentiment", "bullish")
        min_confidence = context.get("min_confidence", 0.6)

        if not symbol:
            return EvaluationResult(
                decision=False,
                confidence=0.0,
                reasoning="No symbol provided for sentiment evaluation",
                metadata={},
            )

        if not self._analyzer:
            return EvaluationResult(
                decision=False,
                confidence=0.0,
                reasoning="Analyzer not available",
                metadata={},
            )

        try:
            result = self._analyzer.analyze_crypto_sentiment(symbol)
            if not result:
                return EvaluationResult(
                    decision=False,
                    confidence=0.0,
                    reasoning="Could not analyze sentiment",
                    metadata={},
                )

            # Extract sentiment from result
            sentiment = result.get("sentiment", result.get("overall_sentiment", "neutral"))
            strength = result.get("sentiment_strength", result.get("strength", 50)) / 100

            # Normalize sentiment
            if isinstance(sentiment, str):
                sentiment = sentiment.lower()

            # Check if sentiment matches required
            sentiment_matches = (
                (required_sentiment == "bullish" and sentiment in ["bullish", "positive"]) or
                (required_sentiment == "bearish" and sentiment in ["bearish", "negative"]) or
                (required_sentiment == "neutral" and sentiment in ["neutral", "mixed"])
            )

            decision = sentiment_matches and strength >= min_confidence

            return EvaluationResult(
                decision=decision,
                confidence=strength,
                reasoning=f"Sentiment: {sentiment} ({strength:.0%} strength). "
                         f"Required: {required_sentiment} with {min_confidence:.0%} min confidence.",
                metadata={
                    "symbol": symbol,
                    "sentiment": sentiment,
                    "strength": strength,
                    "raw_result": result,
                },
            )
        except Exception as e:
            return EvaluationResult(
                decision=False,
                confidence=0.0,
                reasoning=f"Evaluation failed: {str(e)}",
                metadata={},
            )


class XSentimentPlugin(Plugin):
    """
    X/Twitter Sentiment Analysis Plugin.

    Provides:
    - Sentiment analysis for text
    - Crypto sentiment from X
    - Trend analysis
    - Sentiment-based evaluation
    """

    def __init__(self, context, manifest):
        super().__init__(context, manifest)
        self._analyzer = None
        self._actions: List[Any] = []
        self._providers: List[Any] = []
        self._evaluators: List[Any] = []

    async def on_load(self) -> None:
        """Initialize the plugin."""
        logger.info("Loading X Sentiment plugin")

        # Try to import the analyzer module
        try:
            from core import x_sentiment
            self._analyzer = x_sentiment
            logger.info("X sentiment analyzer loaded")
        except ImportError as e:
            logger.warning(f"x_sentiment module not available: {e}")
            self._analyzer = None

        # Get plugin config
        config = self._context.config if self._context else {}

        # Create PAE components
        self._actions = [
            AnalyzeSentimentAction(self._manifest.name, config),
            AnalyzeCryptoAction(self._manifest.name, config),
            AnalyzeTrendAction(self._manifest.name, config),
        ]

        self._providers = [
            SentimentProvider(self._manifest.name, config),
            TrendProvider(self._manifest.name, config),
        ]

        self._evaluators = [
            SentimentEvaluator(self._manifest.name, config),
        ]

        # Set analyzer on all components
        for action in self._actions:
            action.set_analyzer(self._analyzer)
        for provider in self._providers:
            provider.set_analyzer(self._analyzer)
        for evaluator in self._evaluators:
            evaluator.set_analyzer(self._analyzer)

        # Register with PAE if available
        if self._context and "jarvis" in self._context.services:
            jarvis = self._context.services["jarvis"]
            if hasattr(jarvis, "pae"):
                for action in self._actions:
                    jarvis.pae.register_action(action)
                for provider in self._providers:
                    jarvis.pae.register_provider(provider)
                for evaluator in self._evaluators:
                    jarvis.pae.register_evaluator(evaluator)
                logger.info("Registered X Sentiment PAE components")

    async def on_enable(self) -> None:
        """Enable the plugin."""
        logger.info("Enabling X Sentiment plugin")

        # Subscribe to sentiment request events
        if self._context and "event_bus" in self._context.services:
            event_bus = self._context.services["event_bus"]

            @event_bus.on("sentiment.request")
            async def handle_sentiment_request(event):
                symbol = event.data.get("symbol")
                if symbol and self._analyzer:
                    result = self._analyzer.analyze_crypto_sentiment(symbol)
                    if result:
                        await event_bus.emit("sentiment.result", {
                            "symbol": symbol,
                            "result": result,
                            "correlation_id": event.correlation_id,
                        })

            await event_bus.emit("x_sentiment.enabled", {
                "analyzer_available": self._analyzer is not None,
            })

    async def on_disable(self) -> None:
        """Disable the plugin."""
        logger.info("Disabling X Sentiment plugin")

        if self._context and "event_bus" in self._context.services:
            await self._context.services["event_bus"].emit("x_sentiment.disabled")

    async def on_unload(self) -> None:
        """Clean up plugin resources."""
        logger.info("Unloading X Sentiment plugin")
        self._analyzer = None
        self._actions.clear()
        self._providers.clear()
        self._evaluators.clear()

    # Public API methods

    def analyze_sentiment(
        self,
        text: str,
        context: Optional[str] = None,
        focus: str = "general"
    ) -> Optional[Dict[str, Any]]:
        """Analyze sentiment of text."""
        if not self._analyzer:
            return None

        result = self._analyzer.analyze_sentiment(text, context, focus)
        if result:
            return {
                "sentiment": result.sentiment,
                "confidence": result.confidence,
                "key_topics": result.key_topics,
                "emotional_tone": result.emotional_tone,
                "market_relevance": result.market_relevance,
            }
        return None

    def analyze_crypto(self, symbol: str, sample_size: int = 10) -> Optional[Dict[str, Any]]:
        """Analyze crypto sentiment on X."""
        if not self._analyzer:
            return None
        return self._analyzer.analyze_crypto_sentiment(symbol, sample_size)

    def analyze_trend(self, topic: str, timeframe: str = "24h") -> Optional[Dict[str, Any]]:
        """Analyze trends on X."""
        if not self._analyzer:
            return None

        result = self._analyzer.analyze_trend(topic, timeframe)
        if result:
            return {
                "topic": result.topic,
                "sentiment": result.sentiment,
                "volume": result.volume,
                "key_drivers": result.key_drivers,
                "notable_voices": result.notable_voices,
                "market_impact": result.market_impact,
            }
        return None

    def is_available(self) -> bool:
        """Check if analyzer is available."""
        return self._analyzer is not None
