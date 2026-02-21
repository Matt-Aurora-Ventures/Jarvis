"""Allowlist registry for typed command execution."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional, Set


def normalize_program_name(program: str) -> str:
    """Normalize executable names for policy lookup across platforms."""
    name = Path(program).name.lower()
    for suffix in (".exe", ".cmd", ".bat", ".ps1"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


@dataclass(frozen=True)
class ExecutorPolicy:
    """Policy definition for an allowlisted executor."""

    name: str
    aliases: Set[str]
    description: str

    def matches(self, program: str) -> bool:
        normalized = normalize_program_name(program)
        return normalized in self.aliases


_POLICIES: Dict[str, ExecutorPolicy] = {
    "python": ExecutorPolicy(
        name="python",
        aliases={"python", "python3", "py"},
        description="Python interpreter",
    ),
    "git": ExecutorPolicy(
        name="git",
        aliases={"git"},
        description="Git CLI",
    ),
    "pip": ExecutorPolicy(
        name="pip",
        aliases={"pip", "pip3"},
        description="Python package manager",
    ),
    "npm": ExecutorPolicy(
        name="npm",
        aliases={"npm", "npx"},
        description="Node package manager",
    ),
    "node": ExecutorPolicy(
        name="node",
        aliases={"node"},
        description="Node runtime",
    ),
    "powershell": ExecutorPolicy(
        name="powershell",
        aliases={"powershell", "pwsh"},
        description="PowerShell",
    ),
    "cmd": ExecutorPolicy(
        name="cmd",
        aliases={"cmd"},
        description="Windows command shell executable",
    ),
    "where": ExecutorPolicy(
        name="where",
        aliases={"where", "where.exe", "which"},
        description="Command lookup",
    ),
    "echo": ExecutorPolicy(
        name="echo",
        aliases={"echo"},
        description="Simple output utility",
    ),
}


def resolve_executor_policy(program: str) -> Optional[ExecutorPolicy]:
    """Resolve a policy for the given program name/path."""
    normalized = normalize_program_name(program)
    for policy in _POLICIES.values():
        if normalized in policy.aliases:
            return policy
    return None


def is_executor_allowlisted(program: str) -> bool:
    """Return True if the program is allowlisted."""
    return resolve_executor_policy(program) is not None


def iter_policies() -> Iterable[ExecutorPolicy]:
    """Iterate registered allowlist policies."""
    return _POLICIES.values()
