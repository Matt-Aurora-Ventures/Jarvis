"""
Tests for Bull/Bear Persona Generation

These tests verify:
1. Persona generation with consistent traits
2. Bull persona characteristics (optimistic, opportunity-focused)
3. Bear persona characteristics (cautious, risk-aware)
4. Persona prompt formatting
5. Context injection into persona prompts
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime


class TestPersonaDefinitions:
    """Test persona trait definitions."""

    def test_bull_persona_has_required_attributes(self):
        """Bull persona should have name, role, traits, bias."""
        from core.ai.personas import BullPersona

        persona = BullPersona()

        assert persona.name == "Bull Analyst"
        assert "optimistic" in persona.traits.lower() or "bullish" in persona.bias.lower()
        assert persona.role is not None
        assert len(persona.role) > 10  # Meaningful role description

    def test_bear_persona_has_required_attributes(self):
        """Bear persona should have name, role, traits, bias."""
        from core.ai.personas import BearPersona

        persona = BearPersona()

        assert persona.name == "Bear Analyst"
        assert "cautious" in persona.traits.lower() or "bearish" in persona.bias.lower()
        assert persona.role is not None
        assert len(persona.role) > 10

    def test_bull_and_bear_have_opposing_biases(self):
        """Bull and Bear should have clearly opposing viewpoints."""
        from core.ai.personas import BullPersona, BearPersona

        bull = BullPersona()
        bear = BearPersona()

        # They should not share the same bias
        assert bull.bias != bear.bias
        # Bull should be positive-leaning
        assert any(word in bull.bias.lower() for word in ["bull", "optimis", "opportun", "growth"])
        # Bear should be negative/cautious-leaning
        assert any(word in bear.bias.lower() for word in ["bear", "cautio", "risk", "protect"])


class TestPersonaPromptGeneration:
    """Test persona prompt generation."""

    def test_generate_bull_analysis_prompt(self):
        """Bull analysis prompt should include persona traits and market data."""
        from core.ai.personas import BullPersona

        persona = BullPersona()
        market_data = {
            "symbol": "BONK",
            "price": 0.00001234,
            "change_24h": 15.5,
            "volume_24h": 1500000,
            "sentiment_score": 72,
        }

        prompt = persona.generate_analysis_prompt(market_data)

        # Should include market data
        assert "BONK" in prompt
        assert "15.5" in prompt or "15.5%" in prompt
        # Should include persona context
        assert persona.name in prompt or "bull" in prompt.lower()

    def test_generate_bear_analysis_prompt(self):
        """Bear analysis prompt should include risk warnings."""
        from core.ai.personas import BearPersona

        persona = BearPersona()
        market_data = {
            "symbol": "BONK",
            "price": 0.00001234,
            "change_24h": 15.5,
            "volume_24h": 1500000,
            "sentiment_score": 72,
        }

        prompt = persona.generate_analysis_prompt(market_data)

        # Should include market data
        assert "BONK" in prompt
        # Should include risk-focused context
        assert "risk" in prompt.lower() or "caution" in prompt.lower() or persona.name in prompt

    def test_prompt_includes_signal_data(self):
        """Prompts should include strategy signals when provided."""
        from core.ai.personas import BullPersona

        persona = BullPersona()
        market_data = {"symbol": "WIF", "price": 2.50}
        signals = {
            "rsi": 35,  # Oversold
            "macd_signal": "bullish_crossover",
            "volume_surge": True,
        }

        prompt = persona.generate_analysis_prompt(market_data, signals=signals)

        # Should reference technical signals
        assert "35" in prompt or "rsi" in prompt.lower() or "oversold" in prompt.lower()


class TestPersonaFactory:
    """Test persona factory pattern."""

    def test_create_persona_by_type(self):
        """Factory should create correct persona type."""
        from core.ai.personas import PersonaFactory, BullPersona, BearPersona

        bull = PersonaFactory.create("bull")
        bear = PersonaFactory.create("bear")

        assert isinstance(bull, BullPersona)
        assert isinstance(bear, BearPersona)

    def test_create_persona_invalid_type_raises(self):
        """Factory should raise for unknown persona type."""
        from core.ai.personas import PersonaFactory

        with pytest.raises(ValueError):
            PersonaFactory.create("unknown")

    def test_get_all_personas(self):
        """Factory should return all available personas."""
        from core.ai.personas import PersonaFactory

        all_personas = PersonaFactory.get_all()

        assert len(all_personas) >= 2
        names = [p.name for p in all_personas]
        assert "Bull Analyst" in names
        assert "Bear Analyst" in names


class TestDynamicPersonaGeneration:
    """Test dynamic persona generation via AI."""

    @pytest.mark.asyncio
    async def test_generate_dynamic_persona_traits(self):
        """AI should generate unique persona traits for market context."""
        from core.ai.personas import PersonaGenerator

        # Mock the AI client
        mock_client = AsyncMock()
        mock_client.generate.return_value = {
            "content": "Focus on momentum plays, short-term catalysts, "
                      "news-driven price action. Risk tolerance: high.",
            "tokens_used": 50,
        }

        generator = PersonaGenerator(client=mock_client)

        # Generate dynamic bull for specific market regime
        persona = await generator.generate_dynamic(
            base_type="bull",
            market_context={"regime": "trending_up", "volatility": "high"}
        )

        assert persona is not None
        assert "momentum" in persona.traits.lower() or mock_client.generate.called

    @pytest.mark.asyncio
    async def test_fallback_to_static_on_error(self):
        """Should fall back to static persona if AI generation fails."""
        from core.ai.personas import PersonaGenerator, BullPersona

        # Mock client that fails
        mock_client = AsyncMock()
        mock_client.generate.side_effect = Exception("API Error")

        generator = PersonaGenerator(client=mock_client)

        persona = await generator.generate_dynamic(
            base_type="bull",
            market_context={}
        )

        # Should return default bull persona
        assert isinstance(persona, BullPersona)


class TestPersonaSerialization:
    """Test persona serialization for storage/replay."""

    def test_persona_to_dict(self):
        """Persona should serialize to dictionary."""
        from core.ai.personas import BullPersona

        persona = BullPersona()
        data = persona.to_dict()

        assert "name" in data
        assert "role" in data
        assert "traits" in data
        assert "bias" in data
        assert data["name"] == "Bull Analyst"

    def test_persona_from_dict(self):
        """Persona should deserialize from dictionary."""
        from core.ai.personas import Persona

        data = {
            "name": "Custom Analyst",
            "role": "Test role",
            "traits": "Test traits",
            "bias": "neutral",
        }

        persona = Persona.from_dict(data)

        assert persona.name == "Custom Analyst"
        assert persona.bias == "neutral"
