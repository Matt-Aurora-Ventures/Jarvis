"""
PersonaPlex Integration for Jarvis Voice System
================================================

This module provides the integration between PersonaPlex-7B and Jarvis's
existing voice infrastructure (core/voice.py).

Add these functions to core/voice.py to enable PersonaPlex support.
"""

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _personaplex_configured(voice_cfg: dict) -> bool:
    """Check if PersonaPlex is configured and available."""
    engine = str(voice_cfg.get("tts_engine", "")).lower()
    if engine == "personaplex":
        return True

    # Check if personaplex is explicitly enabled
    personaplex_cfg = voice_cfg.get("personaplex", {})
    return personaplex_cfg.get("enabled", False)


def _get_personaplex_persona(voice_cfg: dict):
    """Get PersonaConfig based on voice configuration."""
    try:
        from core.personaplex_engine import (
            PersonaConfig,
            create_jarvis_persona,
            create_morgan_freeman_persona,
        )

        personaplex_cfg = voice_cfg.get("personaplex", {})
        persona_name = personaplex_cfg.get("persona", "jarvis").lower()

        # Use predefined personas
        if persona_name == "jarvis":
            return create_jarvis_persona()
        elif persona_name == "morgan_freeman":
            return create_morgan_freeman_persona()
        elif persona_name == "custom":
            # Custom persona from config
            custom = personaplex_cfg.get("custom_persona", {})
            return PersonaConfig(
                role_prompt=custom.get("role_prompt", "You are a helpful assistant."),
                voice_prompt=custom.get("voice_prompt"),
                temperature=float(custom.get("temperature", 0.7)),
                max_tokens=int(custom.get("max_tokens", 256)),
                interrupt_threshold=float(custom.get("interrupt_threshold", 0.5)),
            )
        else:
            # Default to Jarvis
            return create_jarvis_persona()

    except ImportError as e:
        logger.error(f"PersonaPlex not available: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to get PersonaPlex persona: {e}")
        return None


