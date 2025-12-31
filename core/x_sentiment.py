"""
X.com (Twitter) Sentiment Analysis using Grok (X.AI).

This module provides sentiment analysis capabilities leveraging Grok's
native integration with X.com data and understanding of social media context.
"""

import json
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from core import providers, config


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
    if not _is_grok_available():
        return None

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
            return None

        # Extract JSON from response
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if not json_match:
            return None

        data = json.loads(json_match.group())

        return SentimentResult(
            text=text,
            sentiment=data.get("sentiment", "neutral"),
            confidence=float(data.get("confidence", 0.5)),
            key_topics=data.get("key_topics", []),
            emotional_tone=data.get("emotional_tone", "neutral"),
            market_relevance=data.get("market_relevance")
        )
    except Exception as e:
        return None


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

        return TrendAnalysis(
            topic=data.get("topic", topic),
            sentiment=data.get("sentiment", "neutral"),
            volume=data.get("volume", "medium"),
            key_drivers=data.get("key_drivers", []),
            notable_voices=data.get("notable_voices", []),
            market_impact=data.get("market_impact")
        )
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
    results = []
    for text in texts:
        result = analyze_sentiment(text, focus=focus)
        results.append(result)
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
