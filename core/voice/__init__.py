"""
JARVIS Voice Module - Speech Capabilities

Provides:
- Wake word detection (Hey JARVIS)
- Speech recognition
- Text to speech

Usage:
    from core.voice import get_voice_listener

    listener = get_voice_listener()
    listener.on_wake(lambda e: print(f"Wake: {e.phrase}"))
    listener.start()
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from .wakeword import (
    WakeWordEvent,
    WakeWordDetector,
    PorcupineDetector,
    VoskDetector,
    SimpleAudioDetector,
    JarvisVoiceListener,
    get_voice_listener,
    start_voice_listener,
)

from .command_parser import (
    VoiceCommandParser,
    CommandIntent,
    Intent,
)

from .trading_commands import (
    VoiceTradingCommands,
    VoiceResponse,
)

def _load_legacy_voice_module():
    legacy_path = Path(__file__).resolve().parents[1] / "voice.py"
    if not legacy_path.exists():
        return None
    spec = spec_from_file_location("core._voice_legacy", legacy_path)
    if spec is None or spec.loader is None:
        return None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_legacy_voice = _load_legacy_voice_module()
VoiceManager = getattr(_legacy_voice, "VoiceManager", None) if _legacy_voice else None
start_chat_session = (
    getattr(_legacy_voice, "start_chat_session", None) if _legacy_voice else None
)
chat_session = getattr(_legacy_voice, "chat_session", None) if _legacy_voice else None

# Voice doctor diagnostic functions
diagnose_voice_pipeline = (
    getattr(_legacy_voice, "diagnose_voice_pipeline", None) if _legacy_voice else None
)
format_voice_doctor_report = (
    getattr(_legacy_voice, "format_voice_doctor_report", None) if _legacy_voice else None
)
check_voice_health = (
    getattr(_legacy_voice, "check_voice_health", None) if _legacy_voice else None
)
get_voice_doctor_summary = (
    getattr(_legacy_voice, "get_voice_doctor_summary", None) if _legacy_voice else None
)

__all__ = [
    "WakeWordEvent",
    "WakeWordDetector",
    "PorcupineDetector",
    "VoskDetector",
    "SimpleAudioDetector",
    "JarvisVoiceListener",
    "get_voice_listener",
    "start_voice_listener",
    "VoiceManager",
    "start_chat_session",
    "chat_session",
    "diagnose_voice_pipeline",
    "format_voice_doctor_report",
    "check_voice_health",
    "get_voice_doctor_summary",
    # Voice trading terminal
    "VoiceCommandParser",
    "CommandIntent",
    "Intent",
    "VoiceTradingCommands",
    "VoiceResponse",
]
