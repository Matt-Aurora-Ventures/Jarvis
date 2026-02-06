"""
Centralized Environment Loading Utility

Provides isolated, validated environment variable loading for components.
Prevents credential leakage and ensures proper component isolation.

Usage:
    from core.config.env_loader import load_component_env

    result = load_component_env(
        component_path=Path(__file__).parent,
        required_vars=["API_KEY", "SECRET_TOKEN"],
        optional_vars=["DEBUG_MODE"],
        validate=True
    )
"""

import os
from pathlib import Path
from typing import List, Optional, Dict, Set
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class EnvLoadResult:
    """Result of loading environment variables"""
    loaded_vars: List[str] = field(default_factory=list)
    missing_vars: List[str] = field(default_factory=list)
    path: Optional[Path] = None
    warnings: List[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """True if all required vars were loaded"""
        return len(self.missing_vars) == 0

    def __str__(self) -> str:
        status = "✓" if self.success else "✗"
        return (
            f"{status} EnvLoadResult:\n"
            f"  Path: {self.path}\n"
            f"  Loaded: {len(self.loaded_vars)} vars\n"
            f"  Missing: {len(self.missing_vars)} vars\n"
            f"  Warnings: {len(self.warnings)}"
        )


def load_component_env(
    component_path: Path,
    required_vars: Optional[List[str]] = None,
    optional_vars: Optional[List[str]] = None,
    validate: bool = True,
    env_file_name: str = ".env"
) -> EnvLoadResult:
    """
    Load .env file for a component with isolation guarantees

    This function:
    - Loads .env with override=False (never overwrites existing vars)
    - Validates required vars exist
    - Tracks loaded vs missing vars
    - Logs warnings for common issues
    - Ensures component isolation

    Args:
        component_path: Path to component directory (e.g., Path(__file__).parent)
        required_vars: List of required environment variable names
        optional_vars: List of optional environment variable names
        validate: Whether to raise error on missing required vars
        env_file_name: Name of .env file (default: ".env")

    Returns:
        EnvLoadResult with loaded/missing vars and any warnings

    Raises:
        FileNotFoundError: If .env doesn't exist and validation enabled
        ValueError: If validation enabled and required vars missing

    Example:
        >>> from pathlib import Path
        >>> result = load_component_env(
        ...     component_path=Path(__file__).parent,
        ...     required_vars=["TELEGRAM_BOT_TOKEN"],
        ...     optional_vars=["DEBUG_MODE"],
        ...     validate=True
        ... )
        >>> print(result)
        ✓ EnvLoadResult:
          Path: /path/to/component/.env
          Loaded: 1 vars
          Missing: 0 vars
          Warnings: 0
    """
    required_vars = required_vars or []
    optional_vars = optional_vars or []
    all_vars = set(required_vars + optional_vars)

    result = EnvLoadResult(path=component_path / env_file_name)

    # Check if .env file exists
    env_path = component_path / env_file_name
    if not env_path.exists():
        if validate and required_vars:
            raise FileNotFoundError(
                f"Component .env not found: {env_path}\n"
                f"Required variables: {required_vars}"
            )
        result.warnings.append(f".env file not found: {env_path}")
        result.missing_vars = required_vars
        return result

    # Capture vars before loading
    vars_before = set(os.environ.keys())

    # Load with override=False (NEVER overwrite existing vars)
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path, override=False)
        logger.debug(f"Loaded .env from {env_path}")
    except Exception as e:
        result.warnings.append(f"Failed to load .env: {e}")
        if validate:
            raise RuntimeError(f"Failed to load .env from {env_path}: {e}")
        return result

    # Capture vars after loading (for audit trail)
    vars_after = set(os.environ.keys())
    newly_loaded = vars_after - vars_before

    # Check which vars from our list were actually loaded
    loaded_from_file = all_vars & newly_loaded

    # Check required vars
    for var in required_vars:
        if os.getenv(var):
            result.loaded_vars.append(var)
            if var not in loaded_from_file:
                # Var exists but wasn't loaded from this file (pre-existing)
                result.warnings.append(
                    f"{var} exists but was not loaded from {env_path} "
                    "(pre-existing in environment)"
                )
        else:
            result.missing_vars.append(var)

    # Check optional vars
    for var in optional_vars:
        if os.getenv(var):
            result.loaded_vars.append(var)
            if var not in loaded_from_file:
                result.warnings.append(
                    f"{var} exists but was not loaded from {env_path} "
                    "(pre-existing in environment)"
                )

    # Validate required vars
    if validate and result.missing_vars:
        raise ValueError(
            f"Component at {component_path} missing required environment variables:\n"
            f"  Missing: {result.missing_vars}\n"
            f"  Please add them to {env_path}\n"
            f"  Loaded: {result.loaded_vars}"
        )

    # Log result
    if result.warnings:
        for warning in result.warnings:
            logger.warning(warning)

    logger.info(
        f"Loaded {len(result.loaded_vars)} vars from {env_path} "
        f"(missing: {len(result.missing_vars)})"
    )

    return result


