"""
JARVIS Introspection - Self-Awareness Module

Enables JARVIS to understand and describe its own capabilities.
This is the "self-awareness" layer that allows the system to:
- Describe what it can do
- Find the right service for a task
- Understand relationships between services
- Generate documentation
- Answer questions about itself

Usage:
    from core.introspection import jarvis_self

    # What can JARVIS do?
    capabilities = jarvis_self.what_can_i_do()

    # Find a service for a task
    service = await jarvis_self.find_for_task("get bitcoin price")

    # Generate system documentation
    docs = jarvis_self.generate_docs()
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from core.jarvis_core import jarvis, Category

logger = logging.getLogger(__name__)


@dataclass
class CapabilityMatch:
    """Result of matching a task to capabilities."""
    capability: str
    confidence: float
    method: Optional[str] = None
    reason: str = ""


class JarvisSelf:
    """
    Self-awareness module for JARVIS.

    Provides introspection capabilities that allow JARVIS to
    understand and describe itself.
    """

    # Task keywords mapped to categories and capabilities
    TASK_PATTERNS = {
        # Data/Prices
        r"(get|fetch|check|what.?is).*(price|cost|value)": {
            "category": Category.DATA,
            "capabilities": ["jupiter", "twelve_data", "hyperliquid", "commodities", "dexscreener"],
            "method": "get_price",
        },
        r"(market|trading).*(data|info|stats)": {
            "category": Category.DATA,
            "capabilities": ["hyperliquid", "dexscreener", "twelve_data"],
        },
        r"(order.?book|liquidity|depth)": {
            "category": Category.DATA,
            "capabilities": ["hyperliquid"],
            "method": "get_order_book",
        },
        r"(funding.?rate|perp)": {
            "category": Category.DATA,
            "capabilities": ["hyperliquid"],
            "method": "get_funding_rates",
        },
        r"(liquidation|liq)": {
            "category": Category.DATA,
            "capabilities": ["hyperliquid"],
            "method": "get_liquidations",
        },

        # Trading
        r"(buy|sell|swap|trade|exchange)": {
            "category": Category.TRADING,
            "capabilities": ["jupiter", "trading_engine"],
            "method": "execute_swap",
        },
        r"(open|close).*(position|trade)": {
            "category": Category.TRADING,
            "capabilities": ["trading_engine"],
        },
        r"(portfolio|holdings|balance)": {
            "category": Category.TRADING,
            "capabilities": ["trading_engine", "jupiter"],
            "method": "get_portfolio_value",
        },

        # Analytics
        r"(sentiment|mood|feeling|bullish|bearish)": {
            "category": Category.ANALYTICS,
            "capabilities": ["sentiment_generator", "sentiment_aggregator"],
            "method": "analyze",
        },
        r"(signal|recommendation|should.?i)": {
            "category": Category.ANALYTICS,
            "capabilities": ["sentiment_generator"],
        },
        r"(analyze|analysis|report)": {
            "category": Category.ANALYTICS,
            "capabilities": ["sentiment_generator", "sentiment_aggregator"],
        },

        # Messaging
        r"(send|post|tweet|message)": {
            "category": Category.MESSAGING,
            "capabilities": ["telegram_bot", "twitter_client"],
        },
        r"(telegram|tg)": {
            "category": Category.MESSAGING,
            "capabilities": ["telegram_bot"],
        },
        r"(twitter|tweet|x\.com)": {
            "category": Category.SOCIAL,
            "capabilities": ["twitter_client"],
        },

        # AI
        r"(generate|write|create|compose)": {
            "category": Category.AI,
            "capabilities": ["grok", "claude"],
            "method": "complete",
        },
        r"(summarize|explain|describe)": {
            "category": Category.AI,
            "capabilities": ["grok", "claude"],
        },

        # Technical indicators
        r"(rsi|macd|sma|ema|bollinger|indicator)": {
            "category": Category.DATA,
            "capabilities": ["twelve_data"],
        },

        # Fundamentals
        r"(earnings|dividend|p/?e|market.?cap|fundamental)": {
            "category": Category.DATA,
            "capabilities": ["twelve_data"],
        },
    }

    # Capability descriptions for natural language
    CAPABILITY_DESCRIPTIONS = {
        "jupiter": "swap tokens on Solana, get prices, find best routes",
        "hyperliquid": "perp trading data, order books, liquidations, funding rates",
        "twelve_data": "stock prices, forex, ETFs, technical indicators, fundamentals",
        "commodities": "gold, silver, and precious metals prices",
        "dexscreener": "DEX token data, new pairs, trading volume",
        "birdeye": "Solana token analytics and data",
        "trading_engine": "open/close positions, manage portfolio, set TP/SL",
        "sentiment_generator": "analyze market sentiment, generate reports",
        "sentiment_aggregator": "combine sentiment from multiple sources",
        "telegram_bot": "send messages, handle commands on Telegram",
        "twitter_client": "post tweets, manage X/Twitter engagement",
        "grok": "generate text, analyze content using xAI Grok",
        "claude": "generate text, analyze content using Anthropic Claude",
    }

    def what_can_i_do(self) -> Dict[str, List[str]]:
        """
        Get a summary of JARVIS capabilities by category.

        Returns:
            Dict mapping category to list of capabilities
        """
        result = {}
        for category in Category:
            services = jarvis.list_capabilities(category=category)
            if services:
                result[category.value] = [
                    f"{s}: {self.CAPABILITY_DESCRIPTIONS.get(s, jarvis.get_metadata(s).description if jarvis.get_metadata(s) else 'No description')}"
                    for s in services
                ]
        return result

    def describe_capability(self, name: str) -> Optional[str]:
        """Get a natural language description of a capability."""
        if name in self.CAPABILITY_DESCRIPTIONS:
            return self.CAPABILITY_DESCRIPTIONS[name]

        meta = jarvis.get_metadata(name)
        if meta:
            return meta.description

        return None

    async def find_for_task(self, task: str) -> List[CapabilityMatch]:
        """
        Find the best capabilities to handle a task.

        Args:
            task: Natural language task description

        Returns:
            List of matching capabilities sorted by confidence
        """
        task_lower = task.lower()
        matches: List[CapabilityMatch] = []

        for pattern, info in self.TASK_PATTERNS.items():
            if re.search(pattern, task_lower):
                for cap in info["capabilities"]:
                    if jarvis.has(cap):
                        matches.append(CapabilityMatch(
                            capability=cap,
                            confidence=0.8,
                            method=info.get("method"),
                            reason=f"Matched pattern: {pattern}",
                        ))

        # Deduplicate and sort by confidence
        seen = set()
        unique = []
        for m in sorted(matches, key=lambda x: -x.confidence):
            if m.capability not in seen:
                seen.add(m.capability)
                unique.append(m)

        return unique

    async def execute_task(self, task: str) -> Tuple[bool, Any, str]:
        """
        Attempt to execute a natural language task.

        Args:
            task: Natural language task description

        Returns:
            Tuple of (success, result, explanation)
        """
        matches = await self.find_for_task(task)

        if not matches:
            return False, None, f"No capability found for: {task}"

        best = matches[0]
        try:
            service = await jarvis.get(best.capability)

            # If we know the method, try to call it
            if best.method and hasattr(service, best.method):
                # Extract potential arguments from task
                result = f"Would call {best.capability}.{best.method}()"
                return True, result, f"Found {best.capability} for task"

            return True, service, f"Found service: {best.capability}"

        except Exception as e:
            return False, None, f"Error accessing {best.capability}: {e}"

    def generate_docs(self) -> str:
        """
        Generate documentation for all JARVIS capabilities.

        Returns:
            Markdown-formatted documentation
        """
        lines = [
            "# JARVIS Capability Documentation",
            "",
            "Auto-generated documentation of all registered services.",
            "",
        ]

        manifest = jarvis.to_manifest()

        for category in Category:
            category_caps = [
                (name, info) for name, info in manifest["capabilities"].items()
                if info["category"] == category.value
            ]

            if not category_caps:
                continue

            lines.append(f"## {category.value.title()}")
            lines.append("")

            for name, info in sorted(category_caps):
                lines.append(f"### {name}")
                lines.append("")
                lines.append(f"**Description:** {info['description']}")
                lines.append("")

                if info.get("tags"):
                    lines.append(f"**Tags:** {', '.join(info['tags'])}")
                    lines.append("")

                if info.get("provides"):
                    lines.append(f"**Provides:** {', '.join(info['provides'])}")
                    lines.append("")

                if info.get("dependencies"):
                    lines.append(f"**Dependencies:** {', '.join(info['dependencies'])}")
                    lines.append("")

                lines.append(f"**Status:** {info['status']}")
                lines.append("")
                lines.append("---")
                lines.append("")

        return "\n".join(lines)

    def generate_mermaid_diagram(self) -> str:
        """
        Generate a Mermaid diagram showing service relationships.

        Returns:
            Mermaid diagram code
        """
        lines = [
            "```mermaid",
            "graph TD",
            "    subgraph Core[JARVIS Core]",
            "        JC[JarvisCore]",
            "        EB[Event Bus]",
            "        CF[Config]",
            "    end",
            "",
        ]

        # Group by category
        for category in Category:
            services = jarvis.list_capabilities(category=category)
            if services:
                safe_cat = category.value.replace("-", "_")
                lines.append(f"    subgraph {safe_cat}[{category.value.title()}]")
                for s in services:
                    safe_s = s.replace("-", "_")
                    lines.append(f"        {safe_s}[{s}]")
                lines.append("    end")
                lines.append("")

        # Add connections to core
        for category in Category:
            services = jarvis.list_capabilities(category=category)
            for s in services:
                safe_s = s.replace("-", "_")
                lines.append(f"    {safe_s} --> JC")

        lines.append("```")
        return "\n".join(lines)

    def explain_self(self) -> str:
        """
        Generate a natural language explanation of what JARVIS is and can do.
        """
        manifest = jarvis.to_manifest()
        total = len(manifest["capabilities"])

        by_category = {}
        for name, info in manifest["capabilities"].items():
            cat = info["category"]
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(name)

        explanation = f"""