def _speak_with_personaplex(text: str, voice_cfg: dict) -> bool:
    """
    Speak using PersonaPlex-7B full-duplex engine.

    This replaces the traditional TTS pipeline with end-to-end
    speech generation from the PersonaPlex model.
    """
    try:
        from core.personaplex_engine import get_engine

        engine = get_engine()
        if not engine or not engine.is_initialized:
            logger.warning("PersonaPlex engine not initialized")
            _set_voice_error("PersonaPlex engine not available")
            return False

        # Get persona configuration
        persona = _get_personaplex_persona(voice_cfg)
        if persona:
            engine.set_persona(persona)

        # Generate speech
        output_path = engine.synthesize_speech(
            text=text,
            output_path=Path(tempfile.mktemp(suffix=".wav")),
        )

        if not output_path or not output_path.exists():
            logger.error("PersonaPlex speech synthesis failed")
            _set_voice_error("PersonaPlex synthesis failed")
            return False

        # Play audio
        try:
            subprocess.run(
                ["afplay", str(output_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
                timeout=30,
            )
            success = True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.error(f"Audio playback failed: {e}")
            success = False
        finally:
            # Cleanup temp file
            try:
                output_path.unlink(missing_ok=True)
            except Exception:
                pass

        return success

    except ImportError:
        logger.error("PersonaPlex module not available")
        _set_voice_error("PersonaPlex not installed")
        return False
    except Exception as e:
        logger.error(f"PersonaPlex TTS error: {e}")
        _set_voice_error(f"PersonaPlex error: {e}")
        return False


def _start_personaplex_process(text: str, voice_cfg: dict) -> Optional[subprocess.Popen]:
    """
    Start PersonaPlex speech synthesis as a subprocess (for barge-in support).

    This enables the barge-in feature where users can interrupt Jarvis
    mid-sentence using the wake word.
    """
    try:
        from core.personaplex_engine import get_engine

        engine = get_engine()
        if not engine or not engine.is_initialized:
            logger.warning("PersonaPlex engine not initialized")
            return None

        # Get persona
        persona = _get_personaplex_persona(voice_cfg)
        if persona:
            engine.set_persona(persona)

        # Generate speech to temp file
        output_path = engine.synthesize_speech(
            text=text,
            output_path=Path(tempfile.mktemp(suffix=".wav")),
        )

        if not output_path or not output_path.exists():
            logger.error("PersonaPlex synthesis failed")
            return None

        # Start playback as subprocess
        proc = subprocess.Popen(
            ["afplay", str(output_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Set active speech with cleanup callback
        _set_active_speech(
            proc,
            cleanup=lambda: Path(output_path).unlink(missing_ok=True)
        )

        return proc

    except Exception as e:
        logger.error(f"PersonaPlex process start failed: {e}")
        return None


def _personaplex_full_duplex_mode(voice_cfg: dict) -> bool:
    """Check if PersonaPlex full-duplex mode is enabled."""
    personaplex_cfg = voice_cfg.get("personaplex", {})
    return personaplex_cfg.get("full_duplex", False)


def _run_personaplex_full_duplex_session(voice_cfg: dict) -> None:
    """
    Run a full-duplex conversation session using PersonaPlex.

    This is the revolutionary mode where PersonaPlex can listen and speak
    simultaneously, enabling natural conversation flow with:
    - Instant responses (170ms latency)
    - Natural interruptions (240ms detection)
    - Backchanneling (uh-huh, yeah, etc.)
    - Seamless turn-taking
    """
    try:
        import numpy as np
        import sounddevice as sd
        from core.personaplex_engine import get_engine

        engine = get_engine()
        if not engine or not engine.is_initialized:
            logger.error("PersonaPlex engine not available for full-duplex")
            return

        # Set persona
        persona = _get_personaplex_persona(voice_cfg)
        if persona:
            engine.set_persona(persona)

        print("[PersonaPlex Full-Duplex Mode]")
        print("Listening and speaking simultaneously...")
        print("Say 'goodbye' or 'stop' to end session.")
        print("-" * 50)

        # Audio callback for output
        def audio_callback(output_audio: np.ndarray):
            """Play generated audio through speakers."""
            sd.play(output_audio, samplerate=24000)
            sd.wait()

        # Start full-duplex session
        engine.start_full_duplex_session(audio_callback)

        # Stream audio from microphone
        try:
            with sd.InputStream(samplerate=24000, channels=1, dtype='float32') as stream:
                while True:
                    audio_chunk, overflowed = stream.read(1280)  # ~50ms chunks

                    if overflowed:
                        logger.warning("Audio buffer overflow")

                    # Process audio through PersonaPlex
                    output = engine.process_audio_stream(
                        audio_chunk.flatten(),
                        sample_rate=24000
                    )

                    if output is not None:
                        audio_callback(output)

                    # Check for session end (implement your own logic)
                    # For now, runs indefinitely until interrupted

        except KeyboardInterrupt:
            print("\n[Full-Duplex Session Ended]")
        finally:
            engine.stop_full_duplex_session()

    except ImportError as e:
        logger.error(f"Missing dependencies for full-duplex: {e}")
        logger.info("Install: pip install sounddevice numpy")
    except Exception as e:
        logger.error(f"Full-duplex session error: {e}")


# Integration points for core/voice.py

def integrate_personaplex_into_voice_module():
    """
    Integration instructions for core/voice.py.

    Add the following code snippets to core/voice.py:
    """

    # 1. Import PersonaPlex integration at the top
    IMPORT_BLOCK = '''
    try:
        from core.voice_personaplex_integration import (
            _personaplex_configured,
            _speak_with_personaplex,
            _start_personaplex_process,
            _personaplex_full_duplex_mode,
            _run_personaplex_full_duplex_session,
        )
        PERSONAPLEX_AVAILABLE = True
    except ImportError:
        PERSONAPLEX_AVAILABLE = False
    '''

    # 2. Add PersonaPlex to _speak() function (around line 906)
    SPEAK_INTEGRATION = '''
    def _speak(text: str) -> None:
        voice_cfg = _voice_cfg()
        if not voice_cfg.get("speak_responses", False):
            return
        _stop_active_speech()

        engine = str(voice_cfg.get("tts_engine", "piper")).lower()
        clone_engine = engine in ("voice_clone", "xtts", "clone")
        spoke = False

        # Try PersonaPlex first if configured
        if PERSONAPLEX_AVAILABLE and _personaplex_configured(voice_cfg):
            spoke = _speak_with_personaplex(text, voice_cfg)
            if spoke:
                _remember_spoken(text)
                return

        # Try OpenAI TTS first if configured
        if engine == "openai_tts":
            spoke = _speak_with_openai_tts(text, voice_cfg)
            if spoke:
                _remember_spoken(text)
                return

        # ... rest of the function
    '''

    # 3. Add PersonaPlex to _speak_with_barge_in() (around line 946)
    BARGE_IN_INTEGRATION = '''
    def _speak_with_barge_in(text: str, voice_cfg: dict) -> Optional[str]:
        if not voice_cfg.get("speak_responses", False):
            return None
        if not voice_cfg.get("barge_in_enabled", True):
            _speak(text)
            return None

        engine = str(voice_cfg.get("tts_engine", "piper")).lower()
        clone_engine = engine in ("voice_clone", "xtts", "clone")
        proc: Optional[subprocess.Popen] = None

        # Try PersonaPlex first if configured
        if PERSONAPLEX_AVAILABLE and _personaplex_configured(voice_cfg):
            proc = _start_personaplex_process(text, voice_cfg)
            if proc:
                _remember_spoken(text)

        # Try OpenAI TTS first if configured
        if not proc and engine == "openai_tts":
            proc = _start_openai_tts_process(text, voice_cfg)
            if proc:
                _remember_spoken(text)

        # ... rest of the function
    '''

    # 4. Add PersonaPlex to run_voice_diagnostics() (around line 100)
    DIAGNOSTICS_INTEGRATION = '''
    def run_voice_diagnostics() -> VoiceDiagnostics:
        diag = VoiceDiagnostics()
        voice_cfg = _voice_cfg()

        # ... existing checks ...

        # Check PersonaPlex
        if voice_cfg.get("tts_engine") == "personaplex":
            try:
                from core.personaplex_engine import get_engine
                engine = get_engine()
                if engine and engine.is_initialized:
                    health = engine.check_health()
                    if health.get("cuda_available"):
                        diag.tts_available = True
                        diag.tts_engine = "personaplex"
                    else:
                        diag.tts_error = "PersonaPlex requires CUDA GPU"
                else:
                    diag.tts_error = "PersonaPlex initialization failed"
            except ImportError:
                diag.tts_error = "PersonaPlex not installed"
            except Exception as e:
                diag.tts_error = f"PersonaPlex check failed: {e}"

        # ... rest of diagnostics ...
    '''

    return {
        "import_block": IMPORT_BLOCK,
        "speak_integration": SPEAK_INTEGRATION,
        "barge_in_integration": BARGE_IN_INTEGRATION,
        "diagnostics_integration": DIAGNOSTICS_INTEGRATION,
    }


if __name__ == "__main__":
    # Print integration instructions
    instructions = integrate_personaplex_into_voice_module()
    print("=" * 70)
    print("PersonaPlex Integration Instructions for core/voice.py")
    print("=" * 70)
    print("\n1. ADD IMPORTS (top of file):")
    print(instructions["import_block"])
    print("\n2. UPDATE _speak() function:")
    print(instructions["speak_integration"])
    print("\n3. UPDATE _speak_with_barge_in() function:")
    print(instructions["barge_in_integration"])
    print("\n4. UPDATE run_voice_diagnostics() function:")
    print(instructions["diagnostics_integration"])
    print("\n" + "=" * 70)
    print("See docs/personaplex_setup.md for complete setup guide")
    print("=" * 70)
