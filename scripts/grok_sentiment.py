#!/usr/bin/env python3
"""Grok sentiment analysis for trading candidates (budget-aware)."""

from core import x_sentiment

TOKENS = [
    "FARTCOIN - meme coin",
    "TRUMP - Official Trump token",
    "PIPPIN - AI agent token",
    "FAFO - Trending token (+1000% today)",
    "WIF - dogwifhat",
]

print("Querying Grok for real-time X sentiment (with caching + budget caps)...")
results = x_sentiment.batch_sentiment_analysis(TOKENS, focus="trading")

for token, result in zip(TOKENS, results):
    if not result:
        print(f"{token}: no result")
        continue
    print(
        f"{token}: {result.sentiment} "
        f"(conf={result.confidence:.2f}) "
        f"tone={result.emotional_tone}"
    )
