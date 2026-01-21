"""
Dexter Agent - ReAct (Reasoning + Acting) autonomous trading agent.

Uses Grok-3 to reason about market conditions and make intelligent trading decisions.
Implements the full ReAct loop:
1. Observe: Gather market data and context
2. Think: Reason about the situation
3. Act: Execute a tool or make a decision
4. Repeat until confident decision is reached
"""

import asyncio
import logging
import os
import json
import uuid
from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class DecisionType(str, Enum):
    """Decision types for Dexter agent."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    UNKNOWN = "UNKNOWN"


class ReActDecision:
    """ReAct decision output."""

    def __init__(
        self,
        action: str,
        symbol: str,
        confidence: float,
        rationale: str,
        iterations: int = 0,
        tools_used: Optional[List[str]] = None,
        evidence: Optional[Dict[str, Any]] = None,
    ):
        self.action = action
        self.symbol = symbol
        self.confidence = confidence
        self.rationale = rationale
        self.iterations = iterations
        self.tools_used = tools_used or []
        self.evidence = evidence or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "action": self.action,
            "symbol": self.symbol,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "iterations": self.iterations,
            "tools_used": self.tools_used,
            "evidence": self.evidence,
        }


# ReAct prompts
SYSTEM_PROMPT = """You are Dexter, an autonomous trading agent using ReAct (Reasoning and Acting).

Your task is to analyze tokens and make BUY, SELL, or HOLD decisions.

For each iteration, you must:
1. THINK: Reason about what you know and what you need to find out
2. ACT: Either call a tool to gather more information, or make a final decision

Available tools:
- sentiment_analysis(symbol): Get social sentiment score and trends
- technical_analysis(symbol): Get RSI, MACD, moving averages
- liquidity_check(symbol): Check liquidity depth and slippage
- position_check(): Get current portfolio positions and risk
- price_data(symbol): Get current price and recent changes

Response format for tool calls:
THINK: [your reasoning]
ACT: tool_name(argument)

Response format for final decision:
THINK: [your final reasoning]
DECISION: [BUY|SELL|HOLD]
CONFIDENCE: [0-100]
RATIONALE: [brief explanation]

