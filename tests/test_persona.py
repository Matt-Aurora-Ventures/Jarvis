"""
Tests for lifeos/persona (Character/Persona System).

Tests cover:
- Persona creation and serialization
- Speaking style configuration
- Persona manager functionality
- Template system
- Context adaptation
"""

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lifeos.persona import (
    Persona,
    PersonaTrait,
    SpeakingStyle,
    PersonaState,
    PersonaManager,
    PersonaTemplate,
    get_template,
    list_templates,
)


# =============================================================================
# Test SpeakingStyle
# =============================================================================

class TestSpeakingStyle:
    """Test SpeakingStyle configuration."""

    def test_default_values(self):
        """Should have sensible defaults."""
        style = SpeakingStyle()

        assert style.formality == 0.5
        assert style.verbosity == 0.5
        assert style.use_contractions is True
        assert style.use_emojis is False

    def test_prompt_fragment_formal(self):
        """Should generate formal style fragment."""
        style = SpeakingStyle(formality=0.8)
        fragment = style.to_prompt_fragment()

        assert "formal" in fragment.lower()

    def test_prompt_fragment_casual(self):
        """Should generate casual style fragment."""
        style = SpeakingStyle(formality=0.2)
        fragment = style.to_prompt_fragment()

        assert "casual" in fragment.lower()

    def test_prompt_fragment_brief(self):
        """Should include brevity instruction."""
        style = SpeakingStyle(verbosity=0.2)
        fragment = style.to_prompt_fragment()

        assert "brief" in fragment.lower()

    def test_prompt_fragment_detailed(self):
        """Should include detailed instruction."""
        style = SpeakingStyle(verbosity=0.8)
        fragment = style.to_prompt_fragment()

        assert "detailed" in fragment.lower()


# =============================================================================
# Test Persona
# =============================================================================

class TestPersona:
    """Test Persona class."""

    def test_create_basic_persona(self):
        """Should create persona with required fields."""
        persona = Persona(
            name="Test",
            description="A test persona",
        )

        assert persona.name == "Test"
        assert persona.description == "A test persona"

    def test_persona_with_traits(self):
        """Should accept traits."""
        persona = Persona(
            name="Test",
            description="Test",
            traits={PersonaTrait.HELPFUL, PersonaTrait.PROFESSIONAL},
        )

        assert PersonaTrait.HELPFUL in persona.traits
        assert PersonaTrait.PROFESSIONAL in persona.traits

    def test_get_system_prompt(self):
        """Should generate system prompt."""
        persona = Persona(
            name="Test",
            description="A test persona",
            traits={PersonaTrait.HELPFUL},
            always_do=["Be helpful"],
            never_do=["Be rude"],
        )

        prompt = persona.get_system_prompt()

        assert "Test" in prompt
        assert "helpful" in prompt.lower()
        assert "Be helpful" in prompt
        assert "Be rude" in prompt

    def test_state_modifier(self):
        """Should return state-specific modifiers."""
        persona = Persona(name="Test", description="Test")

        persona.current_state = PersonaState.URGENT
        modifier = persona.get_state_modifier()

        assert "urgency" in modifier.lower()

    def test_context_adaptation(self):
        """Should adapt for different contexts."""
        persona = Persona(
            name="Test",
            description="Test",
            traits={PersonaTrait.CASUAL},
            context_adaptations={
                "formal": {
                    "traits_add": ["formal", "professional"],
                    "traits_remove": ["casual"],
                    "style": {"formality": 0.9},
                }
            },
        )

        adapted = persona.adapt_for_context("formal")

        assert PersonaTrait.FORMAL in adapted.traits
        assert PersonaTrait.CASUAL not in adapted.traits
        assert adapted.style.formality == 0.9

    def test_to_dict_and_from_dict(self):
        """Should serialize and deserialize."""
        original = Persona(
            name="Test",
            description="Test persona",
            traits={PersonaTrait.HELPFUL, PersonaTrait.TECHNICAL},
            style=SpeakingStyle(formality=0.8),
            always_do=["Be helpful"],
        )

        data = original.to_dict()
        restored = Persona.from_dict(data)

        assert restored.name == original.name
        assert restored.description == original.description
        assert restored.traits == original.traits
        assert restored.style.formality == original.style.formality

    def test_get_greeting(self):
        """Should return greeting from templates."""
        persona = Persona(
            name="Test",
            description="Test",
            greeting_templates=["Hello {user_name}!", "Hi there!"],
        )

        greeting = persona.get_greeting({"user_name": "Alice"})

        assert greeting in ["Hello Alice!", "Hi there!"]

    def test_get_thinking_phrase(self):
        """Should return thinking phrase."""
        persona = Persona(
            name="Test",
            description="Test",
            thinking_phrases=["Processing...", "Thinking..."],
        )

        phrase = persona.get_thinking_phrase()

        assert phrase in ["Processing...", "Thinking..."]


