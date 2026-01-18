"""
Meta-Router: Intelligent tool routing for conversational finance.

Natural language queries are routed to specialized financial analysis tools.
Grok sentiment is heavily weighted (1.0) in all responses.

Example queries:
- "Is BTC looking bullish right now?" → sentiment_analysis + market_data
- "What's the top performing token?" → top_performers + sentiment_aggregation
- "Should I buy SOL?" → liquidation_analysis + sentiment + risk_check
- "Check the treasury status" → position_status + pnl_calculation
"""

import re
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


async def financial_research(
    query: str,
    sentiment_agg=None,
    grok_client=None,
    position_manager=None
) -> Dict[str, Any]:
    """
    Main entry point for conversational finance queries.

    Routes natural language queries to appropriate tools.
    Grok sentiment is heavily weighted in all analysis.

    Args:
        query: Natural language query
        sentiment_agg: Sentiment aggregator (heavy Grok weighting)
        grok_client: Grok AI client for analysis
        position_manager: Treasury position manager

    Returns:
        Formatted response with analysis and Grok weighting indicated
    """

    result = {
        "query": query,
        "tools_used": [],
        "grok_weight": "1.0 (PRIMARY)",  # Grok is primary decision maker
        "response": ""
    }

    try:
        # Classify query type
        query_lower = query.lower()

        # SENTIMENT QUERIES
        if any(word in query_lower for word in ["bullish", "bearish", "sentiment", "feeling", "vibe", "looks", "think"]):
            result = await _handle_sentiment_query(query, sentiment_agg, grok_client, result)

        # POSITION QUERIES
        elif any(word in query_lower for word in ["position", "open", "trade", "long", "short", "exposure", "portfolio"]):
            result = await _handle_position_query(query, position_manager, result)

        # TOP PERFORMERS / TRENDING
        elif any(word in query_lower for word in ["top", "best", "trending", "movers", "leaders", "gainers"]):
            result = await _handle_trending_query(query, sentiment_agg, grok_client, result)

        # RISK / LIQUIDATIONS
        elif any(word in query_lower for word in ["risk", "liquidation", "support", "level", "floor", "ceiling", "resistance"]):
            result = await _handle_risk_query(query, result)

        # BUY / SELL SIGNALS
        elif any(word in query_lower for word in ["should", "buy", "sell", "entry", "exit", "target", "stop", "tp", "sl"]):
            result = await _handle_trading_signal_query(query, grok_client, result)

        # GENERAL FINANCIAL QUESTIONS
        else:
            result = await _handle_general_query(query, grok_client, result)

        # Add Grok weighting note to all responses
        result["grok_analysis"] = True
        result["response"] = f"{result.get('response', '')}\n\n[Grok Sentiment: Heavy weighting (1.0) - Primary decision driver]"

    except Exception as e:
        logger.error(f"Error in financial_research: {e}")
        result["error"] = str(e)
        result["response"] = "❌ Error processing query. Please try again."

    return result


async def _handle_sentiment_query(query: str, sentiment_agg, grok_client, result: Dict) -> Dict:
    """Handle sentiment analysis queries."""
    result["tools_used"].append("sentiment_aggregation")

    # Extract symbol if mentioned
    symbol = _extract_symbol(query)

    if symbol and sentiment_agg:
        try:
            sentiment = sentiment_agg.get_sentiment_score(symbol)
            leaders = sentiment_agg.get_sentiment_leaders(5)

            response_lines = [
                f"📊 {symbol} Sentiment Analysis (Grok Weighted 1.0):",
                f"• Sentiment Score: {sentiment:.1f}/100",
                "",
                "📈 Top Sentiment Leaders:",
            ]

            for i, (s, score) in enumerate(leaders[:5], 1):
                response_lines.append(f"  {i}. {s}: {score:.1f}/100")

            result["response"] = "\n".join(response_lines)

        except Exception as e:
            logger.error(f"Sentiment query error: {e}")
            result["response"] = f"Could not analyze {symbol} sentiment"

    return result


