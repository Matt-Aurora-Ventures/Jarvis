from pathlib import Path
from typing import List, Tuple

from core import config, state, system_profiler

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "lifeos" / "context" / "index.md"


def _parse_index_lines(lines: List[str]) -> List[str]:
    paths: List[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line[0].isdigit() and "." in line:
            _, remainder = line.split(".", 1)
            path = remainder.strip()
        elif line.startswith("-"):
            path = line.lstrip("-").strip()
        else:
            continue
        if path and not path.startswith("##") and not path.startswith("#"):
            paths.append(path)
    return paths


def _load_index_paths() -> List[Path]:
    if not INDEX_PATH.exists():
        return []
    lines = INDEX_PATH.read_text(encoding="utf-8").splitlines()
    raw_paths = _parse_index_lines(lines)
    resolved: List[Path] = []
    for raw in raw_paths:
        if raw.startswith("context/"):
            raw = raw.replace("context/", "")
        candidate = INDEX_PATH.parent / raw
        resolved.append(candidate)
    return resolved


def _compute_context_budget(update_state: bool = True) -> Tuple[int, int]:
    cfg = config.load_config()
    context_cfg = cfg.get("context", {})
    base_docs = int(context_cfg.get("load_budget_docs", 20))
    base_chars = int(context_cfg.get("load_budget_chars", 12000))

    profile = system_profiler.read_profile()
    docs = base_docs
    chars = base_chars

    if profile.ram_total_gb and profile.ram_total_gb < 8:
        docs = min(docs, 10)
        chars = min(chars, 8000)
    if profile.ram_free_gb and profile.ram_free_gb < 2:
        docs = min(docs, 8)
        chars = min(chars, 6000)
    if profile.cpu_load and profile.cpu_load > 4:
        docs = min(docs, 8)
        chars = min(chars, 6000)
    if profile.disk_free_gb and profile.disk_free_gb < 10:
        docs = min(docs, 8)
        chars = min(chars, 6000)

    if update_state:
        state.update_state(context_budget_docs=docs, context_budget_chars=chars)
    return docs, chars


def load_context(update_state: bool = True) -> str:
    docs_budget, chars_budget = _compute_context_budget(update_state=update_state)
    paths = _load_index_paths()
    sections: List[str] = []
    total_chars = 0
    loaded_docs = 0

    for path in paths:
        if loaded_docs >= docs_budget:
            break
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        if not content.strip():
            continue
        header = f"# {path.name}\n"
        block = header + content.strip() + "\n"
        if total_chars + len(block) > chars_budget:
            break
        sections.append(block)
        total_chars += len(block)
        loaded_docs += 1

    if update_state:
        state.update_state(context_docs_loaded=loaded_docs, context_chars_loaded=total_chars)
    return "\n".join(sections).strip()
