"""Policy validation for typed command execution."""

from typing import Iterable, Optional

from core.command_dsl.registry import resolve_executor_policy
from core.command_dsl.types import CommandValidationDecision, TypedCommand
from core.command_validator import validate_argv_before_run

_DENY_TOKENS = ("&&", "||", ";", "|", "`", "$(", ">", "<")
_SAFE_ENV_PREFIXES = (
    "JARVIS_",
    "PYTHON",
    "PATH",
    "HOME",
    "USERPROFILE",
    "TMP",
    "TEMP",
)


def _contains_shell_metachar(token: str) -> bool:
    return any(marker in token for marker in _DENY_TOKENS)


def _invalid_env_keys(keys: Iterable[str]) -> Optional[str]:
    for key in keys:
        if not key:
            return "Environment override key cannot be empty"
        if not key.isidentifier():
            return f"Environment override key is invalid: {key}"
        if not key.startswith(_SAFE_ENV_PREFIXES):
            return f"Environment override key is not allowlisted: {key}"
    return None


def validate_typed_command(command: TypedCommand) -> CommandValidationDecision:
    """Validate typed command against allowlist and argument policies."""
    if not command.argv:
        return CommandValidationDecision(allowed=False, error="argv is empty")

    policy = resolve_executor_policy(command.argv[0])
    if policy is None:
        return CommandValidationDecision(
            allowed=False,
            error=f"Executor is not allowlisted: {command.argv[0]}",
        )

    if policy.name != command.executor:
        return CommandValidationDecision(
            allowed=False,
            error=f"Executor mismatch: expected {policy.name}, got {command.executor}",
        )

    for arg in command.argv:
        if _contains_shell_metachar(arg):
            return CommandValidationDecision(
                allowed=False,
                error=f"Shell metacharacters are blocked in typed command args: {arg}",
            )

    env_key_error = _invalid_env_keys(command.env_overrides.keys())
    if env_key_error:
        return CommandValidationDecision(allowed=False, error=env_key_error)

    is_safe, error, warnings = validate_argv_before_run(command.argv)
    if not is_safe:
        return CommandValidationDecision(allowed=False, error=error, warnings=warnings)

    return CommandValidationDecision(allowed=True, warnings=warnings)
