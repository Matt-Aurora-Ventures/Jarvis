"""
AI Agents Module

Base agents and specialized implementations.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from .base import BaseAgent, Capabilities
from .capabilities import AgentCapabilities

_module_path = Path(__file__).resolve().parents[1] / "agents.py"
_spec = importlib.util.spec_from_file_location("core.ai_runtime._agents_module", _module_path)
_agents_module = importlib.util.module_from_spec(_spec) if _spec and _spec.loader else None
if _agents_module and _spec and _spec.loader:
    sys.modules[_spec.name] = _agents_module
    _spec.loader.exec_module(_agents_module)
else:
    _agents_module = None

if _agents_module:
    AgentReport = _agents_module.AgentReport
    ComponentAgent = _agents_module.ComponentAgent
    build_default_agents = _agents_module.build_default_agents
    error_tracker = _agents_module.error_tracker
else:
    AgentReport = None
    ComponentAgent = None
    build_default_agents = None
    error_tracker = None

if TYPE_CHECKING:  # pragma: no cover - typing helpers
    from typing import Callable
    from typing import Any, List

__all__ = [
    "BaseAgent",
    "Capabilities",
    "AgentCapabilities",
    "AgentReport",
    "ComponentAgent",
    "build_default_agents",
    "error_tracker",
]
