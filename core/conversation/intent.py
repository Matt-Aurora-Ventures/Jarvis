"""
Intent Classifier - Classify user intents for context-aware responses.

Intent Types:
- Trading: Buy, sell, portfolio, analysis
- General: Chat, greeting, farewell
- Technical: Help, documentation, debugging
- System: Settings, preferences, status
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import re


class IntentType(Enum):
    """Types of user intents."""
    # Trading intents
    TRADING_BUY = "trading.buy"
    TRADING_SELL = "trading.sell"
    TRADING_PORTFOLIO = "trading.portfolio"
    TRADING_ANALYSIS = "trading.analysis"
    TRADING_PRICE = "trading.price"
    TRADING_ALERT = "trading.alert"
    TRADING_HISTORY = "trading.history"

    # Staking intents
    STAKING_STAKE = "staking.stake"
    STAKING_UNSTAKE = "staking.unstake"
    STAKING_REWARDS = "staking.rewards"
    STAKING_STATUS = "staking.status"

    # General conversation
    GENERAL_GREETING = "general.greeting"
    GENERAL_FAREWELL = "general.farewell"
    GENERAL_THANKS = "general.thanks"
    GENERAL_CHAT = "general.chat"
    GENERAL_QUESTION = "general.question"

    # Technical/help
    TECHNICAL_HELP = "technical.help"
    TECHNICAL_DOCS = "technical.docs"
    TECHNICAL_DEBUG = "technical.debug"
    TECHNICAL_STATUS = "technical.status"

    # System intents
    SYSTEM_SETTINGS = "system.settings"
    SYSTEM_PREFERENCES = "system.preferences"
    SYSTEM_NOTIFICATIONS = "system.notifications"
    SYSTEM_CONNECT = "system.connect"

    # Unknown
    UNKNOWN = "unknown"


@dataclass
class Intent:
    """Classified intent from user message."""
    intent_type: IntentType
    confidence: float  # 0.0 to 1.0
    entities: Dict[str, Any] = field(default_factory=dict)
    raw_message: str = ""
    detected_at: datetime = field(default_factory=datetime.utcnow)
    alternatives: List[Tuple[IntentType, float]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "intent_type": self.intent_type.value,
            "confidence": self.confidence,
            "entities": self.entities,
            "raw_message": self.raw_message,
            "detected_at": self.detected_at.isoformat(),
            "alternatives": [
                {"type": t.value, "confidence": c}
                for t, c in self.alternatives
            ],
        }

    @property
    def is_trading(self) -> bool:
        """Check if intent is trading-related."""
        return self.intent_type.value.startswith("trading.")

    @property
    def is_staking(self) -> bool:
        """Check if intent is staking-related."""
        return self.intent_type.value.startswith("staking.")

    @property
    def is_high_confidence(self) -> bool:
        """Check if confidence is high enough for action."""
        return self.confidence >= 0.7

    @property
    def needs_clarification(self) -> bool:
        """Check if we should ask for clarification."""
        return self.confidence < 0.5 or (
            len(self.alternatives) > 0 and
            self.alternatives[0][1] > self.confidence * 0.8
        )


class IntentClassifier:
    """Classify user intents using pattern matching and heuristics."""

    def __init__(self):
        self._patterns = self._build_patterns()
        self._entity_patterns = self._build_entity_patterns()

    def _build_patterns(self) -> Dict[IntentType, List[re.Pattern]]:
        """Build regex patterns for intent classification."""
        return {
            # Trading
            IntentType.TRADING_BUY: [
                re.compile(r"\b(buy|purchase|get|acquire|long)\b.*\b(sol|token|crypto|coin)\b", re.I),
                re.compile(r"\b(buy|purchase)\s+\$?\d+", re.I),
                re.compile(r"\bgo\s+long\b", re.I),
            ],
            IntentType.TRADING_SELL: [
                re.compile(r"\b(sell|dump|exit|close|short)\b.*\b(sol|token|crypto|coin|position)\b", re.I),
                re.compile(r"\b(take\s+profit|tp)\b", re.I),
                re.compile(r"\bgo\s+short\b", re.I),
            ],
            IntentType.TRADING_PORTFOLIO: [
                re.compile(r"\b(portfolio|holdings|positions|balance|wallet)\b", re.I),
                re.compile(r"\bwhat\s+(do\s+)?i\s+(have|own|hold)\b", re.I),
                re.compile(r"\bshow\s+(me\s+)?(my\s+)?(portfolio|balance)\b", re.I),
            ],
            IntentType.TRADING_ANALYSIS: [
                re.compile(r"\b(analyze|analysis|analyse|review)\b", re.I),
                re.compile(r"\bwhat\s+do\s+you\s+think\s+(about|of)\b", re.I),
                re.compile(r"\bshould\s+i\s+(buy|sell|hold)\b", re.I),
            ],
            IntentType.TRADING_PRICE: [
                re.compile(r"\b(price|cost|value|worth)\b.*\b(of|for)?\b", re.I),
                re.compile(r"\bhow\s+much\s+is\b", re.I),
                re.compile(r"\bwhat('s|\s+is)\s+\w+\s+(trading\s+)?(at|for)\b", re.I),
            ],
            IntentType.TRADING_ALERT: [
                re.compile(r"\b(alert|notify|tell\s+me|remind)\b.*\b(when|if|price)\b", re.I),
                re.compile(r"\bset\s+(an?\s+)?alert\b", re.I),
            ],
            IntentType.TRADING_HISTORY: [
                re.compile(r"\b(history|trades|transactions|orders)\b", re.I),
                re.compile(r"\bpast\s+(trades|transactions)\b", re.I),
            ],

            # Staking
            IntentType.STAKING_STAKE: [
                re.compile(r"\b(stake|staking|lock)\b.*\b(kr8tiv|tokens?)\b", re.I),
                re.compile(r"\bi\s+want\s+to\s+stake\b", re.I),
            ],
            IntentType.STAKING_UNSTAKE: [
                re.compile(r"\b(unstake|unlock|withdraw)\b", re.I),
            ],
            IntentType.STAKING_REWARDS: [
                re.compile(r"\b(rewards?|earnings?|yield|apy)\b", re.I),
                re.compile(r"\bhow\s+much\s+(have\s+i|did\s+i)\s+earn\b", re.I),
            ],
            IntentType.STAKING_STATUS: [
                re.compile(r"\bstaking\s+(status|info)\b", re.I),
                re.compile(r"\bmy\s+stake\b", re.I),
            ],

            # General
            IntentType.GENERAL_GREETING: [
                re.compile(r"^(hi|hello|hey|yo|sup|greetings|good\s+(morning|afternoon|evening))\b", re.I),
                re.compile(r"\bhow\s+are\s+you\b", re.I),
            ],
            IntentType.GENERAL_FAREWELL: [
                re.compile(r"\b(bye|goodbye|later|see\s+you|cya|goodnight)\b", re.I),
            ],
            IntentType.GENERAL_THANKS: [
                re.compile(r"\b(thanks?|thank\s+you|thx|ty|appreciate)\b", re.I),
            ],
            IntentType.GENERAL_QUESTION: [
                re.compile(r"^(what|who|where|when|why|how|is|are|can|could|would|will|do|does)\b", re.I),
            ],

            # Technical
            IntentType.TECHNICAL_HELP: [
                re.compile(r"\b(help|assist|support)\b", re.I),
                re.compile(r"\bhow\s+do\s+i\b", re.I),
                re.compile(r"\bcan\s+you\s+(help|show|explain)\b", re.I),
            ],
            IntentType.TECHNICAL_DOCS: [
                re.compile(r"\b(docs?|documentation|guide|tutorial)\b", re.I),
            ],
            IntentType.TECHNICAL_DEBUG: [
                re.compile(r"\b(debug|error|issue|problem|bug|broken|fix)\b", re.I),
                re.compile(r"\b(not\s+working|doesn't\s+work)\b", re.I),
            ],
            IntentType.TECHNICAL_STATUS: [
                re.compile(r"\b(status|health|uptime|running)\b", re.I),
                re.compile(r"\bis\s+(jarvis|the\s+bot)\s+(online|working|up)\b", re.I),
            ],

            # System
            IntentType.SYSTEM_SETTINGS: [
                re.compile(r"\b(settings?|config|configure|setup)\b", re.I),
            ],
            IntentType.SYSTEM_PREFERENCES: [
                re.compile(r"\b(preferences?|customize|personalize)\b", re.I),
            ],
            IntentType.SYSTEM_NOTIFICATIONS: [
                re.compile(r"\b(notifications?|alerts?)\s+(settings?|on|off|enable|disable)\b", re.I),
            ],
            IntentType.SYSTEM_CONNECT: [
                re.compile(r"\b(connect|link|integrate)\s+(wallet|account)\b", re.I),
            ],
        }

    def _build_entity_patterns(self) -> Dict[str, re.Pattern]:
        """Build patterns for entity extraction."""
        return {
            "token": re.compile(r"\b(SOL|BONK|WIF|JUP|RAY|ORCA|USDC|USDT|BTC|ETH)\b", re.I),
            "amount_usd": re.compile(r"\$(\d+(?:,\d{3})*(?:\.\d{2})?)", re.I),
            "amount_number": re.compile(r"(\d+(?:\.\d+)?)\s*(sol|tokens?|coins?)?", re.I),
            "percentage": re.compile(r"(\d+(?:\.\d+)?)\s*%", re.I),
            "wallet_address": re.compile(r"\b([1-9A-HJ-NP-Za-km-z]{32,44})\b"),
            "contract_address": re.compile(r"\b([1-9A-HJ-NP-Za-km-z]{43,44})\b"),
        }

    def classify(self, message: str) -> Intent:
        """Classify user message into an intent."""
        message = message.strip()
        if not message:
            return Intent(
                intent_type=IntentType.UNKNOWN,
                confidence=0.0,
                raw_message=message,
            )

        # Find matching intents
        matches: List[Tuple[IntentType, float]] = []

        for intent_type, patterns in self._patterns.items():
            max_confidence = 0.0
            for pattern in patterns:
                if pattern.search(message):
                    # Base confidence from pattern match
                    confidence = 0.7

                    # Boost for start-of-message matches
                    if pattern.match(message):
                        confidence += 0.1

                    # Boost for longer messages (more context)
                    if len(message) > 20:
                        confidence += 0.05

                    max_confidence = max(max_confidence, min(confidence, 1.0))

            if max_confidence > 0:
                matches.append((intent_type, max_confidence))

        # Sort by confidence
        matches.sort(key=lambda x: x[1], reverse=True)

        # Extract entities
        entities = self._extract_entities(message)

        if matches:
            best_intent, best_confidence = matches[0]
            alternatives = matches[1:4]  # Keep top 3 alternatives

            return Intent(
                intent_type=best_intent,
                confidence=best_confidence,
                entities=entities,
                raw_message=message,
                alternatives=alternatives,
            )

        # Default to general chat if no patterns match
        return Intent(
            intent_type=IntentType.GENERAL_CHAT,
            confidence=0.3,
            entities=entities,
            raw_message=message,
        )

    def _extract_entities(self, message: str) -> Dict[str, Any]:
        """Extract entities from message."""
        entities = {}

        for entity_name, pattern in self._entity_patterns.items():
            matches = pattern.findall(message)
            if matches:
                if entity_name == "token":
                    entities["tokens"] = [m.upper() for m in matches]
                elif entity_name == "amount_usd":
                    entities["amounts_usd"] = [float(m.replace(",", "")) for m in matches]
                elif entity_name == "amount_number":
                    entities["amounts"] = [float(m[0]) for m in matches]
                elif entity_name == "percentage":
                    entities["percentages"] = [float(m) for m in matches]
                elif entity_name in ("wallet_address", "contract_address"):
                    entities[entity_name + "es"] = matches

        return entities

    def get_suggested_responses(self, intent: Intent) -> List[str]:
        """Get suggested quick responses based on intent."""
        suggestions = {
            IntentType.TRADING_BUY: [
                "How much would you like to buy?",
                "Which token?",
                "Confirm purchase",
            ],
            IntentType.TRADING_SELL: [
                "How much to sell?",
                "Sell all",
                "Set limit order",
            ],
            IntentType.TRADING_PORTFOLIO: [
                "Show detailed",
                "Show P&L",
                "Export CSV",
            ],
            IntentType.GENERAL_GREETING: [
                "Check portfolio",
                "View trending",
                "Get help",
            ],
            IntentType.STAKING_REWARDS: [
                "Claim rewards",
                "View history",
                "Calculate APY",
            ],
        }

        return suggestions.get(intent.intent_type, [])


# Singleton instance
_intent_classifier: Optional[IntentClassifier] = None


def get_intent_classifier() -> IntentClassifier:
    """Get the global intent classifier instance."""
    global _intent_classifier
    if _intent_classifier is None:
        _intent_classifier = IntentClassifier()
    return _intent_classifier
