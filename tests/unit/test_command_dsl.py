"""Unit tests for typed command DSL execution path."""

from __future__ import annotations

import sys

from core.command_dsl.executor import execute_typed_command, parse_typed_command
from core.command_dsl.types import TypedCommand


def test_unknown_executor_is_blocked() -> None:
    cmd = TypedCommand(executor="unknown", argv=["unknown", "--help"], timeout=5)
    result = execute_typed_command(cmd)

    assert result["blocked"] is True
    assert result["returncode"] == -1
    assert "allowlisted" in result["stderr"]


def test_shell_metacharacters_are_blocked() -> None:
    cmd = TypedCommand(
        executor="python",
        argv=[sys.executable, "&&", "whoami"],
        timeout=5,
    )
    result = execute_typed_command(cmd)

    assert result["blocked"] is True
    assert "metacharacters" in result["stderr"]


def test_allowlisted_command_executes_with_shell_disabled() -> None:
    cmd = TypedCommand(
        executor="python",
        argv=[sys.executable, "-c", "print('typed-dsl-ok')"],
        timeout=10,
    )
    result = execute_typed_command(cmd)

    assert result["blocked"] is False
    assert result["returncode"] == 0
    assert "typed-dsl-ok" in result["stdout"]


def test_parse_typed_command_resolves_executor_policy() -> None:
    typed = parse_typed_command("git status")
    assert typed.executor == "git"
    assert typed.argv[0] == "git"
