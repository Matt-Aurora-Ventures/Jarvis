"""Prompt package exports with legacy compatibility."""

from __future__ import annotations

from core.prompts.library import PromptLibrary
from core.prompts.templates import PromptTemplate

__all__ = ["PromptLibrary", "PromptTemplate"]

# Keep older `from core import prompts` callsites working by exposing symbols from
# the legacy single-file module if present.
try:
    import importlib.util
    from pathlib import Path

    _legacy_path = Path(__file__).resolve().parents[1] / "prompts.py"
    if _legacy_path.exists():
        _spec = importlib.util.spec_from_file_location("_core_prompts_legacy", _legacy_path)
        if _spec and _spec.loader:
            _legacy = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_legacy)
            for _name in dir(_legacy):
                if _name.startswith("_"):
                    continue
                if _name in globals():
                    continue
                globals()[_name] = getattr(_legacy, _name)
                __all__.append(_name)
except Exception:
    # Legacy fallback should never block imports for tests/runtime.
    pass
