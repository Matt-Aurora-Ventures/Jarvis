"""
Telegram Voice Handler - Voice Message Support for JARVIS.

Provides voice-based conversational trading interface:
- Voice message transcription (STT)
- Command parsing and execution
- Voice response synthesis (TTS)
- Voice cloning and customization

Commands:
- Send voice message: Transcribed and processed as trading command
- /tts <text>: Convert text to speech
- /voice clone <name>: Clone a voice from audio
- /voice list: List available voices
- /voice delete <name>: Delete a cloned voice
- /voicesettings: Configure voice preferences
- /voicehelp: Voice command help
"""

import logging
import os
import tempfile
import asyncio
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# Rate limiter for voice processing
class VoiceRateLimiter:
    """Rate limit voice processing per user."""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[int, List[float]] = defaultdict(list)

    def check(self, user_id: int) -> bool:
        """Check if user is within rate limit."""
        now = time.time()
        window_start = now - self.window_seconds

        # Clean old requests
        self._requests[user_id] = [
            t for t in self._requests[user_id] if t > window_start
        ]

        # Check limit
        if len(self._requests[user_id]) >= self.max_requests:
            return False

        # Record this request
        self._requests[user_id].append(now)
        return True


class VoiceTranscriber:
    """Transcribe voice messages to text using Whisper."""

    def __init__(self, model_name: str = "base"):
        """Initialize the transcriber."""
        self.model_name = model_name
        self._model = None

    def transcribe(self, audio_path: str) -> str:
        """
        Transcribe audio file to text.

        Args:
            audio_path: Path to audio file (OGG, WAV, etc.)

        Returns:
            Transcribed text
        """
        if not audio_path or not os.path.exists(audio_path):
            return ""

        return self._run_whisper(audio_path)

    def _run_whisper(self, audio_path: str) -> str:
        """Run Whisper transcription."""
        try:
            import whisper

            if self._model is None:
                self._model = whisper.load_model(self.model_name)

            result = self._model.transcribe(audio_path)
            return result.get("text", "").strip()

        except ImportError:
            logger.warning("Whisper not installed, trying OpenAI API")
            return self._run_openai_whisper(audio_path)
        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            return ""

    def _run_openai_whisper(self, audio_path: str) -> str:
        """Use OpenAI Whisper API as fallback."""
        try:
            import openai

            client = openai.OpenAI()

            with open(audio_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file
                )
            return transcript.text.strip()

        except Exception as e:
            logger.error(f"OpenAI Whisper API failed: {e}")
            return ""


class VoiceTTS:
    """Text-to-speech synthesis."""

    def __init__(self, preset: str = "jarvis"):
        """Initialize TTS engine."""
        self.preset = preset

    def synthesize_to_bytes(self, text: str, voice_id: Optional[str] = None) -> bytes:
        """
        Synthesize text to audio bytes.

        Args:
            text: Text to synthesize
            voice_id: Optional custom voice ID

        Returns:
            Audio bytes (OGG format for Telegram)
        """
        try:
            from core.voice_tts import VoiceTTS as EdgeTTS

            tts = EdgeTTS(preset=self.preset)

            # Use edge-tts to generate audio
            import asyncio
            loop = asyncio.get_event_loop()

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                temp_path = f.name

            try:
                # Generate audio synchronously
                asyncio.run(self._generate_audio(tts, text, temp_path))

                # Read and return bytes
                with open(temp_path, "rb") as f:
                    return f.read()
            finally:
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            raise

    async def _generate_audio(self, tts, text: str, output_path: str) -> None:
        """Generate audio file."""
        try:
            import edge_tts

            # Get voice config
            config = tts._config
            communicate = edge_tts.Communicate(
                text,
                config.voice,
                rate=config.rate,
                pitch=config.pitch,
            )
            await communicate.save(output_path)
        except Exception as e:
            logger.error(f"Audio generation failed: {e}")
            raise


