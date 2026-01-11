import difflib
import gzip
import io
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import requests

from core import (
    config,
    conversation,
    evolution,
    context_manager,
    memory,
    notes_manager,
    observation,
    providers,
    secrets,
    skill_manager,
    state,
    system_profiler,
)

VOICES_DIR = Path(__file__).resolve().parents[1] / "data" / "voices"
DEFAULT_PIPER_MODEL = "en_US-lessac-medium.onnx"
DEFAULT_PIPER_URL = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US-lessac-medium.onnx.gz"
)
PIPER_BINARY = "piper"

_LAST_SPOKEN_AT = 0.0
_LAST_SPOKEN_TEXT = ""
_LAST_SPOKEN_LOCK = threading.Lock()
_ACTIVE_SPEECH_PROCESS: Optional[subprocess.Popen] = None
_ACTIVE_SPEECH_CLEANUP: Optional[Callable[[], None]] = None
_ACTIVE_SPEECH_LOCK = threading.Lock()
_CHAT_LOCK_PATH = state.LOGS_DIR / "voice_chat.lock"
_SAY_VOICES_CACHE: Optional[set[str]] = None
_SAY_VOICES_LOCK = threading.Lock()
_FASTER_WHISPER_MODEL = None
_FASTER_WHISPER_LOCK = threading.Lock()


@dataclass
class VoiceCommand:
    action: str
    payload: str


@dataclass
class VoiceDiagnostics:
    """Results from voice system diagnostics."""
    microphone_available: bool = False
    microphone_error: str = ""
    tts_engine: str = ""
    tts_available: bool = False
    tts_error: str = ""
    stt_engine: str = ""
    stt_available: bool = False
    stt_error: str = ""
    wake_word_available: bool = False
    wake_word_error: str = ""
    overall_status: str = "unknown"

    def to_report(self) -> str:
        """Generate human-readable diagnostics report."""
        lines = ["🎙️ VOICE SYSTEM DIAGNOSTICS", "=" * 40]

        # Microphone
        mic_status = "✅" if self.microphone_available else "❌"
        lines.append(f"{mic_status} Microphone: {'OK' if self.microphone_available else self.microphone_error}")

        # TTS
        tts_status = "✅" if self.tts_available else "❌"
        lines.append(f"{tts_status} TTS ({self.tts_engine}): {'OK' if self.tts_available else self.tts_error}")

        # STT
        stt_status = "✅" if self.stt_available else "❌"
        lines.append(f"{stt_status} STT ({self.stt_engine}): {'OK' if self.stt_available else self.stt_error}")

        # Wake Word
        wake_status = "✅" if self.wake_word_available else "⚠️"
        lines.append(f"{wake_status} Wake Word: {'OK' if self.wake_word_available else self.wake_word_error}")

        lines.append("=" * 40)
        lines.append(f"Overall: {self.overall_status}")

        return "\n".join(lines)


def run_voice_diagnostics() -> VoiceDiagnostics:
    """Run comprehensive voice system diagnostics.

    Checks:
    - Microphone availability and permissions
    - TTS engine availability
    - STT engine availability
    - Wake word model availability

    Returns:
        VoiceDiagnostics with detailed status
    """
    diag = VoiceDiagnostics()
    voice_cfg = _voice_cfg()

    # Check microphone
    try:
        import pyaudio
        pa = pyaudio.PyAudio()
        device_count = pa.get_device_count()
        input_devices = [
            pa.get_device_info_by_index(i)
            for i in range(device_count)
            if pa.get_device_info_by_index(i).get("maxInputChannels", 0) > 0
        ]
        pa.terminate()
        if input_devices:
            diag.microphone_available = True
        else:
            diag.microphone_error = "No input devices found"
    except ImportError:
        diag.microphone_error = "pyaudio not installed (pip install pyaudio)"
    except Exception as e:
        diag.microphone_error = f"Microphone check failed: {e}"

    # Check TTS
    diag.tts_engine = voice_cfg.get("tts_engine", "piper")
    try:
        if diag.tts_engine == "piper":
            if shutil.which(PIPER_BINARY):
                diag.tts_available = True
            else:
                diag.tts_error = "Piper not found (brew install piper)"
        elif diag.tts_engine == "edge_tts":
            try:
                import edge_tts
                diag.tts_available = True
            except ImportError:
                diag.tts_error = "edge_tts not installed (pip install edge-tts)"
        elif diag.tts_engine == "say":
            if shutil.which("say"):
                diag.tts_available = True
            else:
                diag.tts_error = "macOS 'say' command not available"
        else:
            diag.tts_available = True  # Assume OK for other engines
    except Exception as e:
        diag.tts_error = f"TTS check failed: {e}"

    # Check STT
    diag.stt_engine = voice_cfg.get("local_stt_engine", "faster_whisper")
    try:
        if diag.stt_engine == "faster_whisper":
            try:
                from faster_whisper import WhisperModel
                diag.stt_available = True
            except ImportError:
                diag.stt_error = "faster-whisper not installed (pip install faster-whisper)"
        elif diag.stt_engine == "whisper":
            try:
                import whisper
                diag.stt_available = True
            except ImportError:
                diag.stt_error = "openai-whisper not installed (pip install openai-whisper)"
        else:
            diag.stt_available = True  # Assume OK for cloud engines
    except Exception as e:
        diag.stt_error = f"STT check failed: {e}"

    # Check wake word
    try:
        from openwakeword.model import Model
        diag.wake_word_available = True
    except ImportError:
        diag.wake_word_error = "openwakeword not installed (pip install openwakeword)"
    except Exception as e:
        diag.wake_word_error = f"Wake word check failed: {e}"

    # Overall status
    if diag.microphone_available and diag.tts_available and diag.stt_available:
        diag.overall_status = "✅ Voice system ready"
    elif diag.tts_available:
        diag.overall_status = "⚠️ TTS only (no voice input)"
    else:
        diag.overall_status = "❌ Voice system not available"

    return diag


def _load_config() -> dict:
    return config.load_config()


def _wake_word_model_name(wake_word: str) -> str:
    wake_lower = wake_word.lower().strip()
    model_map = {
        "jarvis": "hey_jarvis",
        "hey jarvis": "hey_jarvis",
        "alexa": "alexa",
        "hey mycroft": "hey_mycroft",
        "mycroft": "hey_mycroft",
        "ok google": "ok_google",
        "hey google": "hey_google",
    }
    for key, model in model_map.items():
        if key in wake_lower:
            return model
    return "hey_jarvis"


def _voice_cfg() -> dict:
    cfg = _load_config()
    voice_cfg = cfg.get("voice", {}).copy()
    voice_cfg.setdefault("tts_engine", "piper")
    voice_cfg.setdefault("speak_responses", True)
    voice_cfg.setdefault("fallback_voices", ["Samantha", "Ava", "Allison", "Victoria", "Alex"])
    voice_cfg.setdefault("barge_in_enabled", True)
    voice_cfg.setdefault("barge_in_timeout_seconds", 3)
    voice_cfg.setdefault("barge_in_phrase_time_limit", 3)
    voice_cfg.setdefault("barge_in_wake_window_words", 1)
    voice_cfg.setdefault("voice_clone_enabled", False)
    voice_cfg.setdefault("voice_clone_language", "en")
    voice_cfg.setdefault("allow_cloud_stt", True)
    voice_cfg.setdefault("local_stt_enabled", True)
    voice_cfg.setdefault("local_stt_engine", "faster_whisper")
    voice_cfg.setdefault("local_stt_language", "en")
    voice_cfg.setdefault("local_whisper_model", "base.en")
    voice_cfg.setdefault("local_stt_device", "cpu")
    voice_cfg.setdefault("local_stt_compute_type", "int8")
    voice_cfg.setdefault("local_stt_vad_filter", True)
    voice_cfg.setdefault("vad_enabled", True)
    voice_cfg.setdefault("vad_aggressiveness", 2)
    voice_cfg.setdefault("vad_frame_ms", 30)
    voice_cfg.setdefault("vad_speech_ratio", 0.1)
    voice_cfg.setdefault(
        "morgan_freeman_voice_candidates",
        ["Reed (English (US))", "Ralph", "Fred", "Eddy (English (US))", "Daniel"],
    )
    voice_cfg.setdefault("voice_max_chars", 280)
    voice_cfg.setdefault("voice_max_sentences", 2)
    voice_cfg.setdefault("echo_window_seconds", 8.0)
    voice_cfg.setdefault("echo_similarity_threshold", 0.78)
    voice_cfg.setdefault("echo_min_chars", 12)
    return voice_cfg


