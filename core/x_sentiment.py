"""
X.com (Twitter) Sentiment Analysis using Grok (X.AI).

This module provides sentiment analysis capabilities leveraging Grok's
native integration with X.com data and understanding of social media context.
"""

import json
import logging
import re
import time
from hashlib import sha256
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict

from core import providers, config

ROOT = Path(__file__).resolve().parents[1]
CACHE_PATH = ROOT / "data" / "trader" / "grok_cache.json"
USAGE_PATH = ROOT / "data" / "trader" / "grok_usage.json"
logger = logging.getLogger(__name__)

@dataclass
class SentimentResult:
    """Sentiment analysis result."""
    text: str
    sentiment: str  # "positive", "negative", "neutral", "mixed"
    confidence: float  # 0.0 to 1.0
    key_topics: List[str]
    emotional_tone: str
    market_relevance: Optional[str] = None  # For trading-related sentiment


@dataclass
class TrendAnalysis:
    """X.com trend analysis result."""
    topic: str
    sentiment: str
    volume: str  # "low", "medium", "high", "viral"
    key_drivers: List[str]
    notable_voices: List[str]
    market_impact: Optional[str] = None


def _is_grok_available() -> bool:
    """Check if Grok provider is available and configured."""
    cfg = config.load_config()
    grok_enabled = cfg.get("providers", {}).get("grok", {}).get("enabled", False)
    if not grok_enabled:
        return False

    client = providers._grok_client()
    return client is not None


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _budget_config() -> Dict[str, Any]:
    cfg = config.load_config()
    policy = cfg.get("sentiment_spend_policy", {})
    return {
        "enabled": bool(policy.get("enabled", True)),
        "daily_budget_usd": float(policy.get("daily_budget_usd", 3.0)),
        "warn_at_usd": float(policy.get("warn_at_usd", 3.0)),
        "per_request_cost_usd": float(policy.get("per_request_cost_usd", 0.05)),
        "per_cycle_cap": int(policy.get("per_cycle_cap", 5)),
        "ttl_seconds": int(policy.get("ttl_seconds", 3600)),
    }


def _usage_key() -> str:
    return time.strftime("%Y-%m-%d")


def _check_budget(requests_needed: int = 1) -> Tuple[bool, Dict[str, Any]]:
    policy = _budget_config()
    if not policy["enabled"]:
        return True, policy
    usage = _load_json(USAGE_PATH)
    day_key = _usage_key()
    daily = usage.get(day_key, {"requests": 0, "cost_usd": 0.0})
    projected_cost = daily["cost_usd"] + (requests_needed * policy["per_request_cost_usd"])
    if projected_cost > policy["daily_budget_usd"]:
        return False, policy
    return True, policy


def _record_usage(requests_used: int) -> None:
    policy = _budget_config()
    if not policy["enabled"]:
        return
    usage = _load_json(USAGE_PATH)
    day_key = _usage_key()
    daily = usage.get(day_key, {"requests": 0, "cost_usd": 0.0})
    daily["requests"] = int(daily.get("requests", 0)) + requests_used
    daily["cost_usd"] = float(daily.get("cost_usd", 0.0)) + (requests_used * policy["per_request_cost_usd"])
    usage[day_key] = daily
    _write_json(USAGE_PATH, usage)
    if daily["cost_usd"] >= policy["warn_at_usd"]:
        logger.warning("Grok spend warning: $%.2f >= $%.2f", daily["cost_usd"], policy["warn_at_usd"])


def _cache_key(text: str, focus: str) -> str:
    payload = f"{focus}::{text}".encode("utf-8")
    return sha256(payload).hexdigest()


def _cache_get(text: str, focus: str) -> Optional[Dict[str, Any]]:
    policy = _budget_config()
    cache = _load_json(CACHE_PATH)
    key = _cache_key(text, focus)
    entry = cache.get(key)
    if not entry:
        return None
    if time.time() - float(entry.get("timestamp", 0)) > policy["ttl_seconds"]:
        return None
    return entry.get("payload")


def _cache_set(text: str, focus: str, payload: Dict[str, Any]) -> None:
    cache = _load_json(CACHE_PATH)
    cache[_cache_key(text, focus)] = {
        "timestamp": time.time(),
        "payload": payload,
    }
    _write_json(CACHE_PATH, cache)


def _heuristic_sentiment(text: str) -> SentimentResult:
    lowered = text.lower()
    score = 0
    for word in ("bull", "bullish", "pump", "moon", "breakout", "strong"):
        if word in lowered:
            score += 1
    for word in ("bear", "bearish", "dump", "rug", "weak", "scam"):
        if word in lowered:
            score -= 1
    sentiment = "neutral"
    if score >= 2:
        sentiment = "positive"
    elif score <= -2:
        sentiment = "negative"
    return SentimentResult(
        text=text,
        sentiment=sentiment,
        confidence=0.35,
        key_topics=[],
        emotional_tone="heuristic",
        market_relevance=None,
    )