class VoiceLibrary:
    """Manage cloned voices."""

    def __init__(self, storage_dir: Optional[Path] = None):
        """Initialize voice library."""
        self.storage_dir = storage_dir or Path.home() / ".jarvis" / "voices"
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def add_voice(
        self,
        audio_path: str,
        name: str,
        user_id: int
    ) -> str:
        """Add a cloned voice."""
        import uuid
        import shutil
        import json

        voice_id = f"voice_{uuid.uuid4().hex[:8]}"
        voice_dir = self.storage_dir / voice_id
        voice_dir.mkdir(exist_ok=True)

        # Copy audio
        shutil.copy(audio_path, voice_dir / "reference.wav")

        # Save metadata
        metadata = {
            "id": voice_id,
            "name": name,
            "user_id": user_id,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        (voice_dir / "metadata.json").write_text(json.dumps(metadata))

        return voice_id

    def list_voices(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """List available voices."""
        import json

        voices = []
        for voice_dir in self.storage_dir.iterdir():
            if voice_dir.is_dir():
                metadata_path = voice_dir / "metadata.json"
                if metadata_path.exists():
                    metadata = json.loads(metadata_path.read_text())
                    if user_id is None or metadata.get("user_id") == user_id:
                        voices.append(metadata)
        return voices

    def delete_voice(self, name: str, user_id: int) -> bool:
        """Delete a voice."""
        import json
        import shutil

        for voice_dir in self.storage_dir.iterdir():
            if voice_dir.is_dir():
                metadata_path = voice_dir / "metadata.json"
                if metadata_path.exists():
                    metadata = json.loads(metadata_path.read_text())
                    if metadata.get("name") == name and metadata.get("user_id") == user_id:
                        shutil.rmtree(voice_dir)
                        return True
        return False


class VoiceConversationManager:
    """Manage multi-turn voice conversations."""

    def __init__(self, timeout_seconds: int = 300):
        """Initialize conversation manager."""
        self.timeout_seconds = timeout_seconds
        self._contexts: Dict[int, Dict[str, Any]] = {}
        self._timestamps: Dict[int, float] = {}

    async def process_turn(
        self,
        user_id: int,
        text: str
    ) -> Dict[str, Any]:
        """Process a conversation turn."""
        # Check for expired context
        if user_id in self._timestamps:
            if time.time() - self._timestamps[user_id] > self.timeout_seconds:
                self.expire_context(user_id)

        # Get or create context
        context = self._contexts.get(user_id, {})

        # Parse command
        from core.voice import VoiceCommandParser, VoiceTradingCommands

        parser = VoiceCommandParser()
        intent = parser.parse(text)

        # Add context if available
        if "context_token" in context:
            if "params" not in intent:
                intent["params"] = {}
            if "token" not in intent.get("params", {}) and intent.get("intent") in [
                "position_query", "price_query", "trade_command"
            ]:
                # Inherit token from context
                intent["params"]["token"] = context["context_token"]

        # Execute command
        handler = VoiceTradingCommands()
        result = await handler.execute(intent)

        # Update context
        if result.get("success") and intent.get("params", {}).get("token"):
            context["context_token"] = intent["params"]["token"]
            self._contexts[user_id] = context
            self._timestamps[user_id] = time.time()

        return result

    def expire_context(self, user_id: int) -> None:
        """Expire a user's conversation context."""
        self._contexts.pop(user_id, None)
        self._timestamps.pop(user_id, None)


# User voice preferences storage
_user_preferences: Dict[int, Dict[str, Any]] = {}


def set_user_voice_preference(user_id: int, **kwargs) -> None:
    """Set user voice preferences."""
    if user_id not in _user_preferences:
        _user_preferences[user_id] = {}
    _user_preferences[user_id].update(kwargs)


def get_user_voice_preference(user_id: int) -> Dict[str, Any]:
    """Get user voice preferences."""
    return _user_preferences.get(user_id, {"enabled": False})


# Audio utilities
def validate_voice_file(path: str) -> bool:
    """Validate that file is a valid voice file."""
    if not os.path.exists(path):
        return False

    with open(path, "rb") as f:
        header = f.read(4)

    # Check for OGG or WAV magic bytes
    if header[:4] == b"OggS":  # OGG
        return True
    if header[:4] == b"RIFF":  # WAV
        return True
    if header[:3] == b"ID3":  # MP3
        return True

    return False


def convert_audio_to_wav(input_path: str) -> str:
    """Convert audio file to WAV format."""
    import subprocess

    output_path = input_path.rsplit(".", 1)[0] + ".wav"

    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", input_path, "-ar", "16000", "-ac", "1", output_path
        ], check=True, capture_output=True)
        return output_path
    except Exception as e:
        logger.error(f"Audio conversion failed: {e}")
        return input_path