def _set_voice_error(message: str) -> None:
    """Persist the latest voice error so CLI/status can surface it."""
    state.update_state(voice_error=message[:160])


def _stop_active_speech() -> None:
    global _ACTIVE_SPEECH_PROCESS, _ACTIVE_SPEECH_CLEANUP
    with _ACTIVE_SPEECH_LOCK:
        proc = _ACTIVE_SPEECH_PROCESS
        cleanup = _ACTIVE_SPEECH_CLEANUP
        _ACTIVE_SPEECH_PROCESS = None
        _ACTIVE_SPEECH_CLEANUP = None
    if proc and proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            proc.kill()
        except Exception:
            pass
    if cleanup:
        try:
            cleanup()
        except Exception:
            pass


def _set_active_speech(proc: subprocess.Popen, cleanup: Optional[Callable[[], None]] = None) -> None:
    _stop_active_speech()
    global _ACTIVE_SPEECH_PROCESS, _ACTIVE_SPEECH_CLEANUP
    with _ACTIVE_SPEECH_LOCK:
        _ACTIVE_SPEECH_PROCESS = proc
        _ACTIVE_SPEECH_CLEANUP = cleanup


def _clear_active_speech() -> None:
    global _ACTIVE_SPEECH_PROCESS, _ACTIVE_SPEECH_CLEANUP
    with _ACTIVE_SPEECH_LOCK:
        cleanup = _ACTIVE_SPEECH_CLEANUP
        _ACTIVE_SPEECH_PROCESS = None
        _ACTIVE_SPEECH_CLEANUP = None
    if cleanup:
        try:
            cleanup()
        except Exception:
            pass


def _normalize_transcript(text: str) -> str:
    return " ".join(text.lower().strip().split())


def _remember_spoken(text: str) -> None:
    global _LAST_SPOKEN_AT, _LAST_SPOKEN_TEXT
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return
    with _LAST_SPOKEN_LOCK:
        _LAST_SPOKEN_AT = time.time()
        _LAST_SPOKEN_TEXT = cleaned[:2000]


def _last_spoken() -> tuple[float, str]:
    with _LAST_SPOKEN_LOCK:
        return _LAST_SPOKEN_AT, _LAST_SPOKEN_TEXT


def get_voice_runtime_status() -> dict:
    """Return runtime voice status for UI/diagnostics."""
    with _ACTIVE_SPEECH_LOCK:
        proc = _ACTIVE_SPEECH_PROCESS
    speaking = bool(proc and proc.poll() is None)
    last_at, last_text = _last_spoken()
    return {
        "speaking": speaking,
        "last_spoken_at": last_at,
        "last_spoken_text": last_text,
    }


def speak_text(text: str) -> bool:
    """Speak text using the configured TTS engine."""
    if not text:
        return False
    _speak(text)
    return True


def _is_self_echo(text: str, voice_cfg: dict) -> bool:
    normalized = _normalize_transcript(text)
    min_chars = int(voice_cfg.get("echo_min_chars", 12))
    if len(normalized) < min_chars:
        return False

    last_at, last_text = _last_spoken()
    if not last_text:
        return False
    window = float(voice_cfg.get("echo_window_seconds", 8.0))
    if window and (time.time() - last_at) > window:
        return False

    last_norm = _normalize_transcript(last_text)
    if not last_norm:
        return False

    if normalized in last_norm or last_norm in normalized:
        return True

    threshold = float(voice_cfg.get("echo_similarity_threshold", 0.78))
    similarity = difflib.SequenceMatcher(None, normalized, last_norm).ratio()
    return similarity >= threshold


def _speech_rate_for_voice(voice_cfg: dict) -> Optional[int]:
    rate = voice_cfg.get("speech_rate")
    voice_name = str(voice_cfg.get("speech_voice", "")).strip().lower()
    if voice_name == "morgan freeman":
        mf_rate = voice_cfg.get("morgan_freeman_rate")
        if isinstance(mf_rate, (int, float)) and mf_rate:
            rate = mf_rate
    if isinstance(rate, (int, float)) and rate:
        return int(rate)
    return None


def _available_say_voices() -> set[str]:
    global _SAY_VOICES_CACHE
    with _SAY_VOICES_LOCK:
        if _SAY_VOICES_CACHE is not None:
            return _SAY_VOICES_CACHE
        try:
            result = subprocess.run(
                ["say", "-v", "?"],
                capture_output=True,
                text=True,
                check=False,
                timeout=3,
            )
        except (subprocess.TimeoutExpired, Exception):
            _SAY_VOICES_CACHE = set()
            return _SAY_VOICES_CACHE

        voices = set()
        for line in (result.stdout or "").splitlines():
            parts = line.strip().split()
            if parts:
                voices.add(parts[0])
        _SAY_VOICES_CACHE = voices
        return voices


def _test_say_voice(name: str) -> bool:
    try:
        result = subprocess.run(
            ["say", "-v", name, "test"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=3,
        )
    except subprocess.TimeoutExpired:
        return False
    lowered = (result.stderr or "").lower()
    if result.returncode != 0:
        return False
    if "not found" in lowered or "not available" in lowered or "voice wasn" in lowered:
        return False
    return True


def _trim_voice_output(text: str, voice_cfg: dict) -> str:
    if not text:
        return text
    max_chars = int(voice_cfg.get("voice_max_chars", 280))
    max_sentences = int(voice_cfg.get("voice_max_sentences", 2))

    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    if max_sentences > 0:
        parts = parts[:max_sentences]
    cleaned = " ".join(parts).strip()
    if max_chars > 0 and len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].rsplit(" ", 1)[0].rstrip() + "..."
    return cleaned


def _normalize_wake_text(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9\\s]", " ", text.lower())
    return " ".join(cleaned.split())


def _match_wake_word(text: str, wake_words: list[str], max_offset_words: int) -> Optional[str]:
    normalized = _normalize_wake_text(text)
    if not normalized:
        return None
    tokens = normalized.split()
    if not tokens:
        return None
    max_offset = max(0, min(max_offset_words, len(tokens)))
    for wake_word in wake_words:
        wake_norm = _normalize_wake_text(wake_word)
        if not wake_norm:
            continue
        wake_tokens = wake_norm.split()
        if not wake_tokens:
            continue
        for idx in range(0, max_offset + 1):
            end = idx + len(wake_tokens)
            if end > len(tokens):
                continue
            if tokens[idx:end] == wake_tokens:
                command_tokens = tokens[end:]
                return " ".join(command_tokens).strip()
    return None


def _load_faster_whisper(voice_cfg: dict):
    global _FASTER_WHISPER_MODEL
    with _FASTER_WHISPER_LOCK:
        if _FASTER_WHISPER_MODEL is not None:
            return _FASTER_WHISPER_MODEL
        try:
            from faster_whisper import WhisperModel
        except Exception:
            return None
        model_name = str(voice_cfg.get("local_whisper_model", "base.en")).strip() or "base.en"
        device = str(voice_cfg.get("local_stt_device", "cpu")).strip() or "cpu"
        compute = str(voice_cfg.get("local_stt_compute_type", "int8")).strip() or "int8"
        try:
            _FASTER_WHISPER_MODEL = WhisperModel(model_name, device=device, compute_type=compute)
            return _FASTER_WHISPER_MODEL
        except Exception as exc:
            _set_voice_error(f"faster-whisper init failed: {exc}")
            return None


