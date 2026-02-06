"""
Tests for bots/shared/personality.py - Personality loader for ClawdBots.

Tests cover:
- PersonalityConfig dataclass
- load_personality() function
- get_system_prompt() function
- get_personality_traits() function
- adjust_response_style() function
- Caching behavior
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import json
import os


class TestPersonalityConfig:
    """Tests for PersonalityConfig dataclass."""

    def test_personality_config_creation(self):
        """PersonalityConfig can be created with required fields."""
        from bots.shared.personality import PersonalityConfig

        config = PersonalityConfig(
            name="TestBot",
            role="Test assistant",
            tone="friendly",
            expertise_areas=["testing", "automation"],
            communication_style={"formality": "casual"},
            example_phrases=["Hello!", "How can I help?"],
            restrictions=["no profanity"],
        )

        assert config.name == "TestBot"
        assert config.role == "Test assistant"
        assert config.tone == "friendly"
        assert "testing" in config.expertise_areas
        assert config.communication_style["formality"] == "casual"
        assert len(config.example_phrases) == 2
        assert "no profanity" in config.restrictions

    def test_personality_config_defaults(self):
        """PersonalityConfig has sensible defaults for optional fields."""
        from bots.shared.personality import PersonalityConfig

        config = PersonalityConfig(
            name="MinimalBot",
            role="Basic assistant",
        )

        assert config.tone == ""
        assert config.expertise_areas == []
        assert config.communication_style == {}
        assert config.example_phrases == []
        assert config.restrictions == []
        assert config.soul_content is None
        assert config.identity_content is None
        assert config.bootstrap_content is None

    def test_personality_config_to_dict(self):
        """PersonalityConfig can be converted to dictionary."""
        from bots.shared.personality import PersonalityConfig

        config = PersonalityConfig(
            name="TestBot",
            role="Test role",
            tone="professional",
            expertise_areas=["coding"],
        )

        d = config.to_dict()

        assert isinstance(d, dict)
        assert d["name"] == "TestBot"
        assert d["role"] == "Test role"
        assert d["tone"] == "professional"
        assert d["expertise_areas"] == ["coding"]

    def test_personality_config_from_dict(self):
        """PersonalityConfig can be created from dictionary."""
        from bots.shared.personality import PersonalityConfig

        data = {
            "name": "FromDict",
            "role": "Dict assistant",
            "tone": "casual",
            "expertise_areas": ["python"],
            "communication_style": {"verbose": True},
            "example_phrases": ["Hey!"],
            "restrictions": ["stay on topic"],
        }

        config = PersonalityConfig.from_dict(data)

        assert config.name == "FromDict"
        assert config.role == "Dict assistant"
        assert config.expertise_areas == ["python"]


class TestLoadPersonality:
    """Tests for load_personality() function."""

    def test_load_personality_jarvis(self):
        """Can load ClawdJarvis personality."""
        from bots.shared.personality import load_personality

        config = load_personality("jarvis")

        assert config.name == "ClawdJarvis"
        assert "orchestrator" in config.role.lower() or "assistant" in config.role.lower()
        assert config.soul_content is not None
        assert "JARVIS" in config.soul_content

    def test_load_personality_matt(self):
        """Can load ClawdMatt personality."""
        from bots.shared.personality import load_personality

        config = load_personality("matt")

        assert config.name == "ClawdMatt"
        assert "pr" in config.role.lower() or "marketing" in config.role.lower()
        assert config.soul_content is not None

    def test_load_personality_friday(self):
        """Can load ClawdFriday personality."""
        from bots.shared.personality import load_personality

        config = load_personality("friday")

        assert config.name == "ClawdFriday"
        assert "email" in config.role.lower()
        assert config.soul_content is not None

    def test_load_personality_with_prefix(self):
        """Can load personality with 'clawd' prefix."""
        from bots.shared.personality import load_personality

        config = load_personality("clawdjarvis")

        assert config.name == "ClawdJarvis"

    def test_load_personality_case_insensitive(self):
        """Bot name is case insensitive."""
        from bots.shared.personality import load_personality

        config1 = load_personality("JARVIS")
        config2 = load_personality("jarvis")
        config3 = load_personality("Jarvis")

        assert config1.name == config2.name == config3.name

    def test_load_personality_unknown_bot(self):
        """Loading unknown bot raises appropriate error."""
        from bots.shared.personality import load_personality, PersonalityNotFoundError

        with pytest.raises(PersonalityNotFoundError):
            load_personality("unknownbot")

    def test_load_personality_caching(self):
        """Loaded personalities are cached."""
        from bots.shared.personality import load_personality, clear_personality_cache

        clear_personality_cache()

        config1 = load_personality("jarvis")
        config2 = load_personality("jarvis")

        # Should return same cached instance
        assert config1 is config2

    def test_clear_cache(self):
        """Cache can be cleared."""
        from bots.shared.personality import load_personality, clear_personality_cache

        config1 = load_personality("jarvis")
        clear_personality_cache()
        config2 = load_personality("jarvis")

        # After cache clear, should be different instances
        assert config1 is not config2


class TestGetSystemPrompt:
    """Tests for get_system_prompt() function."""

    def test_get_system_prompt_jarvis(self):
        """Get system prompt for Jarvis."""
        from bots.shared.personality import get_system_prompt

        prompt = get_system_prompt("jarvis")

        assert isinstance(prompt, str)
        assert len(prompt) > 100  # Should be substantial
        assert "JARVIS" in prompt or "Jarvis" in prompt

    def test_get_system_prompt_includes_role(self):
        """System prompt includes role information."""
        from bots.shared.personality import get_system_prompt

        prompt = get_system_prompt("jarvis")

        # Should mention the role somehow
        assert "orchestrator" in prompt.lower() or "assistant" in prompt.lower()

    def test_get_system_prompt_includes_tone(self):
        """System prompt includes tone guidance."""
        from bots.shared.personality import get_system_prompt

        prompt = get_system_prompt("jarvis")

        # Should have tone-related content
        assert "professional" in prompt.lower() or "witty" in prompt.lower() or "helpful" in prompt.lower()

    def test_get_system_prompt_includes_soul(self):
        """System prompt includes soul content."""
        from bots.shared.personality import get_system_prompt

        prompt = get_system_prompt("jarvis")

        # Should include key soul content
        assert "values" in prompt.lower() or "identity" in prompt.lower() or "core" in prompt.lower()

    def test_get_system_prompt_matt(self):
        """Get system prompt for Matt (PR filter)."""
        from bots.shared.personality import get_system_prompt

        prompt = get_system_prompt("matt")

        assert isinstance(prompt, str)
        assert "PR" in prompt or "marketing" in prompt.lower() or "communications" in prompt.lower()

    def test_get_system_prompt_friday(self):
        """Get system prompt for Friday (email assistant)."""
        from bots.shared.personality import get_system_prompt

        prompt = get_system_prompt("friday")

        assert isinstance(prompt, str)
        assert "email" in prompt.lower()


class TestGetPersonalityTraits:
    """Tests for get_personality_traits() function."""

    def test_get_personality_traits_returns_dict(self):
        """get_personality_traits returns a dictionary."""
        from bots.shared.personality import get_personality_traits

        traits = get_personality_traits("jarvis")

        assert isinstance(traits, dict)

    def test_get_personality_traits_has_expected_keys(self):
        """Traits dict has expected keys."""
        from bots.shared.personality import get_personality_traits

        traits = get_personality_traits("jarvis")

        expected_keys = ["name", "role", "tone", "expertise_areas", "communication_style"]
        for key in expected_keys:
            assert key in traits

    def test_get_personality_traits_jarvis(self):
        """Jarvis traits include expected values."""
        from bots.shared.personality import get_personality_traits

        traits = get_personality_traits("jarvis")

        assert traits["name"] == "ClawdJarvis"
        assert len(traits["expertise_areas"]) > 0

    def test_get_personality_traits_matt(self):
        """Matt traits include PR/marketing expertise."""
        from bots.shared.personality import get_personality_traits

        traits = get_personality_traits("matt")

        assert traits["name"] == "ClawdMatt"
        # Should have PR-related capabilities
        expertise = [e.lower() for e in traits["expertise_areas"]]
        assert any("pr" in e or "content" in e or "review" in e for e in expertise)

    def test_get_personality_traits_friday(self):
        """Friday traits include email expertise."""
        from bots.shared.personality import get_personality_traits

        traits = get_personality_traits("friday")

        assert traits["name"] == "ClawdFriday"
        # Should have email-related capabilities
        expertise = [e.lower() for e in traits["expertise_areas"]]
        assert any("email" in e for e in expertise)


class TestAdjustResponseStyle:
    """Tests for adjust_response_style() function."""

    def test_adjust_response_style_returns_string(self):
        """adjust_response_style returns a string."""
        from bots.shared.personality import adjust_response_style

        response = "Hello, how can I help you today?"
        adjusted = adjust_response_style(response, "jarvis")

        assert isinstance(adjusted, str)

    def test_adjust_response_style_preserves_meaning(self):
        """Adjusted response preserves core meaning."""
        from bots.shared.personality import adjust_response_style

        response = "The task is complete."
        adjusted = adjust_response_style(response, "jarvis")

        # Should preserve the core message
        assert "complete" in adjusted.lower() or "done" in adjusted.lower() or "finished" in adjusted.lower()

    def test_adjust_response_style_jarvis_professional(self):
        """Jarvis style is professional and helpful."""
        from bots.shared.personality import adjust_response_style

        response = "ok i did the thing"
        adjusted = adjust_response_style(response, "jarvis")

        # Jarvis wouldn't use "ok" casually
        # Adjusted should be more professional
        assert len(adjusted) >= len(response)

    def test_adjust_response_style_empty_response(self):
        """Handles empty response gracefully."""
        from bots.shared.personality import adjust_response_style

        adjusted = adjust_response_style("", "jarvis")

        assert adjusted == ""

    def test_adjust_response_style_unknown_bot_passthrough(self):
        """Unknown bot returns original response."""
        from bots.shared.personality import adjust_response_style

        response = "Hello world"
        adjusted = adjust_response_style(response, "unknownbot")

        # Should return original for unknown bot
        assert adjusted == response

    def test_adjust_response_style_no_modification_for_good_text(self):
        """Well-formed professional text may pass through."""
        from bots.shared.personality import adjust_response_style

        response = "I have completed the analysis of the trading data. The results indicate a positive trend."
        adjusted = adjust_response_style(response, "jarvis")

        # Good text should be preserved or minimally modified
        assert "analysis" in adjusted.lower()
        assert "trading" in adjusted.lower() or "result" in adjusted.lower()


class TestCachingBehavior:
    """Tests for caching behavior across functions."""

    def test_multiple_calls_use_cache(self):
        """Multiple calls to different functions use same cached personality."""
        from bots.shared.personality import (
            load_personality,
            get_system_prompt,
            get_personality_traits,
            clear_personality_cache,
        )

        clear_personality_cache()

        # First call loads
        config = load_personality("jarvis")

        # These should use cached personality
        prompt = get_system_prompt("jarvis")
        traits = get_personality_traits("jarvis")

        assert config.name in prompt
        assert traits["name"] == config.name

    def test_reload_refreshes_cache(self):
        """reload_personality refreshes the cache."""
        from bots.shared.personality import load_personality, reload_personality, clear_personality_cache

        clear_personality_cache()

        config1 = load_personality("jarvis")
        config2 = reload_personality("jarvis")

        # After reload, should be different instance
        assert config1 is not config2


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_handles_missing_soul_file(self):
        """Gracefully handles missing SOUL file."""
        from bots.shared.personality import load_personality

        # This test validates the loader handles missing optional files
        # The core personality.json must exist, but SOUL is optional
        try:
            config = load_personality("jarvis")
            # If soul file exists, content should be populated
            # If not, should be None but not raise
            assert config.name == "ClawdJarvis"
        except Exception:
            pytest.fail("Should handle missing soul file gracefully")

    def test_thread_safety_basic(self):
        """Basic thread safety - cache access doesn't crash."""
        import threading
        from bots.shared.personality import load_personality, clear_personality_cache

        clear_personality_cache()

        results = []
        errors = []

        def load_jarvis():
            try:
                config = load_personality("jarvis")
                results.append(config.name)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=load_jarvis) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 5
        assert all(name == "ClawdJarvis" for name in results)


class TestIntegration:
    """Integration tests with actual bot files."""

    def test_all_bots_loadable(self):
        """All ClawdBots can be loaded."""
        from bots.shared.personality import load_personality

        bots = ["jarvis", "matt", "friday"]

        for bot in bots:
            config = load_personality(bot)
            assert config.name.startswith("Clawd")
            assert config.role != ""

    def test_all_bots_have_system_prompts(self):
        """All ClawdBots have valid system prompts."""
        from bots.shared.personality import get_system_prompt

        bots = ["jarvis", "matt", "friday"]

        for bot in bots:
            prompt = get_system_prompt(bot)
            assert len(prompt) > 50
            assert isinstance(prompt, str)

    def test_all_bots_have_traits(self):
        """All ClawdBots have personality traits."""
        from bots.shared.personality import get_personality_traits

        bots = ["jarvis", "matt", "friday"]

        for bot in bots:
            traits = get_personality_traits(bot)
            assert "name" in traits
            assert "role" in traits
            assert len(traits["expertise_areas"]) > 0
