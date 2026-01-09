"""
Tests for lifeos/jarvis (Main Orchestration Class).

Tests cover:
- Configuration system
- Jarvis lifecycle
- Chat interface
- Memory interface
- Event interface
- Persona interface
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lifeos.config import Config, ConfigSection, get_config
from lifeos.jarvis import Jarvis
from lifeos.memory import MemoryContext
from lifeos.persona import PersonaState


# =============================================================================
# Test Configuration
# =============================================================================

class TestConfigSection:
    """Test ConfigSection class."""

    def test_create_section(self):
        """Should create section with name."""
        section = ConfigSection(name="test")

        assert section.name == "test"
        assert section.data == {}

    def test_get_set_values(self):
        """Should get and set values."""
        section = ConfigSection(name="test")

        section.set("key", "value")
        assert section.get("key") == "value"

    def test_get_default(self):
        """Should return default for missing keys."""
        section = ConfigSection(name="test")

        assert section.get("missing", "default") == "default"

    def test_mask_sensitive(self):
        """Should mask sensitive values."""
        section = ConfigSection(
            name="test",
            data={"api_key": "secret123", "name": "test"},
            sensitive_keys={"api_key"},
        )

        result = section.to_dict(include_sensitive=False)

        assert result["api_key"] == "***MASKED***"
        assert result["name"] == "test"

    def test_include_sensitive(self):
        """Should include sensitive when requested."""
        section = ConfigSection(
            name="test",
            data={"api_key": "secret123"},
            sensitive_keys={"api_key"},
        )

        result = section.to_dict(include_sensitive=True)

        assert result["api_key"] == "secret123"


class TestConfig:
    """Test Config class."""

    def test_create_config(self):
        """Should create config with defaults."""
        config = Config()

        assert config.get("general.name") == "Jarvis"
        assert config.get("llm.provider") == "groq"

    def test_get_set(self):
        """Should get and set values."""
        config = Config()

        config.set("test.key", "value")
        assert config.get("test.key") == "value"

    def test_get_nested_default(self):
        """Should return default for missing keys."""
        config = Config()

        assert config.get("missing.key", "default") == "default"

    def test_get_section(self):
        """Should get entire section."""
        config = Config()

        section = config.get_section("general")

        assert section is not None
        assert "name" in section

    def test_has_key(self):
        """Should check key existence."""
        config = Config()

        assert config.has("general.name")
        assert not config.has("missing.key")

    def test_require_missing(self):
        """Should raise for missing required key."""
        config = Config()

        with pytest.raises(ValueError):
            config.require("missing.required")

    def test_require_present(self):
        """Should return value for present key."""
        config = Config()

        value = config.require("general.name")
        assert value == "Jarvis"

    def test_to_dict(self):
        """Should convert to dictionary."""
        config = Config()

        data = config.to_dict()

        assert "general" in data
        assert "llm" in data

    def test_env_parsing_bool(self):
        """Should parse boolean env values."""
        config = Config()

        assert config._parse_env_value("true") is True
        assert config._parse_env_value("false") is False
        assert config._parse_env_value("yes") is True
        assert config._parse_env_value("no") is False

    def test_env_parsing_number(self):
        """Should parse numeric env values."""
        config = Config()

        assert config._parse_env_value("42") == 42
        assert config._parse_env_value("3.14") == 3.14

    def test_env_parsing_json(self):
        """Should parse JSON env values."""
        config = Config()

        assert config._parse_env_value('{"key": "value"}') == {"key": "value"}
        assert config._parse_env_value('[1, 2, 3]') == [1, 2, 3]


# =============================================================================
# Test Jarvis Lifecycle
# =============================================================================

class TestJarvisLifecycle:
    """Test Jarvis lifecycle management."""

    @pytest.mark.asyncio
    async def test_start(self):
        """Should start Jarvis."""
        jarvis = Jarvis()

        await jarvis.start()

        assert jarvis.is_running
        assert jarvis.event_bus is not None
        assert jarvis.memory is not None
        assert jarvis.pae is not None
        assert jarvis.persona_manager is not None

        await jarvis.stop()

    @pytest.mark.asyncio
    async def test_stop(self):
        """Should stop Jarvis."""
        jarvis = Jarvis()
        await jarvis.start()

        await jarvis.stop()

        assert not jarvis.is_running

    @pytest.mark.asyncio
    async def test_double_start(self):
        """Should handle double start gracefully."""
        jarvis = Jarvis()

        await jarvis.start()
        await jarvis.start()  # Should not raise

        assert jarvis.is_running

        await jarvis.stop()

    @pytest.mark.asyncio
    async def test_stop_not_started(self):
        """Should handle stop when not started."""
        jarvis = Jarvis()

        await jarvis.stop()  # Should not raise

    @pytest.mark.asyncio
    async def test_shutdown_handler(self):
        """Should call shutdown handlers."""
        jarvis = Jarvis()
        called = [False]

        def handler():
            called[0] = True

        jarvis.on_shutdown(handler)
        await jarvis.start()
        await jarvis.stop()

        assert called[0]

    @pytest.mark.asyncio
    async def test_uptime(self):
        """Should track uptime."""
        jarvis = Jarvis()

        await jarvis.start()
        await asyncio.sleep(0.01)

        assert jarvis.uptime > 0

        await jarvis.stop()


# =============================================================================
# Test Jarvis Memory
# =============================================================================

class TestJarvisMemory:
    """Test Jarvis memory interface."""

    @pytest.mark.asyncio
    async def test_remember_recall(self):
        """Should store and retrieve values."""
        jarvis = Jarvis()
        await jarvis.start()

        await jarvis.remember("key", "value")
        result = await jarvis.recall("key")

        assert result == "value"

        await jarvis.stop()

    @pytest.mark.asyncio
    async def test_recall_default(self):
        """Should return default for missing key."""
        jarvis = Jarvis()
        await jarvis.start()

        result = await jarvis.recall("missing", default="default")

        assert result == "default"

        await jarvis.stop()

    @pytest.mark.asyncio
    async def test_forget(self):
        """Should delete values."""
        jarvis = Jarvis()
        await jarvis.start()

        await jarvis.remember("key", "value")
        deleted = await jarvis.forget("key")

        assert deleted is True
        assert await jarvis.recall("key") is None

        await jarvis.stop()


# =============================================================================
# Test Jarvis Events
# =============================================================================

class TestJarvisEvents:
    """Test Jarvis event interface."""

    @pytest.mark.asyncio
    async def test_emit_event(self):
        """Should emit events."""
        jarvis = Jarvis()
        await jarvis.start()

        event = await jarvis.emit("test.event", {"data": 1})

        assert event.topic == "test.event"
        assert event.data["data"] == 1

        await jarvis.stop()

    @pytest.mark.asyncio
    async def test_subscribe_receive(self):
        """Should receive subscribed events."""
        jarvis = Jarvis()
        await jarvis.start()

        received = []

        @jarvis.on("test.*")
        async def handler(event):
            received.append(event)

        await jarvis.emit("test.one")
        await jarvis.emit("test.two")

        assert len(received) == 2

        await jarvis.stop()


# =============================================================================
# Test Jarvis Persona
# =============================================================================

class TestJarvisPersona:
    """Test Jarvis persona interface."""

    @pytest.mark.asyncio
    async def test_set_persona(self):
        """Should switch personas."""
        jarvis = Jarvis()
        await jarvis.start()

        result = jarvis.set_persona("casual")

        assert result is True

        await jarvis.stop()

    @pytest.mark.asyncio
    async def test_set_state(self):
        """Should set persona state."""
        jarvis = Jarvis()
        await jarvis.start()

        jarvis.set_state(PersonaState.FOCUSED)

        assert jarvis.persona_manager.get_state() == PersonaState.FOCUSED

        await jarvis.stop()

    @pytest.mark.asyncio
    async def test_get_greeting(self):
        """Should get greeting."""
        jarvis = Jarvis()
        await jarvis.start()

        greeting = jarvis.get_greeting()

        assert greeting  # Not empty

        await jarvis.stop()


# =============================================================================
# Test Jarvis Stats
# =============================================================================

class TestJarvisStats:
    """Test Jarvis statistics."""

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Should return statistics."""
        jarvis = Jarvis()
        await jarvis.start()

        stats = jarvis.get_stats()

        assert stats["running"] is True
        assert "uptime_seconds" in stats
        assert "events" in stats
        assert "memory" in stats
        assert "pae" in stats

        await jarvis.stop()

    @pytest.mark.asyncio
    async def test_stats_not_running(self):
        """Should return stats when not running."""
        jarvis = Jarvis()

        stats = jarvis.get_stats()

        assert stats["running"] is False
        assert stats["uptime_seconds"] == 0