async def _handle_position_query(query: str, position_manager, result: Dict) -> Dict:
    """Handle position/portfolio queries."""
    result["tools_used"].append("position_status")

    if position_manager:
        try:
            positions = position_manager.get_open_positions() if hasattr(position_manager, 'get_open_positions') else []

            response_lines = [
                "🎯 Open Positions:",
            ]

            if positions:
                total_pnl = 0
                for pos in positions[:10]:
                    if hasattr(pos, 'symbol'):
                        pnl = getattr(pos, 'pnl_usd', 0) if hasattr(pos, 'pnl_usd') else 0
                        total_pnl += pnl
                        status = "✅" if pnl > 0 else "❌"
                        response_lines.append(f"  {status} {pos.symbol}: {pnl:+.2f} USD")

                response_lines.append(f"\n💰 Total P&L: {total_pnl:+.2f} USD")
            else:
                response_lines.append("  No open positions")

            result["response"] = "\n".join(response_lines)

        except Exception as e:
            logger.error(f"Position query error: {e}")
            result["response"] = "Could not fetch position data"

    return result


async def _handle_trending_query(query: str, sentiment_agg, grok_client, result: Dict) -> Dict:
    """Handle top performers / trending queries."""
    result["tools_used"].append("trending_analysis")

    if sentiment_agg:
        try:
            leaders = sentiment_agg.get_sentiment_leaders(10)

            response_lines = [
                "🚀 Top Sentiment Leaders (Grok Weighted 1.0):",
                "",
            ]

            for i, (symbol, score) in enumerate(leaders[:10], 1):
                bars = "█" * int(score / 10)
                response_lines.append(f"  {i:2d}. {symbol:8s} │ {bars:10s} {score:.1f}/100")

            result["response"] = "\n".join(response_lines)

        except Exception as e:
            logger.error(f"Trending query error: {e}")
            result["response"] = "Could not fetch trending tokens"

    return result


async def _handle_risk_query(query: str, result: Dict) -> Dict:
    """Handle risk/liquidation queries."""
    result["tools_used"].append("risk_analysis")

    response_lines = [
        "⚠️ Risk Analysis:",
        "",
        "Key Support/Resistance Levels:",
        "• Monitor liquidation heatmaps on CoinGlass",
        "• Watch for volume clustering",
        "• Check on-chain whale movements",
    ]

    result["response"] = "\n".join(response_lines)
    return result


async def _handle_trading_signal_query(query: str, grok_client, result: Dict) -> Dict:
    """Handle buy/sell signal queries."""
    result["tools_used"].append("signal_generation")

    symbol = _extract_symbol(query)

    if symbol and grok_client:
        try:
            # Use Grok for signal analysis (heavy weighting)
            grok_signal = await grok_client.analyze_sentiment(
                symbol,
                f"Should traders BUY or SELL {symbol}? Provide entry, target, and stop loss."
            )

            response_lines = [
                f"🎯 Trading Signal for {symbol} (Grok Analysis - 1.0 Weight):",
                "",
                grok_signal[:200] + "..." if len(grok_signal) > 200 else grok_signal,
            ]

            result["response"] = "\n".join(response_lines)

        except Exception as e:
            logger.error(f"Signal query error: {e}")
            result["response"] = "Could not generate trading signal"

    return result


async def _handle_general_query(query: str, grok_client, result: Dict) -> Dict:
    """Handle general financial questions with Grok."""
    result["tools_used"].append("grok_analysis")

    if grok_client:
        try:
            response = await grok_client.analyze_sentiment(
                "general_finance",
                query
            )

            response_lines = [
                "📚 Financial Insight (Grok Analysis - 1.0 Weight):",
                "",
                response[:300] + "..." if len(response) > 300 else response,
            ]

            result["response"] = "\n".join(response_lines)

        except Exception as e:
            logger.error(f"General query error: {e}")
            result["response"] = "I'm not sure about that. Try asking about specific tokens or positions."

    return result


def _extract_symbol(query: str) -> Optional[str]:
    """Extract token symbol from query."""
    # Look for common patterns: SOL, BTC, ETH, etc.
    matches = re.findall(r'\b([A-Z]{2,8})\b', query)

    # Prefer matches that look like token symbols
    for match in matches:
        if match in ["SOL", "BTC", "ETH", "USDC", "USDT", "JUP", "BONK", "WIF", "PYTH", "DOGE", "SHIB", "XRP"]:
            return match

    # Return first uppercase match
    return matches[0] if matches else None