def _transcribe_with_faster_whisper(audio, voice_cfg: dict) -> str:
    model = _load_faster_whisper(voice_cfg)
    if model is None:
        return ""
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio.get_wav_data(convert_rate=16000, convert_width=2))
            temp_path = f.name
        language = str(voice_cfg.get("local_stt_language", "en")).strip() or "en"
        vad_filter = bool(voice_cfg.get("local_stt_vad_filter", True))
        segments, _ = model.transcribe(
            temp_path,
            language=language,
            vad_filter=vad_filter,
        )
        text = " ".join(seg.text.strip() for seg in segments if seg.text.strip())
        return text.strip()
    except Exception as exc:
        _set_voice_error(f"faster-whisper failed: {exc}")
        return ""
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except Exception:
                pass


def _has_speech_vad(audio, voice_cfg: dict) -> bool:
    if not bool(voice_cfg.get("vad_enabled", True)):
        return True
    try:
        import webrtcvad
    except Exception:
        return True

    aggressiveness = int(voice_cfg.get("vad_aggressiveness", 2))
    aggressiveness = max(0, min(3, aggressiveness))
    frame_ms = int(voice_cfg.get("vad_frame_ms", 30))
    if frame_ms not in (10, 20, 30):
        frame_ms = 30
    speech_ratio = float(voice_cfg.get("vad_speech_ratio", 0.1))
    speech_ratio = max(0.0, min(1.0, speech_ratio))

    sample_rate = 16000
    raw = audio.get_raw_data(convert_rate=sample_rate, convert_width=2)
    if not raw:
        return True
    frame_bytes = int(sample_rate * (frame_ms / 1000.0) * 2)
    if frame_bytes <= 0:
        return True

    vad = webrtcvad.Vad(aggressiveness)
    speech_frames = 0
    total_frames = 0
    for i in range(0, len(raw) - frame_bytes + 1, frame_bytes):
        frame = raw[i : i + frame_bytes]
        if len(frame) < frame_bytes:
            continue
        total_frames += 1
        if vad.is_speech(frame, sample_rate):
            speech_frames += 1

    if total_frames == 0:
        return True
    return (speech_frames / total_frames) >= speech_ratio


def _speak_with_openai_tts(text: str, voice_cfg: dict) -> bool:
    """Speak using OpenAI TTS."""
    try:
        from core import openai_tts
        
        voice = voice_cfg.get("openai_tts_voice", "alloy")
        model = voice_cfg.get("openai_tts_model", "tts-1")
        
        return openai_tts.speak_openai_tts(text, voice=voice, model=model)
    except Exception as e:
        _set_voice_error(f"OpenAI TTS failed: {e}")
        return False


def _start_openai_tts_process(text: str, voice_cfg: dict) -> Optional[subprocess.Popen]:
    """Start OpenAI TTS as subprocess for barge-in."""
    try:
        from core import openai_tts
        
        voice = voice_cfg.get("openai_tts_voice", "alloy")
        model = voice_cfg.get("openai_tts_model", "tts-1")
        
        result = openai_tts.speak_openai_tts_process(text, voice=voice, model=model)
        if not result or result[0] is None:
            return None
        
        proc, temp_path = result
        
        # Set active speech with cleanup callback
        _set_active_speech(proc, cleanup=lambda: Path(temp_path).unlink(missing_ok=True))
        return proc
        
    except Exception as e:
        _set_voice_error(f"OpenAI TTS process failed: {e}")
        return None


def _say_voice_candidates(voice_cfg: dict) -> list[str]:
    voice_name = str(voice_cfg.get("speech_voice", "")).strip()
    fallback_voices = voice_cfg.get("fallback_voices", [])
    if isinstance(fallback_voices, str):
        fallback_voices = [fallback_voices]

    candidates: list[str] = []
    seen = set()

    def _add(name: str) -> None:
        cleaned = str(name).strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            candidates.append(cleaned)

    if voice_name:
        if voice_name.lower() == "morgan freeman":
            preferred = str(voice_cfg.get("morgan_freeman_voice", "")).strip()
            if preferred:
                _add(preferred)
            mf_candidates = voice_cfg.get("morgan_freeman_voice_candidates", [])
            if isinstance(mf_candidates, str):
                mf_candidates = [mf_candidates]
            for candidate in mf_candidates:
                _add(candidate)
        else:
            _add(voice_name)

    for fallback in fallback_voices:
        _add(fallback)

    return candidates


def _select_say_voice(voice_cfg: dict) -> str:
    available = _available_say_voices()
    for candidate in _say_voice_candidates(voice_cfg):
        if available and candidate in available:
            return candidate
        if not available and _test_say_voice(candidate):
            return candidate
    return ""


def resolve_say_voice(requested: str = "") -> str:
    """Pick a valid macOS say() voice or return empty for default."""
    voice_cfg = _voice_cfg()
    if requested:
        voice_cfg = dict(voice_cfg)
        voice_cfg["speech_voice"] = requested
    return _select_say_voice(voice_cfg)


def _start_say_process(text: str, voice_cfg: dict) -> Optional[subprocess.Popen]:
    try:
        voice_name = _select_say_voice(voice_cfg)
        cmd = ["say"]
        if voice_name:
            cmd.extend(["-v", voice_name])
        speech_rate = _speech_rate_for_voice(voice_cfg)
        if speech_rate:
            cmd.extend(["-r", str(speech_rate)])
        cmd.append(text)
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _set_active_speech(proc)
        return proc
    except Exception as exc:
        _set_voice_error(f"macOS say failed: {exc}")
        return None


def _voice_clone_configured(voice_cfg: dict) -> bool:
    engine = str(voice_cfg.get("tts_engine", "")).lower()
    if engine in ("voice_clone", "xtts", "clone"):
        return True
    if not voice_cfg.get("voice_clone_enabled", False):
        return False
    if str(voice_cfg.get("voice_clone_voice", "")).strip():
        return True
    return str(voice_cfg.get("speech_voice", "")).strip().lower() == "morgan freeman"


def _voice_clone_voice_name(voice_cfg: dict) -> str:
    configured = str(voice_cfg.get("voice_clone_voice", "")).strip()
    if configured:
        return configured
    if str(voice_cfg.get("speech_voice", "")).strip().lower() == "morgan freeman":
        return "morgan_freeman"
    return ""


