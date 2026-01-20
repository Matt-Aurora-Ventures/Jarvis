"""
Trending Token Tracker for Twitter/X Bot

Tracks trending tokens and detects patterns:
- Monitor trending tokens on exchanges
- Detect pump/dump patterns
- Track social mentions spike
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)

# Default data directory
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "social" / "trending"


class TrendingTokenTracker:
    """
    Tracks trending tokens across exchanges.

    Usage:
        tracker = TrendingTokenTracker()
        trending = tracker.get_trending_tokens(limit=10)
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        exchanges: Optional[List[str]] = None
    ):
        """
        Initialize trending token tracker.

        Args:
            data_dir: Directory for caching data
            exchanges: List of exchanges to monitor
        """
        self.data_dir = data_dir or DEFAULT_DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.exchanges = exchanges or ["jupiter", "raydium", "orca"]
        self._cache_file = self.data_dir / "trending_tokens.json"
        self._cached_data: List[Dict[str, Any]] = []
        self._last_fetch: Optional[datetime] = None
        self._alerts_config: Dict[str, Any] = {}

        self._load_cache()

    def _load_cache(self):
        """Load cached trending data."""
        try:
            if self._cache_file.exists():
                data = json.loads(self._cache_file.read_text())
                self._cached_data = data.get("tokens", [])
                updated_at = data.get("updated_at")
                if updated_at:
                    self._last_fetch = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")

    def _cache_trending_data(self, tokens: List[Dict[str, Any]]):
        """Cache trending data to file."""
        try:
            data = {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "tokens": tokens
            }
            self._cache_file.write_text(json.dumps(data, indent=2))
            self._cached_data = tokens
            self._last_fetch = datetime.now(timezone.utc)
        except Exception as e:
            logger.error(f"Failed to cache data: {e}")

    def _fetch_exchange_data(self) -> List[Dict[str, Any]]:
        """
        Fetch data from exchanges.
        Override this method for actual API integration.

        Returns:
            List of token data dicts
        """
        # Placeholder - actual implementation would call exchange APIs
        return []

    def get_trending_tokens(
        self,
        limit: int = 20,
        sort_by: str = "volume",
        min_change: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Get trending tokens.

        Args:
            limit: Maximum number of tokens to return
            sort_by: Sort key ("volume" or "change")
            min_change: Minimum price change percentage filter

        Returns:
            List of trending token dicts
        """
        # Try to fetch fresh data
        fresh_data = self._fetch_exchange_data()

        if fresh_data:
            tokens = fresh_data
            self._cache_trending_data(tokens)
        else:
            tokens = self._cached_data

        # Filter by minimum change
        if min_change is not None:
            tokens = [
                t for t in tokens
                if t.get("price_change_24h", 0) >= min_change
            ]

        # Sort
        if sort_by == "volume":
            tokens = sorted(tokens, key=lambda x: x.get("volume_24h", 0), reverse=True)
        elif sort_by == "change":
            tokens = sorted(tokens, key=lambda x: x.get("price_change_24h", 0), reverse=True)

        return tokens[:limit]

    def get_cached_trending(self) -> List[Dict[str, Any]]:
        """
        Get cached trending data without fetching.

        Returns:
            Cached token list
        """
        return self._cached_data

    def configure_alerts(
        self,
        pump_threshold: float = 0.5,
        mention_spike_multiplier: float = 5.0
    ):
        """
        Configure alert thresholds.

        Args:
            pump_threshold: Price change threshold for pump alert
            mention_spike_multiplier: Multiplier for mention spike alert
        """
        self._alerts_config = {
            "pump_threshold": pump_threshold,
            "mention_spike_multiplier": mention_spike_multiplier
        }

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """
        Get currently active alerts.

        Returns:
            List of alert dicts
        """
        alerts = []

        # Check for pump alerts
        for token in self._cached_data:
            change = token.get("price_change_24h", 0)
            threshold = self._alerts_config.get("pump_threshold", 0.5)

            if change >= threshold * 100:  # Convert to percentage
                alerts.append({
                    "type": "pump",
                    "symbol": token.get("symbol"),
                    "change": change,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

        return alerts


class PumpDumpDetector:
    """
    Detects pump and dump patterns in token prices.

    Usage:
        detector = PumpDumpDetector()
        result = detector.detect_pump(price_data)
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        pump_threshold: float = 0.5,
        dump_threshold: float = 0.3,
        volume_multiplier: float = 3.0
    ):
        """
        Initialize pump/dump detector.

        Args:
            data_dir: Directory for storing detected patterns
            pump_threshold: Price increase threshold for pump (0.5 = 50%)
            dump_threshold: Price decrease threshold for dump (0.3 = 30%)
            volume_multiplier: Volume spike multiplier
        """
        self.data_dir = data_dir or DEFAULT_DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.pump_threshold = pump_threshold
        self.dump_threshold = dump_threshold
        self.volume_multiplier = volume_multiplier

        self._flagged_tokens: Dict[str, Dict[str, Any]] = {}
        self._patterns_file = self.data_dir / "detected_patterns.json"

    def detect_pump(self, price_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect pump pattern in price data.

        Args:
            price_data: Dict with symbol, prices, volumes, timestamps

        Returns:
            Detection result with is_pump, confidence
        """
        prices = price_data.get("prices", [])
        volumes = price_data.get("volumes", [])

        if len(prices) < 2:
            return {"is_pump": False, "confidence": 0}

        # Calculate price change
        start_price = prices[0]
        end_price = prices[-1]

        if start_price <= 0:
            return {"is_pump": False, "confidence": 0}

        price_change = (end_price - start_price) / start_price

        # Check for pump
        if price_change >= self.pump_threshold:
            # Calculate confidence based on volume
            confidence = 0.7

            if volumes:
                avg_volume_start = sum(volumes[:len(volumes)//2]) / max(1, len(volumes)//2)
                avg_volume_end = sum(volumes[len(volumes)//2:]) / max(1, len(volumes) - len(volumes)//2)

                if avg_volume_start > 0 and avg_volume_end >= avg_volume_start * self.volume_multiplier:
                    confidence = 0.9

            return {
                "is_pump": True,
                "confidence": confidence,
                "price_change": price_change,
                "symbol": price_data.get("symbol", "UNKNOWN")
            }

        return {"is_pump": False, "confidence": 0}

    def detect_dump(self, price_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect dump pattern in price data.

        Args:
            price_data: Dict with symbol, prices, volumes, timestamps

        Returns:
            Detection result with is_dump, confidence
        """
        prices = price_data.get("prices", [])

        if len(prices) < 2:
            return {"is_dump": False, "confidence": 0}

        # Calculate price change (from high to low)
        max_price = max(prices)
        end_price = prices[-1]

        if max_price <= 0:
            return {"is_dump": False, "confidence": 0}

        price_drop = (max_price - end_price) / max_price

        # Check for dump
        if price_drop >= self.dump_threshold:
            confidence = min(0.7 + (price_drop - self.dump_threshold), 0.95)

            return {
                "is_dump": True,
                "confidence": confidence,
                "price_drop": price_drop,
                "symbol": price_data.get("symbol", "UNKNOWN")
            }

        return {"is_dump": False, "confidence": 0}

    def detect_pump_and_dump(self, price_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect pump followed by dump pattern.

        Args:
            price_data: Dict with symbol, prices, volumes, timestamps

        Returns:
            Detection result with pattern_detected, risk_level
        """
        prices = price_data.get("prices", [])

        if len(prices) < 4:
            return {"pattern_detected": False, "risk_level": "low"}

        # Find peak
        peak_idx = prices.index(max(prices))

        if peak_idx < 2 or peak_idx >= len(prices) - 1:
            return {"pattern_detected": False, "risk_level": "low"}

        # Check for pump before peak
        start_to_peak = (prices[peak_idx] - prices[0]) / prices[0] if prices[0] > 0 else 0

        # Check for dump after peak
        peak_to_end = (prices[peak_idx] - prices[-1]) / prices[peak_idx] if prices[peak_idx] > 0 else 0

        # Pattern detected if both pump and dump
        if start_to_peak >= self.pump_threshold and peak_to_end >= self.dump_threshold:
            # Calculate risk level
            if peak_to_end >= 0.7:
                risk = "extreme"
            elif peak_to_end >= 0.5:
                risk = "high"
            else:
                risk = "medium"

            # Flag the token
            symbol = price_data.get("symbol", "UNKNOWN")
            self._flagged_tokens[symbol] = {
                "risk": risk,
                "pattern": "pump_and_dump",
                "detected_at": datetime.now(timezone.utc).isoformat()
            }

            return {
                "pattern_detected": True,
                "risk_level": risk,
                "pump_percent": start_to_peak,
                "dump_percent": peak_to_end
            }

        return {"pattern_detected": False, "risk_level": "low"}

    def get_risk_tokens(self) -> List[Dict[str, Any]]:
        """
        Get list of tokens flagged as risky.

        Returns:
            List of flagged token dicts
        """
        return [
            {"symbol": symbol, **data}
            for symbol, data in self._flagged_tokens.items()
        ]


class MentionTracker:
    """
    Tracks social media mentions for tokens.

    Usage:
        tracker = MentionTracker()
        tracker.record_mention("SOL", count=50)
        spike = tracker.detect_spike("SOL")
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        spike_threshold: float = 3.0
    ):
        """
        Initialize mention tracker.

        Args:
            data_dir: Directory for storing mention history
            spike_threshold: Multiplier for spike detection
        """
        self.data_dir = data_dir or DEFAULT_DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.spike_threshold = spike_threshold
        self._history_file = self.data_dir / "mention_history.json"

        # In-memory storage: symbol -> list of (timestamp, count)
        self._mentions: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        self._twitter_client = None

        self._load_history()

    def _load_history(self):
        """Load mention history from file."""
        try:
            if self._history_file.exists():
                data = json.loads(self._history_file.read_text())
                for symbol, entries in data.get("mentions", {}).items():
                    self._mentions[symbol] = entries
        except Exception as e:
            logger.warning(f"Failed to load mention history: {e}")

    def save_history(self):
        """Save mention history to file."""
        try:
            data = {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "mentions": dict(self._mentions)
            }
            self._history_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Failed to save mention history: {e}")

    def record_mention(
        self,
        symbol: str,
        count: int,
        timestamp: Optional[datetime] = None
    ):
        """
        Record mention count for a token.

        Args:
            symbol: Token symbol
            count: Number of mentions
            timestamp: Optional timestamp (defaults to now)
        """
        ts = timestamp or datetime.now(timezone.utc)

        self._mentions[symbol.upper()].append({
            "timestamp": ts.isoformat(),
            "count": count
        })

        # Keep only last 100 entries per symbol
        if len(self._mentions[symbol.upper()]) > 100:
            self._mentions[symbol.upper()] = self._mentions[symbol.upper()][-100:]

    def get_mention_stats(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get mention statistics for a token.

        Args:
            symbol: Token symbol

        Returns:
            Stats dict or None
        """
        symbol = symbol.upper()
        entries = self._mentions.get(symbol, [])

        if not entries:
            return None

        total = sum(e["count"] for e in entries)
        avg = total / len(entries) if entries else 0

        return {
            "symbol": symbol,
            "total_mentions": total,
            "average_mentions": avg,
            "data_points": len(entries)
        }

    def detect_spike(self, symbol: str) -> Dict[str, Any]:
        """
        Detect mention spike for a token.

        Args:
            symbol: Token symbol

        Returns:
            Spike detection result
        """
        symbol = symbol.upper()
        entries = self._mentions.get(symbol, [])

        if len(entries) < 2:
            return {"is_spike": False, "multiplier": 0}

        # Calculate baseline (excluding most recent)
        baseline_entries = entries[:-1]
        baseline_avg = sum(e["count"] for e in baseline_entries) / len(baseline_entries)

        if baseline_avg <= 0:
            return {"is_spike": False, "multiplier": 0}

        # Get most recent count
        recent_count = entries[-1]["count"]

        multiplier = recent_count / baseline_avg

        is_spike = multiplier >= self.spike_threshold

        return {
            "is_spike": is_spike,
            "multiplier": round(multiplier, 2),
            "recent_count": recent_count,
            "baseline_avg": round(baseline_avg, 2)
        }

    def get_trending_by_mentions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get tokens sorted by recent mentions.

        Args:
            limit: Maximum number of tokens to return

        Returns:
            List of token mention stats
        """
        stats = []

        for symbol in self._mentions:
            stat = self.get_mention_stats(symbol)
            if stat:
                stats.append(stat)

        # Sort by total mentions
        stats.sort(key=lambda x: x["total_mentions"], reverse=True)

        return stats[:limit]

    async def fetch_twitter_mentions(self, symbol: str) -> int:
        """
        Fetch mentions from Twitter.

        Args:
            symbol: Token symbol

        Returns:
            Count of mentions found
        """
        if not self._twitter_client:
            return 0

        try:
            results = await self._twitter_client.search_recent(
                query=f"${symbol}",
                max_results=100
            )
            count = len(results) if results else 0

            self.record_mention(symbol, count)
            return count

        except Exception as e:
            logger.error(f"Failed to fetch Twitter mentions: {e}")
            return 0