def get_var_or_raise(var_name: str, component_name: str = "Component") -> str:
    """
    Get environment variable or raise descriptive error

    Args:
        var_name: Name of environment variable
        component_name: Name of component for error message

    Returns:
        Value of environment variable

    Raises:
        ValueError: If variable not set

    Example:
        >>> api_key = get_var_or_raise("XAI_API_KEY", "Twitter Bot")
    """
    value = os.getenv(var_name)
    if not value:
        raise ValueError(
            f"{component_name} requires {var_name} environment variable.\n"
            f"Please set it in your .env file or environment."
        )
    return value


def get_var_with_default(
    var_name: str,
    default: str,
    warn_if_missing: bool = True
) -> str:
    """
    Get environment variable with default value

    Args:
        var_name: Name of environment variable
        default: Default value if not set
        warn_if_missing: Whether to log warning if using default

    Returns:
        Value from env or default

    Example:
        >>> debug = get_var_with_default("DEBUG_MODE", "false")
    """
    value = os.getenv(var_name)
    if not value:
        if warn_if_missing:
            logger.warning(f"{var_name} not set, using default: {default}")
        return default
    return value


def check_var_conflicts(
    component_name: str,
    expected_vars: List[str],
    forbidden_vars: List[str]
) -> List[str]:
    """
    Check for environment variable conflicts

    Useful for detecting when a component has access to credentials
    it shouldn't have (environment bleed).

    Args:
        component_name: Name of component
        expected_vars: Vars this component should have
        forbidden_vars: Vars this component should NOT have

    Returns:
        List of conflicts (empty if none)

    Example:
        >>> conflicts = check_var_conflicts(
        ...     "Twitter Bot",
        ...     expected_vars=["XAI_API_KEY", "X_API_KEY"],
        ...     forbidden_vars=["TELEGRAM_BOT_TOKEN", "TREASURY_BOT_TOKEN"]
        ... )
        >>> if conflicts:
        ...     raise SecurityError(f"Environment bleed detected: {conflicts}")
    """
    conflicts = []

    # Check expected vars are present
    for var in expected_vars:
        if not os.getenv(var):
            conflicts.append(f"Missing expected var: {var}")

    # Check forbidden vars are NOT present
    for var in forbidden_vars:
        if os.getenv(var):
            conflicts.append(
                f"Forbidden var present: {var} "
                f"(possible environment bleed in {component_name})"
            )

    if conflicts:
        logger.error(
            f"Environment conflicts detected in {component_name}:\n"
            + "\n".join(f"  - {c}" for c in conflicts)
        )

    return conflicts


def audit_environment(
    component_name: str,
    show_values: bool = False
) -> Dict[str, any]:
    """
    Audit current environment variables for a component

    Useful for debugging and security audits.

    Args:
        component_name: Name of component
        show_values: Whether to show actual values (SECURITY RISK - use only for debugging)

    Returns:
        Dict with audit information

    Example:
        >>> audit = audit_environment("Twitter Bot")
        >>> print(audit['total_vars'])
        42
    """
    all_vars = dict(os.environ)

    # Group by prefix
    by_prefix: Dict[str, List[str]] = {}
    for key in all_vars:
        prefix = key.split("_")[0] if "_" in key else "OTHER"
        if prefix not in by_prefix:
            by_prefix[prefix] = []
        by_prefix[prefix].append(key)

    # Identify likely credentials (heuristic)
    credential_indicators = ["KEY", "TOKEN", "SECRET", "PASSWORD", "AUTH"]
    credentials = [
        key for key in all_vars
        if any(indicator in key.upper() for indicator in credential_indicators)
    ]

    audit = {
        "component": component_name,
        "total_vars": len(all_vars),
        "by_prefix": {k: len(v) for k, v in by_prefix.items()},
        "credential_count": len(credentials),
        "credential_names": credentials,
    }

    if show_values:
        # SECURITY WARNING: Only use for debugging!
        audit["values"] = {
            k: v[:10] + "..." + v[-4:] if len(v) > 14 else "***"
            for k, v in all_vars.items()
        }
        logger.warning(
            f"Environment audit for {component_name} includes VALUES - "
            "this is a security risk if logged!"
        )

    logger.info(
        f"Environment audit for {component_name}:\n"
        f"  Total vars: {audit['total_vars']}\n"
        f"  Credentials: {audit['credential_count']}\n"
        f"  Prefixes: {list(by_prefix.keys())}"
    )

    return audit


# Testing
if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.DEBUG)

    print("=" * 80)
    print("Environment Loader Utility - Self Test")
    print("=" * 80)

    # Test 1: Load from current directory (will likely fail - that's OK)
    print("\nTest 1: Load from current directory")
    try:
        result = load_component_env(
            component_path=Path(__file__).parent,
            required_vars=["TEST_VAR"],
            validate=False
        )
        print(result)
    except Exception as e:
        print(f"Expected failure: {e}")

    # Test 2: Get var with default
    print("\nTest 2: Get var with default")
    debug_mode = get_var_with_default("DEBUG_MODE", "false", warn_if_missing=False)
    print(f"DEBUG_MODE = {debug_mode}")

    # Test 3: Audit environment
    print("\nTest 3: Audit environment")
    audit = audit_environment("Test Component", show_values=False)
    print(f"Total environment variables: {audit['total_vars']}")
    print(f"Detected credentials: {audit['credential_count']}")

    print("\n" + "=" * 80)
    print("Self-test complete. See above for results.")
    print("=" * 80)
