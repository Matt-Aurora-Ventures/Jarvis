"""
Voice Cloning Engine using Coqui XTTS-v2.

Provides free, local voice cloning for Jarvis TTS.
Requires only a 6-15 second audio sample of the target voice.

Usage:
    from core import voice_clone

    # Generate speech in Morgan Freeman's voice
    voice_clone.speak("Hello, I am Jarvis.", voice="morgan_freeman")
"""

import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Optional

# Paths
ROOT = Path(__file__).resolve().parents[1]
VOICES_DIR = ROOT / "data" / "voices" / "clones"
CACHE_DIR = ROOT / "data" / "voices" / "cache"

# Default reference audio paths
REFERENCE_VOICES = {
    "morgan_freeman": VOICES_DIR / "morgan_freeman.wav",
    "custom": VOICES_DIR / "custom.wav",
}

# Global model cache
_xtts_model = None
_xtts_lock = threading.Lock()


def _ensure_dirs() -> None:
    """Create voice directories if needed."""
    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _install_tts() -> bool:
    """Install Coqui TTS if not present."""
    try:
        import TTS
        return True
    except ImportError:
        print("Installing Coqui TTS (this may take a few minutes)...")
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install",
                "TTS>=0.22.0", "--quiet"
            ])
            return True
        except subprocess.CalledProcessError as e:
            print(f"Failed to install TTS: {e}")
            return False


def _load_xtts_model():
    """Load XTTS-v2 model (cached globally)."""
    global _xtts_model

    with _xtts_lock:
        if _xtts_model is not None:
            return _xtts_model

        if not _install_tts():
            return None

        try:
            from TTS.api import TTS
            print("Loading XTTS-v2 model (first time may download ~2GB)...")

            # Use XTTS-v2 for voice cloning
            _xtts_model = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
            print("XTTS-v2 model loaded successfully!")
            return _xtts_model

        except Exception as e:
            print(f"Failed to load XTTS model: {e}")
            return None


def get_reference_audio(voice: str = "morgan_freeman") -> Optional[Path]:
    """Get path to reference audio file."""
    _ensure_dirs()

    if voice in REFERENCE_VOICES:
        path = REFERENCE_VOICES[voice]
        if path.exists():
            return path

    # Check if custom path provided
    custom_path = Path(voice)
    if custom_path.exists():
        return custom_path

    return None


def clone_voice_tts(
    text: str,
    reference_audio: Path,
    output_path: Optional[Path] = None,
    language: str = "en"
) -> Optional[Path]:
    """
    Generate speech using voice cloning.

    Args:
        text: Text to synthesize
        reference_audio: Path to reference audio file (6-15 seconds ideal)
        output_path: Optional output path (uses temp file if not provided)
        language: Language code (default: "en")

    Returns:
        Path to generated audio file, or None on failure
    """
    model = _load_xtts_model()
    if model is None:
        return None

    if not reference_audio.exists():
        print(f"Reference audio not found: {reference_audio}")
        return None

    # Generate output path
    if output_path is None:
        output_path = Path(tempfile.mktemp(suffix=".wav"))

    try:
        # Generate with voice cloning
        model.tts_to_file(
            text=text,
            file_path=str(output_path),
            speaker_wav=str(reference_audio),
            language=language
        )
        return output_path

    except Exception as e:
        print(f"Voice cloning failed: {e}")
        return None