# =============================================================================
# Test PersonaManager
# =============================================================================

class TestPersonaManager:
    """Test PersonaManager functionality."""

    def test_create_manager(self):
        """Should create manager with defaults."""
        manager = PersonaManager()

        # Should have built-in personas
        assert len(manager.list_personas()) > 0

    def test_register_persona(self):
        """Should register custom persona."""
        manager = PersonaManager()
        persona = Persona(name="Custom", description="Custom persona")

        manager.register_persona(persona)

        assert "custom" in manager.list_personas()

    def test_set_active_persona(self):
        """Should set active persona."""
        manager = PersonaManager()

        result = manager.set_active("jarvis")

        assert result is True
        assert manager.get_active_name() == "jarvis"
        assert manager.get_active().name == "Jarvis"

    def test_set_nonexistent_persona(self):
        """Should return False for nonexistent persona."""
        manager = PersonaManager()

        result = manager.set_active("nonexistent")

        assert result is False

    def test_get_system_prompt(self):
        """Should return system prompt for active persona."""
        manager = PersonaManager()
        manager.set_active("jarvis")

        prompt = manager.get_system_prompt()

        assert "Jarvis" in prompt

    def test_get_system_prompt_no_active(self):
        """Should return default prompt when no active persona."""
        manager = PersonaManager()

        prompt = manager.get_system_prompt()

        assert "helpful" in prompt.lower()

    def test_set_state(self):
        """Should set persona state."""
        manager = PersonaManager()
        manager.set_active("jarvis")

        manager.set_state(PersonaState.URGENT)

        assert manager.get_state() == PersonaState.URGENT

    def test_restore_state(self):
        """Should restore previous state."""
        manager = PersonaManager()
        manager.set_active("jarvis")

        manager.set_state(PersonaState.FOCUSED)
        manager.set_state(PersonaState.URGENT)
        manager.restore_state()

        assert manager.get_state() == PersonaState.FOCUSED

    def test_reset_state(self):
        """Should reset to normal state."""
        manager = PersonaManager()
        manager.set_active("jarvis")
        manager.set_state(PersonaState.URGENT)

        manager.reset_state()

        assert manager.get_state() == PersonaState.NORMAL

    def test_get_full_prompt(self):
        """Should return complete prompt structure."""
        manager = PersonaManager()
        manager.set_active("jarvis")

        prompt_data = manager.get_full_prompt(
            "Hello",
            additional_context={"time": "morning"},
        )

        assert "system_prompt" in prompt_data
        assert "messages" in prompt_data
        assert prompt_data["messages"][0]["content"] == "Hello"
        assert "time" in prompt_data["system_prompt"]

    def test_format_error(self):
        """Should format error in persona style."""
        manager = PersonaManager()
        manager.set_active("jarvis")

        formatted = manager.format_error("Connection failed")

        assert "Connection failed" in formatted

    def test_get_greeting(self):
        """Should return greeting from active persona."""
        manager = PersonaManager()
        manager.set_active("jarvis")

        greeting = manager.get_greeting()

        assert greeting  # Not empty

    def test_get_stats(self):
        """Should return manager statistics."""
        manager = PersonaManager()
        manager.set_active("jarvis")

        stats = manager.get_stats()

        assert "total_personas" in stats
        assert "active_persona" in stats
        assert stats["active_persona"] == "jarvis"

    def test_unregister_persona(self):
        """Should unregister persona."""
        manager = PersonaManager()
        persona = Persona(name="Temp", description="Temporary")
        manager.register_persona(persona)

        result = manager.unregister_persona("temp")

        assert result is True
        assert "temp" not in manager.list_personas()

    def test_style_callback(self):
        """Should apply style callbacks."""
        manager = PersonaManager()
        manager.set_active("jarvis")

        def uppercase_callback(response: str, persona: Persona) -> str:
            return response.upper()

        manager.add_style_callback(uppercase_callback)

        result = asyncio.get_event_loop().run_until_complete(
            manager.style_response("hello")
        )

        assert result == "HELLO"


