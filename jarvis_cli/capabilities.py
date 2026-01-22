"""Detect runtime capabilities for voice startup."""

from __future__ import annotations

import asyncio
import importlib.util
import platform
import shutil
from dataclasses import dataclass
from typing import List, Tuple

from core.llm import get_llm
from core.llm.providers import get_default_configs


@dataclass(frozen=True)
class CapabilityReport:
    tts: str
    tts_available: bool
    stt: str
    stt_available: bool
    llm_selected: str
    llm_fallbacks: List[str]


def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def detect_tts() -> Tuple[str, bool]:
    system = platform.system().lower()
    if system == "darwin" and shutil.which("say"):
        return "say", True
    if system == "windows" and _has_module("pyttsx3"):
        return "pyttsx3", True
    if system == "linux":
        for candidate in ("espeak", "spd-say"):
            if shutil.which(candidate):
                return candidate, True
        if _has_module("pyttsx3"):
            return "pyttsx3", True
    return "text", False


def detect_stt() -> Tuple[str, bool]:
    if _has_module("speech_recognition"):
        return "speech_recognition", True
    if _has_module("faster_whisper"):
        return "faster_whisper", True
    return "text", False


async def detect_llm() -> Tuple[str, List[str]]:
    default_chain = [cfg.provider.value for cfg in get_default_configs()]
    llm = await get_llm()
    health = await llm.health_check()
    available = [provider.value for provider, ok in health.items() if ok]
    selected = available[0] if available else (default_chain[0] if default_chain else "none")
    fallbacks = default_chain if default_chain else [provider.value for provider in health.keys()]
    return selected, fallbacks


def detect_capabilities() -> CapabilityReport:
    tts_name, tts_available = detect_tts()
    stt_name, stt_available = detect_stt()
    llm_selected = "unknown"
    llm_fallbacks: List[str] = []
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        try:
            llm_selected, llm_fallbacks = asyncio.run(detect_llm())
        except Exception:
            llm_selected, llm_fallbacks = "unknown", []
    return CapabilityReport(
        tts=tts_name,
        tts_available=tts_available,
        stt=stt_name,
        stt_available=stt_available,
        llm_selected=llm_selected,
        llm_fallbacks=llm_fallbacks,
    )
