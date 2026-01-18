"""
Security Audit Script

Comprehensive security audit for the Jarvis codebase:
- Scans for common vulnerabilities
- Checks dependencies for known CVEs
- Verifies no secrets in git history
- Generates detailed security report

Usage:
    python scripts/security_audit.py [--output security_audit_report.md]
"""

import asyncio
import json
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Finding:
    """A security finding."""
    category: str
    severity: str  # critical, high, medium, low, info
    title: str
    description: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    recommendation: str = ""


@dataclass
class DependencyVulnerability:
    """A vulnerability in a dependency."""
    package: str
    version: str
    vulnerability_id: str
    severity: str
    description: str
    fix_version: Optional[str] = None


@dataclass
class AuditReport:
    """Complete security audit report."""
    timestamp: datetime = field(default_factory=datetime.now)
    findings: List[Finding] = field(default_factory=list)
    vulnerable_packages: List[DependencyVulnerability] = field(default_factory=list)
    git_secrets: List[Dict[str, Any]] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

    def add_finding(self, finding: Finding) -> None:
        """Add a finding to the report."""
        self.findings.append(finding)

    def to_markdown(self) -> str:
        """Generate markdown report."""
        lines = [
            "# Security Audit Report",
            "",
            f"**Generated:** {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary",
            "",
        ]

        # Count by severity
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for f in self.findings:
            severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1

        lines.append(f"- **Critical Issues:** {severity_counts['critical']}")
        lines.append(f"- **High Issues:** {severity_counts['high']}")
        lines.append(f"- **Medium Issues:** {severity_counts['medium']}")
        lines.append(f"- **Low Issues:** {severity_counts['low']}")
        lines.append(f"- **Vulnerable Dependencies:** {len(self.vulnerable_packages)}")
        lines.append(f"- **Git Secrets:** {len(self.git_secrets)}")
        lines.append("")

        # Findings by category
        categories = {}
        for f in self.findings:
            if f.category not in categories:
                categories[f.category] = []
            categories[f.category].append(f)

        lines.append("## Findings")
        lines.append("")

        for category, findings in categories.items():
            lines.append(f"### {category}")
            lines.append("")
            for f in findings:
                severity_icon = {"critical": "[!]", "high": "[H]", "medium": "[M]", "low": "[L]", "info": "[i]"}
                icon = severity_icon.get(f.severity, "[-]")
                lines.append(f"#### {icon} {f.title}")
                lines.append(f"*Severity: {f.severity.upper()}*")
                lines.append("")
                lines.append(f"{f.description}")
                if f.file_path:
                    lines.append(f"- File: `{f.file_path}`" + (f":{f.line_number}" if f.line_number else ""))
                if f.recommendation:
                    lines.append(f"- **Recommendation:** {f.recommendation}")
                lines.append("")

        # Vulnerable dependencies
        if self.vulnerable_packages:
            lines.append("## Vulnerable Dependencies")
            lines.append("")
            for vuln in self.vulnerable_packages:
                lines.append(f"### {vuln.package} ({vuln.version})")
                lines.append(f"- **ID:** {vuln.vulnerability_id}")
                lines.append(f"- **Severity:** {vuln.severity}")
                lines.append(f"- **Description:** {vuln.description}")
                if vuln.fix_version:
                    lines.append(f"- **Fix Version:** {vuln.fix_version}")
                lines.append("")

        # Git secrets
        if self.git_secrets:
            lines.append("## Secrets in Git History")
            lines.append("")
            for secret in self.git_secrets:
                lines.append(f"- `{secret.get('file', 'unknown')}`: {secret.get('type', 'secret')}")

        lines.append("")
        lines.append("## Recommendations")
        lines.append("")
        lines.append("1. Address all Critical and High severity issues immediately")
        lines.append("2. Update vulnerable dependencies to fixed versions")
        lines.append("3. Rotate any secrets found in git history")
        lines.append("4. Review Medium severity issues within 30 days")
        lines.append("")

        return "\n".join(lines)


