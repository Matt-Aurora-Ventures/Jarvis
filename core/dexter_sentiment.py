"""
Dexter (Claude CLI) Integration with JARVIS Sentiment Analysis.

Provides a bridge for Dexter to:
- Query sentiment data (latest reports, token-specific sentiment)
- Trigger sentiment analysis via CLI commands
- Respect timing controls from context_engine

Usage from CLI:
    # Query latest sentiment
    dexter> get sentiment report

    # Get specific token sentiment
    dexter> sentiment for BONK

    # Trigger new analysis
    dexter> run sentiment analysis
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Path to predictions history written by SentimentReportGenerator
_ROOT = Path(__file__).resolve().parents[1]
_PREDICTIONS_FILE = _ROOT / "bots" / "buy_tracker" / "predictions_history.json"

# Sentiment command patterns
SENTIMENT_COMMAND_PATTERNS = [
    r'\b(get|show|display)\s+.*\b(sentiment|market)',  # "show me the sentiment"
    r'\b(sentiment|market)\s+(for|of|on)\s+\w+',
    r'\b(run|trigger|start)\s+sentiment\s*(analysis)?',
    r"\bwhat'?s?\s+(the\s+)?(market\s+)?sentiment",
    r'\bsentiment\s+report',
    r'\bmarket\s+sentiment',
]

# Compiled patterns for efficiency
_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in SENTIMENT_COMMAND_PATTERNS]


def is_sentiment_command(command: str) -> bool:
    """
    Check if a command is sentiment-related.

    Args:
        command: The user's command text

    Returns:
        True if this is a sentiment command, False otherwise
    """
    for pattern in _COMPILED_PATTERNS:
        if pattern.search(command):
            return True
    return False


def format_sentiment_for_cli(report: Dict[str, Any]) -> str:
    """
    Format a sentiment report for CLI display.

    Args:
        report: Sentiment report dictionary

    Returns:
        Formatted string for CLI output
    """
    lines = []

    # Header
    generated_at = report.get("generated_at", "unknown")
    market_regime = report.get("market_regime", "UNKNOWN")
    lines.append(f"JARVIS Sentiment Report")
    lines.append(f"Generated: {generated_at}")
    lines.append(f"Market Regime: {market_regime}")
    lines.append("-" * 40)

    # Tokens
    tokens = report.get("tokens", [])
    if tokens:
        lines.append("\nToken Sentiments:")
        for token in tokens:
            symbol = token.get("symbol", "???")
            sentiment = token.get("sentiment", "neutral")
            score = token.get("score", 0)
            change = token.get("change_24h", 0)

            # Sentiment indicator
            if sentiment.lower() == "bullish":
                indicator = "[+]"
            elif sentiment.lower() == "bearish":
                indicator = "[-]"
            else:
                indicator = "[=]"

            lines.append(
                f"  {indicator} {symbol}: {sentiment} (score: {score:.2f}, 24h: {change:+.1f}%)"
            )
    else:
        lines.append("\nNo token data available.")

    return "\n".join(lines)


def format_token_sentiment_for_cli(token_data: Dict[str, Any]) -> str:
    """
    Format a single token's sentiment for CLI display.

    Args:
        token_data: Token sentiment dictionary

    Returns:
        Formatted string for CLI output
    """
    symbol = token_data.get("symbol", "???")
    sentiment = token_data.get("sentiment", "neutral")
    score = token_data.get("score", 0)
    change = token_data.get("change_24h", 0)
    volume = token_data.get("volume_24h", 0)

    lines = [
        f"Token: {symbol}",
        f"Sentiment: {sentiment}",
        f"Score: {score:.2f}",
        f"24h Change: {change:+.1f}%",
        f"24h Volume: ${volume:,.0f}",
    ]

    return "\n".join(lines)


class DexterSentimentBridge:
    """
    Bridge between Dexter (Claude CLI) and JARVIS sentiment analysis.

    Allows Dexter to query and trigger sentiment analysis while respecting
    timing controls from the context engine.
    """

    def __init__(
        self,
        context_engine=None,
        sentiment_service=None,
        sentiment_generator=None,
    ):
        """
        Initialize the bridge.

        Args:
            context_engine: Optional context engine for timing controls
            sentiment_service: Optional sentiment service for data queries
            sentiment_generator: Optional generator for triggering analysis
        """
        self._context_engine = context_engine
        self._sentiment_service = sentiment_service
        self._sentiment_generator = sentiment_generator

        # Lazy-load defaults
        self._cached_report: Optional[Dict[str, Any]] = None
        self._cache_time: Optional[datetime] = None
        self._cache_ttl_seconds = 300  # 5 minutes

    @property
    def context_engine(self):
        """Lazy-load context engine."""
        if self._context_engine is None:
            try:
                from core.context_engine import context
                self._context_engine = context
            except ImportError:
                logger.warning("Context engine not available")
        return self._context_engine

    @property
    def sentiment_service(self):
        """Lazy-load sentiment service."""
        if self._sentiment_service is None:
            try:
                from tg_bot.services.signal_service import get_signal_service
                self._sentiment_service = get_signal_service()
            except ImportError:
                logger.warning("Sentiment service not available")
        return self._sentiment_service

    def get_latest_report(self, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get the latest sentiment report.

        Args:
            use_cache: Whether to use cached data if available

        Returns:
            Sentiment report dictionary or None
        """
        # Check for cached report first
        if use_cache and self._sentiment_service:
            cached = getattr(self._sentiment_service, "get_cached_report", None)
            if cached:
                cached_report = cached()
                if cached_report:
                    return cached_report

        # Check local cache
        if use_cache and self._cached_report and self._cache_time:
            elapsed = (datetime.now() - self._cache_time).total_seconds()
            if elapsed < self._cache_ttl_seconds:
                return self._cached_report

        # Get from service if available
        if self._sentiment_service and hasattr(self._sentiment_service, "get_latest_report"):
            try:
                report = self._sentiment_service.get_latest_report()
                if report:
                    self._cached_report = report
                    self._cache_time = datetime.now()
                    return report
            except Exception as e:
                logger.debug(f"Sentiment service report failed: {e}")

        # Fallback: load from predictions history
        report = self._load_latest_predictions()
        if report:
            self._cached_report = report
            self._cache_time = datetime.now()
            return report

        return None

    def get_token_sentiment(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get sentiment for a specific token.

        Args:
            symbol: Token symbol (e.g., "BONK")

        Returns:
            Token sentiment dictionary or None
        """
        if self._sentiment_service and hasattr(self._sentiment_service, "get_token_sentiment"):
            try:
                return self._sentiment_service.get_token_sentiment(symbol.upper())
            except Exception as e:
                logger.debug(f"Sentiment service token lookup failed: {e}")

        return self._load_token_prediction(symbol)

    async def trigger_sentiment_analysis(
        self, force: bool = False
    ) -> Tuple[bool, str]:
        """
        Trigger a new sentiment analysis.

        Args:
            force: Force analysis even if timing doesn't allow

        Returns:
            Tuple of (success, message)
        """
        # Check timing controls unless force is True
        if not force and self.context_engine:
            if not self.context_engine.can_run_sentiment():
                return False, "Sentiment analysis blocked by timing controls. Use force=True to override."

        # Trigger the analysis
        if self._sentiment_generator:
            try:
                await self._sentiment_generator.generate_and_post_report(force=force)

                # Record the run in context engine
                if self.context_engine:
                    self.context_engine.record_sentiment_run()

                return True, "Sentiment analysis triggered successfully."
            except Exception as e:
                logger.error(f"Failed to trigger sentiment analysis: {e}")
                return False, f"Failed to trigger analysis: {e}"

        return False, "Sentiment generator not available."

    def _load_latest_predictions(self) -> Optional[Dict[str, Any]]:
        """Load the latest predictions history entry and normalize into report format."""
        if not _PREDICTIONS_FILE.exists():
            return None

        try:
            with open(_PREDICTIONS_FILE, "r", encoding="utf-8") as handle:
                history = json.load(handle)
        except Exception as e:
            logger.debug(f"Failed to read predictions history: {e}")
            return None

        if not history:
            return None

        latest = history[-1]
        token_predictions = latest.get("token_predictions", {})
        tokens: List[Dict[str, Any]] = []

        for symbol, data in token_predictions.items():
            verdict = data.get("verdict", "")
            tokens.append({
                "symbol": symbol,
                "sentiment": _normalize_sentiment(verdict),
                "score": data.get("score", 0),
                "change_24h": 0,
            })

        return {
            "tokens": tokens,
            "generated_at": latest.get("timestamp"),
            "market_regime": latest.get("market_regime", "UNKNOWN"),
        }

    def _load_token_prediction(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Load sentiment for a specific token from predictions history."""
        if not _PREDICTIONS_FILE.exists():
            return None

        try:
            with open(_PREDICTIONS_FILE, "r", encoding="utf-8") as handle:
                history = json.load(handle)
        except Exception as e:
            logger.debug(f"Failed to read predictions history: {e}")
            return None

        if not history:
            return None

        latest = history[-1]
        token_predictions = latest.get("token_predictions", {})
        token = token_predictions.get(symbol.upper())
        if not token:
            return None

        verdict = token.get("verdict", "")
        return {
            "symbol": symbol.upper(),
            "sentiment": _normalize_sentiment(verdict),
            "score": token.get("score", 0),
            "change_24h": 0,
            "volume_24h": 0,
        }


def _normalize_sentiment(verdict: str) -> str:
    verdict_upper = (verdict or "").upper()
    if "BUY" in verdict_upper or "BULL" in verdict_upper:
        return "bullish"
    if "SELL" in verdict_upper or "BEAR" in verdict_upper:
        return "bearish"
    if not verdict:
        return "neutral"
    return verdict.lower()

    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of sentiment services.

        Returns:
            Status dictionary
        """
        status = {
            "context_engine_available": self.context_engine is not None,
            "sentiment_service_available": self.sentiment_service is not None,
            "generator_available": self._sentiment_generator is not None,
            "cache_valid": self._cached_report is not None,
        }

        if self.context_engine:
            status.update(self.context_engine.get_status())

        return status


async def handle_sentiment_command(
    command: str,
    bridge: Optional[DexterSentimentBridge] = None,
) -> Optional[str]:
    """
    Handle a sentiment-related command from Dexter.

    Args:
        command: The user's command text
        bridge: Optional sentiment bridge instance

    Returns:
        Formatted response string or None
    """
    if bridge is None:
        bridge = DexterSentimentBridge()

    command_lower = command.lower()

    # Check for token-specific query
    token_match = re.search(r'sentiment\s+(?:for|of|on)\s+(\w+)', command_lower)
    if token_match:
        symbol = token_match.group(1).upper()
        token_data = bridge.get_token_sentiment(symbol)
        if token_data:
            return format_token_sentiment_for_cli(token_data)
        return f"No sentiment data available for {symbol}"

    # Check for trigger command
    if any(word in command_lower for word in ['run', 'trigger', 'start']):
        force = 'force' in command_lower
        success, message = await bridge.trigger_sentiment_analysis(force=force)
        return message

    # Default: get latest report
    report = bridge.get_latest_report()
    if report:
        return format_sentiment_for_cli(report)

    return "No sentiment report available."


# Singleton instance
_bridge: Optional[DexterSentimentBridge] = None


def get_sentiment_bridge() -> DexterSentimentBridge:
    """Get the singleton sentiment bridge instance."""
    global _bridge
    if _bridge is None:
        _bridge = DexterSentimentBridge()
    return _bridge
