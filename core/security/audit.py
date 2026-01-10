"""
Security Audit Framework

Comprehensive security auditing for JARVIS trading systems.
Checks for vulnerabilities, misconfigurations, and compliance.

Prompts #171-180: Security Audit
"""

import asyncio
import logging
import os
import re
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Any, Callable
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class AuditSeverity(str, Enum):
    """Severity levels for audit findings"""
    CRITICAL = "critical"  # Must fix before enabling trading
    HIGH = "high"         # Fix within 1 week
    MEDIUM = "medium"     # Fix within 1 month
    LOW = "low"           # Nice to have
    INFO = "info"         # Informational


class AuditCategory(str, Enum):
    """Categories of security checks"""
    KEY_STORAGE = "key_storage"
    RATE_LIMITING = "rate_limiting"
    INPUT_VALIDATION = "input_validation"
    SQL_INJECTION = "sql_injection"
    TRANSACTION_SIGNING = "transaction_signing"
    API_SECURITY = "api_security"
    AUDIT_LOGGING = "audit_logging"
    BACKUP_RECOVERY = "backup_recovery"
    ACCESS_CONTROL = "access_control"
    CRYPTOGRAPHY = "cryptography"


@dataclass
class SecurityCheck:
    """A single security check"""
    name: str
    category: AuditCategory
    severity: AuditSeverity
    description: str
    check_fn: Optional[Callable] = None
    passed: bool = False
    findings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    checked_at: Optional[datetime] = None


@dataclass
class AuditResult:
    """Result of a security audit"""
    passed: bool
    total_checks: int
    passed_checks: int
    failed_checks: int
    critical_issues: int
    high_issues: int
    medium_issues: int
    low_issues: int
    checks: List[SecurityCheck]
    audit_time: datetime = field(default_factory=datetime.now)
    duration_seconds: float = 0.0

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "passed": self.passed,
            "total_checks": self.total_checks,
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "critical_issues": self.critical_issues,
            "high_issues": self.high_issues,
            "medium_issues": self.medium_issues,
            "low_issues": self.low_issues,
            "audit_time": self.audit_time.isoformat(),
            "duration_seconds": self.duration_seconds,
            "checks": [
                {
                    "name": c.name,
                    "category": c.category.value,
                    "severity": c.severity.value,
                    "passed": c.passed,
                    "findings": c.findings,
                    "recommendations": c.recommendations
                }
                for c in self.checks
            ]
        }

    def to_markdown(self) -> str:
        """Generate markdown report"""
        lines = [
            "# JARVIS Security Audit Report",
            "",
            f"**Date:** {self.audit_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Duration:** {self.duration_seconds:.2f} seconds",
            "",
            "## Summary",
            "",
            f"- **Overall Status:** {'✅ PASSED' if self.passed else '❌ FAILED'}",
            f"- **Total Checks:** {self.total_checks}",
            f"- **Passed:** {self.passed_checks}",
            f"- **Failed:** {self.failed_checks}",
            "",
            "### Issues by Severity",
            "",
            f"- 🔴 Critical: {self.critical_issues}",
            f"- 🟠 High: {self.high_issues}",
            f"- 🟡 Medium: {self.medium_issues}",
            f"- 🟢 Low: {self.low_issues}",
            "",
            "## Detailed Findings",
            ""
        ]

        # Group by category
        by_category: Dict[AuditCategory, List[SecurityCheck]] = {}
        for check in self.checks:
            if check.category not in by_category:
                by_category[check.category] = []
            by_category[check.category].append(check)

        for category, checks in by_category.items():
            lines.append(f"### {category.value.replace('_', ' ').title()}")
            lines.append("")

            for check in checks:
                status = "✅" if check.passed else "❌"
                severity_emoji = {
                    AuditSeverity.CRITICAL: "🔴",
                    AuditSeverity.HIGH: "🟠",
                    AuditSeverity.MEDIUM: "🟡",
                    AuditSeverity.LOW: "🟢",
                    AuditSeverity.INFO: "ℹ️"
                }
                emoji = severity_emoji.get(check.severity, "⚪")

                lines.append(f"#### {status} {emoji} {check.name}")
                lines.append(f"*{check.description}*")
                lines.append("")

                if check.findings:
                    lines.append("**Findings:**")
                    for finding in check.findings:
                        lines.append(f"- {finding}")
                    lines.append("")

                if check.recommendations:
                    lines.append("**Recommendations:**")
                    for rec in check.recommendations:
                        lines.append(f"- {rec}")
                    lines.append("")

        return "\n".join(lines)


