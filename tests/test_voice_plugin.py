"""
Tests for Voice plugin.

Tests cover:
- Plugin lifecycle
- PAE component registration
- Action functionality
- Provider functionality
- Evaluator functionality
- Persona voice mapping
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Import plugin components directly for testing
from plugins.voice.main import (
    VoicePlugin,
    VoiceConfig,
    SpeakAction,
    TranscribeAction,
    VoiceStatusProvider,
    PersonaVoiceProvider,
    VoiceHealthEvaluator,
    DEFAULT_VOICE_MAPPINGS,
)
from lifeos.pae.base import EvaluationResult


# =============================================================================
# Test Voice Config
# =============================================================================

class TestVoiceConfig:
    """Test voice configuration."""

    def test_default_config(self):
        """Should have sensible defaults."""
        config = VoiceConfig()

        assert config.voice_name == ""
        assert config.speech_rate == 180
        assert config.tts_engine == "piper"
        assert config.language == "en"

    def test_custom_config(self):
        """Should accept custom values."""
        config = VoiceConfig(
            voice_name="Morgan Freeman",
            speech_rate=150,
            tts_engine="say",
            language="en-US",
        )

        assert config.voice_name == "Morgan Freeman"
        assert config.speech_rate == 150


class TestDefaultMappings:
    """Test default persona-to-voice mappings."""

    def test_jarvis_mapping_exists(self):
        """Should have mapping for jarvis."""
        assert "jarvis" in DEFAULT_VOICE_MAPPINGS

        config = DEFAULT_VOICE_MAPPINGS["jarvis"]
        assert config.voice_name == "Reed"

    def test_casual_mapping_exists(self):
        """Should have mapping for casual."""
        assert "casual" in DEFAULT_VOICE_MAPPINGS

    def test_analyst_mapping_exists(self):
        """Should have mapping for analyst."""
        assert "analyst" in DEFAULT_VOICE_MAPPINGS


# =============================================================================
# Test Actions
# =============================================================================

class TestSpeakAction:
    """Test speak action."""

    @pytest.mark.asyncio
    async def test_requires_text(self):
        """Should require text parameter."""
        action = SpeakAction("test", {})

        with pytest.raises(ValueError):
            await action.execute({})

    @pytest.mark.asyncio
    async def test_returns_error_without_module(self):
        """Should return error when voice module not available."""
        action = SpeakAction("test", {})

        result = await action.execute({"text": "Hello"})

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_speaks_text(self):
        """Should speak text successfully."""
        action = SpeakAction("test", {})

        mock_voice = MagicMock()
        mock_voice.speak_text = MagicMock(return_value=True)
        action.set_voice_module(mock_voice)

        result = await action.execute({"text": "Hello world"})

        assert result["success"] is True
        mock_voice.speak_text.assert_called_once_with("Hello world")

    @pytest.mark.asyncio
    async def test_uses_persona_voice(self):
        """Should get voice config for persona."""
        action = SpeakAction("test", {})

        mock_voice = MagicMock()
        mock_voice.speak_text = MagicMock(return_value=True)
        action.set_voice_module(mock_voice)

        result = await action.execute({
            "text": "Hello",
            "persona": "jarvis",
        })

        assert result["success"] is True
        assert result["voice"] == "Reed"


class TestTranscribeAction:
    """Test transcribe action."""

    @pytest.mark.asyncio
    async def test_returns_error_without_module(self):
        """Should return error when voice module not available."""
        action = TranscribeAction("test", {})

        result = await action.execute({})

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_transcribes_audio(self):
        """Should transcribe audio."""
        action = TranscribeAction("test", {})

        mock_voice = MagicMock()
        mock_voice._transcribe_once = MagicMock(return_value="Hello Jarvis")
        action.set_voice_module(mock_voice)

        result = await action.execute({"timeout": 5, "phrase_limit": 5})

        assert result["success"] is True
        assert result["text"] == "Hello Jarvis"


# =============================================================================
# Test Providers
# =============================================================================

class TestVoiceStatusProvider:
    """Test voice status provider."""

    @pytest.mark.asyncio
    async def test_returns_unavailable_without_module(self):
        """Should return unavailable without module."""
        provider = VoiceStatusProvider("test", {})

        result = await provider.provide({})

        assert result["available"] is False

    @pytest.mark.asyncio
    async def test_provides_status(self):
        """Should provide voice status."""
        provider = VoiceStatusProvider("test", {})

        mock_voice = MagicMock()
        mock_voice.get_voice_runtime_status = MagicMock(return_value={
            "speaking": True,
            "last_spoken_at": 1234567890,
            "last_spoken_text": "Hello",
        })
        provider.set_voice_module(mock_voice)

        result = await provider.provide({})

        assert result["available"] is True
        assert result["speaking"] is True


class TestPersonaVoiceProvider:
    """Test persona voice provider."""

    @pytest.mark.asyncio
    async def test_provides_all_mappings(self):
        """Should provide all mappings when no persona specified."""
        provider = PersonaVoiceProvider("test", {})

        result = await provider.provide({})

        assert "mappings" in result
        assert "jarvis" in result["mappings"]
        assert "casual" in result["mappings"]

    @pytest.mark.asyncio
    async def test_provides_specific_persona(self):
        """Should provide mapping for specific persona."""
        provider = PersonaVoiceProvider("test", {})

        result = await provider.provide({"persona": "jarvis"})

        assert result["persona"] == "jarvis"
        assert result["voice_name"] == "Reed"
        assert result["speech_rate"] == 180


# =============================================================================
# Test Evaluators
# =============================================================================

class TestVoiceHealthEvaluator:
    """Test voice health evaluator."""

    @pytest.mark.asyncio
    async def test_returns_false_without_module(self):
        """Should return false without module."""
        evaluator = VoiceHealthEvaluator("test", {})

        result = await evaluator.evaluate({})

        assert result.decision is False

    @pytest.mark.asyncio
    async def test_evaluates_health(self):
        """Should evaluate voice health."""
        evaluator = VoiceHealthEvaluator("test", {})

        mock_voice = MagicMock()
        mock_voice.check_voice_health = MagicMock(return_value={
            "microphone": {"ok": True},
            "stt": {"any_working": True},
            "tts": {"any_working": True},
        })
        evaluator.set_voice_module(mock_voice)

        result = await evaluator.evaluate({})

        assert result.decision is True
        assert result.confidence == 1.0
        assert isinstance(result, EvaluationResult)

    @pytest.mark.asyncio
    async def test_reports_partial_health(self):
        """Should report partial health correctly."""
        evaluator = VoiceHealthEvaluator("test", {})

        mock_voice = MagicMock()
        mock_voice.check_voice_health = MagicMock(return_value={
            "microphone": {"ok": True},
            "stt": {"any_working": False},
            "tts": {"any_working": True},
        })
        evaluator.set_voice_module(mock_voice)

        result = await evaluator.evaluate({})

        assert result.decision is False
        assert result.confidence == 2.0 / 3.0
        assert "speech-to-text" in result.reasoning


# =============================================================================
# Test Plugin Integration
# =============================================================================

class TestVoicePluginIntegration:
    """Integration tests for Voice plugin."""

    @pytest.fixture
    def mock_context(self):
        """Create mock plugin context."""
        context = MagicMock()
        context.config = {}

        # Mock jarvis with PAE registry
        mock_jarvis = MagicMock()
        mock_jarvis.pae = MagicMock()
        mock_jarvis.pae.register_provider = MagicMock()
        mock_jarvis.pae.register_action = MagicMock()
        mock_jarvis.pae.register_evaluator = MagicMock()
        mock_jarvis.persona_manager = MagicMock()

        # Mock event bus
        mock_event_bus = MagicMock()
        mock_event_bus.emit = AsyncMock()
        mock_event_bus.on = MagicMock(return_value=lambda f: f)

        context.services = {
            "jarvis": mock_jarvis,
            "event_bus": mock_event_bus,
        }

        return context

    @pytest.fixture
    def mock_manifest(self):
        """Create mock plugin manifest."""
        manifest = MagicMock()
        manifest.name = "voice"
        manifest.version = "1.0.0"
        return manifest

    @pytest.mark.asyncio
    async def test_plugin_loads(self, mock_context, mock_manifest):
        """Should load without errors."""
        plugin = VoicePlugin(mock_context, mock_manifest)
        await plugin.on_load()

        # Should register components
        assert mock_context.services["jarvis"].pae.register_action.called
        assert mock_context.services["jarvis"].pae.register_provider.called
        assert mock_context.services["jarvis"].pae.register_evaluator.called

    @pytest.mark.asyncio
    async def test_plugin_enable_disable(self, mock_context, mock_manifest):
        """Should enable and disable cleanly."""
        plugin = VoicePlugin(mock_context, mock_manifest)

        await plugin.on_load()
        await plugin.on_enable()

        # Should emit enabled event
        event_bus = mock_context.services["event_bus"]
        assert event_bus.emit.called

        await plugin.on_disable()

    @pytest.mark.asyncio
    async def test_plugin_api_methods(self, mock_context, mock_manifest):
        """Should expose API methods."""
        plugin = VoicePlugin(mock_context, mock_manifest)

        # Create mock voice module
        mock_voice = MagicMock()
        mock_voice.speak_text = MagicMock(return_value=True)
        mock_voice._transcribe_once = MagicMock(return_value="Hello")
        mock_voice.get_voice_runtime_status = MagicMock(return_value={
            "speaking": False,
        })
        mock_voice.check_voice_health = MagicMock(return_value={
            "microphone": {"ok": True},
            "stt": {"any_working": True},
            "tts": {"any_working": True},
        })

        plugin._voice_module = mock_voice

        # Test speak
        result = plugin.speak("Hello", persona="jarvis")
        assert result is True

        # Test transcribe
        text = plugin.transcribe(timeout=5)
        assert text == "Hello"

        # Test get_status
        status = plugin.get_status()
        assert "speaking" in status

        # Test get_health
        health = plugin.get_health()
        assert health["microphone"]["ok"] is True

        # Test get_voice_for_persona
        voice = plugin.get_voice_for_persona("jarvis")
        assert voice.voice_name == "Reed"

        # Test is_available
        assert plugin.is_available() is True

    @pytest.mark.asyncio
    async def test_plugin_without_module(self, mock_context, mock_manifest):
        """Should handle missing voice module gracefully."""
        plugin = VoicePlugin(mock_context, mock_manifest)
        plugin._voice_module = None

        assert plugin.speak("hello") is False
        assert plugin.transcribe() == ""
        assert plugin.get_status() == {"available": False}
        assert plugin.is_available() is False

    @pytest.mark.asyncio
    async def test_plugin_unload(self, mock_context, mock_manifest):
        """Should clean up on unload."""
        plugin = VoicePlugin(mock_context, mock_manifest)

        mock_voice = MagicMock()
        plugin._voice_module = mock_voice

        await plugin.on_unload()

        assert plugin._voice_module is None
        assert len(plugin._actions) == 0

    @pytest.mark.asyncio
    async def test_voice_config_for_unknown_persona(self, mock_context, mock_manifest):
        """Should return default config for unknown persona."""
        plugin = VoicePlugin(mock_context, mock_manifest)

        voice = plugin.get_voice_for_persona("unknown_persona")

        assert voice is not None
        assert voice.voice_name == ""  # Default empty
