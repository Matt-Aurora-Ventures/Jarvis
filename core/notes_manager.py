"""
Utilities for keeping all notes, research dumps, and distilled prompts on disk.

Notes are stored under data/notes/ with optional raw artifacts in data/notes/raw/.
Whenever a note is saved we:
- compress/distill the text so it stays lightweight while preserving key facts
- mirror the distilled bullets into the prompt library for future recall
"""

from __future__ import annotations

import re
import subprocess
import textwrap
import time
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from core import prompt_library

ROOT = Path(__file__).resolve().parents[1]
NOTES_ROOT = ROOT / "data" / "notes"
RAW_ROOT = NOTES_ROOT / "raw"

ALLOWED_FORMATS = {"txt", "md", "py"}
PREFERRED_NOTE_TOPIC = "general"


def _ensure_dirs() -> None:
    NOTES_ROOT.mkdir(parents=True, exist_ok=True)
    RAW_ROOT.mkdir(parents=True, exist_ok=True)


def _slugify(text: str, fallback: str = "note") -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return slug or fallback


def _timestamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def _distill_lines(body: str, max_lines: int = 8) -> List[str]:
    raw_lines = [line.strip() for line in body.splitlines() if line.strip()]
    seen = set()
    distilled: List[str] = []
    for line in raw_lines:
        normalized = line.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        clean = textwrap.shorten(line, width=160, placeholder="…")
        distilled.append(clean)
        if len(distilled) >= max_lines:
            break
    return distilled or ["(No content provided.)"]


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def topic_dir(topic: Optional[str] = None) -> Path:
    """Return the directory for a topic (creates it if missing)."""
    _ensure_dirs()
    if not topic:
        return NOTES_ROOT
    return NOTES_ROOT / _slugify(topic, fallback=PREFERRED_NOTE_TOPIC)


def list_note_files(topic: Optional[str] = None) -> List[Path]:
    """List note files for a topic (all topics if None)."""
    root = topic_dir(topic)
    if not root.exists():
        return []
    return sorted(root.glob("*.md")) + sorted(root.glob("*.txt")) + sorted(root.glob("*.py"))


def latest_note(topic: Optional[str] = None) -> Optional[Path]:
    """Return the most recent note path for a topic."""
    files = list_note_files(topic)
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def extract_topic_and_body(text: str, default_topic: str = PREFERRED_NOTE_TOPIC) -> Tuple[str, str]:
    """
    Allow quick syntax like 'topic: body'. If no delimiter or topic too long, fall back.
    """
    text = (text or "").strip()
    if not text:
        return default_topic, ""
    head, sep, tail = text.partition(":")
    if sep and len(head.split()) <= 4:
        topic = head.strip().lower()
        body = tail.strip()
        if topic and body:
            return topic, body
    return default_topic, text


def save_note(
    topic: str,
    content: str,
    *,
    fmt: str = "md",
    tags: Optional[Iterable[str]] = None,
    source: str = "manual",
    metadata: Optional[dict] = None,
) -> Tuple[Path, Path, Optional[str]]:
    """
    Persist a note under data/notes/<topic>/timestamp-topic.ext and create a distilled summary.
    Returns (note_path, summary_path, prompt_id).
    """
    _ensure_dirs()
    fmt = fmt.lower()
    if fmt not in ALLOWED_FORMATS:
        fmt = "md"

    topic_slug = _slugify(topic or "notes")
    note_name = f"{_timestamp()}-{topic_slug}.{fmt}"
    note_path = NOTES_ROOT / topic_slug / note_name
    _write_file(note_path, content.strip() + "\n")

    distilled_lines = _distill_lines(content)
    summary = "\n".join(f"- {line}" for line in distilled_lines)
    summary_path = note_path.with_suffix(".summary.md")
    _write_file(summary_path, summary + "\n")

    prompt_id = None
    try:
        prompt = prompt_library.add_prompt(
            title=f"{topic_slug} distilled facts",
            body=summary,
            tags=list(dict.fromkeys([topic_slug, "notes"] + list(tags or []))),
            source=source,
            metadata={**(metadata or {}), "note_path": str(note_path)},
        )
        prompt_id = prompt.id
    except Exception:
        # Prompt creation is best-effort; do not fail note saves if prompt library errors.
        prompt_id = None

    return note_path, summary_path, prompt_id


def save_python_snippet(topic: str, code: str, metadata: Optional[dict] = None) -> Path:
    """Helper to store executable scratchpads (*.py)."""
    note_path, _, _ = save_note(
        topic=topic,
        content=code,
        fmt="py",
        tags=["code", "automation"],
        source="auto_snippet",
        metadata=metadata,
    )
    return note_path


def ingest_via_curl(url: str, label: str, timeout: int = 30) -> Tuple[Path, str]:
    """
    Fetch a remote resource via curl and store the raw response under data/notes/raw/.
    Returns (raw_path, text_content).
    """
    _ensure_dirs()
    label_slug = _slugify(label or "fetch")
    raw_name = f"{_timestamp()}-{label_slug}.txt"
    raw_path = RAW_ROOT / raw_name

    command = ["curl", "-sSL", "--max-time", str(timeout), url]
    result = subprocess.run(command, capture_output=True, text=True)
    payload = result.stdout.strip()
    if result.returncode != 0:
        payload = f"curl error ({result.returncode}): {result.stderr.strip()}"
    _write_file(raw_path, payload)
    return raw_path, payload


def log_command_snapshot(command: List[str], label: str, output: str) -> Path:
    """Store arbitrary CLI output alongside notes for traceability."""
    _ensure_dirs()
    label_slug = _slugify(label or "command")
    name = f"{_timestamp()}-{label_slug}.txt"
    path = RAW_ROOT / name
    rendered = f"$ {' '.join(command)}\n\n{output.strip()}\n"
    _write_file(path, rendered)
    return path


__all__ = [
    "save_note",
    "save_python_snippet",
    "ingest_via_curl",
    "log_command_snapshot",
    "topic_dir",
    "latest_note",
    "extract_topic_and_body",
]
