"""
Qwen3-TTS integration (local, open-source).

Prefers the official qwen-tts package when available. Falls back to
Transformers pipeline if needed.

Notes:
- This does NOT implement voice impersonation. Use only voices you have
  the rights to use.
"""

from __future__ import annotations

import os
import importlib.util
import shutil
import sys
import tempfile
import threading
from pathlib import Path
from typing import Optional, Tuple

_MODEL_LOCK = threading.Lock()
_CACHED_MODEL = None
_CACHED_MODEL_ID = ""
_CACHED_DEVICE = ""


def _default_model() -> str:
    return os.getenv("QWEN3_TTS_MODEL", "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice")


def _default_mode() -> str:
    return os.getenv("QWEN3_TTS_MODE", "custom_voice")


def _resolve_device_map(device: str) -> str:
    device = (device or "cpu").lower().strip()
    if device in ("cuda", "gpu", "cuda:0"):
        return "cuda:0"
    return "cpu"


def _ensure_sox_on_path() -> bool:
    if shutil.which("sox"):
        return True
    if sys.platform != "win32":
        return False

    candidates = [
        Path(os.getenv("LOCALAPPDATA", "")) / "Programs" / "SoX" / "sox-14.4.2" / "sox.exe",
        Path("C:/Program Files (x86)/sox-14.4.2/sox.exe"),
        Path("C:/Program Files/sox-14.4.2/sox.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            sox_dir = str(candidate.parent)
            os.environ["PATH"] = sox_dir + os.pathsep + os.environ.get("PATH", "")
            return True
    return False


def _resolve_pipeline_device(device: str) -> int:
    """Return transformers device index (-1 for CPU)."""
    device = (device or "cpu").lower().strip()
    if device in ("cuda", "gpu", "cuda:0"):
        try:
            import torch  # type: ignore

            if torch.cuda.is_available():
                return 0
        except Exception:
            pass
    return -1


def _qwen_tts_available() -> bool:
    return importlib.util.find_spec("qwen_tts") is not None


def _transformers_available() -> bool:
    return importlib.util.find_spec("transformers") is not None


def is_available() -> bool:
    """Return True if a supported backend is available."""
    return _qwen_tts_available() or _transformers_available()


def _write_wav(path: Path, audio, sample_rate: int) -> None:
    """Write mono audio to a WAV file without external deps."""
    import wave
    import numpy as np  # type: ignore

    data = np.asarray(audio)
    if data.ndim > 1:
        data = data[:, 0]

    # Convert float audio to int16 if needed
    if data.dtype != np.int16:
        data = np.clip(data, -1.0, 1.0)
        data = (data * 32767.0).astype(np.int16)

    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(data.tobytes())


def _get_qwen_tts_model(model_id: str, device: str):
    global _CACHED_MODEL, _CACHED_MODEL_ID, _CACHED_DEVICE
    device_map = _resolve_device_map(device)

    with _MODEL_LOCK:
        if _CACHED_MODEL and _CACHED_MODEL_ID == model_id and _CACHED_DEVICE == device_map:
            return _CACHED_MODEL

        _ensure_sox_on_path()

        import torch  # type: ignore
        from qwen_tts import Qwen3TTSModel  # type: ignore

        if device_map.startswith("cuda") and torch.cuda.is_available():
            dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        else:
            dtype = torch.float32

        model = Qwen3TTSModel.from_pretrained(
            model_id,
            device_map=device_map,
            dtype=dtype,
        )
        _CACHED_MODEL = model
        _CACHED_MODEL_ID = model_id
        _CACHED_DEVICE = device_map
        return model


def _normalize_list(text: str) -> list[str]:
    return [text] if text else []


def _synthesize_with_qwen_tts(
    text: str,
    voice_cfg: dict,
) -> Optional[Tuple[list, int]]:
    if not text:
        return None

    mode = str(voice_cfg.get("qwen3_mode") or _default_mode()).strip().lower()
    model_id = str(voice_cfg.get("qwen3_model") or _default_model())
    device = str(voice_cfg.get("qwen3_device", "cpu"))

    model = _get_qwen_tts_model(model_id, device)

    language = str(voice_cfg.get("qwen3_language", "English")).strip() or "English"
    instruct = str(voice_cfg.get("qwen3_instruct", "")).strip()

    if mode in ("custom", "custom_voice", "custom-voice"):
        speaker = str(voice_cfg.get("qwen3_speaker", "Ryan")).strip() or "Ryan"
        wavs, sr = model.generate_custom_voice(
            text=_normalize_list(text),
            language=language,
            speaker=speaker,
            instruct=instruct or None,
        )
        return wavs, int(sr)

    if mode in ("voice_design", "design"):
        if not instruct:
            raise ValueError("qwen3_instruct required for voice_design mode")
        wavs, sr = model.generate_voice_design(
            text=_normalize_list(text),
            language=language,
            speaker=instruct,
        )
        return wavs, int(sr)

    if mode in ("voice_clone", "clone"):
        ref_audio = str(voice_cfg.get("qwen3_ref_audio", "")).strip()
        ref_text = str(voice_cfg.get("qwen3_ref_text", "")).strip()
        if not ref_audio or not ref_text:
            raise ValueError("qwen3_ref_audio and qwen3_ref_text required for voice_clone mode")
        wavs, sr = model.generate_voice_clone(
            text=_normalize_list(text),
            language=language,
            ref_audio=ref_audio,
            ref_text=ref_text,
        )
        return wavs, int(sr)

    raise ValueError(f"Unknown qwen3_mode: {mode}")


def synthesize_to_file(
    text: str,
    model_id: Optional[str] = None,
    device: str = "cpu",
    output_path: Optional[Path] = None,
) -> Optional[Path]:
    """
    Generate audio for text and return a WAV path.

    Uses Transformers pipeline("text-to-speech") if available.
    """
    if not text:
        return None

    if output_path is None:
        output_path = Path(tempfile.mkstemp(suffix=".wav")[1])

    model_id = model_id or _default_model()

    try:
        from transformers import pipeline  # type: ignore
        import numpy as np  # noqa: F401  # ensure available
    except Exception:
        return None

    device_index = _resolve_pipeline_device(device)
    tts = pipeline("text-to-speech", model=model_id, device=device_index)
    result = tts(text)

    audio = result.get("audio")
    sample_rate = int(result.get("sampling_rate", 22050))
    if audio is None:
        return None

    _write_wav(output_path, audio, sample_rate)
    return output_path


def synthesize_from_config(
    text: str,
    voice_cfg: dict,
    output_path: Optional[Path] = None,
) -> Optional[Path]:
    """Convenience wrapper using voice config."""
    if not text:
        return None

    if output_path is None:
        output_path = Path(tempfile.mkstemp(suffix=".wav")[1])

    if _qwen_tts_available():
        wavs_sr = _synthesize_with_qwen_tts(text, voice_cfg)
        if not wavs_sr:
            return None
        wavs, sr = wavs_sr
        if not wavs:
            return None
        _write_wav(output_path, wavs[0], sr)
        return output_path

    model_id = str(voice_cfg.get("qwen3_model") or _default_model())
    device = str(voice_cfg.get("qwen3_device", "cpu"))
    return synthesize_to_file(text, model_id=model_id, device=device, output_path=output_path)
