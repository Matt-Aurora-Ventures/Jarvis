"""
Configuration Validator - Validate and manage application configuration.
"""

import os
import re
import logging
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class ConfigType(Enum):
    """Configuration value types."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    URL = "url"
    PATH = "path"
    SOLANA_ADDRESS = "solana_address"
    API_KEY = "api_key"
    LIST = "list"
    CHOICE = "choice"


@dataclass
class ConfigField:
    """Definition of a configuration field."""
    name: str
    config_type: ConfigType
    required: bool = True
    default: Any = None
    description: str = ""
    env_var: str = ""  # Environment variable name
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None  # Regex pattern
    choices: List[str] = field(default_factory=list)
    validator: Optional[Callable[[Any], bool]] = None
    sensitive: bool = False  # Don't log value


@dataclass
class ValidationResult:
    """Result of configuration validation."""
    valid: bool
    field: str
    value: Any = None
    error: str = ""
    warning: str = ""


@dataclass
class ConfigValidationReport:
    """Full validation report."""
    valid: bool
    errors: List[ValidationResult]
    warnings: List[ValidationResult]
    missing_required: List[str]
    invalid_values: List[str]


class ConfigValidator:
    """
    Validate configuration values.

    Usage:
        validator = ConfigValidator()

        validator.add_field(ConfigField(
            name="HELIUS_API_KEY",
            config_type=ConfigType.API_KEY,
            required=True,
            env_var="HELIUS_API_KEY",
            sensitive=True
        ))

        report = validator.validate_all()
        if not report.valid:
            for error in report.errors:
                print(f"Error: {error.field} - {error.error}")
    """

    # Common patterns
    PATTERNS = {
        'url': r'^https?://[^\s/$.?#].[^\s]*$',
        'solana_address': r'^[1-9A-HJ-NP-Za-km-z]{32,44}$',
        'api_key': r'^[A-Za-z0-9_-]{20,}$',
        'telegram_bot_token': r'^\d+:[A-Za-z0-9_-]{35}$',
        'twitter_api_key': r'^[A-Za-z0-9]{20,}$'
    }

    def __init__(self):
        self.fields: Dict[str, ConfigField] = {}
        self._values: Dict[str, Any] = {}
        self._validated = False

    def add_field(self, field: ConfigField):
        """Add a configuration field definition."""
        self.fields[field.name] = field
        self._validated = False

    def add_fields(self, fields: List[ConfigField]):
        """Add multiple field definitions."""
        for field in fields:
            self.add_field(field)

    def get_value(self, name: str) -> Any:
        """Get a configuration value."""
        if name not in self.fields:
            raise KeyError(f"Unknown config field: {name}")

        field = self.fields[name]

        # Try environment variable first
        if field.env_var:
            value = os.environ.get(field.env_var)
            if value is not None:
                return self._convert_type(value, field.config_type)

        # Then check loaded values
        if name in self._values:
            return self._values[name]

        # Return default
        return field.default

    def set_value(self, name: str, value: Any):
        """Set a configuration value."""
        if name not in self.fields:
            raise KeyError(f"Unknown config field: {name}")

        self._values[name] = value
        self._validated = False

    def validate_field(self, name: str) -> ValidationResult:
        """Validate a single field."""
        if name not in self.fields:
            return ValidationResult(
                valid=False,
                field=name,
                error=f"Unknown field: {name}"
            )

        field = self.fields[name]
        value = self.get_value(name)

        # Check required
        if field.required and value is None:
            return ValidationResult(
                valid=False,
                field=name,
                error=f"Required field is missing"
            )

        # Skip validation if value is None and not required
        if value is None:
            return ValidationResult(valid=True, field=name)

        # Type validation
        try:
            value = self._convert_type(value, field.config_type)
        except (ValueError, TypeError) as e:
            return ValidationResult(
                valid=False,
                field=name,
                value=value if not field.sensitive else "***",
                error=f"Invalid type: expected {field.config_type.value}"
            )

        # Pattern validation
        pattern = field.pattern or self._get_default_pattern(field.config_type)
        if pattern and isinstance(value, str):
            if not re.match(pattern, value):
                return ValidationResult(
                    valid=False,
                    field=name,
                    value=value if not field.sensitive else "***",
                    error=f"Value does not match required pattern"
                )

        # Range validation
        if field.min_value is not None and isinstance(value, (int, float)):
            if value < field.min_value:
                return ValidationResult(
                    valid=False,
                    field=name,
                    value=value,
                    error=f"Value {value} is below minimum {field.min_value}"
                )

        if field.max_value is not None and isinstance(value, (int, float)):
            if value > field.max_value:
                return ValidationResult(
                    valid=False,
                    field=name,
                    value=value,
                    error=f"Value {value} exceeds maximum {field.max_value}"
                )

        # Length validation
        if field.min_length is not None and isinstance(value, str):
            if len(value) < field.min_length:
                return ValidationResult(
                    valid=False,
                    field=name,
                    error=f"Value length {len(value)} is below minimum {field.min_length}"
                )

        if field.max_length is not None and isinstance(value, str):
            if len(value) > field.max_length:
                return ValidationResult(
                    valid=False,
                    field=name,
                    error=f"Value length {len(value)} exceeds maximum {field.max_length}"
                )

        # Choice validation
        if field.choices and value not in field.choices:
            return ValidationResult(
                valid=False,
                field=name,
                value=value,
                error=f"Value must be one of: {', '.join(field.choices)}"
            )

        # Custom validator
        if field.validator:
            try:
                if not field.validator(value):
                    return ValidationResult(
                        valid=False,
                        field=name,
                        error="Custom validation failed"
                    )
            except Exception as e:
                return ValidationResult(
                    valid=False,
                    field=name,
                    error=f"Validator error: {str(e)}"
                )

        return ValidationResult(
            valid=True,
            field=name,
            value=value if not field.sensitive else "***"
        )

    def validate_all(self) -> ConfigValidationReport:
        """Validate all configuration fields."""
        errors = []
        warnings = []
        missing_required = []
        invalid_values = []

        for name, field in self.fields.items():
            result = self.validate_field(name)

            if not result.valid:
                errors.append(result)
                if "missing" in result.error.lower():
                    missing_required.append(name)
                else:
                    invalid_values.append(name)

            if result.warning:
                warnings.append(result)

        self._validated = len(errors) == 0

        return ConfigValidationReport(
            valid=self._validated,
            errors=errors,
            warnings=warnings,
            missing_required=missing_required,
            invalid_values=invalid_values
        )

    def _convert_type(self, value: Any, config_type: ConfigType) -> Any:
        """Convert value to the expected type."""
        if value is None:
            return None

        if config_type == ConfigType.STRING:
            return str(value)
        elif config_type == ConfigType.INTEGER:
            return int(value)
        elif config_type == ConfigType.FLOAT:
            return float(value)
        elif config_type == ConfigType.BOOLEAN:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ('true', '1', 'yes', 'on')
            return bool(value)
        elif config_type == ConfigType.URL:
            return str(value)
        elif config_type == ConfigType.PATH:
            return Path(value)
        elif config_type == ConfigType.LIST:
            if isinstance(value, list):
                return value
            if isinstance(value, str):
                return [v.strip() for v in value.split(',')]
            return [value]
        else:
            return str(value)

    def _get_default_pattern(self, config_type: ConfigType) -> Optional[str]:
        """Get default regex pattern for a config type."""
        if config_type == ConfigType.URL:
            return self.PATTERNS['url']
        elif config_type == ConfigType.SOLANA_ADDRESS:
            return self.PATTERNS['solana_address']
        elif config_type == ConfigType.API_KEY:
            return self.PATTERNS['api_key']
        return None

    def get_required_env_vars(self) -> List[str]:
        """Get list of required environment variables."""
        return [
            f.env_var for f in self.fields.values()
            if f.required and f.env_var
        ]

    def get_missing_env_vars(self) -> List[str]:
        """Get list of missing required environment variables."""
        missing = []
        for field in self.fields.values():
            if field.required and field.env_var:
                if not os.environ.get(field.env_var):
                    missing.append(field.env_var)
        return missing

    def print_config_template(self) -> str:
        """Generate a .env template."""
        lines = ["# Jarvis Configuration Template", "# Generated automatically", ""]

        current_section = None
        for name, field in self.fields.items():
            if not field.env_var:
                continue

            # Add section header
            section = name.split('_')[0]
            if section != current_section:
                lines.append(f"\n# === {section.upper()} ===")
                current_section = section

            # Add description
            if field.description:
                lines.append(f"# {field.description}")

            # Add requirement note
            req = "Required" if field.required else "Optional"
            lines.append(f"# Type: {field.config_type.value} | {req}")

            # Add example
            if field.default:
                lines.append(f"# Default: {field.default}")

            lines.append(f"{field.env_var}=")
            lines.append("")

        return "\n".join(lines)


# === JARVIS DEFAULT CONFIG ===

def get_jarvis_config_validator() -> ConfigValidator:
    """Get pre-configured validator for Jarvis."""
    validator = ConfigValidator()

    # Telegram configuration
    validator.add_fields([
        ConfigField(
            name="TELEGRAM_BOT_TOKEN",
            config_type=ConfigType.STRING,
            required=True,
            env_var="TELEGRAM_BOT_TOKEN",
            pattern=r'^\d+:[A-Za-z0-9_-]{35}$',
            description="Telegram bot token from @BotFather",
            sensitive=True
        ),
        ConfigField(
            name="TELEGRAM_ADMIN_ID",
            config_type=ConfigType.INTEGER,
            required=True,
            env_var="ADMIN_ID",
            description="Telegram user ID for admin commands"
        ),
        ConfigField(
            name="TELEGRAM_CHANNEL_ID",
            config_type=ConfigType.STRING,
            required=False,
            env_var="TELEGRAM_CHANNEL_ID",
            description="Telegram channel ID for alerts"
        ),
    ])

    # Helius/Solana configuration
    validator.add_fields([
        ConfigField(
            name="HELIUS_API_KEY",
            config_type=ConfigType.API_KEY,
            required=True,
            env_var="HELIUS_API_KEY",
            description="Helius API key for Solana RPC",
            sensitive=True
        ),
        ConfigField(
            name="TREASURY_WALLET",
            config_type=ConfigType.SOLANA_ADDRESS,
            required=False,
            env_var="TREASURY_WALLET",
            description="Treasury wallet address"
        ),
    ])

    # Twitter configuration
    validator.add_fields([
        ConfigField(
            name="TWITTER_API_KEY",
            config_type=ConfigType.STRING,
            required=False,
            env_var="TWITTER_API_KEY",
            description="Twitter/X API key",
            sensitive=True
        ),
        ConfigField(
            name="TWITTER_API_SECRET",
            config_type=ConfigType.STRING,
            required=False,
            env_var="TWITTER_API_SECRET",
            description="Twitter/X API secret",
            sensitive=True
        ),
        ConfigField(
            name="TWITTER_ACCESS_TOKEN",
            config_type=ConfigType.STRING,
            required=False,
            env_var="TWITTER_ACCESS_TOKEN",
            description="Twitter/X access token",
            sensitive=True
        ),
        ConfigField(
            name="TWITTER_ACCESS_SECRET",
            config_type=ConfigType.STRING,
            required=False,
            env_var="TWITTER_ACCESS_SECRET",
            description="Twitter/X access token secret",
            sensitive=True
        ),
    ])

    # Grok configuration
    validator.add_fields([
        ConfigField(
            name="GROK_API_KEY",
            config_type=ConfigType.API_KEY,
            required=False,
            env_var="GROK_API_KEY",
            description="Grok API key for AI analysis",
            sensitive=True
        ),
    ])

    # Claude configuration
    validator.add_fields([
        ConfigField(
            name="ANTHROPIC_API_KEY",
            config_type=ConfigType.API_KEY,
            required=False,
            env_var="ANTHROPIC_API_KEY",
            description="Anthropic API key for Claude",
            sensitive=True
        ),
    ])

    # Trading configuration
    validator.add_fields([
        ConfigField(
            name="MAX_TRADE_SOL",
            config_type=ConfigType.FLOAT,
            required=False,
            env_var="MAX_TRADE_SOL",
            default=0.1,
            min_value=0.001,
            max_value=10.0,
            description="Maximum trade size in SOL"
        ),
        ConfigField(
            name="DAILY_LIMIT_SOL",
            config_type=ConfigType.FLOAT,
            required=False,
            env_var="DAILY_LIMIT_SOL",
            default=1.0,
            min_value=0.01,
            max_value=100.0,
            description="Daily trading limit in SOL"
        ),
        ConfigField(
            name="SLIPPAGE_BPS",
            config_type=ConfigType.INTEGER,
            required=False,
            env_var="SLIPPAGE_BPS",
            default=300,
            min_value=50,
            max_value=5000,
            description="Slippage tolerance in basis points"
        ),
    ])

    # Application configuration
    validator.add_fields([
        ConfigField(
            name="LOG_LEVEL",
            config_type=ConfigType.CHOICE,
            required=False,
            env_var="LOG_LEVEL",
            default="INFO",
            choices=["DEBUG", "INFO", "WARNING", "ERROR"],
            description="Logging level"
        ),
        ConfigField(
            name="ENVIRONMENT",
            config_type=ConfigType.CHOICE,
            required=False,
            env_var="ENVIRONMENT",
            default="development",
            choices=["development", "staging", "production"],
            description="Application environment"
        ),
    ])

    return validator


# Singleton
_validator: Optional[ConfigValidator] = None

def get_config_validator() -> ConfigValidator:
    """Get singleton config validator."""
    global _validator
    if _validator is None:
        _validator = get_jarvis_config_validator()
    return _validator


def validate_startup_config() -> bool:
    """Validate configuration on startup."""
    validator = get_config_validator()
    report = validator.validate_all()

    if report.valid:
        logger.info("Configuration validation passed")
        return True

    logger.error("Configuration validation failed:")
    for error in report.errors:
        logger.error(f"  - {error.field}: {error.error}")

    if report.missing_required:
        logger.error(f"Missing required: {', '.join(report.missing_required)}")

    return False