def analyze_sentiment(
    text: str,
    context: Optional[str] = None,
    focus: str = "general"
) -> Optional[SentimentResult]:
    """
    Analyze sentiment of text using Grok's X.com understanding.

    Args:
        text: Text to analyze (e.g., tweet, post, comment)
        context: Optional context about the topic
        focus: Analysis focus ("general", "trading", "political", "social")

    Returns:
        SentimentResult or None if Grok unavailable
    """
    cached = _cache_get(text, focus)
    if cached:
        return SentimentResult(**cached)

    allowed, policy = _check_budget(1)
    if not allowed:
        return _heuristic_sentiment(text)

    if not _is_grok_available():
        return _heuristic_sentiment(text)

    cfg = config.load_config()
    model = cfg.get("providers", {}).get("grok", {}).get("model", "grok-beta")

    # Craft specialized prompt for sentiment analysis
    context_str = f"\n\nContext: {context}" if context else ""
    focus_guidance = {
        "trading": "Focus on market sentiment, price implications, and trading signals.",
        "political": "Focus on political sentiment, policy implications, and public opinion.",
        "social": "Focus on social sentiment, cultural trends, and community reactions.",
        "general": "Provide comprehensive sentiment analysis."
    }.get(focus, "Provide comprehensive sentiment analysis.")

    prompt = f"""Analyze the sentiment of the following X.com content.
{focus_guidance}

Text: "{text}"{context_str}

Provide a JSON response with:
- sentiment: "positive", "negative", "neutral", or "mixed"
- confidence: 0.0 to 1.0
- key_topics: list of main topics/themes
- emotional_tone: brief description of emotional tone
- market_relevance: (if applicable) market impact or trading relevance

Respond with ONLY valid JSON, no other text."""

    try:
        response = providers._ask_grok(prompt, model, max_output_tokens=800)
        if not response:
            return _heuristic_sentiment(text)

        # Extract JSON from response
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if not json_match:
            return None

        data = json.loads(json_match.group())

        result = SentimentResult(
            text=text,
            sentiment=data.get("sentiment", "neutral"),
            confidence=float(data.get("confidence", 0.5)),
            key_topics=data.get("key_topics", []),
            emotional_tone=data.get("emotional_tone", "neutral"),
            market_relevance=data.get("market_relevance")
        )
        _cache_set(text, focus, asdict(result))
        _record_usage(1)
        return result
    except Exception as e:
        return _heuristic_sentiment(text)


def analyze_trend(
    topic: str,
    timeframe: str = "24h"
) -> Optional[TrendAnalysis]:
    """
    Analyze X.com trends for a topic using Grok's real-time understanding.

    Args:
        topic: Topic to analyze (e.g., "$BTC", "AI", "politics")
        timeframe: Analysis timeframe ("1h", "24h", "7d")

    Returns:
        TrendAnalysis or None if Grok unavailable
    """
    allowed, policy = _check_budget(1)
    if not allowed:
        return None

    if not _is_grok_available():
        return None

    cfg = config.load_config()
    model = cfg.get("providers", {}).get("grok", {}).get("model", "grok-beta")

    prompt = f"""Analyze X.com (Twitter) trends for the topic: "{topic}"
Timeframe: {timeframe}

Provide a JSON response with:
- topic: the topic being analyzed
- sentiment: overall sentiment ("positive", "negative", "neutral", "mixed")
- volume: discussion volume ("low", "medium", "high", "viral")
- key_drivers: list of main drivers of discussion
- notable_voices: list of influential accounts/perspectives
- market_impact: (if applicable) potential market impact

Respond with ONLY valid JSON, no other text."""

    try:
        response = providers._ask_grok(prompt, model, max_output_tokens=1000)
        if not response:
            return None

        # Extract JSON from response
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if not json_match:
            return None

        data = json.loads(json_match.group())

        result = TrendAnalysis(
            topic=data.get("topic", topic),
            sentiment=data.get("sentiment", "neutral"),
            volume=data.get("volume", "medium"),
            key_drivers=data.get("key_drivers", []),
            notable_voices=data.get("notable_voices", []),
            market_impact=data.get("market_impact")
        )
        _record_usage(1)
        return result
    except Exception as e:
        return None


