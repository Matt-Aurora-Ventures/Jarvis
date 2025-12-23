from typing import Dict, Iterable, Optional

PLAIN_ORDER = (
    "What I did",
    "Why I did it",
    "What happens next",
    "What I need from you",
)

TECH_ORDER = (
    "Modules/files involved",
    "Key concepts/terms",
    "Commands executed (or would execute in dry-run)",
    "Risks/constraints",
)


def _ordered_items(data: Dict[str, str], order: Iterable[str]) -> Iterable[tuple[str, str]]:
    seen = set()
    for key in order:
        if key in data:
            seen.add(key)
            yield key, data[key]
    for key, value in data.items():
        if key not in seen:
            yield key, value


def render(
    plain: Dict[str, str],
    technical: Dict[str, str],
    glossary: Optional[Dict[str, str]] = None,
) -> str:
    lines: list[str] = ["Plain English:"]
    for key, value in _ordered_items(plain, PLAIN_ORDER):
        lines.append(f"- {key}: {value}")

    lines.append("")
    lines.append("Technical Notes:")
    for key, value in _ordered_items(technical, TECH_ORDER):
        lines.append(f"- {key}: {value}")

    if glossary:
        lines.append("")
        lines.append("Glossary:")
        for term, definition in glossary.items():
            lines.append(f"- {term}: {definition}")

    return "\n".join(lines)
