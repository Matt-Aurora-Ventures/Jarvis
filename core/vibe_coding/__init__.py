"""
Vibe Coding - Sentiment-driven autonomous code adaptation.

Maps market sentiment to code changes:
- Bearish → Tighten stop losses, reduce position size
- Bullish → Expand position size, raise take profits
- Uncertain → Hold current positions, increase monitoring
- Frustrated users → Create helper features
"""

from .sentiment_mapper import SentimentMapper
from .regime_adapter import RegimeAdapter

__all__ = ["SentimentMapper", "RegimeAdapter"]
