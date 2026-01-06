from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any, Optional

_MODULE_PATH = Path(__file__).resolve().parents[1] / "evolution.py"
_EVOLUTION_MODULE = None


def _load_evolution_module():
    global _EVOLUTION_MODULE
    if _EVOLUTION_MODULE is not None:
        return _EVOLUTION_MODULE
    if not _MODULE_PATH.exists():
        return None
    spec = spec_from_file_location("core._evolution_module", _MODULE_PATH)
    if spec and spec.loader:
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        _EVOLUTION_MODULE = module
        return module
    return None


module = _load_evolution_module()
if module and hasattr(module, "ImprovementProposal"):
    ImprovementProposal = module.ImprovementProposal


class Evolution:
    """Compatibility wrapper for evolution module functionality."""

    def __init__(self) -> None:
        self._module = _load_evolution_module()

    def get_stats(self) -> dict:
        if self._module:
            return self._module.get_evolution_stats()
        return {
            "total_improvements": 0,
            "skills_created": 0,
            "proposals_saved": 0,
            "last_improvement": None,
        }

    def list_skills(self) -> list:
        if self._module:
            return self._module.list_skills()
        return []

    def propose_from_request(self, user_request: str) -> Optional[Any]:
        if self._module:
            return self._module.propose_improvement_from_request(user_request)
        return None

    def evolve_from_conversation(
        self,
        user_text: str,
        conversation_history: list,
        context: Any,
    ) -> str:
        if self._module:
            return self._module.evolve_from_conversation(user_text, conversation_history, context)
        return "Evolution module unavailable."

    def apply_improvement(self, proposal: Any, context: Any = None, dry_run: Optional[bool] = None) -> dict:
        if self._module:
            return self._module.apply_improvement(proposal, context=context, dry_run=dry_run)
        return {"status": "unavailable", "success": False, "applied": False}

    def auto_evolve_on_boot(self) -> dict:
        if self._module:
            return self._module.auto_evolve_on_boot()
        return {"checked": False, "improvements_found": 0, "improvements_applied": 0, "errors": ["missing module"]}

    def continuous_improvement_check(self) -> Optional[Any]:
        if self._module:
            return self._module.continuous_improvement_check()
        return None


def __getattr__(name: str):
    module = _load_evolution_module()
    if module and hasattr(module, name):
        return getattr(module, name)
    raise AttributeError(f"module 'core.evolution' has no attribute '{name}'")


def __dir__():
    module = _load_evolution_module()
    base = set(globals().keys())
    if not module:
        return sorted(base)
    return sorted(base | set(dir(module)))


__all__ = ["Evolution", "ImprovementProposal"]
