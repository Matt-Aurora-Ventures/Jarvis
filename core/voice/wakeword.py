"""
JARVIS Wake Word Detection - Always Listening

Lightweight wake word detection using:
- Porcupine (if available) - commercial quality
- Vosk (fallback) - open source
- Simple audio level detection (basic fallback)

Wake phrases: "Hey JARVIS", "JARVIS", "J.A.R.V.I.S"

Dependencies:
    pip install pyaudio  # Audio capture
    pip install pvporcupine  # Commercial wake word (optional)
    pip install vosk  # Open source fallback (optional)
"""

import asyncio
import logging
import os
import queue
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

# Check for audio libraries
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    pyaudio = None

try:
    import pvporcupine
    PORCUPINE_AVAILABLE = True
except ImportError:
    PORCUPINE_AVAILABLE = False
    pvporcupine = None

try:
    import vosk
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False
    vosk = None


@dataclass
class WakeWordEvent:
    """Event when wake word is detected."""
    phrase: str
    confidence: float
    timestamp: float
    audio_data: Optional[bytes] = None


class WakeWordDetector(ABC):
    """Base class for wake word detection."""

    def __init__(self, callback: Callable[[WakeWordEvent], None]):
        self.callback = callback
        self._running = False
        self._thread: Optional[threading.Thread] = None

    @abstractmethod
    def start(self):
        """Start listening for wake word."""
        pass

    @abstractmethod
    def stop(self):
        """Stop listening."""
        pass

    @property
    def is_running(self) -> bool:
        return self._running


class PorcupineDetector(WakeWordDetector):
    """
    Wake word detection using Picovoice Porcupine.

    Pros: Very accurate, low latency, low CPU
    Cons: Requires API key (free tier: 3 keywords)

    Get key: https://console.picovoice.ai/
    """

    def __init__(
        self,
        callback: Callable[[WakeWordEvent], None],
        access_key: Optional[str] = None,
        keywords: List[str] = None,
    ):
        super().__init__(callback)
        self.access_key = access_key or os.getenv("PICOVOICE_ACCESS_KEY")
        self.keywords = keywords or ["jarvis", "hey google"]  # Use built-in as fallback
        self._porcupine = None
        self._audio = None
        self._stream = None

    def start(self):
        if not PORCUPINE_AVAILABLE or not self.access_key:
            logger.warning("Porcupine not available or no access key")
            return

        try:
            # Initialize Porcupine
            self._porcupine = pvporcupine.create(
                access_key=self.access_key,
                keywords=self.keywords,
            )

            # Initialize audio
            self._audio = pyaudio.PyAudio()
            self._stream = self._audio.open(
                rate=self._porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self._porcupine.frame_length,
            )

            self._running = True
            self._thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._thread.start()
            logger.info("Porcupine wake word detector started")

        except Exception as e:
            logger.error(f"Failed to start Porcupine: {e}")
            self._cleanup()

    def _listen_loop(self):
        """Main listening loop."""
        while self._running:
            try:
                pcm = self._stream.read(self._porcupine.frame_length, exception_on_overflow=False)
                pcm = list(int.from_bytes(pcm[i:i+2], 'little', signed=True)
                          for i in range(0, len(pcm), 2))

                result = self._porcupine.process(pcm)

                if result >= 0:
                    event = WakeWordEvent(
                        phrase=self.keywords[result],
                        confidence=0.95,
                        timestamp=time.time(),
                    )
                    self.callback(event)

            except Exception as e:
                if self._running:
                    logger.error(f"Porcupine listen error: {e}")
                    time.sleep(0.1)

    def stop(self):
        self._running = False
        self._cleanup()

    def _cleanup(self):
        if self._stream:
            self._stream.close()
        if self._audio:
            self._audio.terminate()
        if self._porcupine:
            self._porcupine.delete()


class VoskDetector(WakeWordDetector):
    """
    Wake word detection using Vosk (open source).

    Pros: Free, offline, decent accuracy
    Cons: Higher CPU, requires model download

    Models: https://alphacephei.com/vosk/models
    """

    def __init__(
        self,
        callback: Callable[[WakeWordEvent], None],
        model_path: Optional[str] = None,
        wake_phrases: List[str] = None,
    ):
        super().__init__(callback)
        self.model_path = model_path or os.getenv("VOSK_MODEL_PATH")
        self.wake_phrases = wake_phrases or ["jarvis", "hey jarvis", "okay jarvis"]
        self._model = None
        self._recognizer = None
        self._audio = None
        self._stream = None

    def start(self):
        if not VOSK_AVAILABLE:
            logger.warning("Vosk not available")
            return

        if not self.model_path or not Path(self.model_path).exists():
            logger.warning("Vosk model not found. Download from https://alphacephei.com/vosk/models")
            return

        try:
            vosk.SetLogLevel(-1)  # Suppress logs
            self._model = vosk.Model(self.model_path)
            self._recognizer = vosk.KaldiRecognizer(self._model, 16000)

            self._audio = pyaudio.PyAudio()
            self._stream = self._audio.open(
                rate=16000,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=4000,
            )

            self._running = True
            self._thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._thread.start()
            logger.info("Vosk wake word detector started")

        except Exception as e:
            logger.error(f"Failed to start Vosk: {e}")
            self._cleanup()

    def _listen_loop(self):
        """Main listening loop."""
        while self._running:
            try:
                data = self._stream.read(4000, exception_on_overflow=False)

                if self._recognizer.AcceptWaveform(data):
                    import json
                    result = json.loads(self._recognizer.Result())
                    text = result.get("text", "").lower()

                    for phrase in self.wake_phrases:
                        if phrase in text:
                            event = WakeWordEvent(
                                phrase=phrase,
                                confidence=0.7,
                                timestamp=time.time(),
                            )
                            self.callback(event)
                            break

            except Exception as e:
                if self._running:
                    logger.error(f"Vosk listen error: {e}")
                    time.sleep(0.1)

    def stop(self):
        self._running = False
        self._cleanup()

    def _cleanup(self):
        if self._stream:
            self._stream.close()
        if self._audio:
            self._audio.terminate()