def check_audio_duration(duration_seconds: float) -> Dict[str, Any]:
    """Check if audio duration is within limits."""
    MAX_DURATION = 60  # 60 seconds max

    if duration_seconds > MAX_DURATION:
        return {
            "valid": False,
            "error": f"Audio is too long. Maximum duration is {MAX_DURATION} seconds."
        }
    return {"valid": True}


async def synthesize_response(text: str, voice_id: Optional[str] = None) -> bytes:
    """Synthesize response text to voice audio."""
    tts = VoiceTTS()
    return tts.synthesize_to_bytes(text, voice_id)


# Telegram Handlers
async def handle_voice_message(update, context) -> None:
    """Handle incoming voice messages."""
    voice = update.message.voice
    user_id = update.effective_user.id

    # Rate limiting
    limiter = VoiceRateLimiter()
    if not limiter.check(user_id):
        await update.message.reply_text(
            "You're sending voice messages too quickly. Please wait a moment."
        )
        return

    # Check duration
    duration_check = check_audio_duration(voice.duration)
    if not duration_check["valid"]:
        await update.message.reply_text(duration_check["error"])
        return

    try:
        # Download voice file
        voice_file = await voice.get_file()

        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
            temp_path = f.name
            await voice_file.download_to_drive(temp_path)

        try:
            # Transcribe
            transcriber = VoiceTranscriber()
            text = transcriber.transcribe(temp_path)

            if not text:
                await update.message.reply_text(
                    "Sorry, I couldn't understand that. Please try again or type your command."
                )
                return

            # Process command
            conversation_manager = VoiceConversationManager()
            result = await conversation_manager.process_turn(user_id, text)

            response_text = result.get("response", "I processed your request.")

            # Check if user wants voice responses
            prefs = get_user_voice_preference(user_id)
            if prefs.get("enabled"):
                try:
                    audio_bytes = await synthesize_response(response_text)
                    await update.message.reply_voice(audio_bytes)
                except Exception as e:
                    logger.error(f"Voice response failed, falling back to text: {e}")
                    await update.message.reply_text(response_text)
            else:
                await update.message.reply_text(response_text)

        finally:
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    except Exception as e:
        logger.error(f"Voice message handling error: {e}")
        await update.message.reply_text(
            "Sorry, there was an error processing your voice message. Please try again."
        )


async def handle_tts_command(update, context) -> None:
    """Handle /tts command - convert text to speech."""
    text = update.message.text.replace("/tts", "").strip()

    if not text:
        await update.message.reply_text(
            "Usage: /tts <text>\n"
            "Example: /tts Hello, I am JARVIS."
        )
        return

    try:
        tts = VoiceTTS()
        audio_bytes = tts.synthesize_to_bytes(text)

        await update.message.reply_voice(audio_bytes)

    except Exception as e:
        logger.error(f"TTS command error: {e}")
        await update.message.reply_text(
            f"Sorry, I couldn't generate the audio. Error: {str(e)}"
        )


async def handle_voice_command(update, context) -> None:
    """Handle /voice command router."""
    text = update.message.text.replace("/voice", "").strip()
    parts = text.split(maxsplit=1)

    if not parts:
        await update.message.reply_text(
            "Voice commands:\n"
            "  /voice clone <name> - Clone a voice (reply to audio)\n"
            "  /voice list - List your voices\n"
            "  /voice delete <name> - Delete a voice\n"
        )
        return

    subcommand = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if subcommand == "clone":
        await handle_voice_clone_command(update, context, args)
    elif subcommand == "list":
        await handle_voice_list_command(update, context)
    elif subcommand == "delete":
        await handle_voice_delete_command(update, context, args)
    else:
        await update.message.reply_text(
            f"Unknown voice subcommand: {subcommand}\n"
            "Use /voice for help."
        )


