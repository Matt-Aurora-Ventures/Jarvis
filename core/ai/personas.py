"""
Bull/Bear Persona Definitions for Trading Debate

This module defines analyst personas used in the Bull/Bear debate architecture.
Each persona has distinct traits, biases, and analysis approaches that create
constructive tension leading to better-informed trading decisions.

Based on the TradingAgents framework (UCLA/MIT) used by institutional hedge funds.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class Persona(ABC):
    """Base class for analyst personas."""

    name: str = ""
    role: str = ""
    traits: str = ""
    bias: str = ""

    def __post_init__(self):
        """Initialize default values if not provided."""
        pass

    def generate_analysis_prompt(
        self,
        market_data: Dict[str, Any],
        signals: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate an analysis prompt incorporating persona traits and market data.

        Args:
            market_data: Token market data (price, volume, sentiment, etc.)
            signals: Optional technical signals (RSI, MACD, etc.)

        Returns:
            Formatted prompt string for the AI model
        """
        # Extract market data
        symbol = market_data.get("symbol", "UNKNOWN")
        price = market_data.get("price", 0)
        change_24h = market_data.get("change_24h", 0)
        volume_24h = market_data.get("volume_24h", 0)
        sentiment_score = market_data.get("sentiment_score", 50)

        prompt = f"""You are {self.name}, a trading analyst.

ROLE: {self.role}

TRAITS: {self.traits}

ANALYTICAL BIAS: {self.bias}

MARKET DATA FOR {symbol}:
- Current Price: ${price:.8f}
- 24h Change: {change_24h:+.1f}%
- 24h Volume: ${volume_24h:,.0f}
- Sentiment Score: {sentiment_score}/100
"""

        # Add technical signals if provided
        if signals:
            prompt += "\nTECHNICAL SIGNALS:\n"
            for key, value in signals.items():
                if key == "rsi":
                    signal_desc = "oversold" if value < 30 else "overbought" if value > 70 else "neutral"
                    prompt += f"- RSI: {value} ({signal_desc})\n"
                elif key == "macd_signal":
                    prompt += f"- MACD: {value}\n"
                elif key == "volume_surge":
                    prompt += f"- Volume Surge: {'Yes' if value else 'No'}\n"
                else:
                    prompt += f"- {key}: {value}\n"

        prompt += f"""
Analyze this token from your perspective as {self.name}.
Focus on factors that align with your {self.bias} analytical bias.

Provide your analysis in a structured format:
1. KEY OBSERVATIONS (2-3 points)
2. SUPPORTING EVIDENCE
3. RISK FACTORS
4. RECOMMENDATION (BUY/SELL/HOLD)
5. CONFIDENCE (0-100)
"""

        return prompt

    def to_dict(self) -> Dict[str, Any]:
        """Convert persona to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Persona":
        """Create a persona from dictionary."""
        return cls(
            name=data.get("name", ""),
            role=data.get("role", ""),
            traits=data.get("traits", ""),
            bias=data.get("bias", ""),
        )


@dataclass
class BullPersona(Persona):
    """
    Bull analyst persona - optimistic, opportunity-focused.

    Looks for growth potential, momentum plays, and positive catalysts.
    """

    name: str = "Bull Analyst"
    role: str = (
        "You are an optimistic trading analyst who specializes in identifying "
        "growth opportunities and momentum plays. You look for positive catalysts, "
        "strong fundamentals, and technical setups that suggest upside potential."
    )
    traits: str = (
        "Optimistic, growth-oriented, momentum-focused, opportunity-seeking, "
        "catalyst-driven, bullish on innovation and new trends."
    )
    bias: str = (
        "Bullish - You naturally focus on the positive aspects of investments "
        "and look for reasons why an asset could appreciate. You emphasize "
        "upside potential while acknowledging but not overweighting risks."
    )


@dataclass
class BearPersona(Persona):
    """
    Bear analyst persona - cautious, risk-aware.

    Focuses on identifying risks, overvaluation, and potential pitfalls.
    """

    name: str = "Bear Analyst"
    role: str = (
        "You are a cautious trading analyst who specializes in risk assessment "
        "and identifying potential pitfalls. You scrutinize valuations, question "
        "momentum sustainability, and look for signs of weakness."
    )
    traits: str = (
        "Cautious, risk-aware, detail-oriented, skeptical, protective of capital, "
        "focused on downside scenarios and risk management."
    )
    bias: str = (
        "Bearish - You naturally focus on the risks and potential downsides of "
        "investments. You question bullish narratives, look for overvaluation, "
        "and emphasize capital protection over aggressive returns."
    )


class PersonaFactory:
    """Factory for creating analyst personas."""

    _persona_types: Dict[str, type] = {
        "bull": BullPersona,
        "bear": BearPersona,
    }

    @classmethod
    def create(cls, persona_type: str) -> Persona:
        """
        Create a persona by type.

        Args:
            persona_type: Type of persona ("bull" or "bear")

        Returns:
            Persona instance

        Raises:
            ValueError: If persona type is unknown
        """
        persona_type = persona_type.lower()
        if persona_type not in cls._persona_types:
            raise ValueError(
                f"Unknown persona type: {persona_type}. "
                f"Valid types: {list(cls._persona_types.keys())}"
            )
        return cls._persona_types[persona_type]()

    @classmethod
    def get_all(cls) -> List[Persona]:
        """Get all available personas."""
        return [persona_class() for persona_class in cls._persona_types.values()]

    @classmethod
    def register(cls, name: str, persona_class: type):
        """Register a new persona type."""
        cls._persona_types[name.lower()] = persona_class


class PersonaGenerator:
    """
    Dynamic persona generator using AI.

    Can create customized personas based on market conditions and context.
    Falls back to static personas on error.
    """

    def __init__(self, client: Optional[Any] = None):
        """
        Initialize persona generator.

        Args:
            client: AI client with generate() method
        """
        self.client = client

    async def generate_dynamic(
        self,
        base_type: str,
        market_context: Optional[Dict[str, Any]] = None,
    ) -> Persona:
        """
        Generate a dynamic persona tailored to current market conditions.

        Args:
            base_type: Base persona type ("bull" or "bear")
            market_context: Current market conditions

        Returns:
            Customized Persona instance
        """
        # Get base persona
        try:
            base_persona = PersonaFactory.create(base_type)
        except ValueError:
            base_persona = BullPersona() if "bull" in base_type.lower() else BearPersona()

        # If no client or no context, return static persona
        if not self.client or not market_context:
            return base_persona

        try:
            # Generate dynamic traits based on market context
            regime = market_context.get("regime", "neutral")
            volatility = market_context.get("volatility", "normal")

            prompt = f"""Given the current market conditions:
- Market Regime: {regime}
- Volatility: {volatility}

Generate specific traits for a {base_type} analyst that are particularly relevant
for these conditions. Keep the response brief (2-3 sentences).
Focus on: risk tolerance, timeframe, key metrics to watch."""

            response = await self.client.generate(
                persona=None,
                context=prompt,
            )

            # Update traits with dynamic content
            dynamic_traits = response.get("content", "")
            if dynamic_traits:
                base_persona.traits = f"{base_persona.traits}\n\nMarket-Specific Focus: {dynamic_traits}"

            return base_persona

        except Exception as e:
            logger.warning(f"Dynamic persona generation failed: {e}, using static persona")
            return base_persona


__all__ = [
    "Persona",
    "BullPersona",
    "BearPersona",
    "PersonaFactory",
    "PersonaGenerator",
]
