"""
JARVIS Startup Validator - Configuration & Health Checks

Validates all required configurations and dependencies before startup.
Prevents runtime failures from missing/invalid config.

Usage:
    from core.startup_validator import validate_startup, StartupValidator

    # Quick validation
    issues = validate_startup()
    if issues:
        print("Startup blocked:", issues)

    # Detailed validation
    validator = StartupValidator()
    report = validator.full_validation()
"""

import asyncio
import logging
import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]


class Severity(Enum):
    """Validation issue severity."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationIssue:
    """A validation issue found during startup."""
    category: str
    message: str
    severity: Severity
    fix_hint: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def __str__(self):
        prefix = {
            Severity.INFO: "[INFO]",
            Severity.WARNING: "[WARN]",
            Severity.ERROR: "[ERROR]",
            Severity.CRITICAL: "[CRITICAL]",
        }[self.severity]
        return f"{prefix} {self.category}: {self.message}"


@dataclass
class ValidationReport:
    """Complete validation report."""
    passed: bool
    issues: List[ValidationIssue]
    checks_run: int
    checks_passed: int
    timestamp: str

    def summary(self) -> str:
        """Get report summary."""
        lines = [
            "=" * 50,
            "JARVIS Startup Validation Report",
            "=" * 50,
            f"Status: {'PASSED' if self.passed else 'FAILED'}",
            f"Checks: {self.checks_passed}/{self.checks_run} passed",
            "",
        ]

        if self.issues:
            lines.append("Issues Found:")
            for issue in self.issues:
                lines.append(f"  {issue}")
                if issue.fix_hint:
                    lines.append(f"    Fix: {issue.fix_hint}")

        lines.append("=" * 50)
        return "\n".join(lines)


class StartupValidator:
    """
    Comprehensive startup validation.

    Checks:
    - Required environment variables
    - Database connectivity
    - API key validity
    - File permissions
    - Network connectivity
    - Dependency availability
    """

    # Required env vars by category
    REQUIRED_ENV = {
        "telegram": [
            ("TELEGRAM_BOT_TOKEN", "Telegram bot functionality"),
        ],
        "treasury": [
            ("JARVIS_SECURE_PASSWORD", "Treasury key encryption"),
        ],
    }

    # Optional but recommended env vars
    RECOMMENDED_ENV = {
        "llm": [
            ("XAI_API_KEY", "xAI/Grok AI responses"),
            ("GROQ_API_KEY", "Groq fast inference"),
            ("OPENAI_API_KEY", "OpenAI models"),
        ],
        "monitoring": [
            ("SENTRY_DSN", "Error tracking"),
        ],
    }

    # Required directories
    REQUIRED_DIRS = [
        "data",
        "data/secure",
        "logs",
    ]

    # Required files (relative to ROOT)
    REQUIRED_FILES = [
        ".env",
    ]

    def __init__(self):
        self.issues: List[ValidationIssue] = []
        self.checks_run = 0
        self.checks_passed = 0

    def _add_issue(
        self,
        category: str,
        message: str,
        severity: Severity,
        fix_hint: str = "",
        **details
    ):
        """Add a validation issue."""
        self.issues.append(ValidationIssue(
            category=category,
            message=message,
            severity=severity,
            fix_hint=fix_hint,
            details=details,
        ))

    def _check(self, passed: bool):
        """Record a check result."""
        self.checks_run += 1
        if passed:
            self.checks_passed += 1
        return passed

    def validate_environment(self) -> bool:
        """Validate required environment variables."""
        all_passed = True

        # Check required vars
        for category, vars_list in self.REQUIRED_ENV.items():
            for var_name, purpose in vars_list:
                value = os.getenv(var_name)
                if not value:
                    self._add_issue(
                        "Environment",
                        f"Missing required: {var_name}",
                        Severity.ERROR,
                        f"Add {var_name}=<value> to .env ({purpose})",
                        var=var_name,
                        category=category,
                    )
                    all_passed = False
                    self._check(False)
                else:
                    self._check(True)

        # Check recommended vars
        for category, vars_list in self.RECOMMENDED_ENV.items():
            for var_name, purpose in vars_list:
                value = os.getenv(var_name)
                if not value:
                    self._add_issue(
                        "Environment",
                        f"Missing recommended: {var_name}",
                        Severity.WARNING,
                        f"Add {var_name}=<value> for {purpose}",
                        var=var_name,
                        category=category,
                    )
                self._check(bool(value))

        return all_passed

    def validate_directories(self) -> bool:
        """Validate required directories exist."""
        all_passed = True

        for dir_path in self.REQUIRED_DIRS:
            full_path = ROOT / dir_path
            if not full_path.exists():
                # Try to create it
                try:
                    full_path.mkdir(parents=True, exist_ok=True)
                    self._add_issue(
                        "Filesystem",
                        f"Created missing directory: {dir_path}",
                        Severity.INFO,
                    )
                    self._check(True)
                except Exception as e:
                    self._add_issue(
                        "Filesystem",
                        f"Cannot create directory: {dir_path}",
                        Severity.ERROR,
                        f"Manually create: mkdir -p {full_path}",
                        error=str(e),
                    )
                    all_passed = False
                    self._check(False)
            else:
                self._check(True)

        return all_passed

    def validate_files(self) -> bool:
        """Validate required files exist."""
        all_passed = True

        for file_path in self.REQUIRED_FILES:
            full_path = ROOT / file_path
            if not full_path.exists():
                self._add_issue(
                    "Filesystem",
                    f"Missing required file: {file_path}",
                    Severity.ERROR,
                    f"Create from template: cp env.example .env",
                )
                all_passed = False
                self._check(False)
            else:
                self._check(True)

        return all_passed

    def validate_database(self) -> bool:
        """Validate database connectivity."""
        try:
            import sqlite3
            db_path = ROOT / "data" / "jarvis.db"

            if db_path.exists():
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                conn.close()
                self._check(True)
                return True
            else:
                self._add_issue(
                    "Database",
                    "Database file not found (will be created on first use)",
                    Severity.INFO,
                )
                self._check(True)
                return True

        except Exception as e:
            self._add_issue(
                "Database",
                f"Database connection failed: {e}",
                Severity.ERROR,
                "Check database file permissions",
            )
            self._check(False)
            return False

    def validate_network(self) -> bool:
        """Validate network connectivity."""
        import socket

        endpoints = [
            ("api.telegram.org", 443, "Telegram API"),
            ("api.x.ai", 443, "xAI API"),
        ]

        all_passed = True

        for host, port, name in endpoints:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex((host, port))
                sock.close()

                if result == 0:
                    self._check(True)
                else:
                    self._add_issue(
                        "Network",
                        f"Cannot reach {name} ({host}:{port})",
                        Severity.WARNING,
                        "Check network/firewall settings",
                    )
                    self._check(False)
            except Exception as e:
                self._add_issue(
                    "Network",
                    f"Network check failed for {name}: {e}",
                    Severity.WARNING,
                )
                self._check(False)

        return all_passed

    def validate_dependencies(self) -> bool:
        """Validate Python dependencies."""
        critical_deps = [
            ("aiohttp", "Async HTTP"),
            ("telegram", "Telegram bot"),
        ]

        optional_deps = [
            ("cryptography", "Key encryption"),
            ("pystray", "System tray"),
            ("PIL", "Image processing"),
        ]

        all_passed = True

        for module, purpose in critical_deps:
            try:
                __import__(module)
                self._check(True)
            except ImportError:
                self._add_issue(
                    "Dependencies",
                    f"Missing critical: {module}",
                    Severity.ERROR,
                    f"Run: pip install {module}",
                    purpose=purpose,
                )
                all_passed = False
                self._check(False)

        for module, purpose in optional_deps:
            try:
                __import__(module)
                self._check(True)
            except ImportError:
                self._add_issue(
                    "Dependencies",
                    f"Missing optional: {module}",
                    Severity.INFO,
                    f"For {purpose}: pip install {module}",
                )
                self._check(True)  # Optional, so still counts as passed

        return all_passed

    def validate_api_keys(self) -> bool:
        """Validate API key formats (not actual auth)."""
        all_passed = True

        # Check Telegram token format
        tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        if tg_token and ":" not in tg_token:
            self._add_issue(
                "API Keys",
                "TELEGRAM_BOT_TOKEN format invalid",
                Severity.ERROR,
                "Token should be in format: 123456:ABC-DEF...",
            )
            all_passed = False
            self._check(False)
        elif tg_token:
            self._check(True)

        # Check other API keys exist and have reasonable length
        api_keys = [
            ("XAI_API_KEY", 20),
            ("GROQ_API_KEY", 20),
            ("OPENAI_API_KEY", 20),
        ]

        for key_name, min_length in api_keys:
            value = os.getenv(key_name, "")
            if value:
                if len(value) < min_length:
                    self._add_issue(
                        "API Keys",
                        f"{key_name} seems too short",
                        Severity.WARNING,
                        "Verify the key is complete",
                    )
                    self._check(False)
                else:
                    self._check(True)

        return all_passed

    def validate_security(self) -> bool:
        """Validate security configurations."""
        all_passed = True

        # Check for plaintext key files
        dangerous_files = [
            "data/treasury_keypair.json",
            "wallets/treasury.json",
        ]

        for file_path in dangerous_files:
            full_path = ROOT / file_path
            if full_path.exists():
                self._add_issue(
                    "Security",
                    f"Plaintext key file found: {file_path}",
                    Severity.CRITICAL,
                    "Migrate to encrypted storage: python -m core.security.encrypted_storage",
                )
                all_passed = False
                self._check(False)
            else:
                self._check(True)

        # Check secure storage is configured
        password = os.getenv("JARVIS_SECURE_PASSWORD")
        if not password:
            self._add_issue(
                "Security",
                "JARVIS_SECURE_PASSWORD not set",
                Severity.WARNING,
                "Set password for encrypted key storage",
            )

        return all_passed

    def full_validation(self) -> ValidationReport:
        """Run all validation checks."""
        from datetime import datetime

        self.issues = []
        self.checks_run = 0
        self.checks_passed = 0

        # Run all validators
        validators = [
            ("Environment", self.validate_environment),
            ("Directories", self.validate_directories),
            ("Files", self.validate_files),
            ("Database", self.validate_database),
            ("Dependencies", self.validate_dependencies),
            ("API Keys", self.validate_api_keys),
            ("Security", self.validate_security),
            ("Network", self.validate_network),
        ]

        for name, validator in validators:
            try:
                validator()
            except Exception as e:
                self._add_issue(
                    name,
                    f"Validator crashed: {e}",
                    Severity.ERROR,
                )

        # Determine if startup should proceed
        critical_issues = [
            i for i in self.issues
            if i.severity == Severity.CRITICAL
        ]
        error_issues = [
            i for i in self.issues
            if i.severity == Severity.ERROR
        ]

        passed = len(critical_issues) == 0

        return ValidationReport(
            passed=passed,
            issues=self.issues,
            checks_run=self.checks_run,
            checks_passed=self.checks_passed,
            timestamp=datetime.now().isoformat(),
        )


def validate_startup(strict: bool = False) -> List[ValidationIssue]:
    """
    Quick startup validation.

    Args:
        strict: If True, treat warnings as errors

    Returns:
        List of issues (empty if all passed)
    """
    validator = StartupValidator()
    report = validator.full_validation()

    if strict:
        return [
            i for i in report.issues
            if i.severity in (Severity.ERROR, Severity.CRITICAL, Severity.WARNING)
        ]

    return [
        i for i in report.issues
        if i.severity in (Severity.ERROR, Severity.CRITICAL)
    ]


def require_startup_validation():
    """
    Require successful validation before continuing.

    Exits with error if critical issues found.
    """
    validator = StartupValidator()
    report = validator.full_validation()

    print(report.summary())

    if not report.passed:
        logger.error("Startup validation failed")
        sys.exit(1)

    return report


if __name__ == "__main__":
    # Load .env file
    from pathlib import Path
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value

    report = require_startup_validation()
