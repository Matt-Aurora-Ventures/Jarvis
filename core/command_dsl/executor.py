"""Parsing and execution for typed command DSL."""

import os
import shlex
from typing import Any, Dict, Optional

from core.command_dsl.policies import validate_typed_command
from core.command_dsl.registry import resolve_executor_policy
from core.command_dsl.types import TypedCommand
from core.safe_subprocess import run_command_safe


def parse_typed_command(
    command: str,
    timeout: Optional[int] = None,
    cwd: Optional[str] = None,
    env_overrides: Optional[Dict[str, str]] = None,
) -> TypedCommand:
    """Parse user command text into a typed command object."""
    if not command or not command.strip():
        raise ValueError("Command is empty")

    parts = shlex.split(command, posix=(os.name != "nt"))
    if not parts:
        raise ValueError("Command is empty")

    policy = resolve_executor_policy(parts[0])
    executor_name = policy.name if policy else parts[0]

    return TypedCommand(
        executor=executor_name,
        argv=parts,
        timeout=timeout,
        cwd=cwd,
        env_overrides=env_overrides or {},
    )


def execute_typed_command(
    command: TypedCommand,
    capture_output: bool = True,
    check: bool = False,
) -> Dict[str, Any]:
    """Validate and execute a typed command with shell disabled."""
    decision = validate_typed_command(command)
    if not decision.allowed:
        return {
            "stdout": "",
            "stderr": f"Command blocked by typed DSL: {decision.error}",
            "returncode": -1,
            "timed_out": False,
            "killed": False,
            "blocked": True,
            "warnings": decision.warnings,
            "command": " ".join(command.argv),
            "timeout": command.timeout,
            "executor": command.executor,
        }

    env = None
    if command.env_overrides:
        env = os.environ.copy()
        env.update(command.env_overrides)

    result = run_command_safe(
        command.argv,
        timeout=command.timeout,
        shell=False,
        capture_output=capture_output,
        check=check,
        cwd=command.cwd,
        env=env,
    )
    result["warnings"] = decision.warnings
    result["executor"] = command.executor
    return result
