"""
Cross-platform wake word detection for Jarvis.

Uses continuous speech recognition to detect "Hey Jarvis" or "Jarvis"
and trigger actions. Works on Windows, macOS, and Linux without
requiring custom wake word model training.
"""

import logging
import queue
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Wake word phrases (case-insensitive matching)
WAKE_PHRASES = [
    "hey jarvis",
    "hey jarves",  # Common misrecognition
    "jarvis",
    "jarves",
    "hey travis",  # Another common misrecognition
]


class WakeWordListener:
    """
    Continuous wake word listener using speech recognition.

    Cross-platform implementation that doesn't require openwakeword
    or custom model training. Uses Google Speech Recognition by default.
    """

    def __init__(
        self,
        on_wake: Optional[Callable[[str], None]] = None,
        wake_phrases: Optional[list[str]] = None,
        sensitivity: float = 0.8,
    ):
        """
        Initialize the wake word listener.

        Args:
            on_wake: Callback when wake word detected. Receives command text (if any).
            wake_phrases: Custom wake phrases to listen for.
            sensitivity: How strict the matching should be (0.0-1.0).
        """
        self._on_wake = on_wake
        self._wake_phrases = [p.lower() for p in (wake_phrases or WAKE_PHRASES)]
        self._sensitivity = sensitivity
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._recognizer = None
        self._microphone = None
        self._command_queue: queue.Queue = queue.Queue()

    def start(self) -> bool:
        """Start listening for wake word. Returns True if started successfully."""
        if self._running:
            logger.warning("Wake word listener already running")
            return True

        try:
            import speech_recognition as sr
            self._recognizer = sr.Recognizer()

            # Configure for faster response
            self._recognizer.energy_threshold = 300
            self._recognizer.dynamic_energy_threshold = True
            self._recognizer.pause_threshold = 0.5
            self._recognizer.non_speaking_duration = 0.3

        except ImportError:
            logger.error("SpeechRecognition not installed: pip install SpeechRecognition")
            return False

        try:
            import speech_recognition as sr
            self._microphone = sr.Microphone()

            # Test microphone access
            with self._microphone as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=0.5)

        except OSError as e:
            logger.error(f"Microphone not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize microphone: {e}")
            return False

        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

        logger.info("Wake word listener started - say 'Hey Jarvis' to activate")
        return True

    def stop(self) -> None:
        """Stop listening for wake word."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("Wake word listener stopped")

    def is_running(self) -> bool:
        """Check if listener is running."""
        return self._running

    def get_command(self, timeout: float = 0.1) -> Optional[str]:
        """Get detected command from queue (non-blocking)."""
        try:
            return self._command_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def _listen_loop(self) -> None:
        """Main listening loop."""
        import speech_recognition as sr

        consecutive_errors = 0
        max_errors = 5

        while self._running:
            try:
                with self._microphone as source:
                    # Listen for speech (with short timeout for responsiveness)
                    try:
                        audio = self._recognizer.listen(
                            source,
                            timeout=2.0,  # Max time to wait for speech to start
                            phrase_time_limit=5.0,  # Max duration of phrase
                        )
                    except sr.WaitTimeoutError:
                        # No speech detected, continue listening
                        consecutive_errors = 0
                        continue

                # Try to recognize the speech
                text = self._transcribe(audio)
                if text:
                    self._process_transcript(text)
                    consecutive_errors = 0

            except sr.UnknownValueError:
                # Speech was unintelligible, continue
                consecutive_errors = 0
                continue
            except sr.RequestError as e:
                # API error
                logger.warning(f"Speech recognition API error: {e}")
                consecutive_errors += 1
                if consecutive_errors >= max_errors:
                    logger.error("Too many consecutive errors, pausing listener")
                    time.sleep(5.0)
                    consecutive_errors = 0
            except Exception as e:
                logger.error(f"Wake word listener error: {e}")
                consecutive_errors += 1
                if consecutive_errors >= max_errors:
                    time.sleep(5.0)
                    consecutive_errors = 0

    def _transcribe(self, audio) -> str:
        """Transcribe audio to text using available engines."""
        import speech_recognition as sr

        # Try Google Speech Recognition (free, no API key needed)
        try:
            text = self._recognizer.recognize_google(audio)
            return text.strip()
        except sr.UnknownValueError:
            pass
        except sr.RequestError:
            pass

        # Try Sphinx as offline fallback (if available)
        try:
            text = self._recognizer.recognize_sphinx(audio)
            return text.strip()
        except (sr.UnknownValueError, sr.RequestError):
            pass
        except Exception:
            pass  # Sphinx not installed

        return ""

    def _process_transcript(self, text: str) -> None:
        """Check if transcript contains wake word and extract command."""
        text_lower = text.lower().strip()

        if not text_lower:
            return

        # Check for wake phrases
        for phrase in self._wake_phrases:
            if phrase in text_lower:
                # Extract command after wake phrase
                idx = text_lower.find(phrase)
                command = text[idx + len(phrase):].strip()

                # Clean up command
                if command.startswith(","):
                    command = command[1:].strip()

                logger.info(f"Wake word detected! Command: '{command or '(none)'}'")

                # Put command in queue
                self._command_queue.put(command)

                # Call callback if provided
                if self._on_wake:
                    try:
                        self._on_wake(command)
                    except Exception as e:
                        logger.error(f"Wake callback error: {e}")

                return

    def listen_for_command(self, timeout: float = 5.0) -> str:
        """
        Listen for a single command after wake word activation.

        This is called after the wake word is detected to capture
        the user's full command.
        """
        import speech_recognition as sr

        if not self._recognizer or not self._microphone:
            return ""

        try:
            with self._microphone as source:
                logger.info("Listening for command...")
                audio = self._recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=10.0,
                )

            return self._transcribe(audio)
        except sr.WaitTimeoutError:
            return ""
        except Exception as e:
            logger.error(f"Error listening for command: {e}")
            return ""


class WakeWordManager:
    """
    Manages wake word detection and integrates with Jarvis.

    Provides a simple interface to start/stop wake word listening
    and handle detected commands.
    """

    def __init__(self):
        self._listener: Optional[WakeWordListener] = None
        self._command_handler: Optional[Callable[[str], str]] = None
        self._speak_handler: Optional[Callable[[str], None]] = None

    def set_command_handler(self, handler: Callable[[str], str]) -> None:
        """Set the handler for processing voice commands."""
        self._command_handler = handler

    def set_speak_handler(self, handler: Callable[[str], None]) -> None:
        """Set the handler for speaking responses."""
        self._speak_handler = handler

    def start(self) -> bool:
        """Start wake word detection."""
        if self._listener and self._listener.is_running():
            return True

        self._listener = WakeWordListener(on_wake=self._handle_wake)
        return self._listener.start()

    def stop(self) -> None:
        """Stop wake word detection."""
        if self._listener:
            self._listener.stop()
            self._listener = None

    def is_running(self) -> bool:
        """Check if wake word detection is running."""
        return self._listener is not None and self._listener.is_running()

    def _handle_wake(self, initial_command: str) -> None:
        """Handle wake word detection."""
        try:
            # Acknowledge wake
            if self._speak_handler:
                self._speak_handler("Yes?")

            # Get command - use initial if provided, otherwise listen
            if initial_command:
                command = initial_command
            else:
                # Listen for command
                command = self._listener.listen_for_command() if self._listener else ""

            if not command:
                if self._speak_handler:
                    self._speak_handler("I didn't catch that. Please try again.")
                return

            logger.info(f"Processing command: {command}")

            # Process command
            if self._command_handler:
                response = self._command_handler(command)
                if response and self._speak_handler:
                    self._speak_handler(response)
            else:
                logger.warning("No command handler configured")

        except Exception as e:
            logger.error(f"Error handling wake: {e}")


def create_default_manager() -> WakeWordManager:
    """Create a WakeWordManager with default Jarvis integration."""
    manager = WakeWordManager()

    # Try to set up default handlers
    try:
        from core import voice, conversation

        # Set up speak handler using voice module
        def speak(text: str) -> None:
            voice.speak_text(text)

        manager.set_speak_handler(speak)

        # Set up command handler
        def handle_command(text: str) -> str:
            # Try voice command parsing first
            cmd = voice.parse_command(text)
            if cmd:
                return voice.handle_command(cmd)

            # Fall back to conversation
            return conversation.generate_response(
                text,
                screen_context="",
                conversation_history=None,
                channel="voice",
            )

        manager.set_command_handler(handle_command)

    except ImportError as e:
        logger.warning(f"Could not set up default handlers: {e}")

    return manager


# Global manager instance
_manager: Optional[WakeWordManager] = None


def get_manager() -> WakeWordManager:
    """Get the global wake word manager."""
    global _manager
    if _manager is None:
        _manager = create_default_manager()
    return _manager


def start_listening() -> bool:
    """Start wake word listening with default configuration."""
    return get_manager().start()


def stop_listening() -> None:
    """Stop wake word listening."""
    get_manager().stop()


def is_listening() -> bool:
    """Check if wake word detection is active."""
    return get_manager().is_running()


# CLI entry point
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    print("=" * 50)
    print("Jarvis Wake Word Test")
    print("Say 'Hey Jarvis' followed by a command")
    print("Press Ctrl+C to exit")
    print("=" * 50)

    def on_wake(command: str):
        print(f"\n>>> Wake detected! Command: '{command}'")

    listener = WakeWordListener(on_wake=on_wake)

    if not listener.start():
        print("Failed to start wake word listener")
        sys.exit(1)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
        listener.stop()
