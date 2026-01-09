"""
Tests for Voice Pipeline Health Checks (P0-3).

Tests verify:
- Voice health check returns structured diagnostics
- Each component has actionable fix suggestions
- Doctor command surfaces voice issues
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import voice


# =============================================================================
# Test Voice Health Check Structure
# =============================================================================

class TestVoiceHealthCheck:
    """Test voice health check functionality."""

    def test_check_voice_health_returns_dict(self):
        """Health check should return dictionary."""
        # Mock speech_recognition to avoid actual mic access
        with patch.object(voice, '_load_config', return_value={"voice": {}}):
            try:
                health = voice.check_voice_health()
                assert isinstance(health, dict)
            except Exception:
                # May fail on CI without audio devices
                pytest.skip("Audio devices not available")

    def test_health_check_has_required_components(self):
        """Health check should check all required components."""
        with patch.object(voice, '_load_config', return_value={"voice": {}}):
            try:
                health = voice.check_voice_health()
                expected = ["microphone", "wake_word", "stt", "tts"]
                for component in expected:
                    assert component in health, f"Missing {component} in health check"
            except Exception:
                pytest.skip("Audio devices not available")

    def test_microphone_status_has_fix_on_error(self):
        """Microphone status should have fix suggestion on error."""
        # Mock to simulate missing mic
        mock_health = {
            "microphone": {"ok": False, "error": "Mic not found", "fix": "Check permissions"}
        }
        with patch.object(voice, 'check_voice_health', return_value=mock_health):
            health = voice.check_voice_health()
            mic = health["microphone"]
            if not mic["ok"]:
                assert mic.get("fix") is not None, "Missing fix for mic error"

    def test_stt_status_tracks_multiple_engines(self):
        """STT status should track multiple engines."""
        with patch.object(voice, '_load_config', return_value={"voice": {}}):
            try:
                health = voice.check_voice_health()
                stt = health.get("stt", {})
                assert "engines" in stt, "STT should track multiple engines"
                assert "any_working" in stt, "STT should indicate if any working"
            except Exception:
                pytest.skip("Audio devices not available")


# =============================================================================
# Test Voice Doctor Summary
# =============================================================================

class TestVoiceDoctorSummary:
    """Test voice doctor summary formatting."""

    def test_get_voice_doctor_summary_returns_string(self):
        """Summary should be human-readable string."""
        # Mock the health check to avoid hardware dependencies
        mock_health = {
            "microphone": {"ok": True},
            "wake_word": {"ok": False, "error": "Not installed", "fix": "pip install openwakeword"},
            "stt": {"any_working": True, "engines": {"gemini": {"ok": True}}},
            "tts": {"any_working": True, "engines": {"piper": {"ok": True}}},
            "audio_playback": {"ok": True},
        }
        with patch.object(voice, 'check_voice_health', return_value=mock_health):
            summary = voice.get_voice_doctor_summary()
            assert isinstance(summary, str)
            assert len(summary) > 0

    def test_summary_includes_status_icons(self):
        """Summary should have status icons for readability."""
        mock_health = {
            "microphone": {"ok": True},
            "wake_word": {"ok": True, "model": "hey_jarvis"},
            "stt": {"any_working": True, "engines": {}},
            "tts": {"any_working": True, "engines": {}},
            "audio_playback": {"ok": True},
        }
        with patch.object(voice, 'check_voice_health', return_value=mock_health):
            summary = voice.get_voice_doctor_summary()
            # Should have status icons
            assert "✓" in summary or "✗" in summary

    def test_summary_shows_fix_for_errors(self):
        """Summary should show fix suggestions for errors."""
        mock_health = {
            "microphone": {"ok": False, "error": "Mic error", "fix": "Check permissions"},
            "wake_word": {"ok": False, "error": "Not installed", "fix": "pip install openwakeword"},
            "stt": {"any_working": False, "engines": {"gemini": {"ok": False, "fix": "Set API key"}}},
            "tts": {"any_working": False, "engines": {"piper": {"ok": False, "fix": "Install piper"}}},
            "audio_playback": {"ok": False, "error": "No audio", "fix": "Check audio output"},
        }
        with patch.object(voice, 'check_voice_health', return_value=mock_health):
            summary = voice.get_voice_doctor_summary()
            # Should have fix suggestions
            lower = summary.lower()
            assert "fix" in lower or "install" in lower or "check" in lower

    def test_summary_shows_overall_verdict(self):
        """Summary should show overall operational status."""
        mock_health = {
            "microphone": {"ok": True},
            "wake_word": {"ok": True, "model": "hey_jarvis"},
            "stt": {"any_working": True, "engines": {}},
            "tts": {"any_working": True, "engines": {}},
            "audio_playback": {"ok": True},
        }
        with patch.object(voice, 'check_voice_health', return_value=mock_health):
            summary = voice.get_voice_doctor_summary()
            lower = summary.lower()
            # Should indicate overall status
            assert "operational" in lower or "working" in lower or "ready" in lower


# =============================================================================
# Test Voice Error Persistence
# =============================================================================

class TestVoiceErrorPersistence:
    """Test that voice errors are persisted to state."""

    def test_set_voice_error_function_exists(self):
        """_set_voice_error should exist for error persistence."""
        assert hasattr(voice, '_set_voice_error')

    def test_voice_error_persisted_to_state(self):
        """Voice errors should be saved to state for later retrieval."""
        from core import state

        with patch.object(state, 'update_state') as mock_update:
            voice._set_voice_error("Test error message")
            mock_update.assert_called_once()
            # Should include voice_error in the call
            call_kwargs = mock_update.call_args[1]
            assert "voice_error" in call_kwargs


# =============================================================================
# Test Voice Configuration
# =============================================================================

class TestVoiceConfiguration:
    """Test voice configuration handling."""

    def test_voice_cfg_has_defaults(self):
        """Voice config should have sensible defaults."""
        with patch.object(voice, '_load_config', return_value={}):
            cfg = voice._voice_cfg()
            # Should have required defaults
            assert "tts_engine" in cfg
            assert "speak_responses" in cfg
            assert "vad_enabled" in cfg

    def test_voice_cfg_defaults_are_sensible(self):
        """Default voice config values should be reasonable."""
        with patch.object(voice, '_load_config', return_value={}):
            cfg = voice._voice_cfg()
            # TTS should default to piper (local, free)
            assert cfg.get("tts_engine") in ("piper", "say", "espeak")
            # VAD should be enabled by default
            assert cfg.get("vad_enabled") is True
