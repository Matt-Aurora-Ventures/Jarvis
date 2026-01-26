"""
Voice Command Parser - Natural Language Trading Commands.

Parses voice input into structured intents for the JARVIS voice trading terminal.
Supports conversational trading commands like:
- "Morning briefing"
- "Activate momentum strategy"
- "Set my max position to 3 percent"
- "Alert me when SOL hits 150"
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class Intent(Enum):
    """Supported voice command intents."""
    MORNING_BRIEFING = "morning_briefing"
    STRATEGY_CONTROL = "strategy_control"
    STRATEGY_STATUS = "strategy_status"
    RISK_ADJUSTMENT = "risk_adjustment"
    RISK_QUERY = "risk_query"
    PRICE_ALERT = "price_alert"
    LIST_ALERTS = "list_alerts"
    CANCEL_ALERT = "cancel_alert"
    POSITION_QUERY = "position_query"
    PRICE_QUERY = "price_query"
    MARKET_OVERVIEW = "market_overview"
    TRADE_COMMAND = "trade_command"
    UNKNOWN = "unknown"


@dataclass
class CommandIntent:
    """Parsed command intent with parameters."""
    intent: str
    confidence: float
    params: Dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "intent": self.intent,
            "confidence": self.confidence,
            "params": self.params,
            "raw_text": self.raw_text,
        }


# Token name normalization map
TOKEN_ALIASES = {
    "solana": "SOL",
    "sol": "SOL",
    "bitcoin": "BTC",
    "btc": "BTC",
    "ethereum": "ETH",
    "eth": "ETH",
    "bonk": "BONK",
    "wif": "WIF",
    "dogecoin": "DOGE",
    "doge": "DOGE",
    "jupiter": "JUP",
    "jup": "JUP",
    "raydium": "RAY",
    "ray": "RAY",
    "pyth": "PYTH",
    "jito": "JTO",
    "jto": "JTO",
    "render": "RNDR",
    "rndr": "RNDR",
    "helium": "HNT",
    "hnt": "HNT",
}

# Word to number mapping
WORD_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
    "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90, "hundred": 100, "thousand": 1000,
}

# Strategy name normalization
STRATEGY_ALIASES = {
    "momentum": "momentum",
    "dca": "dca",
    "dollar cost averaging": "dca",
    "grid": "grid",
    "grid trading": "grid",
    "scalping": "scalping",
    "scalp": "scalping",
    "mean reversion": "mean_reversion",
    "mean-reversion": "mean_reversion",
    "reversion": "mean_reversion",
    "breakout": "breakout",
    "trend following": "trend_following",
    "trend": "trend_following",
}


class VoiceCommandParser:
    """
    Parse natural language voice commands into structured intents.

    Uses pattern matching and keyword extraction for offline operation.
    Can be enhanced with LLM-based parsing for complex commands.
    """

    def __init__(self):
        """Initialize the parser with command patterns."""
        self._patterns = self._build_patterns()

    def _build_patterns(self) -> List[Tuple[str, re.Pattern, str, float]]:
        """Build regex patterns for command matching."""
        patterns = []

        # Morning briefing patterns
        briefing_patterns = [
            r"(?:morning|market|overnight)\s*(?:briefing|summary|update)",
            r"what(?:'s|\s+is)?\s+(?:the\s+)?(?:morning\s+)?briefing",
            r"(?:give|get)\s+me\s+(?:the\s+)?(?:morning\s+)?briefing",
            r"what\s+happened\s+overnight",
            r"overnight\s+(?:summary|update|moves)",
            r"gm\s+briefing",
            r"good\s+morning\s+briefing",
        ]
        for p in briefing_patterns:
            patterns.append((Intent.MORNING_BRIEFING.value, re.compile(p, re.IGNORECASE), p, 0.9))

        # Strategy control patterns
        strategy_activate = [
            r"(?:activate|enable|turn\s+on|start)\s+(\w+(?:\s+\w+)?)\s*(?:strategy)?",
        ]
        for p in strategy_activate:
            patterns.append(("strategy_activate", re.compile(p, re.IGNORECASE), p, 0.9))

        strategy_deactivate = [
            r"deactivate\s+(\w+(?:\s+\w+)?)\s*(?:strategy)?",
            r"disable\s+(\w+(?:\s+\w+)?)\s*(?:strategy)?",
            r"turn\s+off\s+(\w+(?:\s+\w+)?)\s*(?:strategy)?",
            r"stop\s+(\w+)\s+strategy",  # More specific - requires "strategy" after
        ]
        # Add deactivate patterns at higher priority
        for p in strategy_deactivate:
            patterns.insert(0, ("strategy_deactivate", re.compile(p, re.IGNORECASE), p, 0.95))

        strategy_status = [
            r"what\s+(?:strategies|strategy)\s+(?:are|is)\s+active",
            r"(?:list|show)\s+(?:active\s+)?strategies",
            r"strategy\s+status",
        ]
        for p in strategy_status:
            patterns.append((Intent.STRATEGY_STATUS.value, re.compile(p, re.IGNORECASE), p, 0.85))

        # Risk adjustment patterns - more specific to avoid conflicts
        risk_patterns = [
            r"(?:set|change|reduce|increase)\s+(?:my\s+)?(?:max\s+)?position(?:\s+size)?\s+(?:to\s+)?(.+)",
            r"(?:set|change|reduce|increase)\s+(?:my\s+)?stop[\s-]*loss\s+(?:to\s+)?(.+)",
            r"(?:set|change|reduce|increase)\s+(?:my\s+)?take[\s-]*profit\s+(?:to\s+)?(.+)",
            r"(?:set|change|reduce|increase)\s+(?:my\s+)?daily[\s-]*loss[\s-]*limit\s+(?:to\s+)?(.+)",
            r"(?:set|change|reduce|increase)\s+(?:my\s+)?max[\s-]*drawdown\s+(?:to\s+)?(.+)",
        ]
        # Add risk patterns BEFORE strategy patterns (higher priority)
        for p in risk_patterns:
            patterns.insert(0, ("risk_adjustment", re.compile(p, re.IGNORECASE), p, 0.95))

        risk_query = [
            r"what\s+(?:are|is)\s+(?:my\s+)?(?:current\s+)?risk\s+limit",
            r"(?:show|list|get)\s+(?:my\s+)?risk\s+(?:limits|settings)",
            r"risk\s+status",
        ]
        for p in risk_query:
            patterns.append((Intent.RISK_QUERY.value, re.compile(p, re.IGNORECASE), p, 0.85))

        # Price alert patterns
        alert_patterns = [
            r"(?:alert|notify|tell)\s+(?:me\s+)?when\s+(?:\$)?(\w+)\s+(?:hits|reaches|goes\s+(?:to|above|below))\s+([\d.]+)",
            r"set\s+(?:a\s+)?(?:price\s+)?alert\s+(?:for\s+)?(?:\$)?(\w+)\s+(?:at|when)\s+([\d.]+)",
            r"alert\s+(?:me\s+)?when\s+(?:\$)?(\w+)\s+(?:drops?\s+)?(?:below|above)\s+([\d.]+)",
        ]
        for p in alert_patterns:
            patterns.append(("price_alert", re.compile(p, re.IGNORECASE), p, 0.9))

        list_alerts = [
            r"(?:what|show|list)\s+(?:my\s+)?alerts",
            r"(?:what\s+)?alerts\s+(?:do\s+I\s+)?have",
            r"active\s+alerts",
        ]
        # Higher priority for alerts to avoid confusion with positions
        for p in list_alerts:
            patterns.insert(0, (Intent.LIST_ALERTS.value, re.compile(p, re.IGNORECASE), p, 0.95))

        cancel_alert = [
            r"(?:cancel|remove|delete)\s+(?:the\s+)?alert\s+(?:for\s+)?(?:\$)?(\w+)",
        ]
        for p in cancel_alert:
            patterns.append(("cancel_alert", re.compile(p, re.IGNORECASE), p, 0.9))

        # Position query patterns
        position_patterns = [
            r"(?:what\s+(?:are|is)\s+)?(?:my\s+)?(?:open\s+)?positions?",
            r"(?:show|list)\s+(?:my\s+)?(?:open\s+)?positions?",
            r"what\s+(?:am\s+I|are\s+we)\s+holding",
            r"(?:current\s+)?portfolio(?:\s+status)?",
            r"what(?:'s|\s+is)\s+in\s+(?:my\s+)?portfolio",
        ]
        for p in position_patterns:
            patterns.append((Intent.POSITION_QUERY.value, re.compile(p, re.IGNORECASE), p, 0.85))

        specific_position = [
            r"(?:what(?:'s|\s+is)?\s+)?(?:my\s+)?position\s+(?:in|on)\s+(?:\$)?(\w+)",
            # Match "how much SOL do I have" - requires word boundary after amount words
            r"(?:how\s+(?:much|many)\s+)(?:\$)?(\w+)\s+(?:do\s+I\s+)?(?:have|hold)",
        ]
        # Insert at beginning for higher priority than generic position_query
        for p in specific_position:
            patterns.insert(0, ("position_token", re.compile(p, re.IGNORECASE), p, 0.95))

        # Price query patterns
        price_patterns = [
            r"(?:what(?:'s|\s+is)?\s+)?(?:the\s+)?price\s+(?:of\s+)?(?:\$)?(\w+)",
            r"(?:\$)?(\w+)\s+price",
            r"how\s+much\s+is\s+(?:\$)?(\w+)",
            r"check\s+(?:\$)?(\w+)\s+price",
            r"(?:what(?:'s|\s+is)?\s+)?(?:\$)?(\w+)\s+trading\s+at",
        ]
        for p in price_patterns:
            patterns.append(("price_query", re.compile(p, re.IGNORECASE), p, 0.9))

        # Market overview patterns
        market_patterns = [
            r"how(?:'s|\s+is)?\s+(?:the\s+)?market(?:\s+doing)?",
            r"market\s+(?:overview|status|update)",
            r"(?:what(?:'s|\s+is)?\s+)?(?:the\s+)?market\s+(?:like|looking)",
        ]
        for p in market_patterns:
            patterns.append((Intent.MARKET_OVERVIEW.value, re.compile(p, re.IGNORECASE), p, 0.85))

        # Trading command patterns - order matters, more specific first
        buy_amount_patterns = [
            r"buy\s+([\d.]+)\s+(?:dollars?|usd)\s+(?:of|worth(?:\s+of)?)\s+(?:\$)?(\w+)",
        ]
        # Higher priority for amount patterns
        for p in buy_amount_patterns:
            patterns.insert(0, ("trade_buy_amount", re.compile(p, re.IGNORECASE), p, 0.95))

        buy_patterns = [
            r"buy\s+(?:some\s+)?(?:\$)?(\w+)",
        ]
        for p in buy_patterns:
            patterns.append(("trade_buy", re.compile(p, re.IGNORECASE), p, 0.9))

        sell_pct_patterns = [
            r"sell\s+([\d.]+)\s+(?:percent|%)\s+(?:of\s+)?(?:my\s+)?(?:\$)?(\w+)",
        ]
        # Higher priority for percentage patterns
        for p in sell_pct_patterns:
            patterns.insert(0, ("trade_sell_pct", re.compile(p, re.IGNORECASE), p, 0.95))

        sell_patterns = [
            r"sell\s+(?:my\s+)?(?:\$)?(\w+)",
        ]
        for p in sell_patterns:
            patterns.append(("trade_sell", re.compile(p, re.IGNORECASE), p, 0.9))

        close_patterns = [
            r"(?:close|exit)\s+(?:my\s+)?(?:\$)?(\w+)\s+position",  # Requires "position" to avoid conflicts
        ]
        # Add trade close patterns at higher priority
        for p in close_patterns:
            patterns.insert(0, ("trade_close", re.compile(p, re.IGNORECASE), p, 0.95))

        return patterns

    def parse(self, text: Optional[str]) -> Dict[str, Any]:
        """
        Parse voice command text into a structured intent.

        Args:
            text: The transcribed voice command text

        Returns:
            Dictionary with intent, confidence, params, and raw_text
        """
        # Handle None/empty input
        if not text or not text.strip():
            return CommandIntent(
                intent=Intent.UNKNOWN.value,
                confidence=0.0,
                params={},
                raw_text=text or ""
            ).to_dict()

        # Normalize text
        text = text.strip()
        text_lower = text.lower()

        # Remove "jarvis" prefix if present
        text_lower = re.sub(r"^(?:hey\s+)?jarvis[,]?\s*", "", text_lower).strip()

        # Try each pattern
        for intent_type, pattern, _, base_confidence in self._patterns:
            match = pattern.search(text_lower)
            if match:
                return self._build_result(intent_type, match, text, base_confidence)

        # No pattern matched
        return CommandIntent(
            intent=Intent.UNKNOWN.value,
            confidence=0.0,
            params={},
            raw_text=text
        ).to_dict()

    def _build_result(
        self,
        intent_type: str,
        match: re.Match,
        raw_text: str,
        base_confidence: float
    ) -> Dict[str, Any]:
        """Build result dictionary from pattern match."""
        params = {}

        # Handle strategy commands
        if intent_type == "strategy_activate":
            strategy_name = self._normalize_strategy(match.group(1))
            params = {"action": "activate", "strategy": strategy_name}
            intent_type = Intent.STRATEGY_CONTROL.value

        elif intent_type == "strategy_deactivate":
            strategy_name = self._normalize_strategy(match.group(1))
            params = {"action": "deactivate", "strategy": strategy_name}
            intent_type = Intent.STRATEGY_CONTROL.value

        # Handle risk adjustment
        elif intent_type == "risk_adjustment":
            params = self._parse_risk_params(raw_text, match)
            intent_type = Intent.RISK_ADJUSTMENT.value

        # Handle price alerts
        elif intent_type == "price_alert":
            groups = match.groups()
            token = self._normalize_token(groups[0])
            price = self._parse_number(groups[1])
            direction = self._extract_alert_direction(raw_text.lower())
            params = {"token": token, "price": price, "direction": direction}
            intent_type = Intent.PRICE_ALERT.value

        # Handle cancel alert
        elif intent_type == "cancel_alert":
            token = self._normalize_token(match.group(1))
            params = {"token": token}
            intent_type = Intent.CANCEL_ALERT.value

        # Handle position queries
        elif intent_type == "position_token":
            token = self._normalize_token(match.group(1))
            params = {"token": token}
            intent_type = Intent.POSITION_QUERY.value

        # Handle price queries
        elif intent_type == "price_query":
            token = self._normalize_token(match.group(1))
            params = {"token": token}
            intent_type = Intent.PRICE_QUERY.value

        # Handle trading commands
        elif intent_type == "trade_buy":
            token = self._normalize_token(match.group(1))
            params = {"action": "buy", "token": token}
            intent_type = Intent.TRADE_COMMAND.value

        elif intent_type == "trade_buy_amount":
            groups = match.groups()
            amount = self._parse_number(groups[0])
            token = self._normalize_token(groups[1])
            params = {"action": "buy", "token": token, "amount": amount, "currency": "USD"}
            intent_type = Intent.TRADE_COMMAND.value

        elif intent_type == "trade_sell":
            token = self._normalize_token(match.group(1))
            params = {"action": "sell", "token": token}
            intent_type = Intent.TRADE_COMMAND.value

        elif intent_type == "trade_sell_pct":
            groups = match.groups()
            percentage = self._parse_number(groups[0])
            token = self._normalize_token(groups[1])
            params = {"action": "sell", "token": token, "percentage": percentage}
            intent_type = Intent.TRADE_COMMAND.value

        elif intent_type == "trade_close":
            token = self._normalize_token(match.group(1))
            params = {"action": "close", "token": token}
            intent_type = Intent.TRADE_COMMAND.value

        return CommandIntent(
            intent=intent_type,
            confidence=base_confidence,
            params=params,
            raw_text=raw_text
        ).to_dict()

    def _normalize_token(self, token: str) -> str:
        """Normalize token name to standard symbol."""
        if not token:
            return ""

        # Remove $ prefix
        token = token.strip().lstrip("$")
        token_lower = token.lower()

        # Check alias map
        if token_lower in TOKEN_ALIASES:
            return TOKEN_ALIASES[token_lower]

        # Return uppercase
        return token.upper()

    def _normalize_strategy(self, strategy: str) -> str:
        """Normalize strategy name."""
        if not strategy:
            return ""

        strategy_lower = strategy.lower().strip()

        # Remove trailing "strategy" word
        strategy_lower = re.sub(r"\s+strategy$", "", strategy_lower)

        # Check alias map
        if strategy_lower in STRATEGY_ALIASES:
            return STRATEGY_ALIASES[strategy_lower]

        # Return as-is with underscores for spaces
        return strategy_lower.replace(" ", "_")

    def _parse_number(self, text: str) -> float:
        """Parse number from text (handles words and digits)."""
        if not text:
            return 0.0

        text = text.strip().lower()

        # Remove common prefixes/suffixes
        text = text.lstrip("$")
        text = re.sub(r"\s*(percent|%|dollars?|usd)\s*", "", text)

        # Try direct float conversion
        try:
            return float(text)
        except ValueError:
            pass

        # Try word-to-number conversion
        total = 0.0
        current = 0.0
        words = text.split()

        for word in words:
            if word in WORD_NUMBERS:
                num = WORD_NUMBERS[word]
                if num == 100:
                    current = current * 100 if current else 100
                elif num == 1000:
                    current = current * 1000 if current else 1000
                else:
                    current += num
            elif word == "and":
                continue
            else:
                # Try parsing as number
                try:
                    current += float(word)
                except ValueError:
                    pass

        total += current
        return total if total > 0 else 0.0

    def _parse_risk_params(self, raw_text: str, match: re.Match) -> Dict[str, Any]:
        """Parse risk adjustment parameters."""
        params = {}
        text_lower = raw_text.lower()

        # Extract the value part
        value_text = match.group(1) if match.groups() else ""
        value = self._parse_number(value_text)

        # Determine which risk parameter
        if "position" in text_lower:
            params["max_position_pct"] = value
        elif "stop" in text_lower and "loss" in text_lower:
            params["stop_loss_pct"] = value
        elif "take" in text_lower and "profit" in text_lower:
            params["take_profit_pct"] = value
        elif "daily" in text_lower and "loss" in text_lower:
            params["daily_loss_limit"] = value
        elif "drawdown" in text_lower:
            params["max_drawdown_pct"] = value

        return params

    def _extract_alert_direction(self, text: str) -> str:
        """Extract price alert direction from text."""
        if "above" in text:
            return "above"
        elif "below" in text or "drop" in text:
            return "below"
        return "at"

    def _parse_buy_params(self, match: re.Match, raw_text: str) -> Dict[str, Any]:
        """Parse buy command parameters."""
        groups = match.groups()
        params = {"action": "buy"}

        if len(groups) == 1:
            # Simple "buy sol"
            params["token"] = self._normalize_token(groups[0])
        elif len(groups) == 2:
            # "buy 100 dollars of sol"
            params["amount"] = self._parse_number(groups[0])
            params["token"] = self._normalize_token(groups[1])
            params["currency"] = "USD"

        return params

    def _parse_sell_params(self, match: re.Match, raw_text: str) -> Dict[str, Any]:
        """Parse sell command parameters."""
        groups = match.groups()
        params = {"action": "sell"}

        if len(groups) == 1:
            # Simple "sell sol"
            params["token"] = self._normalize_token(groups[0])
        elif len(groups) == 2:
            # "sell 50 percent of sol"
            params["percentage"] = self._parse_number(groups[0])
            params["token"] = self._normalize_token(groups[1])

        return params
