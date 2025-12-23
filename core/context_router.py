from pathlib import Path
from typing import Dict, List, Tuple

from core import safety

ROOT = Path(__file__).resolve().parents[1]
CONTEXT_DIR = ROOT / "lifeos" / "context"

DEFAULT_ROUTES = [
    ("finance", "context/finance/inbox.md"),
    ("habit", "context/habits/inbox.md"),
    ("project", "context/projects/inbox.md"),
    ("goal", "context/goals.md"),
    ("principle", "context/principles.md"),
]


def _routes() -> List[Tuple[str, str]]:
    return DEFAULT_ROUTES


def _resolve_path(route_path: str) -> Path:
    return CONTEXT_DIR / route_path.replace("context/", "")


def route_entries(entries: List[Dict[str, str]]) -> Dict[str, List[str]]:
    routed: Dict[str, List[str]] = {}
    routes = _routes()
    for entry in entries:
        text = entry.get("text", "")
        lower = text.lower()
        target = "context/projects/inbox.md"
        matched = False
        for keyword, route_path in routes:
            if keyword in lower:
                target = route_path
                matched = True
                break
        if not matched:
            routed.setdefault(target, []).append(f"[Needs routing] {text}")
        else:
            routed.setdefault(target, []).append(text)
    return routed


def apply_routes(
    routed: Dict[str, List[str]],
    context: safety.SafetyContext,
) -> List[Path]:
    written: List[Path] = []
    if context.dry_run:
        return written
    for route, items in routed.items():
        path = _resolve_path(route)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            for item in items:
                handle.write(f"- {item}\n")
        written.append(path)
    return written
