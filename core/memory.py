import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

from core import config, safety, state, system_profiler

ROOT = Path(__file__).resolve().parents[1]
RECENT_PATH = ROOT / "lifeos" / "memory" / "recent.jsonl"
PENDING_PATH = ROOT / "lifeos" / "memory" / "pending.jsonl"


@dataclass
class MemoryEntry:
    timestamp: float
    text: str
    source: str


def _now() -> float:
    return time.time()


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    items = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return items


def _write_jsonl(path: Path, items: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=True) + "\n")


def compute_adaptive_cap(update_state: bool = True) -> int:
    cfg = config.load_config()
    memory_cfg = cfg.get("memory", {})
    target = int(memory_cfg.get("target_cap", 200))
    min_cap = int(memory_cfg.get("min_cap", 50))
    max_cap = int(memory_cfg.get("max_cap", 300))

    profile = system_profiler.read_profile()
    cap = target

    if profile.ram_total_gb and profile.ram_total_gb < 8:
        cap = min(cap, 100)
    if profile.ram_free_gb and profile.ram_free_gb < 2:
        cap = min(cap, 80)
    if profile.cpu_load and profile.cpu_load > 4:
        cap = min(cap, 100)
    if profile.disk_free_gb and profile.disk_free_gb < 10:
        cap = min(cap, 80)

    cap = max(min_cap, min(cap, max_cap))
    if update_state:
        state.update_state(memory_cap=cap)
    return cap


def append_entry(
    text: str,
    source: str,
    context: safety.SafetyContext,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    entry = MemoryEntry(timestamp=_now(), text=text.strip(), source=source)
    recent = _read_jsonl(RECENT_PATH)
    pending = _read_jsonl(PENDING_PATH)

    cap = compute_adaptive_cap(update_state=not context.dry_run)
    recent.append(entry.__dict__)

    overflow = []
    if len(recent) > cap:
        overflow = recent[:-cap]
        recent = recent[-cap:]
        pending.extend(overflow)

    if context.dry_run:
        return recent, overflow

    _write_jsonl(RECENT_PATH, recent)
    if overflow:
        _write_jsonl(PENDING_PATH, pending)
    return recent, overflow


def get_recent_entries() -> List[Dict[str, Any]]:
    return _read_jsonl(RECENT_PATH)


def get_factual_entries() -> List[Dict[str, Any]]:
    """Get memory entries excluding assistant responses.

    This prevents the "echo chamber" effect where the LLM sees its own
    previous responses as "facts" and reinforces shallow patterns.

    Returns only:
    - User inputs (voice_chat_user, cli_log, cli_capture)
    - External data (research, discoveries, etc.)

    Excludes:
    - voice_chat_assistant (LLM responses)
    """
    entries = _read_jsonl(RECENT_PATH)
    # Filter out assistant outputs to prevent echo chamber
    assistant_sources = {"voice_chat_assistant"}
    return [e for e in entries if e.get("source") not in assistant_sources]


def get_quality_filtered_entries(min_length: int = 10) -> List[Dict[str, Any]]:
    """Get memory entries with quality filtering applied.

    Filters:
    - Echo chamber prevention (no assistant responses)
    - Minimum text length
    - Deduplication (case-insensitive)
    - Removes common filler phrases

    Args:
        min_length: Minimum text length to include

    Returns:
        High-quality memory entries
    """
    entries = get_factual_entries()

    # Low-value patterns to filter out
    filler_patterns = {
        "ok", "okay", "yes", "no", "sure", "thanks", "thank you",
        "got it", "i see", "understood", "alright", "right",
        "hmm", "uh", "um", "ah", "oh", "huh", "what", "why",
    }

    seen_normalized: set = set()
    quality_entries: List[Dict[str, Any]] = []

    for entry in entries:
        text = str(entry.get("text", "")).strip()

        # Skip too short
        if len(text) < min_length:
            continue

        # Skip filler phrases
        normalized = text.lower().strip(".,!?")
        if normalized in filler_patterns:
            continue

        # Skip duplicates (normalized)
        if normalized in seen_normalized:
            continue
        seen_normalized.add(normalized)

        # Skip if mostly punctuation/whitespace
        alpha_ratio = sum(1 for c in text if c.isalnum()) / max(len(text), 1)
        if alpha_ratio < 0.5:
            continue

        quality_entries.append(entry)

    return quality_entries


def fetch_recent_entries(limit: int = 10) -> List[Dict[str, Any]]:
    entries = _read_jsonl(RECENT_PATH)
    if limit <= 0:
        return entries
    return entries[-limit:]


def get_pending_entries() -> List[Dict[str, Any]]:
    return _read_jsonl(PENDING_PATH)


def clear_pending_entries(context: safety.SafetyContext) -> bool:
    if context.dry_run:
        return False
    _write_jsonl(PENDING_PATH, [])
    return True


def summarize_entries(entries: List[Dict[str, Any]]) -> str:
    if not entries:
        return ""
    lines = []
    seen = set()
    for item in entries:
        text = str(item.get("text", "")).strip()
        if text:
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"- {text}")
    return "\n".join(lines)


def load_memory_state() -> Dict[str, Any]:
    cap = compute_adaptive_cap(update_state=False)
    return {
        "recent_count": len(_read_jsonl(RECENT_PATH)),
        "pending_count": len(_read_jsonl(PENDING_PATH)),
        "memory_cap": cap,
    }
