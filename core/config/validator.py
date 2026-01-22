"""
Comprehensive Configuration Validation.

Validates all environment variables and configuration at startup.
Fails fast with clear error messages if configuration is invalid.

Usage:
    from core.config.validator import validate_config, ConfigValidationError

    # Validate all config at startup
    validate_config(strict=True)  # Raises on error

    # Or get detailed report
    is_valid, errors = validate_config(strict=False)
    if not is_valid:
        for error in errors:
            print(f"❌ {error}")
"""

import os
import re
import logging
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """Validation severity levels."""
    ERROR = "error"  # Must be fixed, blocks startup
    WARNING = "warning"  # Should be fixed, but not critical
    INFO = "info"  # Optional, informational only


@dataclass
class ValidationRule:
    """A single validation rule for a config value."""
    key: str
    description: str
    validator: Callable[[Any], Tuple[bool, Optional[str]]]
    level: ValidationLevel = ValidationLevel.ERROR
    required: bool = True
    default: Optional[Any] = None
    group: str = "general"


@dataclass
class ValidationResult:
    """Result of a validation check."""
    key: str
    level: ValidationLevel
    message: str
    is_valid: bool = False


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    def __init__(self, errors: List[ValidationResult]):
        self.errors = errors
        error_msgs = [f"{e.level.value.upper()}: {e.key} - {e.message}" for e in errors]
        super().__init__("\n".join(error_msgs))


