"""Unit tests for typed command DSL registry policies."""

from core.command_dsl.registry import (
    is_executor_allowlisted,
    normalize_program_name,
    resolve_executor_policy,
)


def test_normalize_program_name_strips_windows_suffix() -> None:
    assert normalize_program_name("C:/Python/python.exe") == "python"
    assert normalize_program_name("POWERSHELL.EXE") == "powershell"


def test_allowlisted_executors_include_common_safe_tools() -> None:
    assert is_executor_allowlisted("python")
    assert is_executor_allowlisted("git")
    assert is_executor_allowlisted("powershell.exe")


def test_non_allowlisted_shell_wrappers_are_rejected() -> None:
    assert not is_executor_allowlisted("bash")
    assert not is_executor_allowlisted("zsh")
    assert resolve_executor_policy("bash") is None
