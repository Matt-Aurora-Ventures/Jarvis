"""
Unit tests for TTSManager.

Tests the Qwen3-TTS based voice synthesis and voice cloning capabilities.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
import json


class TestTTSManager:
    """Tests for TTSManager class."""

    def test_tts_manager_initializes(self):
        """TTSManager should initialize with default settings."""
        from core.voice.tts_manager import TTSManager

        manager = TTSManager()
        assert manager is not None
        assert manager.device in ("cpu", "cuda:0")
        assert manager.model is None  # Lazy loading

    def test_detect_device_cpu_fallback(self):
        """Should fall back to CPU when CUDA unavailable."""
        from core.voice.tts_manager import TTSManager

        with patch("core.voice.tts_manager.torch") as mock_torch:
            mock_torch.cuda.is_available.return_value = False
            manager = TTSManager()
            assert manager.device == "cpu"

    def test_detect_device_cuda_when_available(self):
        """Should use CUDA when available."""
        from core.voice.tts_manager import TTSManager

        with patch("core.voice.tts_manager.torch") as mock_torch:
            mock_torch.cuda.is_available.return_value = True
            manager = TTSManager(prefer_gpu=True)
            assert manager.device == "cuda:0"

    def test_synthesize_requires_text(self):
        """synthesize should raise ValueError for empty text."""
        from core.voice.tts_manager import TTSManager

        manager = TTSManager()
        with pytest.raises(ValueError, match="text cannot be empty"):
            manager.synthesize("")

    def test_synthesize_returns_bytes(self, tmp_path):
        """synthesize should return audio bytes."""
        from core.voice.tts_manager import TTSManager

        with patch("core.voice.tts_manager.qwen3_tts") as mock_qwen:
            # Mock successful synthesis
            wav_path = tmp_path / "test.wav"
            wav_path.write_bytes(b"RIFF" + b"\x00" * 100)  # Minimal WAV header
            mock_qwen.synthesize_from_config.return_value = wav_path

            manager = TTSManager()
            audio = manager.synthesize("Hello world")

            assert isinstance(audio, bytes)
            assert len(audio) > 0

    def test_synthesize_with_voice_id(self, tmp_path):
        """synthesize should use voice_id for cloned voice lookup."""
        from core.voice.tts_manager import TTSManager, VoiceNotFoundError

        manager = TTSManager()

        # Non-existent voice should raise error
        with pytest.raises(VoiceNotFoundError):
            manager.synthesize("Hello", voice_id="nonexistent_voice")

    def test_clone_voice_requires_audio_path(self):
        """clone_voice should raise error for missing audio file."""
        from core.voice.tts_manager import TTSManager

        manager = TTSManager()
        with pytest.raises(FileNotFoundError):
            manager.clone_voice("/nonexistent/audio.wav", name="test")

    def test_clone_voice_returns_voice_id(self, tmp_path):
        """clone_voice should return a voice_id string."""
        from core.voice.tts_manager import TTSManager

        # Create a mock audio file
        audio_file = tmp_path / "reference.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 100)

        manager = TTSManager()

        with patch.object(manager, "_validate_audio") as mock_validate:
            mock_validate.return_value = True
            with patch.object(manager, "_save_voice_clone") as mock_save:
                mock_save.return_value = "voice_abc123"
                voice_id = manager.clone_voice(str(audio_file), name="my_voice")

        assert isinstance(voice_id, str)
        assert len(voice_id) > 0

    def test_list_voices_returns_list(self):
        """list_voices should return a list of voice dictionaries."""
        from core.voice.tts_manager import TTSManager

        manager = TTSManager()
        voices = manager.list_voices()

        assert isinstance(voices, list)
        # Default voices should include builtin speakers
        assert any(v.get("builtin", False) for v in voices) or len(voices) == 0

    def test_delete_voice_removes_clone(self, tmp_path):
        """delete_voice should remove a cloned voice."""
        from core.voice.tts_manager import TTSManager

        manager = TTSManager()
        manager._voices_dir = tmp_path

        # Create a voice entry
        voice_dir = tmp_path / "voice_test123"
        voice_dir.mkdir()
        (voice_dir / "metadata.json").write_text('{"name": "test", "id": "voice_test123"}')
        (voice_dir / "reference.wav").write_bytes(b"RIFF" + b"\x00" * 100)

        success = manager.delete_voice("voice_test123")
        assert success is True
        assert not voice_dir.exists()

    def test_delete_voice_fails_for_builtin(self):
        """delete_voice should fail for builtin voices."""
        from core.voice.tts_manager import TTSManager

        manager = TTSManager()

        # Builtin voices like "Ryan" cannot be deleted
        success = manager.delete_voice("Ryan")
        assert success is False

    def test_get_voice_metadata(self, tmp_path):
        """get_voice should return voice metadata."""
        from core.voice.tts_manager import TTSManager

        manager = TTSManager()
        manager._voices_dir = tmp_path

        # Create a voice entry
        voice_dir = tmp_path / "voice_test456"
        voice_dir.mkdir()
        metadata = {
            "id": "voice_test456",
            "name": "Test Voice",
            "created_at": "2026-01-25T00:00:00Z",
            "reference_audio": "reference.wav",
        }
        (voice_dir / "metadata.json").write_text(json.dumps(metadata))
        (voice_dir / "reference.wav").write_bytes(b"RIFF" + b"\x00" * 100)

        voice = manager.get_voice("voice_test456")

        assert voice is not None
        assert voice["id"] == "voice_test456"
        assert voice["name"] == "Test Voice"


class TestTTSManagerAsync:
    """Tests for async TTSManager methods."""

    @pytest.mark.asyncio
    async def test_synthesize_async(self, tmp_path):
        """synthesize_async should work asynchronously."""
        from core.voice.tts_manager import TTSManager

        with patch("core.voice.tts_manager.qwen3_tts") as mock_qwen:
            wav_path = tmp_path / "test.wav"
            wav_path.write_bytes(b"RIFF" + b"\x00" * 100)
            mock_qwen.synthesize_from_config.return_value = wav_path

            manager = TTSManager()
            audio = await manager.synthesize_async("Hello world")

            assert isinstance(audio, bytes)

    @pytest.mark.asyncio
    async def test_clone_voice_async(self, tmp_path):
        """clone_voice_async should work asynchronously."""
        from core.voice.tts_manager import TTSManager

        audio_file = tmp_path / "reference.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 100)

        manager = TTSManager()

        with patch.object(manager, "_validate_audio", return_value=True):
            with patch.object(manager, "_save_voice_clone", return_value="voice_async123"):
                voice_id = await manager.clone_voice_async(str(audio_file), name="async_voice")

        assert isinstance(voice_id, str)


class TestAudioValidation:
    """Tests for audio validation functions."""

    def test_validate_audio_format_wav(self, tmp_path):
        """Should accept valid WAV files."""
        from core.voice.tts_manager import TTSManager

        # Create minimal WAV file
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"RIFF" + b"\x00" * 40 + b"WAVE" + b"\x00" * 100)

        manager = TTSManager()
        # Should not raise
        result = manager._validate_audio_format(str(wav_file))
        assert result is True

    def test_validate_audio_format_mp3(self, tmp_path):
        """Should accept MP3 files."""
        from core.voice.tts_manager import TTSManager

        # Create minimal MP3 file (ID3 header)
        mp3_file = tmp_path / "test.mp3"
        mp3_file.write_bytes(b"ID3" + b"\x00" * 100)

        manager = TTSManager()
        result = manager._validate_audio_format(str(mp3_file))
        assert result is True

    def test_validate_audio_format_rejects_invalid(self, tmp_path):
        """Should reject non-audio files."""
        from core.voice.tts_manager import TTSManager

        text_file = tmp_path / "test.txt"
        text_file.write_text("This is not audio")

        manager = TTSManager()
        result = manager._validate_audio_format(str(text_file))
        assert result is False


class TestVoiceCloneIntegration:
    """Integration tests for voice cloning with Qwen3-TTS."""

    def test_clone_mode_configuration(self):
        """Voice cloning should use correct Qwen3 mode."""
        from core.voice.tts_manager import TTSManager

        manager = TTSManager()
        config = manager._build_voice_config(
            voice_id="voice_test",
            ref_audio="/path/to/audio.wav",
            ref_text="Hello, this is a test."
        )

        assert config["qwen3_mode"] == "voice_clone"
        assert config["qwen3_ref_audio"] == "/path/to/audio.wav"
        assert config["qwen3_ref_text"] == "Hello, this is a test."

    def test_builtin_voice_configuration(self):
        """Builtin voices should use custom_voice mode."""
        from core.voice.tts_manager import TTSManager

        manager = TTSManager()
        config = manager._build_voice_config(speaker="Ryan")

        assert config["qwen3_mode"] == "custom_voice"
        assert config["qwen3_speaker"] == "Ryan"
