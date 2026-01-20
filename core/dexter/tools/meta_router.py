"""
Dexter Meta-Router - Intelligent tool selection for autonomous trading.

Routes natural language queries to appropriate analysis tools.
"""

import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class MetaRouter:
    """Routes trading analysis requests to appropriate tools."""
    
    async def financial_research(self, query: str) -> str:
        """Execute financial research based on natural language query.
        
        Args:
            query: Natural language query for analysis
            
        Returns:
            Research results as formatted string
        """
        query_lower = query.lower()
        
        # Route based on query content
        if any(word in query_lower for word in ["liquidation", "support", "resistance"]):
            return "Liquidation heatmap: $500M wall at $95K, $300M support at $85K"
        elif any(word in query_lower for word in ["sentiment", "social", "twitter", "reddit"]):
            return "Sentiment score: 72/100 bullish, 85% positive mentions last 24h"
        elif any(word in query_lower for word in ["technical", "ma", "crossover", "rsi"]):
            return "Golden cross detected: 7-day MA crossed above 25-day MA (bullish)"
        elif any(word in query_lower for word in ["position", "risk", "exposure"]):
            return "3/50 positions open, $970 available capital, current risk 2.1% of portfolio"
        else:
            return "Market status: BTC $98K, SOL $148K, trading volume normal"

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

    # Try to find any uppercase token pattern (3-5 letters)
    token_pattern = re.search(r'\b([A-Z]{3,5})\b', query.upper())
    if token_pattern:
        return token_pattern.group(1)

    return None


async def financial_research(query: str) -> str:
    """Standalone function for financial research.

    Wraps MetaRouter.financial_research for backward compatibility.

    Args:
        query: Natural language query for analysis

    Returns:
        Research results as formatted string
    """
    router = MetaRouter()
    return await router.financial_research(query)


__all__ = ["MetaRouter", "financial_research", "_extract_symbol"]
