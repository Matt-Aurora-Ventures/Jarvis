"""
Jarvis Treasury Security Testing
Penetration testing and security audit tools
"""

import os
import re
import sys
import json
import logging
import asyncio
import hashlib
from pathlib import Path
from typing import List, Dict, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SecurityIssue:
    """Security issue found during audit."""
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW, INFO
    category: str
    description: str
    file_path: str = ""
    line_number: int = 0
    recommendation: str = ""

    def __str__(self):
        loc = f"{self.file_path}:{self.line_number}" if self.file_path else "N/A"
        return f"[{self.severity}] {self.category}: {self.description} @ {loc}"


@dataclass
class SecurityAuditResult:
    """Results from security audit."""
    timestamp: datetime
    passed: bool
    critical_issues: int
    high_issues: int
    medium_issues: int
    low_issues: int
    info_issues: int
    issues: List[SecurityIssue]

    def to_report(self) -> str:
        """Generate text report."""
        status = "PASSED" if self.passed else "FAILED"

        report = f"""
SECURITY AUDIT REPORT
=====================
Timestamp: {self.timestamp.isoformat()}
Status: {status}

SUMMARY:
  Critical: {self.critical_issues}
  High: {self.high_issues}
  Medium: {self.medium_issues}
  Low: {self.low_issues}
  Informational: {self.info_issues}

ISSUES:
"""
        for issue in self.issues:
            report += f"\n{issue}\n  Recommendation: {issue.recommendation}\n"

        return report


