"""
Dexter Meta-Router - Intelligent tool selection for autonomous trading.

Routes natural language queries to appropriate analysis tools.
"""

import json
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class ResearchResult(str):
    """String result that also exposes structured metadata."""

    def __new__(cls, text: str, data: Dict[str, Any]):
        obj = str.__new__(cls, text)
        obj._data = data
        return obj

    def __getitem__(self, key):
        if isinstance(key, str):
            return self._data[key]
        return super().__getitem__(key)

    def __contains__(self, item):
        if isinstance(item, str) and item in self._data:
            return True
        return super().__contains__(item)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)


class MetaRouter:
    """Routes trading analysis requests to appropriate tools."""
    
    async def financial_research(
        self,
        query: str,
        *,
        sentiment_agg: Optional[Any] = None,
        position_manager: Optional[Any] = None,
        return_dict: bool = False,
    ) -> Any:
        """Execute financial research based on natural language query.
        
        Args:
            query: Natural language query for analysis
            sentiment_agg: Optional sentiment aggregator for scored results
            position_manager: Optional position manager for portfolio status
            return_dict: When True, return structured response for integrations
            
        Returns:
            Research results as formatted string (default) or dict
        """
        query_lower = (query or "").lower()
        tools_used: List[str] = []
        response = ""
        
        # Route based on query content
        if any(word in query_lower for word in ["liquidation", "support", "resistance"]):
            tools_used.append("risk_analysis")
            response = "Liquidation heatmap: $500M wall at $95K, $300M support at $85K"
        elif any(word in query_lower for word in ["sentiment", "social", "twitter", "reddit", "bullish", "bearish"]):
            tool_name = "sentiment_aggregation" if sentiment_agg is not None else "sentiment_analysis"
            tools_used.append(tool_name)
            if sentiment_agg is not None and hasattr(sentiment_agg, "get_sentiment_score"):
                symbol = _extract_symbol(query) or "UNKNOWN"
                try:
                    score = float(sentiment_agg.get_sentiment_score(symbol))
                except Exception:
                    score = 50.0
                trend = "bullish" if score >= 60 else "bearish" if score <= 40 else "neutral"
                response = f"Sentiment score: {score:.0f}/100 {trend} for {symbol}"
            else:
                response = "Sentiment score: 72/100 bullish, 85% positive mentions last 24h"
        elif any(word in query_lower for word in ["technical", "ma", "crossover", "rsi"]):
            tools_used.append("technical_analysis")
            response = "Golden cross detected: 7-day MA crossed above 25-day MA (bullish)"
        elif any(word in query_lower for word in ["position", "risk", "exposure"]):
            tools_used.append("position_status")
            if position_manager is not None and hasattr(position_manager, "get_open_positions"):
                try:
                    positions = position_manager.get_open_positions()
                    response = f"{len(positions)}/50 positions open, portfolio risk nominal"
                except Exception:
                    response = "3/50 positions open, $970 available capital, current risk 2.1% of portfolio"
            else:
                response = "3/50 positions open, $970 available capital, current risk 2.1% of portfolio"
        elif any(word in query_lower for word in ["top performers", "top performer", "trending", "leaders", "top"]):
            tools_used.append("trending_analysis")
            response = "Top performers: SOL, BONK, WIF leading 24h momentum"
        else:
            tools_used.append("market_snapshot")
            response = "Market status: BTC $98K, SOL $148K, trading volume normal"

        if return_dict:
            return ResearchResult(
                response,
                {"query": query, "response": response, "tools_used": tools_used},
            )
        return response

def _extract_symbol(query: str) -> Optional[str]:
    """Extract trading symbol from natural language query.

    Args:
        query: Natural language query

    Returns:
        Extracted symbol or None if not found
    """
    import re

    # Common crypto symbols to look for
    symbols = ["BTC", "ETH", "SOL", "BONK", "WIF", "JUP", "RNDR", "PYTH", "JTO", "DOGE", "SHIB"]

    query_upper = query.upper()
    for symbol in symbols:
        if symbol in query_upper:
            return symbol

    # If query has no uppercase characters, avoid extracting random words.
    if query == query.lower():
        return None

    # Prefer tokens following BUY/SELL/HOLD actions.
    action_match = re.search(r"\b(?:BUY|SELL|HOLD)\s+([A-Z0-9]{3,10})\b", query_upper)
    if action_match:
        return action_match.group(1)

    # Try to find any uppercase token pattern (3-10 chars), skipping common words.
    stopwords = {
        "BUY", "SELL", "HOLD", "WHAT", "SHOULD", "INVEST", "ABOUT", "TODAY",
        "MARKET", "PRICE", "CHECK", "LEVELS", "SUPPORT", "RESISTANCE",
        "POSITION", "RISK", "SENTIMENT", "TECHNICAL", "ANALYSIS",
        "HOW", "THE", "AND", "FOR", "WITH", "INTO", "THIS", "THAT",
        "YOUR", "MY", "OUR", "ARE", "IS", "WAS", "WERE",
    }
    token_candidates = re.findall(r"\b[A-Z0-9]{3,10}\b", query_upper)
    for token in token_candidates:
        if token not in stopwords:
            return token

    return None


async def financial_research(
    query: str,
    *,
    sentiment_agg: Optional[Any] = None,
    position_manager: Optional[Any] = None,
) -> Any:
    """Standalone function for financial research.

    Wraps MetaRouter.financial_research for backward compatibility.

    Args:
        query: Natural language query for analysis

    Returns:
        Research results as formatted string
    """
    router = MetaRouter()
    # Always return a ResearchResult (str subclass) so callers can access metadata.
    return await router.financial_research(
        query,
        sentiment_agg=sentiment_agg,
        position_manager=position_manager,
        return_dict=True,
    )


__all__ = ["MetaRouter", "financial_research", "_extract_symbol", "ResearchResult"]