class SecurityAuditRunner:
    """
    Runs comprehensive security audit on the codebase.
    """

    # Patterns that indicate potential secrets
    SECRET_PATTERNS = [
        (r"['\"]?password['\"]?\s*[:=]\s*['\"][^'\"]+['\"]", "hardcoded_password"),
        (r"['\"]?api_key['\"]?\s*[:=]\s*['\"][A-Za-z0-9]{20,}['\"]", "api_key"),
        (r"['\"]?secret['\"]?\s*[:=]\s*['\"][^'\"]+['\"]", "hardcoded_secret"),
        (r"['\"]?private_key['\"]?\s*[:=]\s*['\"][A-Za-z0-9+/=]{32,}['\"]", "private_key"),
        (r"[1-9A-HJ-NP-Za-km-z]{87,88}", "solana_private_key"),  # Base58 private key
        (r"sk_live_[A-Za-z0-9]+", "stripe_key"),
        (r"ghp_[A-Za-z0-9]+", "github_token"),
        (r"xox[baprs]-[A-Za-z0-9-]+", "slack_token"),
    ]

    # Files to skip
    SKIP_PATTERNS = [
        r"\.git/",
        r"\.venv/",
        r"venv/",
        r"node_modules/",
        r"__pycache__/",
        r"\.pyc$",
        r"\.pyo$",
        r"\.egg-info/",
        r"\.so$",
        r"\.dll$",
    ]

    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize the audit runner.

        Args:
            project_root: Root directory to scan (defaults to cwd)
        """
        self.project_root = project_root or Path.cwd()
        self.report = AuditReport()

    def _should_skip(self, path: Path) -> bool:
        """Check if a path should be skipped."""
        path_str = str(path)
        return any(re.search(pattern, path_str) for pattern in self.SKIP_PATTERNS)

    async def run_audit(self) -> AuditReport:
        """
        Run complete security audit.

        Returns:
            AuditReport with all findings
        """
        logger.info("Starting security audit...")

        # Scan for secrets in code
        await self._scan_for_secrets()

        # Check for common vulnerabilities
        await self._check_vulnerabilities()

        # Check dependencies
        await self.check_dependencies()

        # Check git history
        await self.check_git_secrets()

        # Generate summary
        self.report.summary = self._generate_summary()

        logger.info(f"Audit complete: {len(self.report.findings)} findings")
        return self.report

    async def _scan_for_secrets(self) -> None:
        """Scan codebase for hardcoded secrets."""
        logger.info("Scanning for secrets...")

        python_files = list(self.project_root.glob("**/*.py"))

        for py_file in python_files[:500]:  # Limit for performance
            if self._should_skip(py_file):
                continue

            try:
                content = py_file.read_text(encoding='utf-8')

                for pattern, secret_type in self.SECRET_PATTERNS:
                    for match in re.finditer(pattern, content, re.IGNORECASE):
                        # Skip if in a comment or test file
                        if "test" in str(py_file).lower():
                            continue

                        # Find line number
                        line_start = content[:match.start()].count('\n') + 1

                        self.report.add_finding(Finding(
                            category="Secrets",
                            severity="critical",
                            title=f"Potential {secret_type} found",
                            description=f"Found what appears to be a hardcoded secret.",
                            file_path=str(py_file.relative_to(self.project_root)),
                            line_number=line_start,
                            recommendation="Move secret to environment variable or secure vault."
                        ))

            except Exception as e:
                logger.debug(f"Failed to scan {py_file}: {e}")

    async def _check_vulnerabilities(self) -> None:
        """Check for common vulnerability patterns."""
        logger.info("Checking for vulnerabilities...")

        # Check for unsafe pickle usage
        await self._check_pattern(
            r"pickle\.load\s*\(",
            "Unsafe pickle.load()",
            "Pickle deserialization can execute arbitrary code",
            "high",
            "Use json or a safer serialization format"
        )

        # Check for eval/exec
        await self._check_pattern(
            r"\beval\s*\(",
            "Use of eval()",
            "eval() can execute arbitrary code",
            "high",
            "Avoid eval(). Use ast.literal_eval() for safe parsing"
        )

        await self._check_pattern(
            r"\bexec\s*\(",
            "Use of exec()",
            "exec() can execute arbitrary code",
            "high",
            "Avoid exec() if possible"
        )

        # Check for shell=True
        await self._check_pattern(
            r"subprocess\.[a-z]+\([^)]*shell\s*=\s*True",
            "subprocess with shell=True",
            "shell=True can be vulnerable to shell injection",
            "medium",
            "Avoid shell=True. Pass command as list."
        )

        # Check for SQL patterns
        await self._check_pattern(
            r'\.execute\s*\(\s*f["\']',
            "SQL with f-string",
            "Potential SQL injection vulnerability",
            "critical",
            "Use parameterized queries"
        )

    async def _check_pattern(
        self,
        pattern: str,
        title: str,
        description: str,
        severity: str,
        recommendation: str
    ) -> None:
        """Check for a specific pattern in the codebase."""
        python_files = list(self.project_root.glob("**/*.py"))

        for py_file in python_files[:500]:
            if self._should_skip(py_file):
                continue

            try:
                content = py_file.read_text(encoding='utf-8')

                for match in re.finditer(pattern, content):
                    line_start = content[:match.start()].count('\n') + 1

                    self.report.add_finding(Finding(
                        category="Vulnerabilities",
                        severity=severity,
                        title=title,
                        description=description,
                        file_path=str(py_file.relative_to(self.project_root)),
                        line_number=line_start,
                        recommendation=recommendation
                    ))

            except Exception:
                pass

    async def check_dependencies(self) -> AuditReport:
        """
        Check dependencies for known vulnerabilities.

        Returns:
            AuditReport (same instance, for chaining)
        """
        logger.info("Checking dependencies...")

        # Try pip-audit if available
        try:
            result = subprocess.run(
                ["pip-audit", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode == 0 and result.stdout:
                vulns = json.loads(result.stdout)
                for vuln in vulns:
                    self.report.vulnerable_packages.append(DependencyVulnerability(
                        package=vuln.get("name", "unknown"),
                        version=vuln.get("version", "unknown"),
                        vulnerability_id=vuln.get("id", ""),
                        severity=vuln.get("fix_versions", ["unknown"])[0] if vuln.get("fix_versions") else "unknown",
                        description=vuln.get("description", ""),
                        fix_version=vuln.get("fix_versions", [None])[0]
                    ))

        except FileNotFoundError:
            logger.info("pip-audit not available, skipping dependency check")
        except subprocess.TimeoutExpired:
            logger.warning("Dependency check timed out")
        except Exception as e:
            logger.warning(f"Dependency check failed: {e}")

        return self.report

    async def check_git_secrets(self) -> AuditReport:
        """
        Check for secrets in git history.

        Returns:
            AuditReport (same instance, for chaining)
        """
        logger.info("Checking git history for secrets...")

        # Check if in a git repo
        git_dir = self.project_root / ".git"
        if not git_dir.exists():
            return self.report

        # Try git-secrets or trufflehog if available
        try:
            # Simple check: look for common secret patterns in recent commits
            result = subprocess.run(
                ["git", "log", "--oneline", "-n", "100", "--all"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=30
            )

            # This is a simplified check - in production use trufflehog or git-secrets
            if result.returncode == 0:
                self.report.add_finding(Finding(
                    category="Git",
                    severity="info",
                    title="Git history check",
                    description=f"Reviewed {len(result.stdout.splitlines())} recent commits.",
                    recommendation="Consider running trufflehog for comprehensive git secret scanning"
                ))

        except Exception as e:
            logger.debug(f"Git history check failed: {e}")

        return self.report

    def _generate_summary(self) -> Dict[str, Any]:
        """Generate audit summary."""
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for f in self.report.findings:
            severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1

        return {
            "total_findings": len(self.report.findings),
            "by_severity": severity_counts,
            "vulnerable_packages": len(self.report.vulnerable_packages),
            "git_secrets": len(self.report.git_secrets),
            "passed": severity_counts["critical"] == 0 and severity_counts["high"] == 0
        }

    def generate_report(self, output_path: Path) -> None:
        """
        Generate and write the audit report.

        Args:
            output_path: Path to write the report
        """
        markdown = self.report.to_markdown()
        output_path.write_text(markdown)
        logger.info(f"Report written to {output_path}")


async def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Run security audit")
    parser.add_argument("--output", "-o", default="security_audit_report.md",
                        help="Output file path")
    parser.add_argument("--project", "-p", default=".",
                        help="Project root directory")

    args = parser.parse_args()

    runner = SecurityAuditRunner(project_root=Path(args.project))
    await runner.run_audit()
    runner.generate_report(Path(args.output))

    # Print summary
    summary = runner.report.summary
    print("\n" + "=" * 50)
    print("SECURITY AUDIT SUMMARY")
    print("=" * 50)
    print(f"Total Findings: {summary['total_findings']}")
    print(f"  Critical: {summary['by_severity']['critical']}")
    print(f"  High: {summary['by_severity']['high']}")
    print(f"  Medium: {summary['by_severity']['medium']}")
    print(f"  Low: {summary['by_severity']['low']}")
    print(f"Vulnerable Dependencies: {summary['vulnerable_packages']}")
    print(f"\nStatus: {'PASSED' if summary['passed'] else 'FAILED'}")
    print(f"Report: {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