def _start_voice_clone_process(text: str, voice_cfg: dict) -> Optional[subprocess.Popen]:
    if not _voice_clone_configured(voice_cfg):
        return None
    voice_name = _voice_clone_voice_name(voice_cfg)
    if not voice_name:
        _set_voice_error("Voice clone enabled but no reference voice configured.")
        return None
    try:
        from core import voice_clone
    except Exception as exc:
        _set_voice_error(f"Voice clone unavailable: {exc}")
        return None

    reference = voice_clone.get_reference_audio(voice_name)
    if reference is None:
        _set_voice_error(f"Voice clone reference not found: {voice_name}")
        return None

    output_path = Path(tempfile.mkstemp(suffix=".wav")[1])
    language = str(voice_cfg.get("voice_clone_language", "en")).strip() or "en"
    result = voice_clone.clone_voice_tts(
        text=text,
        reference_audio=reference,
        output_path=output_path,
        language=language,
    )
    if not result or not Path(result).exists():
        _set_voice_error("Voice clone generation failed.")
        output_path.unlink(missing_ok=True)
        return None

    try:
        proc = subprocess.Popen(
            ["afplay", str(result)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        _set_voice_error(f"Audio playback failed: {exc}")
        Path(result).unlink(missing_ok=True)
        return None

    _set_active_speech(proc, cleanup=lambda: Path(result).unlink(missing_ok=True))
    return proc


def _speak_with_voice_clone(text: str, voice_cfg: dict) -> bool:
    proc = _start_voice_clone_process(text, voice_cfg)
    if not proc:
        return False
    try:
        proc.wait()
    finally:
        _clear_active_speech()
    return proc.returncode == 0


def _ensure_piper_model(voice_cfg: dict) -> Optional[Path]:
    model_path_value = voice_cfg.get("piper_model_path")
    if model_path_value:
        model_path = Path(model_path_value).expanduser()
    else:
        model_name = voice_cfg.get("piper_model", DEFAULT_PIPER_MODEL)
        model_path = VOICES_DIR / model_name
    if model_path.exists():
        return model_path

    download_url = voice_cfg.get("piper_download_url", DEFAULT_PIPER_URL)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        response = requests.get(download_url, timeout=120)
        response.raise_for_status()
        data = response.content
        if download_url.endswith(".gz"):
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as gz:
                with open(model_path, "wb") as handle:
                    shutil.copyfileobj(gz, handle)
        else:
            with open(model_path, "wb") as handle:
                handle.write(data)
    except Exception as exc:
        print(f"Failed to download Piper model: {exc}")
        return None
    return model_path


def _speak_with_piper(text: str, voice_cfg: dict) -> bool:
    model_path = _ensure_piper_model(voice_cfg)
    if not model_path:
        _set_voice_error("Missing Piper model; falling back to macOS say.")
        return False
    if shutil.which(PIPER_BINARY) is None:
        _set_voice_error("Piper binary not found in PATH; install piper.")
        return False
    tmp_wav = Path(tempfile.mkstemp(suffix=".wav")[1])
    cmd = [
        PIPER_BINARY,
        "--model",
        str(model_path),
        "--output_file",
        str(tmp_wav),
    ]
    speaker = voice_cfg.get("piper_speaker")
    if speaker:
        cmd.extend(["--speaker", str(speaker)])
    try:
        subprocess.run(
            cmd,
            input=text.encode("utf-8"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        subprocess.run(
            ["afplay", str(tmp_wav)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        _set_voice_error(f"Piper TTS failed: {exc}")
        return False
    finally:
        if tmp_wav.exists():
            tmp_wav.unlink(missing_ok=True)


def _start_piper_process(text: str, voice_cfg: dict) -> Optional[subprocess.Popen]:
    model_path = _ensure_piper_model(voice_cfg)
    if not model_path:
        _set_voice_error("Missing Piper model; falling back to macOS say.")
        return None
    if shutil.which(PIPER_BINARY) is None:
        _set_voice_error("Piper binary not found in PATH; install piper.")
        return None
    tmp_wav = Path(tempfile.mkstemp(suffix=".wav")[1])
    cmd = [
        PIPER_BINARY,
        "--model",
        str(model_path),
        "--output_file",
        str(tmp_wav),
    ]
    speaker = voice_cfg.get("piper_speaker")
    if speaker:
        cmd.extend(["--speaker", str(speaker)])
    try:
        subprocess.run(
            cmd,
            input=text.encode("utf-8"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        _set_voice_error(f"Piper TTS failed: {exc}")
        tmp_wav.unlink(missing_ok=True)
        return None

    try:
        proc = subprocess.Popen(
            ["afplay", str(tmp_wav)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        _set_voice_error(f"Audio playback failed: {exc}")
        tmp_wav.unlink(missing_ok=True)
        return None

    _set_active_speech(proc, cleanup=lambda: tmp_wav.unlink(missing_ok=True))
    return proc


def _speak_with_say(text: str, voice_cfg: dict) -> bool:
    speech_rate = _speech_rate_for_voice(voice_cfg)

    def _run_say(name: str = "") -> bool:
        cmd = ["say"]
        if name:
            cmd.extend(["-v", name])
        if speech_rate:
            cmd.extend(["-r", str(speech_rate)])
        try:
            subprocess.run(
                cmd,
                input=text,
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False

    try:
        candidates = _say_voice_candidates(voice_cfg)
        for candidate in candidates:
            if _test_say_voice(candidate) and _run_say(candidate):
                _set_voice_error("")
                return True

        success = _run_say()
        if success:
            _set_voice_error("")
        return success
    except Exception as exc:
        _set_voice_error(f"macOS say failed: {exc}")
        return False


def _speak(text: str) -> None:
    voice_cfg = _voice_cfg()
    if not voice_cfg.get("speak_responses", False):
        return
    _stop_active_speech()

    engine = str(voice_cfg.get("tts_engine", "piper")).lower()
    clone_engine = engine in ("voice_clone", "xtts", "clone")
    spoke = False
    
    # Try OpenAI TTS first if configured
    if engine == "openai_tts":
        spoke = _speak_with_openai_tts(text, voice_cfg)
        if spoke:
            _remember_spoken(text)
            return
    
    # Try voice clone
    if _voice_clone_configured(voice_cfg):
        spoke = _speak_with_voice_clone(text, voice_cfg)
        if spoke:
            _remember_spoken(text)
            return
        if clone_engine:
            engine = "say"
    
    # Fallback engines
    if engine == "piper":
        spoke = _speak_with_piper(text, voice_cfg)
    elif engine == "say":
        spoke = _speak_with_say(text, voice_cfg)
    else:
        _set_voice_error(f"Unsupported TTS engine '{engine}', falling back to say().")
    if not spoke:
        # Final fallback
        spoke = _speak_with_say(text, voice_cfg)
    if spoke:
        _remember_spoken(text)


def _speak_with_barge_in(text: str, voice_cfg: dict) -> Optional[str]:
    if not voice_cfg.get("speak_responses", False):
        return None
    if not voice_cfg.get("barge_in_enabled", True):
        _speak(text)
        return None

    engine = str(voice_cfg.get("tts_engine", "piper")).lower()
    clone_engine = engine in ("voice_clone", "xtts", "clone")
    proc: Optional[subprocess.Popen] = None
    
    # Try OpenAI TTS first if configured
    if engine == "openai_tts":
        proc = _start_openai_tts_process(text, voice_cfg)
        if proc:
            _remember_spoken(text)
    
    # Try voice clone
    if not proc and _voice_clone_configured(voice_cfg):
        proc = _start_voice_clone_process(text, voice_cfg)
        if proc:
            _remember_spoken(text)
        elif clone_engine:
            engine = "say"
    
    # Fallback engines
    if not proc and engine == "piper":
        proc = _start_piper_process(text, voice_cfg)
    elif not proc and engine == "say":
        proc = _start_say_process(text, voice_cfg)
    elif not proc:
        _set_voice_error(f"Unsupported TTS engine '{engine}', falling back to say().")
        _speak(text)
        return None

    if not proc:
        _speak(text)
        return None

    _remember_spoken(text)
    barge_timeout = int(voice_cfg.get("barge_in_timeout_seconds", 3))
    barge_phrase = int(voice_cfg.get("barge_in_phrase_time_limit", 3))
    barge_timeout = max(1, barge_timeout)
    barge_phrase = max(1, barge_phrase)
    
    # Get wake word for barge-in detection
    cfg = _load_config()
    wake_word = cfg.get("voice", {}).get("wake_word", "jarvis").lower()
    max_wake_offset = int(voice_cfg.get("barge_in_wake_window_words", 1))
    
    # Print barge-in status for debugging
    print(f"[Barge-in active - say '{wake_word}' to interrupt]")

    try:
        while proc.poll() is None:
            interrupt = _transcribe_once(timeout=barge_timeout, phrase_time_limit=barge_phrase)
            if interrupt:
                wake_words = [wake_word, "jarvis", "hey jarvis"]
                command_text = _match_wake_word(interrupt, wake_words, max_wake_offset)
                if command_text is not None:
                    print(f"[Barge-in detected: '{interrupt}']")
                    _stop_active_speech()
                    return command_text or None

                if _is_self_echo(interrupt, voice_cfg):
                    print(f"[Ignored self-echo: '{interrupt[:30]}...']")
                    continue

                print(f"[Ignored non-wake-word: '{interrupt[:30]}']")
                # Else: ignore non-wake-word speech, keep playing
    finally:
        if proc.poll() is None:
            _stop_active_speech()
        else:
            _clear_active_speech()
    return None


def _transcribe_once(timeout: int, phrase_time_limit: int) -> str:
    try:
        import speech_recognition as sr
    except Exception as e:
        return ""

    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            audio = recognizer.listen(
                source, timeout=timeout, phrase_time_limit=phrase_time_limit
            )
    except Exception as e:
        return ""

    voice_cfg = _voice_cfg()
    if not _has_speech_vad(audio, voice_cfg):
        return ""

    local_enabled = bool(voice_cfg.get("local_stt_enabled", True))
    local_engine = str(voice_cfg.get("local_stt_engine", "faster_whisper")).strip().lower()
    if local_enabled and local_engine == "faster_whisper":
        local_text = _transcribe_with_faster_whisper(audio, voice_cfg)
        if local_text:
            return local_text

    allow_cloud = bool(voice_cfg.get("allow_cloud_stt", True))

    if allow_cloud:
        # Try Gemini STT (Multimodal)
        gemini_key = secrets.get_gemini_key()
        if gemini_key:
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    f.write(audio.get_wav_data())
                    temp_path = f.name
                
                transcript = providers.transcribe_audio_gemini(temp_path)
                os.unlink(temp_path)
                if transcript:
                    return transcript
            except Exception:
                pass

        # Try OpenAI Whisper
        openai_key = secrets.get_openai_key()
        if openai_key:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=openai_key)
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    f.write(audio.get_wav_data())
                    temp_path = f.name
                
                with open(temp_path, "rb") as audio_file:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file
                    )
                os.unlink(temp_path)
                if transcript.text:
                    return transcript.text
            except Exception:
                pass

    # Fallback to Google
    if allow_cloud:
        try:
            return recognizer.recognize_google(audio)
        except Exception:
            pass

    # Fallback to Sphinx (Last resort)
    try:
        return recognizer.recognize_sphinx(audio)
    except Exception as e:
        return ""

def _stop_phrase_match(text: str, phrase: str) -> bool:
    return phrase.strip().lower() in text.strip().lower()


def parse_command(text: str) -> Optional[VoiceCommand]:
    lower = text.strip().lower()
    if not lower:
        return None
    if "help" in lower or "commands" in lower or "what can you do" in lower:
        return VoiceCommand(action="help", payload="")
    if "stop listening" in lower:
        return VoiceCommand(action="listening_off", payload="")
    if "start listening" in lower:
        return VoiceCommand(action="listening_on", payload="")
    if lower.startswith("status") or "status" in lower:
        return VoiceCommand(action="status", payload="")
    if lower.startswith("diagnostics") or "diagnostics" in lower:
        return VoiceCommand(action="diagnostics", payload="")
    if lower.startswith("summarize") or "summarize" in lower:
        return VoiceCommand(action="summarize", payload="")
    if "overnight" in lower:
        return VoiceCommand(action="overnight", payload="")
    if "report" in lower:
        if "morning" in lower:
            return VoiceCommand(action="report_morning", payload="")
        if "afternoon" in lower:
            return VoiceCommand(action="report_afternoon", payload="")
        if "weekly" in lower:
            return VoiceCommand(action="report_weekly", payload="")
        return VoiceCommand(action="report_daily", payload="")
    if lower.startswith("log"):
        payload = lower.replace("log", "", 1).strip()
        return VoiceCommand(action="log", payload=payload)
    if lower.startswith("research") or lower.startswith("learn about"):
        payload = lower.replace("research", "", 1).strip()
        if lower.startswith("learn about"):
            payload = lower.replace("learn about", "", 1).strip()
        if payload.startswith("on "):
            payload = payload[3:].strip()
        if payload.startswith("about "):
            payload = payload[6:].strip()
        return VoiceCommand(action="research", payload=payload)
    if lower.startswith("search") or lower.startswith("look up") or lower.startswith("lookup"):
        payload = lower
        for prefix in ("search", "look up", "lookup"):
            if payload.startswith(prefix):
                payload = payload.replace(prefix, "", 1).strip()
                break
        if payload.startswith("for "):
            payload = payload[4:].strip()
        return VoiceCommand(action="web_search", payload=payload)
    if "context" in lower or "what's on screen" in lower or "what is on screen" in lower:
        return VoiceCommand(action="context", payload="")
    if (
        "improve yourself" in lower
        or "modify your code" in lower
        or "build ability" in lower
        or "add ability" in lower
        or "add skill" in lower
        or "build skill" in lower
        or "self improve" in lower
        or "self-improve" in lower
        or "upgrade yourself" in lower
        or "optimize yourself" in lower
    ):
        return VoiceCommand(action="evolve", payload=text)
    # Shutdown commands
    if (
        "shut down" in lower
        or "shutdown" in lower
        or "turn off" in lower
        or "go to sleep" in lower
        or "stop running" in lower
        or "goodbye jarvis" in lower
        or "bye jarvis" in lower
    ):
        return VoiceCommand(action="shutdown", payload="")
    return None


def _confirm_apply() -> bool:
    confirmation = _transcribe_once(timeout=4, phrase_time_limit=3)
    return "apply" in confirmation.lower() or "yes" in confirmation.lower()


def handle_command(command: VoiceCommand) -> str:
    from core import cli

    if command.action == "help":
        return (
            "You can say status, diagnostics, report morning or afternoon, summarize, log a note, "
            "research a topic, search the web, improve yourself, or stop listening. "
            "Say Jarvis to interrupt me mid-sentence."
        )

    if command.action == "listening_off":
        state.update_state(voice_enabled=False, mic_status="off")
        return "Plain English:\n- What I did: Turned voice listening off.\n- Why I did it: You asked me to stop listening.\n- What happens next: Say or run 'start listening' to resume.\n- What I need from you: Nothing.\n\nTechnical Notes:\n- Modules/files involved: core/state.py\n- Key concepts/terms: Voice toggle\n- Commands executed (or would execute in dry-run): state update\n- Risks/constraints: None.\n"
    if command.action == "listening_on":
        state.update_state(voice_enabled=True, mic_status="idle")
        return "Plain English:\n- What I did: Turned voice listening on.\n- Why I did it: You asked me to start listening.\n- What happens next: Say 'status' or another command.\n- What I need from you: Nothing.\n\nTechnical Notes:\n- Modules/files involved: core/state.py\n- Key concepts/terms: Voice toggle\n- Commands executed (or would execute in dry-run): state update\n- Risks/constraints: None.\n"

    if command.action == "status":
        return cli.capture_status_text()

    if command.action == "diagnostics":
        return cli.capture_diagnostics_text(dry_run=True)

    if command.action == "summarize":
        if not _confirm_apply():
            return "Plain English:\n- What I did: Canceled summarize because APPLY was not confirmed.\n- Why I did it: Safety gate.\n- What happens next: Say 'summarize' again and confirm APPLY.\n- What I need from you: Say APPLY.\n\nTechnical Notes:\n- Modules/files involved: core/cli.py\n- Key concepts/terms: Apply confirmation\n- Commands executed (or would execute in dry-run): None\n- Risks/constraints: No changes made.\n"
        return cli.capture_summarize_text(dry_run=False)

    if command.action == "overnight":
        if not _confirm_apply():
            return "Plain English:\n- What I did: Canceled overnight run because APPLY was not confirmed.\n- Why I did it: Safety gate.\n- What happens next: Say 'overnight' again and confirm APPLY.\n- What I need from you: Say APPLY.\n\nTechnical Notes:\n- Modules/files involved: core/overnight.py\n- Key concepts/terms: Apply confirmation\n- Commands executed (or would execute in dry-run): None\n- Risks/constraints: No changes made.\n"
        return cli.capture_overnight_text(dry_run=False)

    if command.action.startswith("report"):
        kind = command.action.replace("report_", "")
        if not _confirm_apply():
            return "Plain English:\n- What I did: Canceled report because APPLY was not confirmed.\n- Why I did it: Safety gate.\n- What happens next: Say 'report' again and confirm APPLY.\n- What I need from you: Say APPLY.\n\nTechnical Notes:\n- Modules/files involved: core/reporting.py\n- Key concepts/terms: Apply confirmation\n- Commands executed (or would execute in dry-run): None\n- Risks/constraints: No changes made.\n"
        return cli.capture_report_text(kind=kind, dry_run=False)

    if command.action == "log":
        if not command.payload:
            return "Plain English:\n- What I did: Could not log because I did not hear the note.\n- Why I did it: Logging requires text.\n- What happens next: Say 'log' followed by your note.\n- What I need from you: Your note text.\n\nTechnical Notes:\n- Modules/files involved: core/voice.py\n- Key concepts/terms: Speech recognition\n- Commands executed (or would execute in dry-run): None\n- Risks/constraints: No changes made.\n"
        if not _confirm_apply():
            return "Plain English:\n- What I did: Canceled log because APPLY was not confirmed.\n- Why I did it: Safety gate.\n- What happens next: Say 'log ...' again and confirm APPLY.\n- What I need from you: Say APPLY.\n\nTechnical Notes:\n- Modules/files involved: core/memory.py\n- Key concepts/terms: Apply confirmation\n- Commands executed (or would execute in dry-run): None\n- Risks/constraints: No changes made.\n"
        topic, body = notes_manager.extract_topic_and_body(command.payload)
        note_path, summary_path, _ = notes_manager.save_note(
            topic=topic,
            content=f"# {topic.title()}\n\n{body}",
            fmt="md",
            tags=["voice", "log"],
            source="voice.log",
            metadata={"command": "voice.log"},
        )
        memory.append_entry(command.payload, "voice_log", safety_context(apply=True))
        return (
            "Plain English:\n"
            "- What I did: Saved your note to memory and wrote a local file.\n"
            "- Why I did it: You asked to log a note.\n"
            "- What happens next: Say 'summarize' to route notes or open the saved file.\n"
            "- What I need from you: Nothing.\n\n"
            "Technical Notes:\n"
            "- Modules/files involved: core/memory.py, core/notes_manager.py\n"
            "- Key concepts/terms: JSONL memory buffer, local note store\n"
            "- Commands executed (or would execute in dry-run): Append entry; write note "
            f"({note_path}) and summary ({summary_path})\n"
            "- Risks/constraints: None.\n"
        )

    if command.action == "context":
        summary = context_manager.get_context_summary()
        if not summary:
            summary = "No context available."
        return f"Context summary: {summary}"

    if command.action == "web_search":
        if not command.payload:
            return "Tell me what you want me to search for."
        cfg = _load_config()
        if not cfg.get("research", {}).get("allow_web", False):
            return "Web access is disabled right now."
        try:
            from core import research_engine

            engine = research_engine.get_research_engine()
            results = engine.search_web(command.payload, max_results=5)
        except Exception as exc:
            return f"I could not search the web: {exc}"
        if not results:
            return "I couldn't find any results."
        top = results[:3]
        formatted = "; ".join(
            f"{item.get('title', 'Untitled')}" for item in top if item.get("title")
        )
        return f"Top results: {formatted}."

    if command.action == "research":
        if not command.payload:
            return "Tell me what you want me to research."
        cfg = _load_config()
        if not cfg.get("research", {}).get("allow_web", False):
            return "Web research is disabled right now."
        try:
            from core import research_engine

            engine = research_engine.get_research_engine()
            result = engine.research_topic(command.payload, max_pages=3)
        except Exception as exc:
            return f"I could not run research: {exc}"
        if not result or not result.get("success"):
            error = result.get("error") if isinstance(result, dict) else "unknown error"
            return f"I could not complete research: {error}."
        summary = result.get("summary") or "I completed the research but did not get a summary."
        return f"Research summary: {summary}"

    if command.action == "evolve":
        if not _confirm_apply():
            return "Plain English:\n- What I did: Canceled self-improvement because APPLY was not confirmed.\n- Why I did it: Safety gate.\n- What happens next: Ask again and confirm APPLY.\n- What I need from you: Say APPLY.\n\nTechnical Notes:\n- Modules/files involved: core/evolution.py\n- Key concepts/terms: Self-improvement\n- Commands executed (or would execute in dry-run): None\n- Risks/constraints: No changes made.\n"
        return evolution.evolve_from_conversation(
            user_text=command.payload,
            conversation_history=[],
            context=safety_context(apply=True),
        )

    if command.action == "shutdown":
        _speak("Goodbye. Shutting down now.")
        # Signal daemon to stop
        pid = state.read_pid()
        if pid:
            try:
                import signal as sig
                os.kill(pid, sig.SIGTERM)
            except Exception as e:
                pass
        state.clear_pid()
        state.update_state(running=False)
        return "Plain English:\n- What I did: Shut down Jarvis.\n- Why I did it: You asked me to stop.\n- What happens next: Run 'lifeos on --apply' to start again.\n- What I need from you: Nothing.\n\nTechnical Notes:\n- Modules/files involved: core/state.py\n- Key concepts/terms: SIGTERM, graceful shutdown\n- Commands executed: kill daemon process\n- Risks/constraints: None.\n"

    return "Plain English:\n- What I did: I could not map that request.\n- Why I did it: The command did not match supported actions.\n- What happens next: Try 'status', 'log', 'report', or 'diagnostics'.\n- What I need from you: A supported command.\n\nTechnical Notes:\n- Modules/files involved: core/voice.py\n- Key concepts/terms: Intent parsing\n- Commands executed (or would execute in dry-run): None\n- Risks/constraints: No changes made.\n"


def safety_context(apply: bool):
    from core import safety

    if apply:
        return safety.SafetyContext(apply=True, dry_run=False)
    return safety.SafetyContext(apply=False, dry_run=True)


def _capture_screen_context(tracker: Optional[observation.MouseTracker]) -> str:
    return observation.format_snapshot(tracker)


def _chat_response(
    user_text: str,
    tracker: Optional[observation.MouseTracker],
    session_history: list[dict],
) -> str:
    screen_context = _capture_screen_context(tracker)
    return conversation.generate_response(user_text, screen_context, session_history, channel="voice")


def _record_command_turn(user_text: str, assistant_text: str) -> None:
    try:
        ctx = safety_context(apply=True)
        memory.append_entry(user_text, "voice_chat_user", ctx)
        memory.append_entry(assistant_text, "voice_chat_assistant", ctx)
        context_manager.add_conversation_message("user", user_text)
        context_manager.add_conversation_message("assistant", assistant_text)
    except Exception:
        pass


def chat_session() -> None:
    voice_cfg = _voice_cfg()
    greeting = voice_cfg.get(
        "chat_greeting", "Hi, I'm here. What do you want me to do?"
    )
    stop_phrase = voice_cfg.get("chat_stop_phrase", "thank you goodbye for now")
    silence_limit = int(voice_cfg.get("chat_silence_limit", 3))
    timeout = int(voice_cfg.get("command_timeout_seconds", 6))
    phrase_limit = int(voice_cfg.get("phrase_time_limit", 6))
    track_mouse = bool(voice_cfg.get("track_mouse", True))

    state.update_state(chat_active=True, mic_status="chat")
    if greeting:
        _speak(greeting)
        print(greeting)

    tracker = observation.MouseTracker() if track_mouse else None
    if tracker:
        tracker.start()

    silence_count = 0
    pending_text: Optional[str] = None
    session_history: list[dict] = []
    try:
        while True:
            if pending_text is None:
                text = _transcribe_once(timeout=timeout, phrase_time_limit=phrase_limit)
                if not text:
                    silence_count += 1
                    if silence_count >= silence_limit:
                        farewell = "Ending chat due to silence."
                        _speak(farewell)
                        print(farewell)
                        break
                    continue
            else:
                text = pending_text
                pending_text = None
            if _is_self_echo(text, voice_cfg):
                silence_count += 1
                if silence_count >= silence_limit:
                    farewell = "Ending chat due to silence."
                    _speak(farewell)
                    print(farewell)
                    break
                continue
            silence_count = 0
            if _stop_phrase_match(text, stop_phrase):
                farewell = "Thank you. Goodbye for now."
                _speak(farewell)
                print(farewell)
                break
            session_history.append({"source": "voice_chat_user", "text": text})
            command = parse_command(text)
            if command:
                response = handle_command(command)
                _record_command_turn(text, response)
            else:
                response = _chat_response(text, tracker, session_history)
            session_history.append({"source": "voice_chat_assistant", "text": response})
            voice_ready = conversation.sanitize_for_voice(response)
            voice_ready = _trim_voice_output(voice_ready, voice_cfg)
            interrupt_text = _speak_with_barge_in(voice_ready, voice_cfg)
            print(response)
            if interrupt_text:
                pending_text = interrupt_text
    finally:
        if tracker:
            tracker.stop()
        state.update_state(chat_active=False, mic_status="idle")


_chat_lock = threading.Lock()


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _acquire_chat_file_lock() -> bool:
    """Prevent concurrent voice chat sessions across processes."""
    _CHAT_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(_CHAT_LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w") as handle:
            handle.write(f"{os.getpid()}:{int(time.time())}")
        return True
    except FileExistsError:
        try:
            raw = _CHAT_LOCK_PATH.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return _acquire_chat_file_lock()
        pid = None
        if raw:
            try:
                pid = int(raw.split(":", 1)[0])
            except (ValueError, IndexError):
                pid = None
        if pid and _process_alive(pid):
            return False
        try:
            _CHAT_LOCK_PATH.unlink()
        except FileNotFoundError:
            pass
        return _acquire_chat_file_lock()


def _release_chat_file_lock() -> None:
    try:
        raw = _CHAT_LOCK_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return
    if raw.startswith(f"{os.getpid()}:"):
        try:
            _CHAT_LOCK_PATH.unlink()
        except FileNotFoundError:
            pass


def start_chat_session() -> None:
    if state.read_state().get("chat_active"):
        return
    if not _chat_lock.acquire(blocking=False):
        return
    if not _acquire_chat_file_lock():
        _chat_lock.release()
        return

    def _run() -> None:
        try:
            chat_session()
        finally:
            _release_chat_file_lock()
            _chat_lock.release()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


class VoiceManager(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self._stop_event = threading.Event()
        self._listening = False

    def stop(self) -> None:
        self._stop_event.set()

    def _wake_word_loop(self) -> None:
        try:
            import numpy as np
            import openwakeword
            import pyaudio
        except Exception as e:
            state.update_state(
                voice_mode="push-to-talk",
                mic_status="off",
                voice_error="openwakeword_unavailable",
            )
            return

        cfg = _load_config()
        wake_word = cfg.get("voice", {}).get("wake_word", "jarvis")
        model_name = _wake_word_model_name(wake_word)
        threshold = float(cfg.get("voice", {}).get("wake_word_threshold", 0.6))
        frame_length = int(cfg.get("voice", {}).get("frame_length", 1280))

        model_meta = openwakeword.MODELS.get(model_name, {})
        model_path = model_meta.get("model_path")
        if model_path and not Path(model_path).exists():
            try:
                from openwakeword import utils as oww_utils

                oww_utils.download_models([model_name])
            except Exception as e:
                state.update_state(
                    voice_mode="push-to-talk",
                    mic_status="off",
                    voice_error="wakeword_model_unavailable",
                )
                return
        try:
            model = openwakeword.Model(wakeword_models=[model_name])
        except Exception as e:
            state.update_state(
                voice_mode="push-to-talk",
                mic_status="off",
                voice_error="wakeword_model_unavailable",
            )
            return
        pa = pyaudio.PyAudio()
        try:
            stream = pa.open(
                rate=16000,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=frame_length,
            )
        except Exception as e:
            state.update_state(
                voice_mode="push-to-talk",
                mic_status="off",
                voice_error="microphone_unavailable",
            )
            pa.terminate()
            return

        state.update_state(voice_mode="wake-word", mic_status="listening", voice_error="none")
        self._listening = True

        try:
            while not self._stop_event.is_set():
                if state.read_state().get("chat_active"):
                    break
                data = stream.read(frame_length, exception_on_overflow=False)
                audio = np.frombuffer(data, dtype=np.int16)
                prediction = model.predict(audio)
                score = float(prediction.get(model_name, 0.0))
                if score >= threshold:
                    state.update_state(mic_status="capturing")
                    text = _transcribe_once(
                        timeout=6,
                        phrase_time_limit=int(
                            cfg.get("voice", {}).get("phrase_time_limit", 6)
                        ),
                    )
                    if not text:
                        state.update_state(mic_status="listening")
                        continue
                    command = parse_command(text)
                    if command:
                        response = handle_command(command)
                        _record_command_turn(text, response)
                        voice_cfg = _voice_cfg()
                        voice_ready = conversation.sanitize_for_voice(response)
                        voice_ready = _trim_voice_output(voice_ready, voice_cfg)
                        _speak(voice_ready)
                    else:
                        screen_context = _capture_screen_context(None)
                        response = conversation.generate_response(
                            text, screen_context, None, channel="voice"
                        )
                        voice_cfg = _voice_cfg()
                        voice_ready = _trim_voice_output(response, voice_cfg)
                        _speak(voice_ready)
                    state.update_state(mic_status="listening")
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()
            self._listening = False

    def run(self) -> None:
        while not self._stop_event.is_set():
            cfg = _load_config()
            if not cfg.get("voice", {}).get("enabled", True):
                state.update_state(voice_enabled=False, mic_status="off")
                time.sleep(2)
                continue

            if state.read_state().get("chat_active"):
                state.update_state(mic_status="chat")
                time.sleep(1)
                continue

            runtime_voice_enabled = state.read_state().get("voice_enabled", True)
            if not runtime_voice_enabled:
                state.update_state(mic_status="off")
                time.sleep(2)
                continue

            profile = system_profiler.read_profile()
            max_cpu_load = float(cfg.get("voice", {}).get("max_cpu_load", 4.0))
            if profile.cpu_load and profile.cpu_load > max_cpu_load:
                state.update_state(
                    voice_mode="push-to-talk",
                    mic_status="off",
                    voice_error="cpu_load_high",
                )
                time.sleep(5)
                continue

            mode = cfg.get("voice", {}).get("mode", "wake-word")
            state_mode = state.read_state().get("voice_mode", mode)
            if mode == "wake-word" and state_mode != "push-to-talk":
                self._wake_word_loop()
                time.sleep(1)
                continue

            state.update_state(voice_mode="push-to-talk", mic_status="idle")
            time.sleep(2)


def listen_once() -> str:
    cfg = _load_config()
    text = _transcribe_once(
        timeout=int(cfg.get("voice", {}).get("command_timeout_seconds", 6)),
        phrase_time_limit=int(cfg.get("voice", {}).get("phrase_time_limit", 6)),
    )
    command = parse_command(text)
    if not command:
        return "Plain English:\n- What I did: I did not catch a valid command.\n- Why I did it: The audio was unclear or unsupported.\n- What happens next: Try again and speak clearly.\n- What I need from you: A supported command.\n\nTechnical Notes:\n- Modules/files involved: core/voice.py\n- Key concepts/terms: Speech recognition\n- Commands executed (or would execute in dry-run): None\n- Risks/constraints: No changes made.\n"
    response = handle_command(command)
    voice_cfg = _voice_cfg()
    voice_ready = conversation.sanitize_for_voice(response)
    voice_ready = _trim_voice_output(voice_ready, voice_cfg)
    _speak(voice_ready)
    return response


def check_voice_health() -> dict:
    """Run comprehensive voice pipeline diagnostics.

    Returns a dict with status for each component:
    - microphone: Can we access the mic?
    - wake_word: Is openwakeword available and working?
    - stt: Speech-to-text engines status
    - tts: Text-to-speech engines status
    - audio_playback: Can we play audio?
    """
    results = {}

    # 1. Microphone check
    mic_status = {"ok": False, "error": None, "fix": None}
    try:
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.2)
        mic_status["ok"] = True
    except ImportError:
        mic_status["error"] = "speech_recognition not installed"
        mic_status["fix"] = "pip install SpeechRecognition"
    except OSError as e:
        mic_status["error"] = f"Microphone unavailable: {e}"
        mic_status["fix"] = "Check System Preferences > Security & Privacy > Microphone"
    except Exception as e:
        mic_status["error"] = str(e)
        mic_status["fix"] = "Grant microphone access to Terminal/IDE"
    results["microphone"] = mic_status

    # 2. Wake word detection check
    wake_status = {"ok": False, "error": None, "fix": None, "model": None}
    try:
        import openwakeword
        import pyaudio

        cfg = _load_config()
        wake_word = cfg.get("voice", {}).get("wake_word", "jarvis")
        model_name = _wake_word_model_name(wake_word)
        wake_status["model"] = model_name

        # Check if model exists
        model_meta = openwakeword.MODELS.get(model_name, {})
        model_path = model_meta.get("model_path")
        if model_path and not Path(model_path).exists():
            wake_status["error"] = f"Model '{model_name}' not downloaded"
            wake_status["fix"] = f"python -c \"from openwakeword import utils; utils.download_models(['{model_name}'])\""
        else:
            # Try to initialize
            try:
                model = openwakeword.Model(wakeword_models=[model_name])
                wake_status["ok"] = True
            except Exception as e:
                wake_status["error"] = f"Model init failed: {e}"
                wake_status["fix"] = "pip install --upgrade openwakeword"
    except ImportError as e:
        missing = "openwakeword" if "openwakeword" in str(e) else "pyaudio"
        wake_status["error"] = f"{missing} not installed"
        if missing == "pyaudio":
            wake_status["fix"] = "brew install portaudio && pip install pyaudio"
        else:
            wake_status["fix"] = "pip install openwakeword"
    except Exception as e:
        wake_status["error"] = str(e)
    results["wake_word"] = wake_status

    # 3. STT engines check
    stt_status = {"engines": {}, "any_working": False}

    # Gemini STT
    gemini_key = secrets.get_gemini_key()
    if gemini_key:
        stt_status["engines"]["gemini"] = {"ok": True, "note": "API key configured"}
        stt_status["any_working"] = True
    else:
        stt_status["engines"]["gemini"] = {"ok": False, "fix": "Set GEMINI_API_KEY env var (free tier available)"}

    # OpenAI Whisper
    openai_key = secrets.get_openai_key()
    if openai_key:
        try:
            from openai import OpenAI
            stt_status["engines"]["whisper"] = {"ok": True, "note": "API key configured"}
            stt_status["any_working"] = True
        except ImportError:
            stt_status["engines"]["whisper"] = {"ok": False, "fix": "pip install openai"}
    else:
        stt_status["engines"]["whisper"] = {"ok": False, "fix": "Set OPENAI_API_KEY env var"}

    # Google (free, no key needed)
    try:
        import speech_recognition as sr
        stt_status["engines"]["google"] = {"ok": True, "note": "Free tier (no key needed)"}
        stt_status["any_working"] = True
    except ImportError:
        stt_status["engines"]["google"] = {"ok": False, "fix": "pip install SpeechRecognition"}

    # Sphinx (offline, last resort)
    try:
        import speech_recognition as sr
        # Check if pocketsphinx is available
        try:
            import pocketsphinx
            stt_status["engines"]["sphinx"] = {"ok": True, "note": "Offline fallback"}
            stt_status["any_working"] = True
        except ImportError:
            stt_status["engines"]["sphinx"] = {"ok": False, "fix": "pip install pocketsphinx (offline fallback)"}
    except ImportError:
        pass

    results["stt"] = stt_status

    # 4. TTS engines check
    tts_status = {"engines": {}, "any_working": False}
    voice_cfg = _voice_cfg()

    # Piper TTS
    piper_ok = False
    if shutil.which(PIPER_BINARY):
        model_path = _ensure_piper_model(voice_cfg)
        if model_path and model_path.exists():
            tts_status["engines"]["piper"] = {"ok": True, "note": f"Model: {model_path.name}"}
            piper_ok = True
            tts_status["any_working"] = True
        else:
            tts_status["engines"]["piper"] = {"ok": False, "fix": "Model download failed; check network"}
    else:
        tts_status["engines"]["piper"] = {"ok": False, "fix": "brew install piper (or pip install piper-tts)"}

    # macOS say (always available on macOS)
    try:
        result = subprocess.run(
            ["say", "-v", "?"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            voice_count = len(result.stdout.strip().split("\n"))
            tts_status["engines"]["macos_say"] = {"ok": True, "note": f"{voice_count} voices available"}
            tts_status["any_working"] = True
        else:
            tts_status["engines"]["macos_say"] = {"ok": False, "error": "say command failed"}
    except FileNotFoundError:
        tts_status["engines"]["macos_say"] = {"ok": False, "note": "Not on macOS"}
    except Exception as e:
        tts_status["engines"]["macos_say"] = {"ok": False, "error": str(e)}

    results["tts"] = tts_status

    # 5. Audio playback check
    playback_status = {"ok": False, "error": None}
    try:
        result = subprocess.run(
            ["afplay", "--help"],
            capture_output=True,
            timeout=5,
        )
        # afplay returns 1 for --help but that's fine
        playback_status["ok"] = True
    except FileNotFoundError:
        playback_status["error"] = "afplay not found (not on macOS?)"
        playback_status["fix"] = "Use a different audio player or run on macOS"
    except Exception as e:
        playback_status["error"] = str(e)
    results["audio_playback"] = playback_status

    return results


def get_voice_doctor_summary() -> str:
    """Get human-readable voice pipeline health summary."""
    results = check_voice_health()
    lines = ["=== Voice Pipeline Health ===\n"]

    # Microphone
    mic = results.get("microphone", {})
    if mic.get("ok"):
        lines.append("✓ Microphone: Working")
    else:
        lines.append(f"✗ Microphone: {mic.get('error', 'Unknown error')}")
        if mic.get("fix"):
            lines.append(f"  Fix: {mic['fix']}")

    # Wake word
    wake = results.get("wake_word", {})
    if wake.get("ok"):
        lines.append(f"✓ Wake Word: Ready (model: {wake.get('model', 'unknown')})")
    else:
        lines.append(f"✗ Wake Word: {wake.get('error', 'Not configured')}")
        if wake.get("fix"):
            lines.append(f"  Fix: {wake['fix']}")

    # STT
    stt = results.get("stt", {})
    if stt.get("any_working"):
        working = [k for k, v in stt.get("engines", {}).items() if v.get("ok")]
        lines.append(f"✓ Speech-to-Text: {', '.join(working)}")
    else:
        lines.append("✗ Speech-to-Text: No engines available")
        for name, info in stt.get("engines", {}).items():
            if not info.get("ok") and info.get("fix"):
                lines.append(f"  - {name}: {info['fix']}")

    # TTS
    tts = results.get("tts", {})
    if tts.get("any_working"):
        working = [k for k, v in tts.get("engines", {}).items() if v.get("ok")]
        lines.append(f"✓ Text-to-Speech: {', '.join(working)}")
    else:
        lines.append("✗ Text-to-Speech: No engines available")
        for name, info in tts.get("engines", {}).items():
            if not info.get("ok") and info.get("fix"):
                lines.append(f"  - {name}: {info['fix']}")

    # Audio playback
    playback = results.get("audio_playback", {})
    if playback.get("ok"):
        lines.append("✓ Audio Playback: Working (afplay)")
    else:
        lines.append(f"✗ Audio Playback: {playback.get('error', 'Unknown error')}")
        if playback.get("fix"):
            lines.append(f"  Fix: {playback['fix']}")

    # Overall verdict
    lines.append("")
    all_critical_ok = (
        results.get("microphone", {}).get("ok") and
        results.get("stt", {}).get("any_working") and
        results.get("tts", {}).get("any_working")
    )
    if all_critical_ok:
        if results.get("wake_word", {}).get("ok"):
            lines.append("✓ Voice pipeline fully operational (wake word + push-to-talk)")
        else:
            lines.append("⚠ Voice pipeline operational (push-to-talk only, wake word needs setup)")
    else:
        lines.append("✗ Voice pipeline NOT operational - fix issues above")

    return "\n".join(lines)