Always gather at least sentiment AND technical data before deciding.
Minimum confidence for BUY/SELL is 70%. Below that, default to HOLD.
"""


class DexterAgent:
    """ReAct agent for autonomous trading decisions."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize Dexter agent."""
        self.session_id = str(uuid.uuid4())[:8]
        self.config = config or {}
        self.model = self.config.get("model", "grok-3")
        self.max_iterations = self.config.get("max_iterations", 15)
        self.min_confidence = self.config.get("min_confidence", 70.0)
        self._iteration = 0
        self._cost = 0.0
        self._tools_used: List[str] = []
        self._evidence: Dict[str, Any] = {}

        # Lazy load components
        self._scratchpad = None
        self._confidence_scorer = None
        self._grok_client = None

    def _get_scratchpad(self):
        """Lazy load scratchpad."""
        if self._scratchpad is None:
            try:
                from .scratchpad import Scratchpad
                self._scratchpad = Scratchpad(self.session_id)
            except ImportError:
                self._scratchpad = MockScratchpad()
        return self._scratchpad

    def _get_confidence_scorer(self):
        """Lazy load confidence scorer."""
        if self._confidence_scorer is None:
            try:
                from .confidence_scorer import ConfidenceScorer
                self._confidence_scorer = ConfidenceScorer()
            except ImportError:
                self._confidence_scorer = MockConfidenceScorer()
        return self._confidence_scorer

    async def _get_grok_client(self):
        """Get or initialize Grok client."""
        if self._grok_client is None:
            try:
                from bots.twitter.grok_client import GrokClient
                self._grok_client = GrokClient()
            except ImportError:
                logger.warning("GrokClient not available, using mock")
                self._grok_client = MockGrokClient()
        return self._grok_client

    async def _call_tool(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Execute a tool and return results."""
        self._tools_used.append(tool_name)
        result = ""

        try:
            if tool_name == "sentiment_analysis":
                result = await self._sentiment_analysis(args.get("symbol", ""))
            elif tool_name == "technical_analysis":
                result = await self._technical_analysis(args.get("symbol", ""))
            elif tool_name == "liquidity_check":
                result = await self._liquidity_check(args.get("symbol", ""))
            elif tool_name == "position_check":
                result = await self._position_check()
            elif tool_name == "price_data":
                result = await self._price_data(args.get("symbol", ""))
            else:
                result = f"Unknown tool: {tool_name}"

            scratchpad = self._get_scratchpad()
            scratchpad.log_action(tool_name, args, result)
            self._evidence[tool_name] = result

        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}")
            result = f"Error: {str(e)}"

        return result

    async def _sentiment_analysis(self, symbol: str) -> str:
        """Get sentiment analysis from real sources."""
        try:
            # Try to get real sentiment from x_sentiment module
            from core import x_sentiment
            score = await x_sentiment.get_sentiment_score(symbol)
            return json.dumps({
                "score": score,
                "trend": "bullish" if score > 60 else "bearish" if score < 40 else "neutral",
                "source": "x_sentiment"
            })

        except Exception as e:
            logger.warning(f"Sentiment analysis fallback: {e}")
            return json.dumps({
                "score": 50,
                "trend": "neutral",
                "error": str(e),
                "source": "fallback"
            })

    async def _technical_analysis(self, symbol: str) -> str:
        """Get technical analysis."""
        try:
            from core.trading.signals import RSIAnalyzer, MACDAnalyzer
            from core.dexscreener import get_token_prices

            prices = await get_token_prices(symbol, limit=50)

            if prices and len(prices) > 20:
                rsi_analyzer = RSIAnalyzer()
                macd_analyzer = MACDAnalyzer()

                rsi_analyzer.add_prices(prices)
                macd_analyzer.add_prices(prices)

                rsi_signal = rsi_analyzer.analyze()
                macd_signal = macd_analyzer.analyze()

                return json.dumps({
                    "rsi": {
                        "value": rsi_signal.rsi_value,
                        "signal": rsi_signal.signal_type,
                        "direction": rsi_signal.direction,
                    },
                    "macd": {
                        "value": macd_signal.macd_value,
                        "signal": macd_signal.signal_type,
                        "direction": macd_signal.direction,
                    },
                    "source": "live"
                })

        except Exception as e:
            logger.warning(f"Technical analysis fallback: {e}")

        return json.dumps({
            "rsi": {"value": 50, "signal": "NO_SIGNAL", "direction": "neutral"},
            "macd": {"value": 0, "signal": "NO_SIGNAL", "direction": "neutral"},
            "source": "fallback"
        })

    async def _liquidity_check(self, symbol: str) -> str:
        """Check liquidity."""
        try:
            from core.dexscreener import get_token_info
            info = await get_token_info(symbol)

            if info:
                return json.dumps({
                    "liquidity_usd": info.get("liquidity", 0),
                    "volume_24h": info.get("volume_24h", 0),
                    "fdv": info.get("fdv", 0),
                    "source": "dexscreener"
                })

        except Exception as e:
            logger.warning(f"Liquidity check fallback: {e}")

        return json.dumps({
            "liquidity_usd": 0,
            "volume_24h": 0,
            "warning": "Could not fetch liquidity",
            "source": "fallback"
        })

    async def _position_check(self) -> str:
        """Check current positions."""
        try:
            from core.position_manager import get_position_manager
            pm = get_position_manager()
            positions = pm.get_open_positions()

            return json.dumps({
                "open_positions": len(positions),
                "max_positions": pm.max_positions,
                "available_slots": pm.max_positions - len(positions),
                "total_exposure_pct": pm.get_total_exposure_pct(),
                "source": "position_manager"
            })

        except Exception as e:
            logger.warning(f"Position check fallback: {e}")

        return json.dumps({
            "open_positions": 0,
            "max_positions": 50,
            "available_slots": 50,
            "source": "fallback"
        })

    async def _price_data(self, symbol: str) -> str:
        """Get current price data."""
        try:
            from core.dexscreener import get_token_price
            price_info = await get_token_price(symbol)

            if price_info:
                return json.dumps({
                    "price_usd": price_info.get("price", 0),
                    "change_24h": price_info.get("change_24h", 0),
                    "change_1h": price_info.get("change_1h", 0),
                    "source": "dexscreener"
                })

        except Exception as e:
            logger.warning(f"Price data fallback: {e}")

        return json.dumps({
            "price_usd": 0,
            "change_24h": 0,
            "source": "fallback"
        })

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse Grok response to extract action or decision."""
        result = {
            "type": "unknown",
            "think": "",
            "action": None,
            "tool": None,
            "args": {},
            "decision": None,
            "confidence": 0,
            "rationale": "",
        }

        lines = response.strip().split("\n")

        for line in lines:
            line = line.strip()
            if line.startswith("THINK:"):
                result["think"] = line[6:].strip()
            elif line.startswith("ACT:"):
                result["type"] = "action"
                action = line[4:].strip()
                if "(" in action and ")" in action:
                    tool_name = action[:action.index("(")]
                    arg = action[action.index("(")+1:action.index(")")]
                    result["tool"] = tool_name
                    result["args"] = {"symbol": arg} if arg else {}
            elif line.startswith("DECISION:"):
                result["type"] = "decision"
                result["decision"] = line[9:].strip().upper()
            elif line.startswith("CONFIDENCE:"):
                try:
                    result["confidence"] = float(line[11:].strip().replace("%", ""))
                except ValueError:
                    pass
            elif line.startswith("RATIONALE:"):
                result["rationale"] = line[10:].strip()

        return result

    async def _grok_reason(self, context: str) -> str:
        """Call Grok to reason about the current state."""
        try:
            grok = await self._get_grok_client()
            if hasattr(grok, 'chat'):
                response = await grok.chat(
                    system=SYSTEM_PROMPT,
                    message=context,
                )
                self._cost += 0.002
                return response
        except Exception as e:
            logger.error(f"Grok reasoning failed: {e}")

        return "THINK: Cannot connect to reasoning model\nDECISION: HOLD\nCONFIDENCE: 0\nRATIONALE: Unable to analyze"

    async def analyze_token(self, symbol: str) -> Dict[str, Any]:
        """
        Analyze a token using the ReAct loop.

        Args:
            symbol: Token symbol to analyze

        Returns:
            Decision dict with action, confidence, rationale, etc.
        """
        self._iteration = 0
        self._tools_used = []
        self._evidence = {}
        self._cost = 0.0

        scratchpad = self._get_scratchpad()
        scratchpad.log_start(f"Analyze {symbol} for trading decision", symbol)

        context = f"Analyze {symbol} for a trading decision. Start by gathering sentiment and technical data."

        while self._iteration < self.max_iterations:
            self._iteration += 1

            response = await self._grok_reason(context)
            parsed = self._parse_response(response)

            scratchpad.log_reasoning(parsed.get("think", ""), self._iteration)

            if parsed["type"] == "decision":
                decision = parsed["decision"] or "HOLD"
                confidence = parsed["confidence"]
                rationale = parsed["rationale"]

                scorer = self._get_confidence_scorer()
                calibrated_confidence, _ = scorer.score_confidence(
                    confidence,
                    decision,
                    symbol,
                )
                if calibrated_confidence < self.min_confidence and decision != "HOLD":
                    logger.info(
                        f"Confidence {calibrated_confidence:.1f}% below threshold "
                        f"{self.min_confidence}%, forcing HOLD"
                    )
                    decision = "HOLD"
                    rationale = f"Insufficient confidence ({calibrated_confidence:.1f}%). {rationale}"

                scratchpad.log_decision(decision, symbol, rationale, calibrated_confidence)

                return {
                    "action": decision,
                    "symbol": symbol,
                    "confidence": calibrated_confidence,
                    "rationale": rationale,
                    "iterations": self._iteration,
                    "tools_used": self._tools_used,
                    "evidence": self._evidence,
                    "cost": self._cost,
                }

            elif parsed["type"] == "action" and parsed["tool"]:
                tool_result = await self._call_tool(parsed["tool"], parsed["args"])
                context = f"""Previous thought: {parsed['think']}
Tool result from {parsed['tool']}: {tool_result}

Continue analyzing {symbol}. You have data from: {', '.join(self._tools_used)}.
If you have enough information (at least sentiment AND technical data), make a decision.
Otherwise, gather more data."""

            else:
                context = f"Please respond in the correct format. Analyze {symbol} and either call a tool or make a decision."

        logger.warning(f"Max iterations ({self.max_iterations}) reached for {symbol}")
        scratchpad.log_decision("HOLD", symbol, "Max iterations reached without confident decision", 50.0)

        return {
            "action": "HOLD",
            "symbol": symbol,
            "confidence": 50.0,
            "rationale": "Analysis incomplete - max iterations reached",
            "iterations": self._iteration,
            "tools_used": self._tools_used,
            "evidence": self._evidence,
            "cost": self._cost,
        }

    async def quick_sentiment(self, symbol: str) -> Dict[str, Any]:
        """Quick sentiment check without full ReAct loop."""
        sentiment = await self._sentiment_analysis(symbol)
        return json.loads(sentiment)


class MockScratchpad:
    """Mock scratchpad for when the real one isn't available."""
    def log_start(self, *args, **kwargs): pass
    def log_reasoning(self, *args, **kwargs): pass
    def log_action(self, *args, **kwargs): pass
    def log_decision(self, *args, **kwargs): pass


class MockConfidenceScorer:
    """Mock confidence scorer."""
    def calibrate(self, confidence, decision, symbol):
        return confidence


class MockGrokClient:
    """Mock Grok client for testing."""

    async def chat(self, system: str, message: str) -> str:
        """Return mock response."""
        if "sentiment" not in message.lower() or "tool result" not in message.lower():
            return "THINK: I need sentiment data first\nACT: sentiment_analysis(BONK)"
        elif "technical" not in message.lower():
            return "THINK: I have sentiment, now need technical\nACT: technical_analysis(BONK)"
        else:
            return """THINK: I have both sentiment and technical data. Sentiment is bullish with score 72, RSI shows oversold conditions.
DECISION: BUY
CONFIDENCE: 75
RATIONALE: Bullish sentiment combined with oversold RSI suggests good entry point."""


__all__ = ["DexterAgent", "DecisionType", "ReActDecision"]
