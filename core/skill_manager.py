import importlib.util
import re
from pathlib import Path
from typing import Dict, Optional

from core import output, providers, safety

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"


def _slugify(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return cleaned or "custom_skill"


def _skill_path(name: str) -> Path:
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    return SKILLS_DIR / f"{name}.py"


def _generate_skill_code(name: str, request: str) -> Optional[str]:
    prompt = (
        "Create a minimal Python skill module for LifeOS.\n"
        "Output ONLY Python code, no markdown.\n"
        "Constraints:\n"
        "- Define SKILL_NAME and DESCRIPTION.\n"
        "- Provide a run(context: dict, **kwargs) -> str function.\n"
        "- Keep it lightweight and safe (no destructive actions).\n"
        f"Skill name: {name}\n"
        f"User request: {request}\n"
    )
    text = providers.generate_text(prompt, max_output_tokens=400)
    if not text:
        return None
    return text.strip()


def _fallback_skill_code(name: str, request: str) -> str:
    return (
        f'SKILL_NAME = "{name}"\n'
        f'DESCRIPTION = "Auto-generated skill: {request}"\n'
        "\n"
        "def run(context: dict, **kwargs) -> str:\n"
        "    return (\n"
        "        \"This skill was created as a stub. \"\n"
        "        \"Please refine its behavior with a more specific request.\"\n"
        "    )\n"
    )


def _load_skill(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    return None


def create_skill(request: str, context: safety.SafetyContext) -> str:
    name = _slugify(request)[:40]
    path = _skill_path(name)
    planned_action = f"Create skill file at {path}"

    plain = {
        "What I did": "Prepared to create a new skill.",
        "Why I did it": "You asked me to add a new ability.",
        "What happens next": "Confirm APPLY to generate the skill file.",
        "What I need from you": "Type APPLY to confirm.",
    }
    technical = {
        "Modules/files involved": "core/skill_manager.py, skills/",
        "Key concepts/terms": "Dynamic module loading, skill stubs",
        "Commands executed (or would execute in dry-run)": planned_action,
        "Risks/constraints": "Write action requires APPLY.",
    }

    if context.dry_run:
        return output.render(plain, technical)

    if not safety.allow_action(context, "Create skill file"):
        plain["What I did"] = "Canceled skill creation because APPLY was not confirmed."
        plain["What happens next"] = "Try again and confirm APPLY."
        plain["What I need from you"] = "Type APPLY to confirm."
        return output.render(plain, technical)

    code = _generate_skill_code(name, request)
    if not code:
        code = _fallback_skill_code(name, request)
    path.write_text(code + "\n", encoding="utf-8")
    module = _load_skill(path)

    plain = {
        "What I did": "Created a new skill file.",
        "Why I did it": "You asked for a new ability.",
        "What happens next": f"Skill is saved as {path.name}.",
        "What I need from you": "Tell me how you want to use it.",
    }
    technical = {
        "Modules/files involved": "core/skill_manager.py, skills/",
        "Key concepts/terms": "Dynamic import",
        "Commands executed (or would execute in dry-run)": planned_action,
        "Risks/constraints": "Generated code should be reviewed before heavy use.",
    }
    if module:
        technical["Key concepts/terms"] = "Dynamic import, skill module loaded"
    return output.render(plain, technical)