class ConfigValidator:
    """Validates Jarvis configuration."""

    # Solana address pattern (base58, 32-44 chars)
    SOLANA_ADDRESS_PATTERN = re.compile(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$')

    # URL pattern
    URL_PATTERN = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE
    )

    # API key patterns (common formats)
    API_KEY_PATTERNS = {
        "generic": re.compile(r'^[A-Za-z0-9_\-]{20,}$'),  # At least 20 alphanumeric chars
        "xai": re.compile(r'^xai-[A-Za-z0-9]{40,}$'),  # XAI format
        "anthropic": re.compile(r'^sk-ant-[A-Za-z0-9\-_]{40,}$'),  # Anthropic format
        "twitter_bearer": re.compile(r'^[A-Za-z0-9%]{100,}$'),  # Twitter bearer tokens
    }

    def __init__(self):
        self.rules: List[ValidationRule] = []
        self._setup_rules()

    def _setup_rules(self):
        """Define all validation rules."""

        # === TELEGRAM CONFIG ===
        self.rules.append(ValidationRule(
            key="TELEGRAM_BOT_TOKEN",
            description="Telegram bot token",
            validator=self._validate_telegram_token,
            level=ValidationLevel.ERROR,
            required=True,
            group="telegram"
        ))

        self.rules.append(ValidationRule(
            key="TELEGRAM_ADMIN_IDS",
            description="Comma-separated Telegram admin user IDs",
            validator=self._validate_admin_ids,
            level=ValidationLevel.ERROR,
            required=True,
            group="telegram"
        ))

        self.rules.append(ValidationRule(
            key="TELEGRAM_BUY_BOT_CHAT_ID",
            description="Telegram chat ID for buy notifications",
            validator=self._validate_chat_id,
            level=ValidationLevel.WARNING,
            required=False,
            group="telegram"
        ))

        self.rules.append(ValidationRule(
            key="TELEGRAM_BROADCAST_CHAT_ID",
            description="Telegram broadcast chat ID",
            validator=self._validate_chat_id,
            level=ValidationLevel.WARNING,
            required=False,
            group="telegram"
        ))

        # === WALLET CONFIG ===
        self.rules.append(ValidationRule(
            key="TREASURY_WALLET_ADDRESS",
            description="Solana treasury wallet address",
            validator=self._validate_solana_address,
            level=ValidationLevel.WARNING,
            required=False,
            group="wallet"
        ))

        self.rules.append(ValidationRule(
            key="TREASURY_WALLET_PATH",
            description="Path to wallet keypair JSON file",
            validator=self._validate_wallet_path,
            level=ValidationLevel.WARNING,
            required=False,
            group="wallet"
        ))

        self.rules.append(ValidationRule(
            key="JARVIS_WALLET_PASSWORD",
            description="Wallet encryption password",
            validator=self._validate_password,
            level=ValidationLevel.WARNING,
            required=False,
            group="wallet"
        ))

        self.rules.append(ValidationRule(
            key="WALLET_PRIVATE_KEY",
            description="Direct wallet private key (less secure than keypair file)",
            validator=self._validate_private_key,
            level=ValidationLevel.WARNING,
            required=False,
            group="wallet"
        ))

        # === API KEYS ===
        self.rules.append(ValidationRule(
            key="XAI_API_KEY",
            description="X.AI (Grok) API key",
            validator=lambda v: self._validate_api_key(v, "xai"),
            level=ValidationLevel.WARNING,
            required=False,
            group="apis"
        ))

        self.rules.append(ValidationRule(
            key="ANTHROPIC_API_KEY",
            description="Anthropic (Claude) API key",
            validator=self._validate_anthropic_key,
            level=ValidationLevel.WARNING,
            required=False,
            group="apis"
        ))

        self.rules.append(ValidationRule(
            key="ANTHROPIC_BASE_URL",
            description="Anthropic API base URL override (e.g., Ollama local gateway)",
            validator=self._validate_url,
            level=ValidationLevel.INFO,
            required=False,
            group="apis"
        ))

        self.rules.append(ValidationRule(
            key="HELIUS_API_KEY",
            description="Helius API key for Solana data",
            validator=lambda v: self._validate_api_key(v, "generic"),
            level=ValidationLevel.WARNING,
            required=False,
            group="apis"
        ))

        self.rules.append(ValidationRule(
            key="BIRDEYE_API_KEY",
            description="BirdEye API key for token data",
            validator=lambda v: self._validate_api_key(v, "generic"),
            level=ValidationLevel.INFO,
            required=False,
            group="apis"
        ))

        # === TWITTER/X CONFIG ===
        self.rules.append(ValidationRule(
            key="X_API_KEY",
            description="Twitter/X API key",
            validator=lambda v: self._validate_api_key(v, "generic"),
            level=ValidationLevel.WARNING,
            required=False,
            group="twitter"
        ))

        self.rules.append(ValidationRule(
            key="X_API_SECRET",
            description="Twitter/X API secret",
            validator=lambda v: self._validate_api_key(v, "generic"),
            level=ValidationLevel.WARNING,
            required=False,
            group="twitter"
        ))

        self.rules.append(ValidationRule(
            key="X_ACCESS_TOKEN",
            description="Twitter/X access token",
            validator=lambda v: self._validate_api_key(v, "generic"),
            level=ValidationLevel.WARNING,
            required=False,
            group="twitter"
        ))

        self.rules.append(ValidationRule(
            key="X_ACCESS_TOKEN_SECRET",
            description="Twitter/X access token secret",
            validator=lambda v: self._validate_api_key(v, "generic"),
            level=ValidationLevel.WARNING,
            required=False,
            group="twitter"
        ))

        self.rules.append(ValidationRule(
            key="X_BEARER_TOKEN",
            description="Twitter/X bearer token",
            validator=lambda v: self._validate_api_key(v, "twitter_bearer"),
            level=ValidationLevel.WARNING,
            required=False,
            group="twitter"
        ))

        self.rules.append(ValidationRule(
            key="JARVIS_ACCESS_TOKEN",
            description="Jarvis Twitter account access token",
            validator=lambda v: self._validate_api_key(v, "generic"),
            level=ValidationLevel.WARNING,
            required=False,
            group="twitter"
        ))

        # === RPC URLS ===
        self.rules.append(ValidationRule(
            key="SOLANA_RPC_URL",
            description="Solana RPC endpoint URL",
            validator=self._validate_url,
            level=ValidationLevel.WARNING,
            required=False,
            default="https://api.mainnet-beta.solana.com",
            group="rpc"
        ))

        self.rules.append(ValidationRule(
            key="HELIUS_RPC_URL",
            description="Helius RPC endpoint URL",
            validator=self._validate_url,
            level=ValidationLevel.INFO,
            required=False,
            group="rpc"
        ))

        # === TRADING CONFIG ===
        self.rules.append(ValidationRule(
            key="TREASURY_LIVE_MODE",
            description="Enable live trading (true/false)",
            validator=self._validate_boolean,
            level=ValidationLevel.WARNING,
            required=False,
            default="false",
            group="trading"
        ))

        self.rules.append(ValidationRule(
            key="BUY_BOT_MIN_USD",
            description="Minimum buy amount in USD",
            validator=lambda v: self._validate_float_range(v, min_val=0.0, max_val=100000.0),
            level=ValidationLevel.INFO,
            required=False,
            default="5.0",
            group="trading"
        ))

        self.rules.append(ValidationRule(
            key="LOW_BALANCE_THRESHOLD",
            description="Low balance warning threshold (SOL)",
            validator=lambda v: self._validate_float_range(v, min_val=0.0, max_val=100.0),
            level=ValidationLevel.INFO,
            required=False,
            default="0.01",
            group="trading"
        ))

        # === MONITORING ===
        self.rules.append(ValidationRule(
            key="HEALTH_PORT",
            description="Health check HTTP server port",
            validator=lambda v: self._validate_port(v),
            level=ValidationLevel.INFO,
            required=False,
            default="8080",
            group="monitoring"
        ))

        self.rules.append(ValidationRule(
            key="MONITORING_PORT",
            description="Monitoring metrics port",
            validator=lambda v: self._validate_port(v),
            level=ValidationLevel.INFO,
            required=False,
            group="monitoring"
        ))

        # === KILL SWITCHES ===
        self.rules.append(ValidationRule(
            key="LIFEOS_KILL_SWITCH",
            description="Emergency kill switch (true/false)",
            validator=self._validate_boolean,
            level=ValidationLevel.WARNING,
            required=False,
            default="false",
            group="safety"
        ))

        self.rules.append(ValidationRule(
            key="X_BOT_ENABLED",
            description="Enable Twitter/X bot (true/false)",
            validator=self._validate_boolean,
            level=ValidationLevel.INFO,
            required=False,
            default="true",
            group="safety"
        ))

    # === VALIDATORS ===

    def _validate_telegram_token(self, value: str) -> Tuple[bool, Optional[str]]:
        """Validate Telegram bot token format."""
        if not value:
            return False, "Telegram bot token is required"

        # Telegram tokens are format: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz
        # Bot ID (8-10 digits) : Token (30-40+ alphanumeric/underscore/dash)
        pattern = re.compile(r'^\d{8,10}:[A-Za-z0-9_-]{30,}$')
        if not pattern.match(value):
            return False, "Invalid Telegram token format (expected: 123456789:ABC...)"

        return True, None

    def _validate_admin_ids(self, value: str) -> Tuple[bool, Optional[str]]:
        """Validate admin IDs (comma-separated integers)."""
        if not value:
            return False, "At least one admin ID is required"

        ids = [s.strip() for s in value.split(",")]
        for id_str in ids:
            if not id_str.isdigit():
                return False, f"Invalid admin ID: {id_str} (must be numeric)"

            # Telegram user IDs are typically 9-10 digits
            if len(id_str) < 6 or len(id_str) > 15:
                return False, f"Suspicious admin ID length: {id_str}"

        return True, None

    def _validate_chat_id(self, value: str) -> Tuple[bool, Optional[str]]:
        """Validate Telegram chat ID (can be negative for groups)."""
        if not value:
            return True, None  # Optional

        # Remove leading minus if present
        num_str = value.lstrip("-")
        if not num_str.isdigit():
            return False, f"Invalid chat ID: {value} (must be numeric, optionally negative)"

        return True, None

    def _validate_solana_address(self, value: str) -> Tuple[bool, Optional[str]]:
        """Validate Solana wallet address (base58)."""
        if not value:
            return True, None  # Optional

        if not self.SOLANA_ADDRESS_PATTERN.match(value):
            return False, "Invalid Solana address format (expected base58, 32-44 chars)"

        return True, None

    def _validate_wallet_path(self, value: str) -> Tuple[bool, Optional[str]]:
        """Validate wallet keypair file path."""
        if not value:
            return True, None  # Optional

        path = Path(value).expanduser()
        if not path.exists():
            return False, f"Wallet file does not exist: {path}"

        if not path.is_file():
            return False, f"Wallet path is not a file: {path}"

        # Check if it's JSON
        try:
            import json
            with open(path, "r") as f:
                data = json.load(f)
                if not isinstance(data, list) or len(data) != 64:
                    return False, "Wallet file must be a JSON array of 64 bytes"
        except json.JSONDecodeError:
            return False, "Wallet file is not valid JSON"
        except Exception as e:
            return False, f"Cannot read wallet file: {e}"

        return True, None

    def _validate_password(self, value: str) -> Tuple[bool, Optional[str]]:
        """Validate wallet password strength."""
        if not value:
            return True, None  # Optional (but warned)

        if len(value) < 12:
            return False, "Password must be at least 12 characters"

        # Check complexity
        has_upper = any(c.isupper() for c in value)
        has_lower = any(c.islower() for c in value)
        has_digit = any(c.isdigit() for c in value)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in value)

        if not (has_upper and has_lower and has_digit):
            return False, "Password must contain uppercase, lowercase, and digits"

        return True, None

    def _validate_private_key(self, value: str) -> Tuple[bool, Optional[str]]:
        """Validate private key format."""
        if not value:
            return True, None  # Optional

        # Private keys are typically base58 or hex
        if len(value) < 32:
            return False, "Private key is too short"

        # Check for base58 or hex
        is_base58 = bool(self.SOLANA_ADDRESS_PATTERN.match(value))
        is_hex = bool(re.match(r'^[0-9a-fA-F]+$', value))

        if not (is_base58 or is_hex):
            return False, "Private key must be base58 or hex format"

        return True, None

    def _validate_api_key(self, value: str, key_type: str = "generic") -> Tuple[bool, Optional[str]]:
        """Validate API key format."""
        if not value:
            return True, None  # Optional

        pattern = self.API_KEY_PATTERNS.get(key_type, self.API_KEY_PATTERNS["generic"])
        if not pattern.match(value):
            return False, f"Invalid {key_type} API key format"

        return True, None

    def _validate_anthropic_key(self, value: str) -> Tuple[bool, Optional[str]]:
        """Validate Anthropic key, allowing local gateways with custom tokens."""
        if not value:
            return True, None  # Optional

        if os.getenv("ANTHROPIC_BASE_URL"):
            return True, None

        pattern = self.API_KEY_PATTERNS.get("anthropic")
        if pattern and not pattern.match(value):
            return False, "Invalid anthropic API key format"

        return True, None

    def _validate_url(self, value: str) -> Tuple[bool, Optional[str]]:
        """Validate URL format."""
        if not value:
            return True, None  # Optional

        if not self.URL_PATTERN.match(value):
            return False, "Invalid URL format (must start with http:// or https://)"

        return True, None

    def _validate_boolean(self, value: str) -> Tuple[bool, Optional[str]]:
        """Validate boolean string."""
        if not value:
            return True, None  # Optional

        valid_values = {"true", "false", "yes", "no", "1", "0", "on", "off"}
        if value.lower() not in valid_values:
            return False, f"Invalid boolean value: {value} (expected true/false, yes/no, 1/0, on/off)"

        return True, None

    def _validate_float_range(
        self,
        value: str,
        min_val: Optional[float] = None,
        max_val: Optional[float] = None
    ) -> Tuple[bool, Optional[str]]:
        """Validate float within range."""
        if not value:
            return True, None  # Optional

        try:
            float_val = float(value)
        except ValueError:
            return False, f"Invalid number: {value}"

        if min_val is not None and float_val < min_val:
            return False, f"Value {float_val} is below minimum {min_val}"

        if max_val is not None and float_val > max_val:
            return False, f"Value {float_val} is above maximum {max_val}"

        return True, None

    def _validate_port(self, value: str) -> Tuple[bool, Optional[str]]:
        """Validate port number."""
        if not value:
            return True, None  # Optional

        try:
            port = int(value)
        except ValueError:
            return False, f"Invalid port number: {value}"

        if port < 1 or port > 65535:
            return False, f"Port {port} out of range (1-65535)"

        return True, None

    # === VALIDATION EXECUTION ===

    def validate(self, strict: bool = True) -> Tuple[bool, List[ValidationResult]]:
        """
        Validate all configuration.

        Args:
            strict: If True, raise exception on errors. If False, return results.

        Returns:
            (is_valid, list_of_results)

        Raises:
            ConfigValidationError: If strict=True and validation fails
        """
        results: List[ValidationResult] = []
        has_errors = False

        for rule in self.rules:
            value = os.environ.get(rule.key, rule.default)

            # Check if required but missing
            if rule.required and not value:
                result = ValidationResult(
                    key=rule.key,
                    level=rule.level,
                    message=f"{rule.description} is required but not set",
                    is_valid=False
                )
                results.append(result)
                if rule.level == ValidationLevel.ERROR:
                    has_errors = True
                continue

            # Skip validation if optional and not set
            if not rule.required and not value:
                continue

            # Run validator
            is_valid, error_msg = rule.validator(value)

            if not is_valid:
                result = ValidationResult(
                    key=rule.key,
                    level=rule.level,
                    message=error_msg or f"{rule.description} validation failed",
                    is_valid=False
                )
                results.append(result)
                if rule.level == ValidationLevel.ERROR:
                    has_errors = True

        # Check for conflicting wallet configs
        has_wallet_path = bool(os.environ.get("TREASURY_WALLET_PATH"))
        has_private_key = bool(os.environ.get("WALLET_PRIVATE_KEY"))

        if has_wallet_path and has_private_key:
            results.append(ValidationResult(
                key="WALLET_CONFIG",
                level=ValidationLevel.WARNING,
                message="Both TREASURY_WALLET_PATH and WALLET_PRIVATE_KEY are set. Path will be used.",
                is_valid=False
            ))

        # Check for required Twitter credential sets
        x_api_key = bool(os.environ.get("X_API_KEY"))
        x_bearer = bool(os.environ.get("X_BEARER_TOKEN"))

        if x_api_key and not os.environ.get("X_API_SECRET"):
            results.append(ValidationResult(
                key="X_API_CONFIG",
                level=ValidationLevel.WARNING,
                message="X_API_KEY set but X_API_SECRET missing (both required for API v1.1)",
                is_valid=False
            ))

        if strict and has_errors:
            error_results = [r for r in results if r.level == ValidationLevel.ERROR]
            raise ConfigValidationError(error_results)

        return not has_errors, results

    def get_validation_summary(self, results: List[ValidationResult]) -> str:
        """Format validation results as a readable summary."""
        if not results:
            return "✅ All configuration valid"

        lines = ["Configuration Validation Results:", ""]

        # Group by level
        errors = [r for r in results if r.level == ValidationLevel.ERROR]
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        infos = [r for r in results if r.level == ValidationLevel.INFO]

        if errors:
            lines.append("❌ ERRORS (must fix):")
            for r in errors:
                lines.append(f"  • {r.key}: {r.message}")
            lines.append("")

        if warnings:
            lines.append("⚠️  WARNINGS (should fix):")
            for r in warnings:
                lines.append(f"  • {r.key}: {r.message}")
            lines.append("")

        if infos:
            lines.append("ℹ️  INFO (optional):")
            for r in infos:
                lines.append(f"  • {r.key}: {r.message}")

        return "\n".join(lines)

    def get_group_summary(self) -> Dict[str, int]:
        """Get summary of configured vs missing keys by group."""
        groups: Dict[str, Dict[str, int]] = {}

        for rule in self.rules:
            if rule.group not in groups:
                groups[rule.group] = {"configured": 0, "missing": 0, "total": 0}

            groups[rule.group]["total"] += 1
            value = os.environ.get(rule.key)

            if value:
                groups[rule.group]["configured"] += 1
            else:
                groups[rule.group]["missing"] += 1

        return groups


# === PUBLIC API ===

_global_validator: Optional[ConfigValidator] = None


def get_validator() -> ConfigValidator:
    """Get global validator instance."""
    global _global_validator
    if _global_validator is None:
        _global_validator = ConfigValidator()
    return _global_validator


def validate_config(strict: bool = True) -> Tuple[bool, List[ValidationResult]]:
    """
    Validate all Jarvis configuration.

    Args:
        strict: If True, raise exception on errors

    Returns:
        (is_valid, list_of_validation_results)

    Raises:
        ConfigValidationError: If strict=True and validation fails
    """
    validator = get_validator()
    return validator.validate(strict=strict)


def print_validation_summary():
    """Print human-readable validation summary."""
    validator = get_validator()
    is_valid, results = validator.validate(strict=False)

    print(validator.get_validation_summary(results))
    print()

    # Print group summary
    groups = validator.get_group_summary()
    print("Configuration by Group:")
    for group, stats in sorted(groups.items()):
        configured_pct = (stats["configured"] / stats["total"] * 100) if stats["total"] > 0 else 0
        print(f"  {group:15s}: {stats['configured']}/{stats['total']} configured ({configured_pct:.0f}%)")


if __name__ == "__main__":
    # CLI mode
    print_validation_summary()
