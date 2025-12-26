"""
Persistent prompt library for Jarvis.

Stores reusable prompt snippets (prompt inspirations) with metadata so
conversation and background systems can pull tailored guidance.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
LIBRARY_PATH = ROOT / "data" / "prompt_library.json"


@dataclass
class PromptRecord:
    id: str
    title: str
    body: str
    tags: List[str] = field(default_factory=list)
    source: str = "system"
    usage_count: int = 0
    quality_score: float = 0.85
    added_at: float = field(default_factory=lambda: time.time())
    last_used: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


DEFAULT_PROMPTS: List[PromptRecord] = [
    PromptRecord(
        id="conversation_fluidity",
        title="Fluid Conversation",
        body=(
            "Mirror the user's tone, acknowledge what they just said, "
            "and add one thoughtful follow-up question before proposing solutions."
        ),
        tags=["conversation", "listening", "rapport"],
        quality_score=0.92,
    ),
    PromptRecord(
        id="crypto_drive",
        title="Crypto Trading Coach",
        body=(
            "Whenever crypto or trading is mentioned, connect ideas back to "
            "profit paths, risk controls, and lightweight automations the user can try tonight."
        ),
        tags=["crypto", "trading", "money"],
        quality_score=0.9,
    ),
    PromptRecord(
        id="research_stack",
        title="Research Depth",
        body=(
            "Break research into: current landscape, key players, opportunities, "
            "and immediate next experiments the user can run."
        ),
        tags=["research", "analysis"],
    ),
    PromptRecord(
        id="social_mapper",
        title="Social Graph Mapper",
        body=(
            "Cross-link mentions of the user's companies, social profiles, and funnels "
            "so we keep a running map of how audiences discover them."
        ),
        tags=["social", "observation", "conversation"],
    ),
]


def _ensure_storage() -> None:
    LIBRARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not LIBRARY_PATH.exists():
        data = {record.id: asdict(record) for record in DEFAULT_PROMPTS}
        LIBRARY_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _load_raw() -> Dict[str, PromptRecord]:
    _ensure_storage()
    try:
        raw = json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raw = {}
    records: Dict[str, PromptRecord] = {}
    for pid, payload in raw.items():
        try:
            records[pid] = PromptRecord(**payload)
        except TypeError:
            continue
    # Merge defaults if missing
    for record in DEFAULT_PROMPTS:
        records.setdefault(record.id, record)
    return records


def _save(records: Dict[str, PromptRecord]) -> None:
    LIBRARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    serializable = {pid: asdict(entry) for pid, entry in records.items()}
    LIBRARY_PATH.write_text(json.dumps(serializable, indent=2), encoding="utf-8")


def add_prompt(
    title: str,
    body: str,
    tags: Iterable[str],
    source: str = "user",
    metadata: Optional[Dict[str, Any]] = None,
) -> PromptRecord:
    """Add a new prompt snippet to the library."""
    records = _load_raw()
    pid = f"prompt_{int(time.time()*1000)}"
    record = PromptRecord(
        id=pid,
        title=title,
        body=body,
        tags=list(dict.fromkeys(t.strip().lower() for t in tags if t.strip())),
        source=source,
        metadata=metadata or {},
    )
    records[pid] = record
    _save(records)
    return record


def list_prompts() -> List[PromptRecord]:
    """Return all prompts in the library."""
    return list(_load_raw().values())


def get_support_prompts(tags: Iterable[str], limit: int = 3) -> List[PromptRecord]:
    """Return the highest-scoring prompts for the supplied tags."""
    tag_set = {t.lower() for t in tags if t}
    if not tag_set:
        tag_set = {"conversation"}
    records = _load_raw()
    scored: List[tuple[float, PromptRecord]] = []
    now = time.time()
    for record in records.values():
        overlap = tag_set.intersection({t.lower() for t in record.tags})
        score = float(len(overlap)) * 2.0
        score += record.quality_score
        score += min(record.usage_count, 20) * 0.05
        if record.last_used:
            hours_since_use = max((now - record.last_used) / 3600.0, 1.0)
            score += 1.0 / hours_since_use
        if not overlap and "conversation" not in tag_set:
            score *= 0.5
        scored.append((score, record))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [entry for _, entry in scored[:limit]]


def record_usage(prompt_ids: Iterable[str], success: bool = True) -> None:
    """Update usage metadata for prompts after they are injected."""
    ids = [pid for pid in prompt_ids if pid]
    if not ids:
        return
    records = _load_raw()
    touched = False
    for pid in ids:
        record = records.get(pid)
        if not record:
            continue
        record.usage_count += 1
        record.last_used = time.time()
        if success:
            record.quality_score = min(record.quality_score + 0.01, 1.0)
        else:
            record.quality_score = max(record.quality_score - 0.02, 0.1)
        touched = True
    if touched:
        _save(records)


def get_recent_prompts(limit: int = 5) -> List[PromptRecord]:
    """Return prompts sorted by most recent use."""
    records = _load_raw()
    sorted_prompts = sorted(
        records.values(),
        key=lambda entry: entry.last_used or entry.added_at,
        reverse=True,
    )
    return sorted_prompts[:limit]