class SimpleAudioDetector(WakeWordDetector):
    """
    Simple audio level detection (basic fallback).

    Just detects when someone starts speaking.
    Use with push-to-talk or as a simple trigger.
    """

    def __init__(
        self,
        callback: Callable[[WakeWordEvent], None],
        threshold: float = 0.1,
        min_duration: float = 0.5,
    ):
        super().__init__(callback)
        self.threshold = threshold
        self.min_duration = min_duration
        self._audio = None
        self._stream = None

    def start(self):
        if not PYAUDIO_AVAILABLE:
            logger.warning("PyAudio not available")
            return

        try:
            self._audio = pyaudio.PyAudio()
            self._stream = self._audio.open(
                rate=16000,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=1024,
            )

            self._running = True
            self._thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._thread.start()
            logger.info("Simple audio detector started")

        except Exception as e:
            logger.error(f"Failed to start audio detector: {e}")
            self._cleanup()

    def _listen_loop(self):
        """Monitor audio levels."""
        import struct

        speaking_start = None

        while self._running:
            try:
                data = self._stream.read(1024, exception_on_overflow=False)

                # Calculate RMS
                count = len(data) // 2
                shorts = struct.unpack(f"{count}h", data)
                rms = (sum(s * s for s in shorts) / count) ** 0.5
                level = rms / 32768.0  # Normalize

                if level > self.threshold:
                    if speaking_start is None:
                        speaking_start = time.time()
                    elif time.time() - speaking_start > self.min_duration:
                        event = WakeWordEvent(
                            phrase="audio_trigger",
                            confidence=level,
                            timestamp=time.time(),
                        )
                        self.callback(event)
                        speaking_start = None
                        time.sleep(1)  # Cooldown
                else:
                    speaking_start = None

            except Exception as e:
                if self._running:
                    logger.error(f"Audio detect error: {e}")
                    time.sleep(0.1)

    def stop(self):
        self._running = False
        self._cleanup()

    def _cleanup(self):
        if self._stream:
            self._stream.close()
        if self._audio:
            self._audio.terminate()


class JarvisVoiceListener:
    """
    High-level voice listener for JARVIS.

    Automatically selects best available detector:
    1. Porcupine (if API key available)
    2. Vosk (if model available)
    3. Simple audio (fallback)
    """

    def __init__(self, on_wake: Optional[Callable[[WakeWordEvent], None]] = None):
        self._detector: Optional[WakeWordDetector] = None
        self._on_wake = on_wake
        self._callbacks: List[Callable[[WakeWordEvent], None]] = []

        if on_wake:
            self._callbacks.append(on_wake)

    def on_wake(self, callback: Callable[[WakeWordEvent], None]):
        """Register wake word callback."""
        self._callbacks.append(callback)

    def _dispatch_wake(self, event: WakeWordEvent):
        """Dispatch wake event to all callbacks."""
        for callback in self._callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Wake callback error: {e}")

    def start(self) -> bool:
        """Start the best available detector."""
        # Try Porcupine first
        if PORCUPINE_AVAILABLE and os.getenv("PICOVOICE_ACCESS_KEY"):
            self._detector = PorcupineDetector(self._dispatch_wake)
            self._detector.start()
            if self._detector.is_running:
                return True

        # Try Vosk
        if VOSK_AVAILABLE and os.getenv("VOSK_MODEL_PATH"):
            self._detector = VoskDetector(self._dispatch_wake)
            self._detector.start()
            if self._detector.is_running:
                return True

        # Fall back to simple audio
        if PYAUDIO_AVAILABLE:
            self._detector = SimpleAudioDetector(self._dispatch_wake)
            self._detector.start()
            if self._detector.is_running:
                return True

        logger.warning("No voice detector available")
        return False

    def stop(self):
        """Stop the detector."""
        if self._detector:
            self._detector.stop()
            self._detector = None

    @property
    def is_running(self) -> bool:
        return self._detector is not None and self._detector.is_running


# Singleton instance
_listener: Optional[JarvisVoiceListener] = None


def get_voice_listener() -> JarvisVoiceListener:
    """Get singleton voice listener."""
    global _listener
    if _listener is None:
        _listener = JarvisVoiceListener()
    return _listener


async def start_voice_listener():
    """Start voice listener in async context."""
    listener = get_voice_listener()
    return listener.start()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    def on_wake(event: WakeWordEvent):
        print(f"\n>>> WAKE WORD DETECTED: {event.phrase} (confidence: {event.confidence:.2f})")

    listener = JarvisVoiceListener(on_wake)
    if listener.start():
        print("Listening for wake word... (Ctrl+C to stop)")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            listener.stop()
            print("\nStopped.")
    else:
        print("Could not start voice listener.")
        print("Install: pip install pyaudio")
        print("Optional: pip install pvporcupine (with PICOVOICE_ACCESS_KEY)")
        print("Optional: pip install vosk (with VOSK_MODEL_PATH)")