def batch_sentiment_analysis(
    texts: List[str],
    focus: str = "general"
) -> List[Optional[SentimentResult]]:
    """
    Analyze sentiment for multiple texts efficiently.

    Args:
        texts: List of texts to analyze
        focus: Analysis focus for all texts

    Returns:
        List of SentimentResults (None for failed analyses)
    """
    if not texts:
        return []

    cached_results: Dict[int, SentimentResult] = {}
    uncached: List[str] = []
    uncached_indexes: List[int] = []
    for idx, text in enumerate(texts):
        cached = _cache_get(text, focus)
        if cached:
            cached_results[idx] = SentimentResult(**cached)
        else:
            uncached.append(text)
            uncached_indexes.append(idx)

    results: List[Optional[SentimentResult]] = [None] * len(texts)
    for idx, result in cached_results.items():
        results[idx] = result

    if not uncached:
        return results

    policy = _budget_config()
    if len(uncached) > policy["per_cycle_cap"]:
        uncached = uncached[: policy["per_cycle_cap"]]
        uncached_indexes = uncached_indexes[: policy["per_cycle_cap"]]

    allowed, policy = _check_budget(requests_needed=1)
    if not allowed or not _is_grok_available():
        for idx in uncached_indexes:
            results[idx] = _heuristic_sentiment(texts[idx])
        return results

    model = config.load_config().get("providers", {}).get("grok", {}).get("model", "grok-beta")
    prompt = {
        "focus": focus,
        "items": uncached,
    }
    batch_prompt = (
        "Analyze sentiment for the following items and return JSON array with "
        "sentiment, confidence, key_topics, emotional_tone, market_relevance.\n"
        f"Payload:\n{json.dumps(prompt, indent=2)}\n"
        "Respond with ONLY valid JSON."
    )
    response = providers._ask_grok(batch_prompt, model, max_output_tokens=1200)
    if not response:
        for idx in uncached_indexes:
            results[idx] = _heuristic_sentiment(texts[idx])
        return results

    try:
        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        if not json_match:
            raise ValueError("batch_json_missing")
        data = json.loads(json_match.group())
    except Exception:
        for idx in uncached_indexes:
            results[idx] = _heuristic_sentiment(texts[idx])
        return results

    for local_idx, item in enumerate(data):
        if local_idx >= len(uncached_indexes):
            break
        text = uncached[local_idx]
        result = SentimentResult(
            text=text,
            sentiment=item.get("sentiment", "neutral"),
            confidence=float(item.get("confidence", 0.5)),
            key_topics=item.get("key_topics", []),
            emotional_tone=item.get("emotional_tone", "neutral"),
            market_relevance=item.get("market_relevance"),
        )
        results[uncached_indexes[local_idx]] = result
        _cache_set(text, focus, asdict(result))

    _record_usage(1)
    for idx in uncached_indexes:
        if results[idx] is None:
            results[idx] = _heuristic_sentiment(texts[idx])
    return results


def get_sentiment_summary(results: List[SentimentResult]) -> Dict[str, Any]:
    """
    Summarize sentiment analysis results.

    Args:
        results: List of SentimentResult objects

    Returns:
        Summary dictionary with aggregate statistics
    """
    if not results:
        return {
            "total": 0,
            "positive": 0,
            "negative": 0,
            "neutral": 0,
            "mixed": 0,
            "avg_confidence": 0.0,
            "top_topics": []
        }

    sentiments = {"positive": 0, "negative": 0, "neutral": 0, "mixed": 0}
    confidences = []
    all_topics = []

    for result in results:
        sentiments[result.sentiment] = sentiments.get(result.sentiment, 0) + 1
        confidences.append(result.confidence)
        all_topics.extend(result.key_topics)

    # Count topic frequencies
    topic_counts = {}
    for topic in all_topics:
        topic_counts[topic] = topic_counts.get(topic, 0) + 1

    # Get top 5 topics
    top_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "total": len(results),
        "positive": sentiments["positive"],
        "negative": sentiments["negative"],
        "neutral": sentiments["neutral"],
        "mixed": sentiments["mixed"],
        "avg_confidence": sum(confidences) / len(confidences) if confidences else 0.0,
        "top_topics": [topic for topic, _ in top_topics]
    }


def analyze_crypto_sentiment(
    symbol: str,
    sample_size: int = 10
) -> Optional[Dict[str, Any]]:
    """
    Analyze crypto asset sentiment on X.com using Grok.

    Args:
        symbol: Crypto symbol (e.g., "BTC", "ETH", "SOL")
        sample_size: How many recent posts to analyze sentiment

    Returns:
        Sentiment summary for the crypto asset
    """
    if not _is_grok_available():
        return None

    cfg = config.load_config()
    model = cfg.get("providers", {}).get("grok", {}).get("model", "grok-beta")

    prompt = f"""Analyze X.com sentiment for cryptocurrency ${symbol}.

Based on recent X.com activity (past 24 hours), provide:
1. Overall sentiment (bullish/bearish/neutral)
2. Sentiment strength (0-100)
3. Key bullish signals
4. Key bearish signals
5. Notable influencer opinions
6. Price prediction sentiment (up/down/sideways)

Respond with JSON format."""

    try:
        response = providers._ask_grok(prompt, model, max_output_tokens=1200)
        if not response:
            return None

        # Extract JSON from response
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())

        # Fallback: structured text response
        return {
            "symbol": symbol,
            "analysis": response,
            "source": "grok"
        }
    except Exception as e:
        return None