class SecurityAuditor:
    """
    Security auditor for the treasury system.

    Checks for:
    - Private key exposure
    - Hardcoded secrets
    - Insecure patterns
    - Input validation issues
    - Authorization bypasses
    """

    # Patterns that indicate potential secrets
    SECRET_PATTERNS = [
        (r'["\']?(?:private[_-]?key|secret|password|api[_-]?key|token)["\']?\s*[:=]\s*["\'][^"\']{10,}["\']', 'Hardcoded secret'),
        (r'(?:^|[^a-zA-Z0-9])[1-9A-HJ-NP-Za-km-z]{87,88}(?:$|[^a-zA-Z0-9])', 'Potential Solana private key'),
        (r'(?:^|[^a-zA-Z0-9])[A-Fa-f0-9]{64}(?:$|[^a-zA-Z0-9])', 'Potential hex private key'),
        (r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----', 'PEM private key'),
        (r'ghp_[a-zA-Z0-9]{36}', 'GitHub token'),
        (r'sk-[a-zA-Z0-9]{48}', 'OpenAI API key'),
        (r'xox[baprs]-[a-zA-Z0-9-]+', 'Slack token'),
    ]

    # Insecure code patterns
    INSECURE_PATTERNS = [
        (r'eval\s*\(', 'Use of eval() - potential code injection'),
        (r'exec\s*\(', 'Use of exec() - potential code injection'),
        (r'subprocess\.(?:call|run|Popen).*shell\s*=\s*True', 'Shell injection risk'),
        (r'pickle\.loads?\(', 'Pickle deserialization - potential RCE'),
        (r'yaml\.load\([^)]*Loader\s*=\s*yaml\.(?:Unsafe)?Loader', 'Unsafe YAML loading'),
        (r'\.format\([^)]*\)', 'String format - check for injection'),
        (r'logging\.[^(]+\([^)]*%[^)]+\)', 'Format string in logging'),
    ]

    # Patterns that should trigger warnings
    WARNING_PATTERNS = [
        (r'TODO|FIXME|HACK|XXX', 'Code quality marker'),
        (r'verify\s*=\s*False', 'SSL verification disabled'),
        (r'allow_redirects\s*=\s*True', 'Redirects enabled - check for SSRF'),
        (r'chmod\s+777', 'World-writable permissions'),
    ]

    def __init__(self, base_path: Path = None):
        """Initialize auditor."""
        self.base_path = base_path or Path(__file__).parent
        self.issues: List[SecurityIssue] = []

    def audit_file(self, file_path: Path) -> List[SecurityIssue]:
        """Audit a single file for security issues."""
        issues = []

        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            lines = content.split('\n')

            # Check for secrets
            for pattern, desc in self.SECRET_PATTERNS:
                for i, line in enumerate(lines, 1):
                    # Skip comments and test files
                    if line.strip().startswith('#') or 'test' in str(file_path).lower():
                        continue

                    if re.search(pattern, line, re.IGNORECASE):
                        issues.append(SecurityIssue(
                            severity='CRITICAL',
                            category='Secret Exposure',
                            description=desc,
                            file_path=str(file_path),
                            line_number=i,
                            recommendation='Remove hardcoded secret and use environment variables'
                        ))

            # Check for insecure patterns
            for pattern, desc in self.INSECURE_PATTERNS:
                for i, line in enumerate(lines, 1):
                    if re.search(pattern, line):
                        issues.append(SecurityIssue(
                            severity='HIGH',
                            category='Insecure Code',
                            description=desc,
                            file_path=str(file_path),
                            line_number=i,
                            recommendation='Review and refactor to use safe alternatives'
                        ))

            # Check for warnings
            for pattern, desc in self.WARNING_PATTERNS:
                for i, line in enumerate(lines, 1):
                    if re.search(pattern, line, re.IGNORECASE):
                        issues.append(SecurityIssue(
                            severity='LOW',
                            category='Code Quality',
                            description=desc,
                            file_path=str(file_path),
                            line_number=i,
                            recommendation='Review and address if applicable'
                        ))

        except Exception as e:
            logger.error(f"Failed to audit {file_path}: {e}")

        return issues

    def audit_wallet_security(self) -> List[SecurityIssue]:
        """Audit wallet security specifically."""
        issues = []

        wallet_file = self.base_path / 'wallet.py'
        if not wallet_file.exists():
            return issues

        content = wallet_file.read_text()

        # Check for key logging
        if re.search(r'logger\.[^(]+\([^)]*(?:key|secret|private)', content, re.IGNORECASE):
            issues.append(SecurityIssue(
                severity='CRITICAL',
                category='Key Exposure',
                description='Potential private key logging detected',
                file_path=str(wallet_file),
                recommendation='Never log private keys or secrets'
            ))

        # Check for key in error messages
        if re.search(r'(?:raise|Exception)\s*\([^)]*(?:key|secret|private)', content, re.IGNORECASE):
            issues.append(SecurityIssue(
                severity='HIGH',
                category='Key Exposure',
                description='Key data may be exposed in exceptions',
                file_path=str(wallet_file),
                recommendation='Sanitize error messages to exclude sensitive data'
            ))

        # Check encryption usage
        if 'Fernet' not in content and 'encrypt' in content.lower():
            issues.append(SecurityIssue(
                severity='MEDIUM',
                category='Weak Encryption',
                description='Non-standard encryption may be used',
                file_path=str(wallet_file),
                recommendation='Use established encryption libraries (Fernet, NaCl)'
            ))

        # Check for proper key derivation
        if 'PBKDF2' not in content and 'scrypt' not in content.lower():
            issues.append(SecurityIssue(
                severity='MEDIUM',
                category='Key Derivation',
                description='Password may not use proper key derivation',
                file_path=str(wallet_file),
                recommendation='Use PBKDF2, scrypt, or Argon2 for key derivation'
            ))

        return issues

    def audit_api_security(self) -> List[SecurityIssue]:
        """Audit API endpoint security."""
        issues = []

        # Check for unauthenticated endpoints
        for py_file in self.base_path.rglob('*.py'):
            try:
                content = py_file.read_text(encoding='utf-8', errors='ignore')

                # Check Telegram bot handlers
                if 'CommandHandler' in content or 'CallbackQueryHandler' in content:
                    if 'is_admin' not in content and 'admin' not in str(py_file).lower():
                        issues.append(SecurityIssue(
                            severity='HIGH',
                            category='Authorization',
                            description='Command handlers may lack admin checks',
                            file_path=str(py_file),
                            recommendation='Add admin verification for sensitive commands'
                        ))

                # Check for rate limiting
                if 'async def' in content and 'rate_limit' not in content.lower():
                    if 'trade' in content.lower() or 'swap' in content.lower():
                        issues.append(SecurityIssue(
                            severity='MEDIUM',
                            category='Rate Limiting',
                            description='Trading endpoints may lack rate limiting',
                            file_path=str(py_file),
                            recommendation='Implement rate limiting for trading functions'
                        ))

            except Exception as e:
                continue

        return issues

    def audit_input_validation(self) -> List[SecurityIssue]:
        """Check input validation."""
        issues = []

        for py_file in self.base_path.rglob('*.py'):
            try:
                content = py_file.read_text(encoding='utf-8', errors='ignore')
                lines = content.split('\n')

                for i, line in enumerate(lines, 1):
                    # Check for direct user input usage
                    if 'context.args' in line or 'update.message.text' in line:
                        # Check if validation follows
                        context_lines = '\n'.join(lines[i:i+5])
                        if not re.search(r'(?:validate|check|verify|if\s+not|try)', context_lines, re.IGNORECASE):
                            issues.append(SecurityIssue(
                                severity='MEDIUM',
                                category='Input Validation',
                                description='User input may not be validated',
                                file_path=str(py_file),
                                line_number=i,
                                recommendation='Validate and sanitize all user input'
                            ))

            except Exception as e:
                continue

        return issues

    def audit_dependencies(self) -> List[SecurityIssue]:
        """Check for known vulnerable dependencies."""
        issues = []

        # Check requirements if exists
        req_files = list(self.base_path.parent.parent.rglob('requirements*.txt'))

        known_vulnerable = {
            'pyyaml<5.4': 'YAML arbitrary code execution',
            'requests<2.20': 'HTTP header injection',
            'urllib3<1.24': 'CRLF injection',
            'cryptography<3.3': 'Various vulnerabilities',
        }

        for req_file in req_files:
            try:
                content = req_file.read_text()
                for vuln_pattern, desc in known_vulnerable.items():
                    pkg, version = vuln_pattern.split('<')
                    if re.search(rf'{pkg}[=<].*{version}', content):
                        issues.append(SecurityIssue(
                            severity='HIGH',
                            category='Vulnerable Dependency',
                            description=f'{pkg}: {desc}',
                            file_path=str(req_file),
                            recommendation=f'Upgrade {pkg} to latest version'
                        ))
            except Exception:
                continue

        return issues

    def run_full_audit(self) -> SecurityAuditResult:
        """Run complete security audit."""
        self.issues = []

        logger.info("Starting security audit...")

        # Audit all Python files
        for py_file in self.base_path.rglob('*.py'):
            if '__pycache__' in str(py_file):
                continue
            self.issues.extend(self.audit_file(py_file))

        # Specific audits
        self.issues.extend(self.audit_wallet_security())
        self.issues.extend(self.audit_api_security())
        self.issues.extend(self.audit_input_validation())
        self.issues.extend(self.audit_dependencies())

        # Count by severity
        critical = len([i for i in self.issues if i.severity == 'CRITICAL'])
        high = len([i for i in self.issues if i.severity == 'HIGH'])
        medium = len([i for i in self.issues if i.severity == 'MEDIUM'])
        low = len([i for i in self.issues if i.severity == 'LOW'])
        info = len([i for i in self.issues if i.severity == 'INFO'])

        # Determine pass/fail
        passed = critical == 0 and high == 0

        result = SecurityAuditResult(
            timestamp=datetime.now(),
            passed=passed,
            critical_issues=critical,
            high_issues=high,
            medium_issues=medium,
            low_issues=low,
            info_issues=info,
            issues=self.issues
        )

        logger.info(f"Audit complete: {'PASSED' if passed else 'FAILED'}")
        logger.info(f"Issues: {critical} critical, {high} high, {medium} medium, {low} low")

        return result


class PenetrationTester:
    """
    Penetration testing for the treasury system.

    Tests for:
    - Authorization bypasses
    - Injection vulnerabilities
    - API abuse scenarios
    """

    def __init__(self, trading_engine=None, wallet=None):
        self.engine = trading_engine
        self.wallet = wallet
        self.results: List[Dict] = []

    async def test_auth_bypass(self) -> List[Dict]:
        """Test for authorization bypasses."""
        tests = []

        if not self.engine:
            return tests

        # Test trading without admin
        fake_user_id = 99999999

        try:
            success, msg, _ = await self.engine.open_position(
                token_mint="So11111111111111111111111111111111111111112",
                token_symbol="SOL",
                direction="LONG",
                user_id=fake_user_id
            )

            tests.append({
                'test': 'Trade without admin auth',
                'passed': not success,
                'details': f"Unauthorized trade {'blocked' if not success else 'ALLOWED - VULNERABILITY!'}"
            })
        except Exception as e:
            tests.append({
                'test': 'Trade without admin auth',
                'passed': True,
                'details': f"Exception raised (expected): {type(e).__name__}"
            })

        # Test position close without admin
        try:
            success, msg = await self.engine.close_position(
                position_id="fake_id",
                user_id=fake_user_id
            )

            tests.append({
                'test': 'Close position without auth',
                'passed': not success,
                'details': f"Unauthorized close {'blocked' if not success else 'ALLOWED - VULNERABILITY!'}"
            })
        except Exception as e:
            tests.append({
                'test': 'Close position without auth',
                'passed': True,
                'details': f"Exception raised (expected): {type(e).__name__}"
            })

        return tests

    async def test_input_injection(self) -> List[Dict]:
        """Test for injection vulnerabilities."""
        tests = []

        if not self.engine:
            return tests

        # Test malicious token mint
        malicious_inputs = [
            "'; DROP TABLE positions; --",
            "<script>alert('xss')</script>",
            "{{7*7}}",
            "${7*7}",
            "../../../etc/passwd",
        ]

        for payload in malicious_inputs:
            try:
                success, msg, _ = await self.engine.open_position(
                    token_mint=payload,
                    token_symbol="TEST",
                    direction="LONG",
                    user_id=self.engine.admin_user_ids[0] if self.engine.admin_user_ids else 1
                )

                tests.append({
                    'test': f'Injection test: {payload[:20]}...',
                    'passed': not success,
                    'details': msg[:100] if msg else 'No message'
                })
            except Exception as e:
                tests.append({
                    'test': f'Injection test: {payload[:20]}...',
                    'passed': True,
                    'details': f"Safely rejected: {type(e).__name__}"
                })

        return tests

    async def test_wallet_security(self) -> List[Dict]:
        """Test wallet security."""
        tests = []

        if not self.wallet:
            return tests

        # Test key exposure in string representation
        treasury = self.wallet.get_treasury()
        if treasury:
            treasury_str = str(treasury)
            treasury_repr = repr(treasury)

            # Check for private key patterns
            has_key = bool(re.search(r'[1-9A-HJ-NP-Za-km-z]{87,88}', treasury_str + treasury_repr))

            tests.append({
                'test': 'Private key in string representation',
                'passed': not has_key,
                'details': 'Key exposure detected!' if has_key else 'No key exposure'
            })

        # Test error messages for key leakage
        try:
            # Try to load non-existent wallet
            self.wallet._load_keypair("nonexistent_address")
        except Exception as e:
            error_msg = str(e)
            has_key_in_error = bool(re.search(r'[1-9A-HJ-NP-Za-km-z]{44,}', error_msg))

            tests.append({
                'test': 'Key in error messages',
                'passed': not has_key_in_error,
                'details': 'Safe error message' if not has_key_in_error else 'Key data in error!'
            })

        return tests

    async def run_all_tests(self) -> Dict:
        """Run all penetration tests."""
        all_tests = []

        logger.info("Running penetration tests...")

        all_tests.extend(await self.test_auth_bypass())
        all_tests.extend(await self.test_input_injection())
        all_tests.extend(await self.test_wallet_security())

        passed = sum(1 for t in all_tests if t['passed'])
        failed = len(all_tests) - passed

        result = {
            'timestamp': datetime.now().isoformat(),
            'total_tests': len(all_tests),
            'passed': passed,
            'failed': failed,
            'success_rate': (passed / len(all_tests) * 100) if all_tests else 0,
            'tests': all_tests
        }

        logger.info(f"Penetration tests complete: {passed}/{len(all_tests)} passed")

        return result


async def run_security_suite():
    """Run complete security test suite."""
    print("\n" + "="*60)
    print("JARVIS TREASURY SECURITY SUITE")
    print("="*60 + "\n")

    # Run static analysis
    print("Running security audit...")
    auditor = SecurityAuditor()
    audit_result = auditor.run_full_audit()
    print(audit_result.to_report())

    # Initialize components for pen testing
    print("\nInitializing components for penetration testing...")

    try:
        from bots.treasury.wallet import SecureWallet
        from bots.treasury.jupiter import JupiterClient
        from bots.treasury.trading import TradingEngine

        # Try to initialize (will fail gracefully if not configured)
        password = os.environ.get('JARVIS_WALLET_PASSWORD', 'test_password_123')
        wallet = SecureWallet(password)
        jupiter = JupiterClient()
        engine = TradingEngine(wallet, jupiter, admin_user_ids=[123456], dry_run=True)

        # Run pen tests
        print("\nRunning penetration tests...")
        tester = PenetrationTester(engine, wallet)
        pen_result = await tester.run_all_tests()

        print(f"\nPenetration Test Results:")
        print(f"  Total: {pen_result['total_tests']}")
        print(f"  Passed: {pen_result['passed']}")
        print(f"  Failed: {pen_result['failed']}")
        print(f"  Success Rate: {pen_result['success_rate']:.1f}%")

        for test in pen_result['tests']:
            status = "" if test['passed'] else ""
            print(f"  {status} {test['test']}: {test['details']}")

    except Exception as e:
        print(f"Penetration tests skipped: {e}")

    print("\n" + "="*60)
    print("SECURITY SUITE COMPLETE")
    print("="*60)

    return audit_result


if __name__ == "__main__":
    asyncio.run(run_security_suite())