def speak(
    text: str,
    voice: str = "morgan_freeman",
    language: str = "en",
    play: bool = True
) -> bool:
    """
    Speak text using cloned voice.

    Args:
        text: Text to speak
        voice: Voice name or path to reference audio
        language: Language code
        play: Whether to play the audio immediately

    Returns:
        True if successful
    """
    reference = get_reference_audio(voice)
    if reference is None:
        print(f"Voice reference not found: {voice}")
        print(f"Please add a 6-15 second audio sample to: {VOICES_DIR}")
        return False

    output = clone_voice_tts(text, reference, language=language)
    if output is None:
        return False

    if play:
        try:
            # Play on macOS
            subprocess.run(
                ["afplay", str(output)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True
            )
        except subprocess.CalledProcessError:
            print("Failed to play audio")
            return False
        finally:
            # Clean up temp file
            if output.exists():
                output.unlink(missing_ok=True)

    return True


def setup_morgan_freeman_voice() -> bool:
    """
    Interactive setup for Morgan Freeman voice.

    Returns:
        True if voice is set up successfully
    """
    _ensure_dirs()
    target_path = REFERENCE_VOICES["morgan_freeman"]

    if target_path.exists():
        print(f"Morgan Freeman voice already configured: {target_path}")
        return True

    print("""
╔═══════════════════════════════════════════════════════════════════╗
║                 MORGAN FREEMAN VOICE SETUP                        ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  To clone Morgan Freeman's voice, you need a 6-15 second audio   ║
║  sample of him speaking clearly.                                 ║
║                                                                   ║
║  RECOMMENDED SOURCES (Fair Use for Personal Projects):           ║
║                                                                   ║
║  1. YouTube Interview Clip:                                       ║
║     - Search "Morgan Freeman interview"                           ║
║     - Use a YouTube audio downloader                             ║
║     - Trim to 6-15 seconds of clear speech                       ║
║                                                                   ║
║  2. Movie Trailer Narration:                                      ║
║     - Many official trailers feature his narration               ║
║     - Extract the audio portion                                  ║
║                                                                   ║
║  3. Audiobook Sample:                                             ║
║     - Audible/public previews of his narrations                  ║
║                                                                   ║
╠═══════════════════════════════════════════════════════════════════╣
║  ONCE YOU HAVE THE AUDIO FILE:                                   ║
║                                                                   ║
║  Save it as:                                                      ║
║  {target_path}
║                                                                   ║
║  Format: WAV or MP3 (WAV preferred)                              ║
║  Duration: 6-15 seconds of clear speech                          ║
║  Quality: Clear audio, minimal background noise                  ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
""".format(target_path=target_path))

    return False


def check_voice_status() -> dict:
    """
    Check status of voice cloning setup.

    Returns:
        Dict with status information
    """
    _ensure_dirs()

    status = {
        "tts_installed": False,
        "model_loaded": False,
        "morgan_freeman_ready": False,
        "voices_available": [],
        "voices_dir": str(VOICES_DIR),
    }

    # Check TTS installation
    try:
        import TTS
        status["tts_installed"] = True
    except ImportError:
        pass

    # Check model
    status["model_loaded"] = _xtts_model is not None

    # Check available voices
    for name, path in REFERENCE_VOICES.items():
        if path.exists():
            status["voices_available"].append(name)

    status["morgan_freeman_ready"] = "morgan_freeman" in status["voices_available"]

    return status


def download_sample_audio(url: str, voice_name: str = "custom") -> Optional[Path]:
    """
    Download audio from URL and save as reference voice.

    Args:
        url: URL to audio file or YouTube video
        voice_name: Name for the voice

    Returns:
        Path to downloaded file, or None on failure
    """
    _ensure_dirs()

    output_path = VOICES_DIR / f"{voice_name}.wav"

    # Check if yt-dlp is available for YouTube URLs
    if "youtube.com" in url or "youtu.be" in url:
        try:
            import subprocess
            result = subprocess.run(
                ["yt-dlp", "--version"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                # Download just audio
                subprocess.run([
                    "yt-dlp",
                    "-x", "--audio-format", "wav",
                    "--audio-quality", "0",
                    "-o", str(output_path),
                    url
                ], check=True)
                print(f"Downloaded to: {output_path}")
                print("NOTE: You may need to trim this to 6-15 seconds")
                return output_path
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("yt-dlp not installed. Install with: brew install yt-dlp")
            return None

    # Direct URL download
    try:
        import urllib.request
        print(f"Downloading audio from {url}...")
        urllib.request.urlretrieve(url, output_path)
        print(f"Downloaded to: {output_path}")
        return output_path
    except Exception as e:
        print(f"Download failed: {e}")
        return None


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Voice Cloning with XTTS-v2")
    parser.add_argument("--setup", action="store_true", help="Setup Morgan Freeman voice")
    parser.add_argument("--status", action="store_true", help="Check voice status")
    parser.add_argument("--speak", type=str, help="Text to speak")
    parser.add_argument("--voice", type=str, default="morgan_freeman", help="Voice to use")
    parser.add_argument("--download", type=str, help="URL to download audio from")

    args = parser.parse_args()

    if args.setup:
        setup_morgan_freeman_voice()
    elif args.status:
        status = check_voice_status()
        print("\n=== Voice Clone Status ===")
        print(f"TTS Installed: {'✓' if status['tts_installed'] else '✗'}")
        print(f"Model Loaded: {'✓' if status['model_loaded'] else '✗'}")
        print(f"Morgan Freeman Ready: {'✓' if status['morgan_freeman_ready'] else '✗'}")
        print(f"Available Voices: {status['voices_available'] or 'None'}")
        print(f"Voices Directory: {status['voices_dir']}")
    elif args.download:
        download_sample_audio(args.download, args.voice)
    elif args.speak:
        speak(args.speak, voice=args.voice)
    else:
        parser.print_help()
