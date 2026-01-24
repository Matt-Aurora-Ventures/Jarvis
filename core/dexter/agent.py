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
from enum import Enum, EnumMeta
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class _DecisionTypeMeta(EnumMeta):
    """Custom EnumMeta to keep legacy iteration behavior."""
    def __iter__(cls):
        for name in ("BUY", "SELL", "HOLD", "UNKNOWN"):
            yield cls.__members__[name]


class DecisionType(str, Enum, metaclass=_DecisionTypeMeta):
    """Decision types for Dexter agent."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    UNKNOWN = "UNKNOWN"
    TRADE_BUY = "TRADE_BUY"
    TRADE_SELL = "TRADE_SELL"
    ERROR = "ERROR"



class ReActDecision:
    """ReAct decision output."""

    def __init__(
        self,
        decision: DecisionType = DecisionType.HOLD,
        symbol: Optional[str] = None,
        confidence: float = 0.0,
        rationale: str = "",
        iterations: int = 0,
        tools_used: Optional[List[str]] = None,
        evidence: Optional[Dict[str, Any]] = None,
        cost_usd: float = 0.0,
        grok_sentiment_score: float = 0.0,
        error: Optional[str] = None,
        action: Optional[str] = None,
    ):
        if action:
            action_upper = action.upper()
            action_map = {
                "BUY": DecisionType.BUY,
                "SELL": DecisionType.SELL,
                "HOLD": DecisionType.HOLD,
                "UNKNOWN": DecisionType.UNKNOWN,
                "ERROR": DecisionType.ERROR,
                "TRADE_BUY": DecisionType.TRADE_BUY,
                "TRADE_SELL": DecisionType.TRADE_SELL,
            }
            decision = action_map.get(action_upper, decision)

        self.decision = decision
        self.symbol = symbol
        self.confidence = confidence
        self.rationale = rationale
        self.iterations = iterations
        self.tools_used = tools_used or []
        self.evidence = evidence or {}
        self.cost_usd = cost_usd
        self.grok_sentiment_score = grok_sentiment_score
        self.error = error

    @property
    def action(self) -> str:
        """Backward-compatible action string."""
        return self.decision.value if self.decision else ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "decision": self.decision.value if self.decision else None,
            "action": self.action,
            "symbol": self.symbol,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "iterations": self.iterations,
            "tools_used": self.tools_used,
            "evidence": self.evidence,
            "cost_usd": self.cost_usd,
            "grok_sentiment_score": self.grok_sentiment_score,
            "error": self.error,
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

    MAX_ITERATIONS = 15
    MAX_COST_USD = 0.50
    MIN_CONFIDENCE = 70.0

    def __init__(
        self,
        grok_client: Optional[Any] = None,
        sentiment_aggregator: Optional[Any] = None,
        config: Optional[Any] = None,
    ):
        """Initialize Dexter agent."""
        self.session_id = str(uuid.uuid4())[:8]

        try:
            from .config import DexterConfig
        except Exception:
            DexterConfig = None

        # Allow legacy positional config usage
        if config is None and DexterConfig is not None and isinstance(grok_client, DexterConfig):
            config = grok_client
            grok_client = None
        elif config is None and isinstance(grok_client, dict):
            config = grok_client
            grok_client = None

        if DexterConfig is not None and isinstance(config, DexterConfig):
            self.config = config
        elif isinstance(config, dict):
            # Minimal dict-based config support
            self.config = config
        else:
            self.config = DexterConfig() if DexterConfig is not None else {}

        # Config-driven settings
        if hasattr(self.config, "model"):
            self.model = self.config.model
            self.max_iterations = getattr(self.config, "max_iterations", self.MAX_ITERATIONS)
            self.min_confidence = getattr(self.config, "min_confidence", self.MIN_CONFIDENCE)
        else:
            self.model = self.config.get("model", "grok-3") if isinstance(self.config, dict) else "grok-3"
            self.max_iterations = self.config.get("max_iterations", self.MAX_ITERATIONS) if isinstance(self.config, dict) else self.MAX_ITERATIONS
            self.min_confidence = self.config.get("min_confidence", self.MIN_CONFIDENCE) if isinstance(self.config, dict) else self.MIN_CONFIDENCE

        self.grok_client = grok_client
        self.sentiment_aggregator = sentiment_aggregator

        self.iteration_count = 0
        self.total_cost = 0.0
        self.scratchpad: List[Dict[str, Any]] = []

        # Legacy internal state
        self._iteration = 0
        self._cost = 0.0
        self._tools_used: List[str] = []
        self._evidence: Dict[str, Any] = {}

        # Lazy load components
        self._scratchpad = None
        self._confidence_scorer = None
        self._grok_client = grok_client

    def _get_scratchpad(self):
        """Lazy load scratchpad."""
        if self._scratchpad is None:
            try:
                from .scratchpad import Scratchpad
                self._scratchpad = Scratchpad(self.session_id)
            except ImportError:
                self._scratchpad = MockScratchpad()
        return self._scratchpad

    def _log_reasoning(self, thought: str, iteration: Optional[int] = None) -> None:
        """Log a reasoning step to the in-memory scratchpad."""
        entry = {
            "type": "reasoning",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "thought": thought,
        }
        if iteration is not None:
            entry["iteration"] = iteration
        self.scratchpad.append(entry)

    def _log_action(self, tool: str, args: Dict[str, Any], result: Any) -> None:
        """Log a tool action to the in-memory scratchpad."""
        entry = {
            "type": "action",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool": tool,
            "args": args,
            "result": result,
        }
        self.scratchpad.append(entry)

    def _log_error(self, error: str, iteration: Optional[int] = None) -> None:
        """Log an error to the in-memory scratchpad."""
        entry = {
            "type": "error",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": error,
        }
        if iteration is not None:
            entry["iteration"] = iteration
        self.scratchpad.append(entry)

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

    def _extract_sentiment_score(self, response: str) -> float:
        """Extract sentiment score from Grok response."""
        if not response:
            return 50.0
        import re
        match = re.search(r"(SENTIMENT_SCORE|SENTIMENT)\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)", response, re.IGNORECASE)
        if match:
            try:
                return float(match.group(2))
            except ValueError:
                return 50.0
        return 50.0

    def _extract_confidence(self, response: str) -> float:
        """Extract confidence score from Grok response."""
        if not response:
            return 50.0
        import re
        match = re.search(r"CONFIDENCE\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)", response, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return 50.0
        return 50.0

    def _parse_recommendation(self, response: str) -> DecisionType:
        """Parse recommendation from Grok response."""
        if not response:
            return DecisionType.HOLD
        import re
        upper = response.upper()
        if re.search(r"\bBUY\b", upper):
            return DecisionType.TRADE_BUY
        if re.search(r"\bSELL\b", upper):
            return DecisionType.TRADE_SELL
        if re.search(r"\bHOLD\b", upper):
            return DecisionType.HOLD
        return DecisionType.HOLD

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

    async def analyze_trading_opportunity(
        self,
        symbol: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ReActDecision:
        """
        Analyze a trading opportunity using Grok sentiment and aggregation.

        Args:
            symbol: Token symbol to analyze
            context: Optional market context

        Returns:
            ReActDecision with decision, confidence, and rationale
        """
        self.iteration_count = 0
        self.total_cost = 0.0
        self.scratchpad = []
        tools_used: List[str] = []
        grok_score = 0.0
        confidence = 50.0
        recommendation = DecisionType.HOLD
        rationale = ""
        agg_score = None

        for _ in range(self.MAX_ITERATIONS):
            self.iteration_count += 1
            self._log_reasoning(f"Analyzing {symbol}", iteration=self.iteration_count)

            grok = self.grok_client

            if grok is not None:
                try:
                    if hasattr(grok, "analyze_sentiment"):
                        response = await grok.analyze_sentiment(symbol)
                    elif hasattr(grok, "chat"):
                        response = await grok.chat(system="Sentiment analysis", message=symbol)
                    else:
                        response = ""

                    tools_used.append("sentiment_analyze")
                    response_text = response
                    if hasattr(response, "content"):
                        response_text = getattr(response, "content", "")
                    elif isinstance(response, dict) and "content" in response:
                        response_text = response.get("content", "")

                    self._log_action("sentiment_analyze", {"symbol": symbol}, response_text)

                    grok_score = self._extract_sentiment_score(str(response_text))
                    confidence = self._extract_confidence(str(response_text))
                    recommendation = self._parse_recommendation(str(response_text))
                    rationale = str(response_text).strip()
                except Exception as e:
                    self._log_error(str(e), iteration=self.iteration_count)
                    return ReActDecision(
                        decision=DecisionType.ERROR,
                        symbol=symbol,
                        confidence=0.0,
                        rationale=str(e),
                        iterations=self.iteration_count,
                        tools_used=tools_used,
                        cost_usd=self.total_cost,
                        grok_sentiment_score=grok_score,
                        error=str(e),
                    )

            if self.sentiment_aggregator and hasattr(self.sentiment_aggregator, "get_sentiment_score"):
                try:
                    agg_score = self.sentiment_aggregator.get_sentiment_score(symbol)
                    tools_used.append("sentiment_aggregate")
                    self._log_action("sentiment_aggregate", {"symbol": symbol}, agg_score)
                except Exception as e:
                    self._log_reasoning(f"Sentiment aggregator error: {e}", iteration=self.iteration_count)

            decision = DecisionType.HOLD
            if recommendation in (DecisionType.TRADE_BUY, DecisionType.TRADE_SELL):
                if confidence >= self.MIN_CONFIDENCE:
                    decision = recommendation
                else:
                    decision = DecisionType.HOLD
                    if not rationale:
                        rationale = f"Confidence {confidence:.1f} below threshold"
            elif grok is None and agg_score is not None:
                decision = DecisionType.TRADE_BUY if agg_score >= self.MIN_CONFIDENCE else DecisionType.HOLD

            self._tools_used = tools_used
            self._evidence = {"sentiment_aggregate": agg_score} if agg_score is not None else {}

            return ReActDecision(
                decision=decision,
                symbol=symbol,
                confidence=confidence,
                rationale=rationale or "No clear signal",
                iterations=self.iteration_count,
                tools_used=tools_used,
                cost_usd=self.total_cost,
                grok_sentiment_score=grok_score,
                evidence=self._evidence,
            )

        return ReActDecision(
            decision=DecisionType.HOLD,
            symbol=symbol,
            confidence=50.0,
            rationale="Max iterations reached",
            iterations=self.iteration_count,
            tools_used=tools_used,
            cost_usd=self.total_cost,
            grok_sentiment_score=grok_score,
        )

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
