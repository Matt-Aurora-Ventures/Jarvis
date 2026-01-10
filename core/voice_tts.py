"""
Cross-Platform Text-to-Speech with Deep Male Voices.

Uses edge-tts (free Microsoft voices) for high-quality speech.
Includes voice presets for different personas including a
deep "narrator" voice similar to Morgan Freeman.

Works on Windows, macOS, and Linux without API keys.
"""

import asyncio
import logging
import os
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Voice presets - deep male voices
VOICE_PRESETS = {
    # Morgan Freeman-like deep narrator voice
    "morgan": {
        "voice": "en-US-GuyNeural",
        "rate": "-15%",  # Slower for gravitas
        "pitch": "-10Hz",  # Deeper pitch
    },
    # Default Jarvis voice
    "jarvis": {
        "voice": "en-US-GuyNeural",
        "rate": "-5%",
        "pitch": "-5Hz",
    },
    # Casual friendly voice
    "casual": {
        "voice": "en-US-ChristopherNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
    },
    # British butler voice
    "butler": {
        "voice": "en-GB-RyanNeural",
        "rate": "-5%",
        "pitch": "-3Hz",
    },
    # Fast technical voice
    "tech": {
        "voice": "en-US-EricNeural",
        "rate": "+10%",
        "pitch": "+0Hz",
    },
    # Deep storyteller
    "narrator": {
        "voice": "en-US-RogerNeural",
        "rate": "-10%",
        "pitch": "-8Hz",
    },
}

# Default voice
DEFAULT_VOICE = "morgan"


@dataclass
class VoiceConfig:
    """Voice configuration."""
    voice: str = "en-US-GuyNeural"
    rate: str = "-10%"
    pitch: str = "-5Hz"
    volume: str = "+0%"


