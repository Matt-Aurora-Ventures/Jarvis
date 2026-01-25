"""
Unit tests for VoiceLibrary.

Tests the voice storage and management system.
"""

import pytest
import tempfile
import sqlite3
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime


class TestVoiceLibrary:
    """Tests for VoiceLibrary class."""

    def test_library_initializes_with_db(self, tmp_path):
        """VoiceLibrary should initialize with a database connection."""
        from core.voice.voice_library import VoiceLibrary

        db_path = tmp_path / "test.db"
        library = VoiceLibrary(db_path=str(db_path))

        assert library is not None
        assert db_path.exists()

    def test_library_creates_tables(self, tmp_path):
        """VoiceLibrary should create voices table on init."""
        from core.voice.voice_library import VoiceLibrary

        db_path = tmp_path / "test.db"
        library = VoiceLibrary(db_path=str(db_path))

        # Verify table exists
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='voices'"
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == "voices"

    def test_add_voice(self, tmp_path):
        """add_voice should insert a new voice record."""
        from core.voice.voice_library import VoiceLibrary

        db_path = tmp_path / "test.db"
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()

        library = VoiceLibrary(db_path=str(db_path), voices_dir=voices_dir)

        # Create reference audio
        ref_audio = tmp_path / "ref.wav"
        ref_audio.write_bytes(b"RIFF" + b"\x00" * 100)

        voice_id = library.add_voice(
            user_id=123,
            name="My Voice",
            reference_audio_path=str(ref_audio),
            reference_text="Hello, this is a test."
        )

        assert voice_id is not None
        assert voice_id.startswith("voice_")

    def test_get_voice_by_id(self, tmp_path):
        """get_voice should return voice by ID."""
        from core.voice.voice_library import VoiceLibrary

        db_path = tmp_path / "test.db"
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()

        library = VoiceLibrary(db_path=str(db_path), voices_dir=voices_dir)

        ref_audio = tmp_path / "ref.wav"
        ref_audio.write_bytes(b"RIFF" + b"\x00" * 100)

        voice_id = library.add_voice(
            user_id=123,
            name="Test Voice",
            reference_audio_path=str(ref_audio),
            reference_text="Test text"
        )

        voice = library.get_voice(voice_id)

        assert voice is not None
        assert voice["id"] == voice_id
        assert voice["name"] == "Test Voice"
        assert voice["user_id"] == 123

    def test_get_voice_returns_none_for_nonexistent(self, tmp_path):
        """get_voice should return None for non-existent voice."""
        from core.voice.voice_library import VoiceLibrary

        db_path = tmp_path / "test.db"
        library = VoiceLibrary(db_path=str(db_path))

        voice = library.get_voice("nonexistent_id")
        assert voice is None

    def test_list_voices_by_user(self, tmp_path):
        """list_voices should filter by user_id."""
        from core.voice.voice_library import VoiceLibrary

        db_path = tmp_path / "test.db"
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()

        library = VoiceLibrary(db_path=str(db_path), voices_dir=voices_dir)

        ref_audio = tmp_path / "ref.wav"
        ref_audio.write_bytes(b"RIFF" + b"\x00" * 100)

        # Add voices for different users
        library.add_voice(user_id=1, name="Voice1", reference_audio_path=str(ref_audio), reference_text="Test")
        library.add_voice(user_id=1, name="Voice2", reference_audio_path=str(ref_audio), reference_text="Test")
        library.add_voice(user_id=2, name="Voice3", reference_audio_path=str(ref_audio), reference_text="Test")

        user1_voices = library.list_voices(user_id=1)
        user2_voices = library.list_voices(user_id=2)

        assert len(user1_voices) == 2
        assert len(user2_voices) == 1

    def test_delete_voice(self, tmp_path):
        """delete_voice should remove voice record and files."""
        from core.voice.voice_library import VoiceLibrary

        db_path = tmp_path / "test.db"
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()

        library = VoiceLibrary(db_path=str(db_path), voices_dir=voices_dir)

        ref_audio = tmp_path / "ref.wav"
        ref_audio.write_bytes(b"RIFF" + b"\x00" * 100)

        voice_id = library.add_voice(
            user_id=123,
            name="Delete Me",
            reference_audio_path=str(ref_audio),
            reference_text="Test"
        )

        success = library.delete_voice(voice_id, user_id=123)
        assert success is True

        voice = library.get_voice(voice_id)
        assert voice is None

    def test_delete_voice_fails_for_wrong_user(self, tmp_path):
        """delete_voice should fail if user doesn't own the voice."""
        from core.voice.voice_library import VoiceLibrary

        db_path = tmp_path / "test.db"
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()

        library = VoiceLibrary(db_path=str(db_path), voices_dir=voices_dir)

        ref_audio = tmp_path / "ref.wav"
        ref_audio.write_bytes(b"RIFF" + b"\x00" * 100)

        voice_id = library.add_voice(
            user_id=123,
            name="User 123's Voice",
            reference_audio_path=str(ref_audio),
            reference_text="Test"
        )

        # Try to delete with wrong user
        success = library.delete_voice(voice_id, user_id=456)
        assert success is False

        # Voice should still exist
        voice = library.get_voice(voice_id)
        assert voice is not None

    def test_update_voice_metadata(self, tmp_path):
        """update_voice should modify voice metadata."""
        from core.voice.voice_library import VoiceLibrary

        db_path = tmp_path / "test.db"
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()

        library = VoiceLibrary(db_path=str(db_path), voices_dir=voices_dir)

        ref_audio = tmp_path / "ref.wav"
        ref_audio.write_bytes(b"RIFF" + b"\x00" * 100)

        voice_id = library.add_voice(
            user_id=123,
            name="Original Name",
            reference_audio_path=str(ref_audio),
            reference_text="Test"
        )

        success = library.update_voice(
            voice_id,
            user_id=123,
            name="New Name",
            metadata={"custom_key": "custom_value"}
        )

        assert success is True

        voice = library.get_voice(voice_id)
        assert voice["name"] == "New Name"
        assert voice["metadata"]["custom_key"] == "custom_value"

    def test_voice_usage_count(self, tmp_path):
        """Voice usage should be tracked."""
        from core.voice.voice_library import VoiceLibrary

        db_path = tmp_path / "test.db"
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()

        library = VoiceLibrary(db_path=str(db_path), voices_dir=voices_dir)

        ref_audio = tmp_path / "ref.wav"
        ref_audio.write_bytes(b"RIFF" + b"\x00" * 100)

        voice_id = library.add_voice(
            user_id=123,
            name="Track Usage",
            reference_audio_path=str(ref_audio),
            reference_text="Test"
        )

        # Record usage
        library.record_usage(voice_id)
        library.record_usage(voice_id)
        library.record_usage(voice_id)

        voice = library.get_voice(voice_id)
        assert voice["usage_count"] == 3


