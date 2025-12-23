from typing import Dict, Tuple


def not_implemented(
    command_name: str,
    planned_action: str,
    next_phase: str,
) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str]]:
    plain = {
        "What I did": (
            f"Confirmed '{command_name}' is available but not implemented yet. "
            "No changes were made."
        ),
        "Why I did it": f"This command is scheduled for {next_phase}.",
        "What happens next": planned_action,
        "What I need from you": "Nothing right now.",
    }
    technical = {
        "Modules/files involved": "core/commands.py",
        "Key concepts/terms": "Stubs, phase-based rollout",
        "Commands executed (or would execute in dry-run)": "None",
        "Risks/constraints": "No side effects; placeholder only.",
    }
    glossary = {
        "Stub": "A placeholder function that reserves a command for a later phase."
    }
    return plain, technical, glossary