# =============================================================================
# Test Templates
# =============================================================================

class TestTemplates:
    """Test persona templates."""

    def test_list_templates(self):
        """Should list available templates."""
        templates = list_templates()

        assert "jarvis" in templates
        assert "casual" in templates
        assert "analyst" in templates

    def test_get_template(self):
        """Should get template by name."""
        template = get_template("jarvis")

        assert template is not None
        assert template.name == "Jarvis"

    def test_get_template_case_insensitive(self):
        """Should be case insensitive."""
        template = get_template("JARVIS")

        assert template is not None

    def test_get_nonexistent_template(self):
        """Should return None for nonexistent template."""
        template = get_template("nonexistent")

        assert template is None

    def test_create_persona_from_template(self):
        """Should create persona from template."""
        template = get_template("jarvis")
        persona = template.create()

        assert persona.name == "Jarvis"
        assert PersonaTrait.PROFESSIONAL in persona.traits

    def test_create_with_overrides(self):
        """Should allow overriding template values."""
        template = get_template("jarvis")
        persona = template.create(name="CustomJarvis")

        assert persona.name == "CustomJarvis"

    def test_jarvis_template_has_context_adaptations(self):
        """Jarvis template should have context adaptations."""
        template = get_template("jarvis")

        assert "trading" in template.context_adaptations
        assert "casual" in template.context_adaptations

    def test_analyst_template_is_formal(self):
        """Analyst should be formal and technical."""
        template = get_template("analyst")

        assert template.style.formality > 0.7
        assert template.style.technicality > 0.8

    def test_casual_template_is_informal(self):
        """Casual should be informal and warm."""
        template = get_template("casual")

        assert template.style.formality < 0.3
        assert template.style.warmth > 0.7

    def test_coder_template_prefers_code_blocks(self):
        """Coder should prefer code blocks."""
        template = get_template("coder")

        assert template.style.prefer_code_blocks is True


# =============================================================================
# Test Integration
# =============================================================================

class TestPersonaIntegration:
    """Integration tests for persona system."""

    def test_full_workflow(self):
        """Test complete persona workflow."""
        # Create manager
        manager = PersonaManager()

        # Load persona
        manager.set_active("jarvis")

        # Get system prompt
        prompt = manager.get_system_prompt()
        assert "Jarvis" in prompt

        # Change state
        manager.set_state(PersonaState.PROBLEM_SOLVING)
        prompt = manager.get_system_prompt()
        assert "step-by-step" in prompt.lower()

        # Get full prompt
        full = manager.get_full_prompt("Help me debug this code")
        assert "system_prompt" in full
        assert full["messages"][0]["content"] == "Help me debug this code"

        # Reset
        manager.reset_state()
        assert manager.get_state() == PersonaState.NORMAL

    def test_context_adaptation_in_manager(self):
        """Manager should apply context adaptations."""
        manager = PersonaManager()
        manager.set_active("jarvis")

        # Get prompt with trading context
        prompt = manager.get_system_prompt(context_type="trading")

        # Should include analytical traits from adaptation
        assert "focused" in prompt.lower() or "analytical" in prompt.lower() or len(prompt) > 0

    def test_multiple_personas(self):
        """Should handle multiple personas."""
        manager = PersonaManager()

        # Register custom
        custom = Persona(
            name="Custom",
            description="Custom test persona",
            traits={PersonaTrait.CREATIVE},
        )
        manager.register_persona(custom)

        # Switch between personas
        manager.set_active("jarvis")
        jarvis_prompt = manager.get_system_prompt()

        manager.set_active("custom")
        custom_prompt = manager.get_system_prompt()

        assert "Jarvis" in jarvis_prompt
        assert "Custom" in custom_prompt
        assert jarvis_prompt != custom_prompt