class TestVoiceLibraryReferenceAudio:
    """Tests for reference audio handling."""

    def test_copy_reference_audio(self, tmp_path):
        """Reference audio should be copied to voices directory."""
        from core.voice.voice_library import VoiceLibrary

        db_path = tmp_path / "test.db"
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()

        library = VoiceLibrary(db_path=str(db_path), voices_dir=voices_dir)

        # Create reference audio in a different location
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        ref_audio = source_dir / "ref.wav"
        ref_audio.write_bytes(b"RIFF_TEST_AUDIO_DATA" + b"\x00" * 100)

        voice_id = library.add_voice(
            user_id=123,
            name="Copy Test",
            reference_audio_path=str(ref_audio),
            reference_text="Test"
        )

        # Check that audio was copied
        voice = library.get_voice(voice_id)
        stored_path = Path(voice["reference_audio_path"])

        assert stored_path.exists()
        assert voices_dir in stored_path.parents
        assert stored_path.read_bytes().startswith(b"RIFF_TEST_AUDIO_DATA")

    def test_validate_audio_duration(self, tmp_path):
        """Should validate audio duration requirements."""
        from core.voice.voice_library import VoiceLibrary, AudioDurationError

        db_path = tmp_path / "test.db"
        library = VoiceLibrary(db_path=str(db_path))

        # Mock audio that's too short
        with patch.object(library, "_get_audio_duration", return_value=2.0):
            with pytest.raises(AudioDurationError, match="too short"):
                library._validate_reference_audio(tmp_path / "short.wav")

        # Mock audio that's too long
        with patch.object(library, "_get_audio_duration", return_value=120.0):
            with pytest.raises(AudioDurationError, match="too long"):
                library._validate_reference_audio(tmp_path / "long.wav")

    def test_audio_duration_in_range(self, tmp_path):
        """Should accept audio within duration range."""
        from core.voice.voice_library import VoiceLibrary

        db_path = tmp_path / "test.db"
        library = VoiceLibrary(db_path=str(db_path))

        # Mock audio with good duration (15-60s recommended)
        with patch.object(library, "_get_audio_duration", return_value=30.0):
            # Should not raise
            result = library._validate_reference_audio(tmp_path / "good.wav")
            assert result is True


class TestVoiceLibrarySchema:
    """Tests for database schema compatibility."""

    def test_schema_has_required_columns(self, tmp_path):
        """Voices table should have all required columns."""
        from core.voice.voice_library import VoiceLibrary

        db_path = tmp_path / "test.db"
        library = VoiceLibrary(db_path=str(db_path))

        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("PRAGMA table_info(voices)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        required = {"id", "user_id", "name", "reference_audio_path", "created_at", "metadata"}
        assert required.issubset(columns)
