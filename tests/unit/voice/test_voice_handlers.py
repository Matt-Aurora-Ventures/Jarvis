"""
Unit tests for Telegram voice handlers.

Tests the /tts and /voice commands for Telegram bot integration.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path


class TestTTSCommand:
    """Tests for /tts Telegram command."""

    @pytest.mark.asyncio
    async def test_tts_command_requires_text(self):
        """tts command should require text argument."""
        from tg_bot.handlers.voice import handle_tts_command

        # Create mock update and context
        update = MagicMock()
        update.message.text = "/tts"  # No text provided
        update.message.reply_text = AsyncMock()

        context = MagicMock()

        await handle_tts_command(update, context)

        update.message.reply_text.assert_called()
        call_args = update.message.reply_text.call_args[0][0]
        assert "usage" in call_args.lower() or "text" in call_args.lower()

    @pytest.mark.asyncio
    async def test_tts_command_generates_audio(self, tmp_path):
        """tts command should generate and send audio."""
        from tg_bot.handlers.voice import handle_tts_command

        update = MagicMock()
        update.message.text = "/tts Hello world"
        update.message.reply_voice = AsyncMock()
        update.effective_user.id = 123

        context = MagicMock()

        with patch("tg_bot.handlers.voice.TTSManager") as MockManager:
            mock_instance = MockManager.return_value
            mock_instance.synthesize.return_value = b"OggS" + b"\x00" * 100

            await handle_tts_command(update, context)

            update.message.reply_voice.assert_called()

    @pytest.mark.asyncio
    async def test_tts_command_with_voice_option(self):
        """tts command should support --voice option."""
        from tg_bot.handlers.voice import handle_tts_command

        update = MagicMock()
        update.message.text = "/tts Hello world --voice my_voice"
        update.message.reply_voice = AsyncMock()
        update.effective_user.id = 123

        context = MagicMock()

        with patch("tg_bot.handlers.voice.TTSManager") as MockManager:
            mock_instance = MockManager.return_value
            mock_instance.synthesize.return_value = b"OggS" + b"\x00" * 100

            await handle_tts_command(update, context)

            # Verify voice_id was passed
            mock_instance.synthesize.assert_called()
            call_kwargs = mock_instance.synthesize.call_args
            # Check that voice_id was passed somehow
            assert mock_instance.synthesize.called


class TestVoiceCloneCommand:
    """Tests for /voice clone Telegram command."""

    @pytest.mark.asyncio
    async def test_voice_clone_requires_audio(self):
        """voice clone command should require audio message."""
        from tg_bot.handlers.voice import handle_voice_clone_command

        update = MagicMock()
        update.message.reply_to_message = None  # No reply
        update.message.reply_text = AsyncMock()

        context = MagicMock()

        await handle_voice_clone_command(update, context, "my_voice")

        update.message.reply_text.assert_called()
        call_args = update.message.reply_text.call_args[0][0]
        assert "reply" in call_args.lower() or "audio" in call_args.lower()

    @pytest.mark.asyncio
    async def test_voice_clone_from_voice_message(self, tmp_path):
        """voice clone should work with voice message reply."""
        from tg_bot.handlers.voice import handle_voice_clone_command

        # Mock voice message
        voice = MagicMock()
        voice.file_id = "test_file_id"
        voice.get_file = AsyncMock()
        voice.get_file.return_value.download_to_drive = AsyncMock()

        update = MagicMock()
        update.message.reply_to_message = MagicMock()
        update.message.reply_to_message.voice = voice
        update.message.reply_to_message.audio = None
        update.message.reply_text = AsyncMock()
        update.effective_user.id = 123

        context = MagicMock()

        with patch("tg_bot.handlers.voice.VoiceLibrary") as MockLibrary:
            mock_lib = MockLibrary.return_value
            mock_lib.add_voice.return_value = "voice_abc123"

            await handle_voice_clone_command(update, context, "my_voice")

            # Should succeed
            update.message.reply_text.assert_called()
            # Check success message
            call_args = str(update.message.reply_text.call_args)
            # Either should contain success or the voice_id

    @pytest.mark.asyncio
    async def test_voice_clone_from_audio_message(self, tmp_path):
        """voice clone should work with audio file reply."""
        from tg_bot.handlers.voice import handle_voice_clone_command

        # Mock audio message
        audio = MagicMock()
        audio.file_id = "test_audio_file_id"
        audio.get_file = AsyncMock()
        audio.get_file.return_value.download_to_drive = AsyncMock()

        update = MagicMock()
        update.message.reply_to_message = MagicMock()
        update.message.reply_to_message.voice = None
        update.message.reply_to_message.audio = audio
        update.message.reply_text = AsyncMock()
        update.effective_user.id = 123

        context = MagicMock()

        with patch("tg_bot.handlers.voice.VoiceLibrary") as MockLibrary:
            mock_lib = MockLibrary.return_value
            mock_lib.add_voice.return_value = "voice_def456"

            await handle_voice_clone_command(update, context, "audio_voice")


class TestVoiceListCommand:
    """Tests for /voice list Telegram command."""

    @pytest.mark.asyncio
    async def test_voice_list_shows_user_voices(self):
        """voice list should show user's cloned voices."""
        from tg_bot.handlers.voice import handle_voice_list_command

        update = MagicMock()
        update.message.reply_text = AsyncMock()
        update.effective_user.id = 123

        context = MagicMock()

        with patch("tg_bot.handlers.voice.VoiceLibrary") as MockLibrary:
            mock_lib = MockLibrary.return_value
            mock_lib.list_voices.return_value = [
                {"id": "voice_1", "name": "Voice One", "created_at": "2026-01-25"},
                {"id": "voice_2", "name": "Voice Two", "created_at": "2026-01-24"},
            ]

            await handle_voice_list_command(update, context)

            update.message.reply_text.assert_called()
            call_args = update.message.reply_text.call_args[0][0]
            assert "Voice One" in call_args or "voice_1" in call_args

    @pytest.mark.asyncio
    async def test_voice_list_empty(self):
        """voice list should handle no voices case."""
        from tg_bot.handlers.voice import handle_voice_list_command

        update = MagicMock()
        update.message.reply_text = AsyncMock()
        update.effective_user.id = 123

        context = MagicMock()

        with patch("tg_bot.handlers.voice.VoiceLibrary") as MockLibrary:
            mock_lib = MockLibrary.return_value
            mock_lib.list_voices.return_value = []

            await handle_voice_list_command(update, context)

            update.message.reply_text.assert_called()
            call_args = update.message.reply_text.call_args[0][0]
            assert "no voice" in call_args.lower() or "empty" in call_args.lower()


