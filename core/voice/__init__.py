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

__all__ = [
    "WakeWordEvent",
    "WakeWordDetector",
    "PorcupineDetector",
    "VoskDetector",
    "SimpleAudioDetector",
    "JarvisVoiceListener",
    "get_voice_listener",
    "start_voice_listener",
]
