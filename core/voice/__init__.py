"""
Voice subpackage for Jarvis.

This package consolidates all voice and audio-related modules.
All modules are re-exported here for backwards compatibility.

Modules:
- Voice management and STT/TTS
- Hotkey handling
- Wake word detection
- Voice cloning
"""

from core.voice import (
    VoiceManager,
    start_chat_session,
    stop_listening,
    is_listening,
    speak,
    speak_async,
    get_voice_status,
)

from core.hotkeys import (
    HotkeyManager,
    register_hotkey,
    unregister_hotkey,
)

from core.openai_tts import (
    speak_openai,
    get_tts_cost,
)

# Voice clone is optional
try:
    from core.voice_clone import (
        clone_voice,
        generate_cloned_speech,
    )
except ImportError:
    clone_voice = None
    generate_cloned_speech = None

__all__ = [
    # Voice Manager
    "VoiceManager",
    "start_chat_session",
    "stop_listening",
    "is_listening",
    "speak",
    "speak_async",
    "get_voice_status",
    # Hotkeys
    "HotkeyManager",
    "register_hotkey",
    "unregister_hotkey",
    # TTS
    "speak_openai",
    "get_tts_cost",
    # Voice Clone
    "clone_voice",
    "generate_cloned_speech",
]