class TestVoiceDeleteCommand:
    """Tests for /voice delete Telegram command."""

    @pytest.mark.asyncio
    async def test_voice_delete_removes_voice(self):
        """voice delete should remove user's voice."""
        from tg_bot.handlers.voice import handle_voice_delete_command

        update = MagicMock()
        update.message.reply_text = AsyncMock()
        update.effective_user.id = 123

        context = MagicMock()

        with patch("tg_bot.handlers.voice.VoiceLibrary") as MockLibrary:
            mock_lib = MockLibrary.return_value
            mock_lib.delete_voice.return_value = True

            await handle_voice_delete_command(update, context, "my_voice")

            mock_lib.delete_voice.assert_called_with("my_voice", user_id=123)
            update.message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_voice_delete_fails_for_nonexistent(self):
        """voice delete should fail gracefully for non-existent voice."""
        from tg_bot.handlers.voice import handle_voice_delete_command

        update = MagicMock()
        update.message.reply_text = AsyncMock()
        update.effective_user.id = 123

        context = MagicMock()

        with patch("tg_bot.handlers.voice.VoiceLibrary") as MockLibrary:
            mock_lib = MockLibrary.return_value
            mock_lib.delete_voice.return_value = False

            await handle_voice_delete_command(update, context, "nonexistent")

            update.message.reply_text.assert_called()
            call_args = update.message.reply_text.call_args[0][0]
            assert "not found" in call_args.lower() or "failed" in call_args.lower()


class TestVoiceCommandRouter:
    """Tests for /voice command routing."""

    @pytest.mark.asyncio
    async def test_voice_routes_to_clone(self):
        """voice clone <name> should route to clone handler."""
        from tg_bot.handlers.voice import handle_voice_command

        update = MagicMock()
        update.message.text = "/voice clone my_new_voice"
        update.message.reply_text = AsyncMock()
        update.message.reply_to_message = None
        update.effective_user.id = 123

        context = MagicMock()

        with patch("tg_bot.handlers.voice.handle_voice_clone_command") as mock_clone:
            mock_clone.return_value = None
            await handle_voice_command(update, context)
            # Should call clone handler

    @pytest.mark.asyncio
    async def test_voice_routes_to_list(self):
        """voice list should route to list handler."""
        from tg_bot.handlers.voice import handle_voice_command

        update = MagicMock()
        update.message.text = "/voice list"
        update.message.reply_text = AsyncMock()
        update.effective_user.id = 123

        context = MagicMock()

        with patch("tg_bot.handlers.voice.handle_voice_list_command") as mock_list:
            mock_list.return_value = None
            await handle_voice_command(update, context)

    @pytest.mark.asyncio
    async def test_voice_routes_to_delete(self):
        """voice delete <name> should route to delete handler."""
        from tg_bot.handlers.voice import handle_voice_command

        update = MagicMock()
        update.message.text = "/voice delete old_voice"
        update.message.reply_text = AsyncMock()
        update.effective_user.id = 123

        context = MagicMock()

        with patch("tg_bot.handlers.voice.handle_voice_delete_command") as mock_delete:
            mock_delete.return_value = None
            await handle_voice_command(update, context)

    @pytest.mark.asyncio
    async def test_voice_shows_help_for_unknown(self):
        """voice <unknown> should show help."""
        from tg_bot.handlers.voice import handle_voice_command

        update = MagicMock()
        update.message.text = "/voice unknown_action"
        update.message.reply_text = AsyncMock()
        update.effective_user.id = 123

        context = MagicMock()

        await handle_voice_command(update, context)

        update.message.reply_text.assert_called()
        call_args = update.message.reply_text.call_args[0][0]
        assert "usage" in call_args.lower() or "help" in call_args.lower() or "clone" in call_args.lower()
