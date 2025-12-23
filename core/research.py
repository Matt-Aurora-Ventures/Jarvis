from typing import Dict


def evaluate_issue(issue: str, allow_web: bool = False) -> Dict[str, str]:
    if not allow_web:
        return {
            "status": "needs_web_research",
            "note": "Web research is disabled in this environment.",
        }
    return {
        "status": "not_implemented",
        "note": "Web research pipeline is a stub for now.",
    }