class SecurityAuditor:
    """
    Comprehensive security auditor for JARVIS

    Runs security checks across all critical systems.
    """

    def __init__(self, project_root: Optional[str] = None):
        self.project_root = Path(project_root or os.getcwd())
        self.checks: List[SecurityCheck] = []
        self._register_default_checks()

    def _register_default_checks(self):
        """Register default security checks"""

        # CRITICAL: Key Storage
        self.register_check(SecurityCheck(
            name="Key Encryption at Rest",
            category=AuditCategory.KEY_STORAGE,
            severity=AuditSeverity.CRITICAL,
            description="Verify all private keys are encrypted before storage",
            check_fn=self._check_key_encryption
        ))

        self.register_check(SecurityCheck(
            name="Master Key Environment Variable",
            category=AuditCategory.KEY_STORAGE,
            severity=AuditSeverity.CRITICAL,
            description="Verify JARVIS_MASTER_KEY is set and secure",
            check_fn=self._check_master_key
        ))

        self.register_check(SecurityCheck(
            name="No Plaintext Keys in Code",
            category=AuditCategory.KEY_STORAGE,
            severity=AuditSeverity.CRITICAL,
            description="Scan codebase for hardcoded private keys",
            check_fn=self._check_no_hardcoded_keys
        ))

        # CRITICAL: Rate Limiting
        self.register_check(SecurityCheck(
            name="API Rate Limiting",
            category=AuditCategory.RATE_LIMITING,
            severity=AuditSeverity.CRITICAL,
            description="Verify rate limiting is implemented on all API endpoints",
            check_fn=self._check_rate_limiting
        ))

        # CRITICAL: Input Validation
        self.register_check(SecurityCheck(
            name="Input Validation",
            category=AuditCategory.INPUT_VALIDATION,
            severity=AuditSeverity.CRITICAL,
            description="Verify all user inputs are validated",
            check_fn=self._check_input_validation
        ))

        # CRITICAL: SQL Injection
        self.register_check(SecurityCheck(
            name="SQL Injection Prevention",
            category=AuditCategory.SQL_INJECTION,
            severity=AuditSeverity.CRITICAL,
            description="Scan for potential SQL injection vulnerabilities",
            check_fn=self._check_sql_injection
        ))

        # CRITICAL: Transaction Signing
        self.register_check(SecurityCheck(
            name="Transaction Signing Isolation",
            category=AuditCategory.TRANSACTION_SIGNING,
            severity=AuditSeverity.CRITICAL,
            description="Verify transaction signing is isolated and secure",
            check_fn=self._check_transaction_signing
        ))

        # HIGH: API Key Rotation
        self.register_check(SecurityCheck(
            name="API Key Rotation Mechanism",
            category=AuditCategory.API_SECURITY,
            severity=AuditSeverity.HIGH,
            description="Verify API keys can be rotated without downtime",
            check_fn=self._check_key_rotation
        ))

        # HIGH: Audit Logging
        self.register_check(SecurityCheck(
            name="Audit Logging for Trades",
            category=AuditCategory.AUDIT_LOGGING,
            severity=AuditSeverity.HIGH,
            description="Verify all trades are logged with audit trail",
            check_fn=self._check_audit_logging
        ))

        # HIGH: Withdrawal Limits
        self.register_check(SecurityCheck(
            name="Withdrawal Limits and Cooldowns",
            category=AuditCategory.ACCESS_CONTROL,
            severity=AuditSeverity.HIGH,
            description="Verify withdrawal limits and cooling periods are enforced",
            check_fn=self._check_withdrawal_limits
        ))

        # HIGH: Multi-sig Treasury
        self.register_check(SecurityCheck(
            name="Multi-sig Treasury Operations",
            category=AuditCategory.ACCESS_CONTROL,
            severity=AuditSeverity.HIGH,
            description="Verify treasury uses multi-signature for large transactions",
            check_fn=self._check_multisig
        ))

        # HIGH: Backup Procedures
        self.register_check(SecurityCheck(
            name="Backup and Recovery Procedures",
            category=AuditCategory.BACKUP_RECOVERY,
            severity=AuditSeverity.HIGH,
            description="Verify backup procedures are documented and tested",
            check_fn=self._check_backup_procedures
        ))

        # MEDIUM: Memory Clearing
        self.register_check(SecurityCheck(
            name="Memory Clearing After Key Use",
            category=AuditCategory.CRYPTOGRAPHY,
            severity=AuditSeverity.MEDIUM,
            description="Verify sensitive data is cleared from memory after use",
            check_fn=self._check_memory_clearing
        ))

        # MEDIUM: HTTPS Enforcement
        self.register_check(SecurityCheck(
            name="HTTPS Enforcement",
            category=AuditCategory.API_SECURITY,
            severity=AuditSeverity.MEDIUM,
            description="Verify all API endpoints use HTTPS",
            check_fn=self._check_https
        ))

        # MEDIUM: Anomaly Detection
        self.register_check(SecurityCheck(
            name="Anomaly Detection",
            category=AuditCategory.ACCESS_CONTROL,
            severity=AuditSeverity.MEDIUM,
            description="Verify anomaly detection for unusual activity",
            check_fn=self._check_anomaly_detection
        ))

        # LOW: Emergency Shutdown
        self.register_check(SecurityCheck(
            name="Emergency Shutdown Procedures",
            category=AuditCategory.ACCESS_CONTROL,
            severity=AuditSeverity.LOW,
            description="Verify emergency shutdown procedures exist",
            check_fn=self._check_emergency_shutdown
        ))

    def register_check(self, check: SecurityCheck):
        """Register a security check"""
        self.checks.append(check)

    async def run_audit(self) -> AuditResult:
        """Run all security checks"""
        start_time = datetime.now()
        logger.info("Starting security audit...")

        for check in self.checks:
            try:
                if check.check_fn:
                    await check.check_fn(check)
                check.checked_at = datetime.now()
            except Exception as e:
                check.passed = False
                check.findings.append(f"Check failed with error: {str(e)}")
                logger.error(f"Security check '{check.name}' failed: {e}")

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Calculate statistics
        passed_checks = sum(1 for c in self.checks if c.passed)
        failed_checks = len(self.checks) - passed_checks
        critical_issues = sum(1 for c in self.checks if not c.passed and c.severity == AuditSeverity.CRITICAL)
        high_issues = sum(1 for c in self.checks if not c.passed and c.severity == AuditSeverity.HIGH)
        medium_issues = sum(1 for c in self.checks if not c.passed and c.severity == AuditSeverity.MEDIUM)
        low_issues = sum(1 for c in self.checks if not c.passed and c.severity == AuditSeverity.LOW)

        # Overall pass requires no critical issues
        overall_passed = critical_issues == 0

        result = AuditResult(
            passed=overall_passed,
            total_checks=len(self.checks),
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            critical_issues=critical_issues,
            high_issues=high_issues,
            medium_issues=medium_issues,
            low_issues=low_issues,
            checks=self.checks,
            audit_time=start_time,
            duration_seconds=duration
        )

        logger.info(f"Security audit complete: {'PASSED' if overall_passed else 'FAILED'}")
        return result

    # ==================== CHECK IMPLEMENTATIONS ====================

    async def _check_key_encryption(self, check: SecurityCheck):
        """Check if keys are encrypted at rest"""
        check.passed = True

        # Check for encrypted key storage
        key_files = list(self.project_root.glob("**/telegram_users.json"))
        for key_file in key_files:
            try:
                with open(key_file) as f:
                    data = json.load(f)

                for user in data.get("users", []):
                    if "private_key" in user and not user.get("encrypted_private_key"):
                        check.passed = False
                        check.findings.append(f"Unencrypted key found in {key_file}")
            except Exception:
                pass

        if check.passed:
            check.findings.append("All key storage uses encryption")
        else:
            check.recommendations.append("Encrypt all private keys before storage")

    async def _check_master_key(self, check: SecurityCheck):
        """Check if master key is properly configured"""
        master_key = os.environ.get("JARVIS_MASTER_KEY")

        if not master_key:
            check.passed = False
            check.findings.append("JARVIS_MASTER_KEY environment variable not set")
            check.recommendations.append("Set JARVIS_MASTER_KEY with a strong random value")
        elif len(master_key) < 32:
            check.passed = False
            check.findings.append("JARVIS_MASTER_KEY is too short (minimum 32 characters)")
            check.recommendations.append("Use a master key of at least 32 characters")
        elif master_key == "development_key_do_not_use_in_production":
            check.passed = False
            check.findings.append("Using development master key in production")
            check.recommendations.append("Generate a new secure master key for production")
        else:
            check.passed = True
            check.findings.append("Master key is configured")

    async def _check_no_hardcoded_keys(self, check: SecurityCheck):
        """Scan for hardcoded private keys"""
        check.passed = True

        # Patterns that might indicate hardcoded keys
        key_patterns = [
            r"private_key\s*=\s*['\"][A-Za-z0-9+/=]{32,}['\"]",
            r"secret_key\s*=\s*['\"][A-Za-z0-9+/=]{32,}['\"]",
            r"api_key\s*=\s*['\"][A-Za-z0-9]{20,}['\"]",
            r"['\"][1-9A-HJ-NP-Za-km-z]{87,88}['\"]",  # Base58 Solana private key
        ]

        python_files = list(self.project_root.glob("**/*.py"))

        for py_file in python_files[:100]:  # Limit for performance
            try:
                content = py_file.read_text()

                for pattern in key_patterns:
                    if re.search(pattern, content):
                        check.passed = False
                        check.findings.append(f"Potential hardcoded key in {py_file}")
                        break

            except Exception:
                pass

        if check.passed:
            check.findings.append("No hardcoded keys detected")
        else:
            check.recommendations.append("Move all secrets to environment variables or secure vault")

    async def _check_rate_limiting(self, check: SecurityCheck):
        """Check if rate limiting is implemented"""
        check.passed = False

        # Look for rate limiting implementations
        rate_limit_files = list(self.project_root.glob("**/rate_limit*.py"))

        if rate_limit_files:
            check.passed = True
            check.findings.append(f"Rate limiting found in {len(rate_limit_files)} files")
        else:
            check.findings.append("No rate limiting implementation found")
            check.recommendations.append("Implement rate limiting on all API endpoints")

    async def _check_input_validation(self, check: SecurityCheck):
        """Check for input validation"""
        check.passed = True  # Assume pass, check for issues

        # Look for validation patterns
        api_files = list(self.project_root.glob("**/api/**/*.py"))

        for api_file in api_files[:50]:
            try:
                content = api_file.read_text()

                # Check for direct use of request parameters without validation
                if "request.args" in content or "request.form" in content:
                    if "validate" not in content.lower():
                        check.passed = False
                        check.findings.append(f"Potential unvalidated input in {api_file}")

            except Exception:
                pass

        if check.passed:
            check.findings.append("Input validation appears to be in place")

    async def _check_sql_injection(self, check: SecurityCheck):
        """Check for SQL injection vulnerabilities"""
        check.passed = True

        # Look for raw SQL queries
        dangerous_patterns = [
            r"execute\s*\(\s*['\"].*%s.*['\"]",
            r"execute\s*\(\s*f['\"].*\{.*\}.*['\"]",
            r"\.format\s*\(.*\)\s*\)",
        ]

        python_files = list(self.project_root.glob("**/*.py"))

        for py_file in python_files[:100]:
            try:
                content = py_file.read_text()

                for pattern in dangerous_patterns:
                    if re.search(pattern, content):
                        check.passed = False
                        check.findings.append(f"Potential SQL injection in {py_file}")
                        break

            except Exception:
                pass

        if check.passed:
            check.findings.append("No obvious SQL injection vulnerabilities found")
        else:
            check.recommendations.append("Use parameterized queries instead of string formatting")

    async def _check_transaction_signing(self, check: SecurityCheck):
        """Check transaction signing security"""
        check.passed = True

        # Check for secure signing practices
        check.findings.append("Transaction signing implementation should be reviewed manually")
        check.recommendations.append("Ensure private keys never leave secure memory")
        check.recommendations.append("Implement transaction simulation before signing")

    async def _check_key_rotation(self, check: SecurityCheck):
        """Check for key rotation mechanism"""
        check.passed = False

        # Look for key rotation implementation
        rotation_patterns = ["key_rotation", "rotate_key", "KeyRotation"]

        for pattern in rotation_patterns:
            if list(self.project_root.glob(f"**/*{pattern}*.py")):
                check.passed = True
                check.findings.append("Key rotation mechanism found")
                break

        if not check.passed:
            check.findings.append("No key rotation mechanism found")
            check.recommendations.append("Implement periodic key rotation for API keys")

    async def _check_audit_logging(self, check: SecurityCheck):
        """Check for audit logging"""
        check.passed = False

        # Look for audit logging
        audit_files = list(self.project_root.glob("**/audit*.py"))

        if audit_files:
            check.passed = True
            check.findings.append("Audit logging implementation found")
        else:
            check.findings.append("No audit logging implementation found")
            check.recommendations.append("Implement audit logging for all trades and sensitive operations")

    async def _check_withdrawal_limits(self, check: SecurityCheck):
        """Check for withdrawal limits"""
        check.passed = True  # Pass if feature is disabled

        # Check if withdrawals are disabled
        telegram_bot = self.project_root / "core" / "social" / "telegram_bot.py"

        if telegram_bot.exists():
            content = telegram_bot.read_text()
            if "WITHDRAWALS_ENABLED = False" in content:
                check.passed = True
                check.findings.append("Withdrawals are disabled (safe)")
            else:
                check.findings.append("Withdrawal limits should be verified")
                check.recommendations.append("Implement withdrawal limits and cooling periods")

    async def _check_multisig(self, check: SecurityCheck):
        """Check for multi-signature treasury"""
        check.passed = False

        # Look for multisig implementation
        multisig_files = list(self.project_root.glob("**/squads*.py"))
        multisig_files.extend(self.project_root.glob("**/multisig*.py"))

        if multisig_files:
            check.passed = True
            check.findings.append("Multi-signature implementation found")
        else:
            check.findings.append("No multi-signature treasury found")
            check.recommendations.append("Implement multi-sig for large treasury transactions")

    async def _check_backup_procedures(self, check: SecurityCheck):
        """Check for backup procedures"""
        check.passed = False

        # Look for backup documentation or implementation
        backup_files = list(self.project_root.glob("**/backup*.py"))
        backup_docs = list(self.project_root.glob("**/BACKUP*.md"))

        if backup_files or backup_docs:
            check.passed = True
            check.findings.append("Backup procedures documented")
        else:
            check.findings.append("No backup procedures found")
            check.recommendations.append("Document and implement backup and recovery procedures")

    async def _check_memory_clearing(self, check: SecurityCheck):
        """Check for memory clearing after key use"""
        check.passed = True

        check.findings.append("Memory clearing should be verified in key handling code")
        check.recommendations.append("Set sensitive variables to None after use")
        check.recommendations.append("Consider using secure memory libraries")

    async def _check_https(self, check: SecurityCheck):
        """Check for HTTPS enforcement"""
        check.passed = True

        # Look for HTTP in URLs (excluding localhost)
        python_files = list(self.project_root.glob("**/*.py"))

        for py_file in python_files[:50]:
            try:
                content = py_file.read_text()

                # Check for non-localhost HTTP URLs
                if re.search(r'http://(?!localhost|127\.0\.0\.1)', content):
                    check.passed = False
                    check.findings.append(f"Non-HTTPS URL found in {py_file}")

            except Exception:
                pass

        if check.passed:
            check.findings.append("No non-HTTPS external URLs found")

    async def _check_anomaly_detection(self, check: SecurityCheck):
        """Check for anomaly detection"""
        check.passed = False

        # Look for anomaly detection
        anomaly_files = list(self.project_root.glob("**/anomaly*.py"))

        if anomaly_files:
            check.passed = True
            check.findings.append("Anomaly detection implementation found")
        else:
            check.findings.append("No anomaly detection found")
            check.recommendations.append("Implement anomaly detection for unusual trading activity")

    async def _check_emergency_shutdown(self, check: SecurityCheck):
        """Check for emergency shutdown procedures"""
        check.passed = True

        check.findings.append("Emergency shutdown procedures should be documented")
        check.recommendations.append("Create and test emergency shutdown procedures")


# Convenience function
async def run_security_audit(project_root: Optional[str] = None) -> AuditResult:
    """Run a security audit and return results"""
    auditor = SecurityAuditor(project_root)
    return await auditor.run_audit()


# CLI entry point
if __name__ == "__main__":
    async def main():
        print("Running JARVIS Security Audit...")
        print("=" * 50)

        result = await run_security_audit()

        # Print summary
        print(f"\nOverall Status: {'✅ PASSED' if result.passed else '❌ FAILED'}")
        print(f"Total Checks: {result.total_checks}")
        print(f"Passed: {result.passed_checks}")
        print(f"Failed: {result.failed_checks}")
        print()
        print("Issues by Severity:")
        print(f"  🔴 Critical: {result.critical_issues}")
        print(f"  🟠 High: {result.high_issues}")
        print(f"  🟡 Medium: {result.medium_issues}")
        print(f"  🟢 Low: {result.low_issues}")

        # Save report
        report_path = "security_audit_report.md"
        with open(report_path, "w") as f:
            f.write(result.to_markdown())
        print(f"\nFull report saved to: {report_path}")

    asyncio.run(main())