async def handle_voice_clone_command(update, context, name: str) -> None:
    """Handle /voice clone command."""
    user_id = update.effective_user.id

    # Check for reply to audio
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "Please reply to a voice or audio message with:\n"
            "/voice clone <name>"
        )
        return

    reply = update.message.reply_to_message
    audio = reply.voice or reply.audio

    if not audio:
        await update.message.reply_text(
            "Please reply to a voice or audio message."
        )
        return

    if not name:
        await update.message.reply_text(
            "Please provide a name for the voice:\n"
            "/voice clone <name>"
        )
        return

    try:
        # Download audio
        audio_file = await audio.get_file()

        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
            temp_path = f.name
            await audio_file.download_to_drive(temp_path)

        try:
            # Add to library
            library = VoiceLibrary()
            voice_id = library.add_voice(temp_path, name, user_id)

            await update.message.reply_text(
                f"Voice '{name}' has been saved!\n"
                f"ID: {voice_id}\n\n"
                "Use it with: /tts --voice {name} <text>"
            )

        finally:
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    except Exception as e:
        logger.error(f"Voice clone error: {e}")
        await update.message.reply_text(
            "Sorry, I couldn't save that voice. Please try again."
        )


async def handle_voice_list_command(update, context) -> None:
    """Handle /voice list command."""
    user_id = update.effective_user.id

    library = VoiceLibrary()
    voices = library.list_voices(user_id)

    if not voices:
        await update.message.reply_text(
            "You don't have any saved voices yet.\n\n"
            "Reply to a voice message with:\n"
            "/voice clone <name>"
        )
        return

    lines = ["Your saved voices:\n"]
    for voice in voices:
        lines.append(f"  - {voice['name']} ({voice['id']})")

    await update.message.reply_text("\n".join(lines))


async def handle_voice_delete_command(update, context, name: str) -> None:
    """Handle /voice delete command."""
    user_id = update.effective_user.id

    if not name:
        await update.message.reply_text(
            "Please specify a voice to delete:\n"
            "/voice delete <name>"
        )
        return

    library = VoiceLibrary()
    success = library.delete_voice(name, user_id)

    if success:
        await update.message.reply_text(f"Voice '{name}' has been deleted.")
    else:
        await update.message.reply_text(
            f"Could not find voice '{name}' or you don't have permission to delete it."
        )


async def handle_voice_settings(update, context) -> None:
    """Handle /voicesettings command."""
    user_id = update.effective_user.id
    text = update.message.text.replace("/voicesettings", "").strip().lower()

    if text == "enable":
        set_user_voice_preference(user_id, enabled=True)
        await update.message.reply_text(
            "Voice responses enabled!\n"
            "I'll reply to your voice messages with voice."
        )
    elif text == "disable":
        set_user_voice_preference(user_id, enabled=False)
        await update.message.reply_text(
            "Voice responses disabled.\n"
            "I'll reply with text messages."
        )
    else:
        prefs = get_user_voice_preference(user_id)
        status = "enabled" if prefs.get("enabled") else "disabled"

        await update.message.reply_text(
            f"Voice settings:\n"
            f"  Voice responses: {status}\n\n"
            "Commands:\n"
            "  /voicesettings enable - Enable voice responses\n"
            "  /voicesettings disable - Disable voice responses"
        )


async def handle_voice_help(update, context) -> None:
    """Handle /voicehelp command."""
    help_text = """Voice Trading Commands:

You can speak to JARVIS! Just send a voice message.

Example commands:
  "Morning briefing" - Get market summary
  "What's the price of SOL?" - Check token price
  "Show my positions" - View portfolio
  "Set alert when SOL hits 200" - Create price alert
  "Activate momentum strategy" - Enable a strategy
  "Reduce my max position to 3 percent" - Adjust risk

Voice Settings:
  /voicesettings - Configure voice preferences
  /tts <text> - Convert text to speech
  /voice clone <name> - Clone a voice
  /voice list - List your voices

Tips:
  - Speak clearly and naturally
  - You can use "JARVIS" at the start of commands
  - Say "yes" or "confirm" to execute trades
"""
    await update.message.reply_text(help_text)


def register_voice_handlers(application) -> None:
    """Register all voice handlers with the Telegram application."""
    from telegram.ext import CommandHandler, MessageHandler, filters

    # Voice message handler
    application.add_handler(MessageHandler(filters.VOICE, handle_voice_message))

    # Command handlers
    application.add_handler(CommandHandler("tts", handle_tts_command))
    application.add_handler(CommandHandler("voice", handle_voice_command))
    application.add_handler(CommandHandler("voicesettings", handle_voice_settings))
    application.add_handler(CommandHandler("voicehelp", handle_voice_help))