class VoiceTTS:
    """
    Text-to-Speech engine using edge-tts.

    Features:
    - High-quality Microsoft Neural voices (free)
    - Multiple voice presets
    - Adjustable rate, pitch, and volume
    - Cross-platform audio playback
    - Async and sync interfaces
    """

    def __init__(self, preset: str = DEFAULT_VOICE):
        """
        Initialize the TTS engine.

        Args:
            preset: Voice preset name (morgan, jarvis, butler, etc.)
        """
        self._config = self._get_preset_config(preset)
        self._speaking = False
        self._lock = threading.Lock()
        self._current_process: Optional[subprocess.Popen] = None
        self._temp_dir = Path(tempfile.gettempdir()) / "jarvis_tts"
        self._temp_dir.mkdir(exist_ok=True)

    def _get_preset_config(self, preset: str) -> VoiceConfig:
        """Get voice config from preset name."""
        if preset in VOICE_PRESETS:
            p = VOICE_PRESETS[preset]
            return VoiceConfig(
                voice=p["voice"],
                rate=p["rate"],
                pitch=p["pitch"],
            )
        return VoiceConfig()

    def set_preset(self, preset: str) -> None:
        """Change voice preset."""
        self._config = self._get_preset_config(preset)
        logger.info(f"Voice preset changed to: {preset}")

    def set_voice(self, voice: str, rate: str = "-5%", pitch: str = "-5Hz") -> None:
        """Set custom voice parameters."""
        self._config = VoiceConfig(voice=voice, rate=rate, pitch=pitch)

    async def speak_async(self, text: str) -> bool:
        """
        Speak text asynchronously.

        Args:
            text: Text to speak

        Returns:
            True if successful
        """
        try:
            import edge_tts
        except ImportError:
            logger.error("edge-tts not installed: pip install edge-tts")
            return False

        with self._lock:
            if self._speaking:
                self.stop()

            self._speaking = True

        try:
            # Generate audio
            communicate = edge_tts.Communicate(
                text,
                self._config.voice,
                rate=self._config.rate,
                pitch=self._config.pitch,
                volume=self._config.volume,
            )

            # Save to temp file
            audio_file = self._temp_dir / f"speech_{int(time.time())}.mp3"
            await communicate.save(str(audio_file))

            # Play audio
            await self._play_audio_async(audio_file)

            # Cleanup
            try:
                audio_file.unlink()
            except Exception:
                pass

            return True

        except Exception as e:
            logger.error(f"TTS failed: {e}")
            return False
        finally:
            self._speaking = False

    def speak(self, text: str) -> bool:
        """
        Speak text synchronously.

        Args:
            text: Text to speak

        Returns:
            True if successful
        """
        return asyncio.run(self.speak_async(text))

    def speak_threaded(self, text: str) -> None:
        """Speak text in a background thread (non-blocking)."""
        thread = threading.Thread(target=self.speak, args=(text,), daemon=True)
        thread.start()

    async def _play_audio_async(self, audio_file: Path) -> None:
        """Play audio file cross-platform."""
        if sys.platform == "win32":
            # Windows: use Windows Media Player via PowerShell
            # or ffplay if available
            try:
                # Try ffplay first (best quality)
                proc = await asyncio.create_subprocess_exec(
                    "ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(audio_file),
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                self._current_process = proc
                await proc.wait()
            except FileNotFoundError:
                # Fallback to Windows Media Player
                script = f'''
                Add-Type -AssemblyName presentationCore
                $player = New-Object System.Windows.Media.MediaPlayer
                $player.Open("{audio_file}")
                $player.Play()
                Start-Sleep -Milliseconds 500
                while ($player.Position -lt $player.NaturalDuration.TimeSpan) {{
                    Start-Sleep -Milliseconds 100
                }}
                $player.Close()
                '''
                proc = await asyncio.create_subprocess_exec(
                    "powershell", "-Command", script,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                self._current_process = proc
                await proc.wait()

        elif sys.platform == "darwin":
            # macOS: use afplay
            proc = await asyncio.create_subprocess_exec(
                "afplay", str(audio_file),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            self._current_process = proc
            await proc.wait()

        else:
            # Linux: try mpv, then ffplay, then aplay
            for player in ["mpv", "ffplay", "aplay"]:
                try:
                    if player == "ffplay":
                        args = [player, "-nodisp", "-autoexit", "-loglevel", "quiet", str(audio_file)]
                    elif player == "mpv":
                        args = [player, "--no-video", str(audio_file)]
                    else:
                        args = [player, str(audio_file)]

                    proc = await asyncio.create_subprocess_exec(
                        *args,
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    self._current_process = proc
                    await proc.wait()
                    break
                except FileNotFoundError:
                    continue

    def stop(self) -> None:
        """Stop current speech."""
        if self._current_process:
            try:
                self._current_process.terminate()
            except Exception:
                pass
            self._current_process = None
        self._speaking = False

    def is_speaking(self) -> bool:
        """Check if currently speaking."""
        return self._speaking

    @staticmethod
    def list_voices() -> list:
        """List all available voices."""
        import asyncio
        try:
            import edge_tts
            return asyncio.run(edge_tts.list_voices())
        except ImportError:
            return []

    @staticmethod
    def list_presets() -> dict:
        """List available voice presets."""
        return VOICE_PRESETS.copy()


# Global instance
_tts: Optional[VoiceTTS] = None


def get_tts(preset: str = DEFAULT_VOICE) -> VoiceTTS:
    """Get the global TTS instance."""
    global _tts
    if _tts is None:
        _tts = VoiceTTS(preset=preset)
    return _tts


def speak(text: str, preset: Optional[str] = None) -> bool:
    """
    Speak text with optional voice preset.

    Args:
        text: Text to speak
        preset: Voice preset (morgan, jarvis, butler, etc.)

    Returns:
        True if successful
    """
    tts = get_tts()
    if preset:
        tts.set_preset(preset)
    return tts.speak(text)


def speak_async(text: str, preset: Optional[str] = None) -> None:
    """Speak text in background (non-blocking)."""
    tts = get_tts()
    if preset:
        tts.set_preset(preset)
    tts.speak_threaded(text)


def stop() -> None:
    """Stop current speech."""
    if _tts:
        _tts.stop()


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Jarvis Text-to-Speech")
    parser.add_argument("text", nargs="?", default="Hello, I am Jarvis. How may I assist you today?")
    parser.add_argument("--preset", "-p", default="morgan", choices=list(VOICE_PRESETS.keys()))
    parser.add_argument("--list-voices", action="store_true", help="List all available voices")
    parser.add_argument("--list-presets", action="store_true", help="List voice presets")

    args = parser.parse_args()

    if args.list_presets:
        print("Voice Presets:")
        for name, config in VOICE_PRESETS.items():
            print(f"  {name}: {config['voice']} (rate: {config['rate']}, pitch: {config['pitch']})")
        sys.exit(0)

    if args.list_voices:
        voices = VoiceTTS.list_voices()
        print("Available Voices:")
        for v in voices:
            if "en-" in v["ShortName"]:
                print(f"  {v['ShortName']}: {v['Gender']} ({v['Locale']})")
        sys.exit(0)

    print(f"Speaking with '{args.preset}' voice...")
    speak(args.text, preset=args.preset)
    print("Done!")