# =============================================================================
# Test Jarvis Chat (Mocked)
# =============================================================================

class TestJarvisChat:
    """Test Jarvis chat interface."""

    @pytest.mark.asyncio
    async def test_chat_no_llm(self):
        """Should handle missing LLM gracefully."""
        jarvis = Jarvis()
        await jarvis.start()

        # LLM may not be available without API key
        response = await jarvis.chat("Hello")

        # Should return something (either response or error message)
        assert response

        await jarvis.stop()

    @pytest.mark.asyncio
    async def test_chat_auto_starts(self):
        """Should auto-start if not started."""
        jarvis = Jarvis()

        response = await jarvis.chat("Hello")

        assert jarvis.is_running
        assert response

        await jarvis.stop()

    @pytest.mark.asyncio
    async def test_chat_emits_events(self):
        """Should emit chat events."""
        jarvis = Jarvis()
        await jarvis.start()

        events = []

        @jarvis.on("chat.*")
        async def handler(event):
            events.append(event)

        await jarvis.chat("Hello")

        assert any(e.topic == "chat.message" for e in events)

        await jarvis.stop()


# =============================================================================
# Test Configuration Integration
# =============================================================================

class TestConfigIntegration:
    """Test configuration with Jarvis."""

    @pytest.mark.asyncio
    async def test_custom_config(self):
        """Should use custom config."""
        config = Config()
        config.set("persona.default", "analyst")

        jarvis = Jarvis(config=config)
        await jarvis.start()

        # Should use analyst persona
        assert jarvis.persona_manager.get_active_name() == "analyst"

        await jarvis.stop()

    @pytest.mark.asyncio
    async def test_plugins_disabled(self):
        """Should respect plugins.enabled=False."""
        config = Config()
        config.set("plugins.enabled", False)

        jarvis = Jarvis(config=config)
        await jarvis.start()

        assert jarvis.plugin_manager is None

        await jarvis.stop()