I am JARVIS, a unified autonomous system with {total} registered capabilities.

Here's what I can do:

"""
        for cat, services in sorted(by_category.items()):
            explanation += f"**{cat.title()}**: "
            descriptions = [
                self.CAPABILITY_DESCRIPTIONS.get(s, s)
                for s in services[:3]  # First 3
            ]
            explanation += ", ".join(descriptions)
            if len(services) > 3:
                explanation += f" (+{len(services) - 3} more)"
            explanation += "\n\n"

        explanation += """
To use my capabilities:
- Ask me to do something in natural language
- I'll find the best service to handle your request
- Everything is connected through my unified core

Example tasks I can handle:
- "What's the price of BTC?"
- "Analyze sentiment for SOL"
- "Show me the order book for ETH perps"
- "Post a market update to Twitter"
"""
        return explanation


# ==================== Global Instance ====================

jarvis_self = JarvisSelf()


# ==================== Convenience Functions ====================

def what_can_i_do() -> Dict[str, List[str]]:
    """Get JARVIS capabilities."""
    return jarvis_self.what_can_i_do()


async def find_for_task(task: str) -> List[CapabilityMatch]:
    """Find capabilities for a task."""
    return await jarvis_self.find_for_task(task)


def explain() -> str:
    """Get self-explanation."""
    return jarvis_self.explain_self()


def generate_docs() -> str:
    """Generate documentation."""
    return jarvis_self.generate_docs()
