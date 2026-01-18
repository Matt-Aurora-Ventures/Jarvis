"""
Dexter ReAct Agent - Autonomous Trading with Grok

Core reasoning loop:
1. ANALYZE: Observe market state
2. DECIDE: Grok decides what tools to use (heavy Grok weighting)
3. ACT: Execute tools via meta-router
4. OBSERVE: Gather results
5. REPEAT: Until trading decision reached

Grok is the primary decision-maker (1.0 weighting) for all financial analysis.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class DecisionType(Enum):
    """Possible Dexter decisions."""
    TRADE_BUY = "TRADE_BUY"
    TRADE_SELL = "TRADE_SELL"
    HOLD = "HOLD"
    ERROR = "ERROR"


@dataclass
class ReActDecision:
    """Result of a ReAct reasoning loop."""
    decision: DecisionType
    symbol: str = ""
    rationale: str = ""
    confidence: float = 0.0
    tools_used: List[str] = field(default_factory=list)
    grok_sentiment_score: float = 0.0  # Grok sentiment drives decision (1.0 weight)
    market_data: Dict[str, Any] = field(default_factory=dict)
    iterations: int = 0
    cost_usd: float = 0.0


class DexterAgent:
    """
    ReAct Trading Agent powered by Grok.

    Grok is the reasoning engine (1.0 weighting) - all financial analysis
    is driven by Grok sentiment and analysis capabilities.
    """

    # Configuration
    MAX_ITERATIONS = 15
    MAX_COST_USD = 0.50
    MIN_CONFIDENCE = 70.0  # Only trade if confidence > this threshold

    def __init__(self, grok_client=None, sentiment_aggregator=None):
        """Initialize agent with Grok and sentiment engine."""
        self.grok = grok_client
        self.sentiment_agg = sentiment_aggregator
        self.iteration_count = 0
        self.total_cost = 0.0
        self.scratchpad: List[Dict[str, Any]] = []

    async def analyze_trading_opportunity(self, symbol: str, context: Dict[str, Any] = None) -> ReActDecision:
        """
        Main ReAct loop for analyzing trading opportunities.

        Flow:
        1. Analyze market state
        2. Grok decides what to research
        3. Gather market data
        4. Grok analyzes all signals
        5. Make trading decision if high confidence

        Args:
            symbol: Token symbol to analyze
            context: Additional context (price, volume, etc.)

        Returns:
            ReActDecision with reasoning trail
        """
        self.iteration_count = 0
        self.scratchpad = []
        decision = ReActDecision(decision=DecisionType.HOLD, symbol=symbol)

        try:
            # Iteration 1: Initial market analysis
            self._log_reasoning(f"Starting analysis for {symbol}")

            if not self.grok:
                logger.warning("Grok not available - using sentiment aggregator fallback")
                return await self._fallback_decision(symbol, context)

            # Get Grok's initial assessment (heavy Grok weighting)
            grok_prompt = f"""
            Analyze {symbol} for trading opportunity.

            Consider:
            1. Current sentiment (bullish/bearish/neutral)
            2. Recent price action
            3. Volume patterns
            4. Risk/reward ratio

            You are the primary decision maker (1.0 weighting).
            Respond with: SENTIMENT_SCORE (0-100), CONFIDENCE (0-100), RECOMMENDATION (BUY/SELL/HOLD)
            """

            grok_response = await self.grok.analyze_sentiment(symbol, grok_prompt)

            # Parse Grok response
            sentiment_score = self._extract_sentiment_score(grok_response)
            decision.grok_sentiment_score = sentiment_score

            self._log_action(
                "grok_analysis",
                {"symbol": symbol},
                f"Sentiment: {sentiment_score}/100"
            )

            self.iteration_count += 1

            # Iteration 2: Market data gathering
            if sentiment_score > 60:  # Only proceed if Grok is somewhat bullish
                market_data = await self._gather_market_data(symbol)
                decision.market_data = market_data
                self._log_action("market_data", {"symbol": symbol}, f"Fetched data: {len(market_data)} metrics")
                self.iteration_count += 1

                # Iteration 3: Grok synthesis
                if self.sentiment_agg:
                    agg_sentiment = self.sentiment_agg.get_sentiment_score(symbol)
                    self._log_action("sentiment_aggregation", {"symbol": symbol}, f"Agg sentiment: {agg_sentiment}")
                    self.iteration_count += 1

                    # Iteration 4: Final Grok decision with heavy weighting
                    final_prompt = f"""
                    Final decision for {symbol}:
                    - Grok sentiment (1.0 weight): {sentiment_score}/100
                    - Aggregated sentiment: {agg_sentiment}
                    - Market data: {json.dumps(market_data, default=str)[:200]}...

                    DECISION: Should we BUY, SELL, or HOLD?
                    CONFIDENCE: 0-100
                    REASONING: Brief explanation
                    """

                    final_response = await self.grok.analyze_sentiment(symbol, final_prompt)

                    # Make decision
                    recommendation = self._parse_recommendation(final_response)
                    confidence = self._extract_confidence(final_response)

                    if confidence >= self.MIN_CONFIDENCE:
                        decision.decision = recommendation
                        decision.confidence = confidence
                        decision.rationale = final_response[:200]
                        self._log_decision(
                            recommendation.value,
                            symbol,
                            f"Confidence: {confidence:.1f}% | Grok Score: {sentiment_score}/100"
                        )

                    self.iteration_count += 1

        except Exception as e:
            logger.error(f"Error in ReAct loop: {e}")
            decision.decision = DecisionType.ERROR
            self._log_action("error", {}, str(e))

        decision.iterations = self.iteration_count
        decision.cost_usd = self.total_cost
        decision.tools_used = list(set(self.scratchpad_tools()))

        return decision

    async def _gather_market_data(self, symbol: str) -> Dict[str, Any]:
        """Gather market data for analysis."""
        try:
            # Placeholder - integrate with Jupiter, CoinGecko, etc.
            return {
                "symbol": symbol,
                "status": "data_gathered",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to gather market data: {e}")
            return {}

    async def _fallback_decision(self, symbol: str, context: Dict = None) -> ReActDecision:
        """Fallback decision if Grok is unavailable."""
        if self.sentiment_agg:
            sentiment = self.sentiment_agg.get_sentiment_score(symbol)
            decision = ReActDecision(
                decision=DecisionType.HOLD if sentiment < 60 else DecisionType.TRADE_BUY,
                symbol=symbol,
                grok_sentiment_score=sentiment,
                confidence=min(sentiment, 85.0)  # Cap at 85% without Grok
            )
            return decision

        return ReActDecision(decision=DecisionType.ERROR, symbol=symbol)

    def _extract_sentiment_score(self, response: str) -> float:
        """Extract sentiment score from Grok response."""
        try:
            # Look for patterns like "SENTIMENT_SCORE: 75"
            import re
            match = re.search(r'(?:SENTIMENT|SCORE)[\s:]*(\d+)', response, re.IGNORECASE)
            if match:
                return float(match.group(1))
        except:
            pass
        return 50.0  # Neutral default

    def _extract_confidence(self, response: str) -> float:
        """Extract confidence score from Grok response."""
        try:
            import re
            match = re.search(r'CONFIDENCE[\s:]*(\d+)', response, re.IGNORECASE)
            if match:
                return float(match.group(1))
        except:
            pass
        return 50.0

    def _parse_recommendation(self, response: str) -> DecisionType:
        """Parse BUY/SELL/HOLD from Grok response."""
        response_upper = response.upper()

        if "BUY" in response_upper:
            return DecisionType.TRADE_BUY
        elif "SELL" in response_upper:
            return DecisionType.TRADE_SELL
        else:
            return DecisionType.HOLD

    def scratchpad_tools(self) -> List[str]:
        """Get list of tools used from scratchpad."""
        return [item.get("tool") for item in self.scratchpad if item.get("tool")]

    def _log_reasoning(self, thought: str):
        """Log a reasoning step."""
        self.scratchpad.append({
            "type": "reasoning",
            "thought": thought,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    def _log_action(self, tool: str, args: Dict, result: str):
        """Log a tool execution."""
        self.scratchpad.append({
            "type": "action",
            "tool": tool,
            "args": args,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    def _log_decision(self, action: str, symbol: str, rationale: str):
        """Log the final decision."""
        self.scratchpad.append({
            "type": "decision",
            "action": action,
            "symbol": symbol,
            "rationale": rationale,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    def get_scratchpad(self) -> str:
        """Return formatted scratchpad for debugging."""
        lines = []
        for entry in self.scratchpad:
            entry_type = entry.get("type", "unknown")
            if entry_type == "reasoning":
                lines.append(f"💭 {entry['thought']}")
            elif entry_type == "action":
                lines.append(f"🔧 {entry['tool']}: {entry['result']}")
            elif entry_type == "decision":
                lines.append(f"✅ {entry['action']} {entry['symbol']}: {entry['rationale']}")

        return "\n".join(lines)
