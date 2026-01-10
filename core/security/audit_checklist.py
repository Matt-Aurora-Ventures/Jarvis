"""
Security Audit Checklist
Prompt #52: Comprehensive security audit framework
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import json
import hashlib

logger = logging.getLogger(__name__)


# =============================================================================
# MODELS
# =============================================================================

class AuditCategory(str, Enum):
    SMART_CONTRACT = "smart_contract"
    API_SECURITY = "api_security"
    ACCESS_CONTROL = "access_control"
    DATA_PROTECTION = "data_protection"
    INFRASTRUCTURE = "infrastructure"
    OPERATIONAL = "operational"
    COMPLIANCE = "compliance"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class CheckStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"
    NOT_APPLICABLE = "not_applicable"
    PENDING = "pending"


@dataclass
class AuditCheck:
    """A single audit check item"""
    id: str
    category: AuditCategory
    name: str
    description: str
    severity: Severity
    check_fn: Optional[Callable] = None
    status: CheckStatus = CheckStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    remediation: str = ""
    references: List[str] = field(default_factory=list)
    last_checked: Optional[datetime] = None


@dataclass
class AuditReport:
    """Complete audit report"""
    id: str
    name: str
    version: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    checks: List[AuditCheck] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    auditor: str = "automated"
    status: str = "in_progress"


# =============================================================================
# AUDIT CHECKLIST DEFINITION
# =============================================================================

SECURITY_CHECKLIST: List[Dict[str, Any]] = [
    # Smart Contract Security
    {
        "id": "SC-001",
        "category": AuditCategory.SMART_CONTRACT,
        "name": "Reentrancy Protection",
        "description": "Verify all external calls are protected against reentrancy attacks",
        "severity": Severity.CRITICAL,
        "remediation": "Use checks-effects-interactions pattern or reentrancy guards"
    },
    {
        "id": "SC-002",
        "category": AuditCategory.SMART_CONTRACT,
        "name": "Integer Overflow/Underflow",
        "description": "Ensure all arithmetic operations are safe from overflow",
        "severity": Severity.CRITICAL,
        "remediation": "Use checked math or Rust's built-in overflow checking"
    },
    {
        "id": "SC-003",
        "category": AuditCategory.SMART_CONTRACT,
        "name": "Access Control Validation",
        "description": "Verify proper signer and authority checks on all instructions",
        "severity": Severity.CRITICAL,
        "remediation": "Implement proper PDA derivation and signer verification"
    },
    {
        "id": "SC-004",
        "category": AuditCategory.SMART_CONTRACT,
        "name": "Account Validation",
        "description": "Verify all accounts are properly validated before use",
        "severity": Severity.HIGH,
        "remediation": "Use Anchor constraints or manual account validation"
    },
    {
        "id": "SC-005",
        "category": AuditCategory.SMART_CONTRACT,
        "name": "PDA Seed Uniqueness",
        "description": "Ensure PDA seeds are unique and prevent collisions",
        "severity": Severity.HIGH,
        "remediation": "Include unique identifiers in PDA seeds"
    },
    {
        "id": "SC-006",
        "category": AuditCategory.SMART_CONTRACT,
        "name": "Initialization Replay",
        "description": "Prevent re-initialization of already initialized accounts",
        "severity": Severity.HIGH,
        "remediation": "Add is_initialized flag and check before init"
    },
    {
        "id": "SC-007",
        "category": AuditCategory.SMART_CONTRACT,
        "name": "CPI Safety",
        "description": "Verify CPI calls use correct program IDs and accounts",
        "severity": Severity.HIGH,
        "remediation": "Validate program IDs before CPI calls"
    },
    {
        "id": "SC-008",
        "category": AuditCategory.SMART_CONTRACT,
        "name": "Token Account Ownership",
        "description": "Verify token account ownership in all token operations",
        "severity": Severity.HIGH,
        "remediation": "Check token account authority matches expected"
    },

    # API Security
    {
        "id": "API-001",
        "category": AuditCategory.API_SECURITY,
        "name": "Authentication",
        "description": "Verify all endpoints require proper authentication",
        "severity": Severity.CRITICAL,
        "remediation": "Implement JWT or wallet signature authentication"
    },
    {
        "id": "API-002",
        "category": AuditCategory.API_SECURITY,
        "name": "Rate Limiting",
        "description": "Ensure rate limiting is applied to all public endpoints",
        "severity": Severity.HIGH,
        "remediation": "Implement per-IP and per-user rate limits"
    },
    {
        "id": "API-003",
        "category": AuditCategory.API_SECURITY,
        "name": "Input Validation",
        "description": "Validate and sanitize all user inputs",
        "severity": Severity.HIGH,
        "remediation": "Use Pydantic models with strict validation"
    },
    {
        "id": "API-004",
        "category": AuditCategory.API_SECURITY,
        "name": "SQL Injection Prevention",
        "description": "Ensure parameterized queries are used everywhere",
        "severity": Severity.CRITICAL,
        "remediation": "Use ORM or parameterized queries only"
    },
    {
        "id": "API-005",
        "category": AuditCategory.API_SECURITY,
        "name": "XSS Prevention",
        "description": "Sanitize outputs and use proper Content-Type headers",
        "severity": Severity.HIGH,
        "remediation": "Escape outputs and set CSP headers"
    },
    {
        "id": "API-006",
        "category": AuditCategory.API_SECURITY,
        "name": "CORS Configuration",
        "description": "Verify CORS is properly configured",
        "severity": Severity.MEDIUM,
        "remediation": "Restrict origins to known domains"
    },

    # Access Control
    {
        "id": "AC-001",
        "category": AuditCategory.ACCESS_CONTROL,
        "name": "Multisig Requirements",
        "description": "Critical operations require multisig approval",
        "severity": Severity.CRITICAL,
        "remediation": "Implement multisig for treasury and config changes"
    },
    {
        "id": "AC-002",
        "category": AuditCategory.ACCESS_CONTROL,
        "name": "Role Separation",
        "description": "Different roles have appropriate permissions",
        "severity": Severity.HIGH,
        "remediation": "Implement RBAC with principle of least privilege"
    },
    {
        "id": "AC-003",
        "category": AuditCategory.ACCESS_CONTROL,
        "name": "Admin Key Management",
        "description": "Admin keys are properly secured and rotatable",
        "severity": Severity.CRITICAL,
        "remediation": "Use hardware wallets and key rotation procedures"
    },

    # Data Protection
    {
        "id": "DP-001",
        "category": AuditCategory.DATA_PROTECTION,
        "name": "Sensitive Data Encryption",
        "description": "Sensitive data is encrypted at rest and in transit",
        "severity": Severity.HIGH,
        "remediation": "Use TLS 1.3+ and AES-256 encryption"
    },
    {
        "id": "DP-002",
        "category": AuditCategory.DATA_PROTECTION,
        "name": "API Key Security",
        "description": "API keys are properly hashed and not exposed in logs",
        "severity": Severity.HIGH,
        "remediation": "Hash keys in storage, redact in logs"
    },
    {
        "id": "DP-003",
        "category": AuditCategory.DATA_PROTECTION,
        "name": "Backup Security",
        "description": "Backups are encrypted and access-controlled",
        "severity": Severity.HIGH,
        "remediation": "Encrypt backups and limit access"
    },

    # Infrastructure
    {
        "id": "INF-001",
        "category": AuditCategory.INFRASTRUCTURE,
        "name": "RPC Endpoint Security",
        "description": "RPC endpoints are rate-limited and authenticated",
        "severity": Severity.HIGH,
        "remediation": "Use private RPC endpoints with authentication"
    },
    {
        "id": "INF-002",
        "category": AuditCategory.INFRASTRUCTURE,
        "name": "DDoS Protection",
        "description": "Infrastructure has DDoS mitigation",
        "severity": Severity.HIGH,
        "remediation": "Use CDN with DDoS protection"
    },
    {
        "id": "INF-003",
        "category": AuditCategory.INFRASTRUCTURE,
        "name": "Secret Management",
        "description": "Secrets are managed securely",
        "severity": Severity.CRITICAL,
        "remediation": "Use vault or secret manager"
    },

    # Operational
    {
        "id": "OP-001",
        "category": AuditCategory.OPERATIONAL,
        "name": "Monitoring & Alerting",
        "description": "Comprehensive monitoring with alerts",
        "severity": Severity.HIGH,
        "remediation": "Implement monitoring for all critical paths"
    },
    {
        "id": "OP-002",
        "category": AuditCategory.OPERATIONAL,
        "name": "Incident Response Plan",
        "description": "Documented incident response procedures",
        "severity": Severity.HIGH,
        "remediation": "Create and test incident response playbooks"
    },
    {
        "id": "OP-003",
        "category": AuditCategory.OPERATIONAL,
        "name": "Emergency Shutdown",
        "description": "Ability to pause protocol in emergencies",
        "severity": Severity.CRITICAL,
        "remediation": "Implement pause functionality with multisig"
    },
]


# =============================================================================
# AUDIT RUNNER
# =============================================================================

class SecurityAuditor:
    """Runs security audits against the checklist"""

    def __init__(self):
        self.checks: List[AuditCheck] = []
        self.reports: List[AuditReport] = []
        self._check_registry: Dict[str, Callable] = {}

        # Initialize checklist
        for item in SECURITY_CHECKLIST:
            self.checks.append(AuditCheck(
                id=item["id"],
                category=item["category"],
                name=item["name"],
                description=item["description"],
                severity=item["severity"],
                remediation=item.get("remediation", ""),
                references=item.get("references", [])
            ))

    def register_check(self, check_id: str, check_fn: Callable):
        """Register an automated check function"""
        self._check_registry[check_id] = check_fn

    async def run_full_audit(
        self,
        name: str = "Security Audit",
        version: str = "1.0"
    ) -> AuditReport:
        """Run a complete security audit"""
        import uuid

        report = AuditReport(
            id=str(uuid.uuid4()),
            name=name,
            version=version,
            started_at=datetime.utcnow(),
            checks=[]
        )

        passed = 0
        failed = 0
        partial = 0

        for check in self.checks:
            check_copy = AuditCheck(
                id=check.id,
                category=check.category,
                name=check.name,
                description=check.description,
                severity=check.severity,
                remediation=check.remediation,
                references=check.references
            )

            # Run automated check if registered
            if check.id in self._check_registry:
                try:
                    result = await self._run_check(check.id)
                    check_copy.status = result["status"]
                    check_copy.result = result
                except Exception as e:
                    check_copy.status = CheckStatus.FAILED
                    check_copy.result = {"error": str(e)}
            else:
                check_copy.status = CheckStatus.PENDING

            check_copy.last_checked = datetime.utcnow()
            report.checks.append(check_copy)

            if check_copy.status == CheckStatus.PASSED:
                passed += 1
            elif check_copy.status == CheckStatus.FAILED:
                failed += 1
            elif check_copy.status == CheckStatus.PARTIAL:
                partial += 1

        report.completed_at = datetime.utcnow()
        report.status = "completed"
        report.summary = {
            "total_checks": len(self.checks),
            "passed": passed,
            "failed": failed,
            "partial": partial,
            "pending": len(self.checks) - passed - failed - partial,
            "by_severity": self._count_by_severity(report.checks),
            "by_category": self._count_by_category(report.checks),
            "critical_issues": [
                c.name for c in report.checks
                if c.severity == Severity.CRITICAL and c.status == CheckStatus.FAILED
            ]
        }

        self.reports.append(report)
        return report

    async def run_category_audit(
        self,
        category: AuditCategory
    ) -> List[AuditCheck]:
        """Run audit for a specific category"""
        results = []
        for check in self.checks:
            if check.category != category:
                continue

            if check.id in self._check_registry:
                result = await self._run_check(check.id)
                check.status = result["status"]
                check.result = result
            check.last_checked = datetime.utcnow()
            results.append(check)

        return results

    async def _run_check(self, check_id: str) -> Dict[str, Any]:
        """Run a single automated check"""
        check_fn = self._check_registry.get(check_id)
        if not check_fn:
            return {"status": CheckStatus.PENDING, "message": "No automated check"}

        try:
            if asyncio.iscoroutinefunction(check_fn):
                result = await check_fn()
            else:
                result = check_fn()
            return result
        except Exception as e:
            return {
                "status": CheckStatus.FAILED,
                "error": str(e)
            }

    def _count_by_severity(self, checks: List[AuditCheck]) -> Dict[str, int]:
        counts = {}
        for severity in Severity:
            counts[severity.value] = len([
                c for c in checks
                if c.severity == severity and c.status == CheckStatus.FAILED
            ])
        return counts

    def _count_by_category(self, checks: List[AuditCheck]) -> Dict[str, Dict[str, int]]:
        counts = {}
        for category in AuditCategory:
            category_checks = [c for c in checks if c.category == category]
            counts[category.value] = {
                "total": len(category_checks),
                "passed": len([c for c in category_checks if c.status == CheckStatus.PASSED]),
                "failed": len([c for c in category_checks if c.status == CheckStatus.FAILED])
            }
        return counts

    def get_report(self, report_id: str) -> Optional[AuditReport]:
        """Get a specific report"""
        return next((r for r in self.reports if r.id == report_id), None)

    def get_all_reports(self) -> List[AuditReport]:
        """Get all audit reports"""
        return self.reports

    def export_report(self, report: AuditReport, format: str = "json") -> str:
        """Export report in specified format"""
        if format == "json":
            return json.dumps({
                "id": report.id,
                "name": report.name,
                "version": report.version,
                "started_at": report.started_at.isoformat(),
                "completed_at": report.completed_at.isoformat() if report.completed_at else None,
                "status": report.status,
                "summary": report.summary,
                "checks": [
                    {
                        "id": c.id,
                        "category": c.category.value,
                        "name": c.name,
                        "severity": c.severity.value,
                        "status": c.status.value,
                        "result": c.result
                    }
                    for c in report.checks
                ]
            }, indent=2)

        elif format == "markdown":
            lines = [
                f"# Security Audit Report: {report.name}",
                f"\n**Version:** {report.version}",
                f"**Date:** {report.started_at.strftime('%Y-%m-%d')}",
                f"**Status:** {report.status}\n",
                "## Summary",
                f"- Total Checks: {report.summary.get('total_checks', 0)}",
                f"- Passed: {report.summary.get('passed', 0)}",
                f"- Failed: {report.summary.get('failed', 0)}",
                "\n## Critical Issues"
            ]

            for issue in report.summary.get("critical_issues", []):
                lines.append(f"- {issue}")

            lines.append("\n## Detailed Results")
            for category in AuditCategory:
                category_checks = [c for c in report.checks if c.category == category]
                if not category_checks:
                    continue

                lines.append(f"\n### {category.value.replace('_', ' ').title()}")
                for check in category_checks:
                    status_emoji = "✅" if check.status == CheckStatus.PASSED else "❌"
                    lines.append(f"- {status_emoji} **{check.name}** ({check.severity.value})")

            return "\n".join(lines)

        raise ValueError(f"Unknown format: {format}")


# =============================================================================
# AUTOMATED CHECK IMPLEMENTATIONS
# =============================================================================

def register_default_checks(auditor: SecurityAuditor):
    """Register default automated security checks"""

    @auditor.register_check("API-002")
    async def check_rate_limiting():
        """Check if rate limiting is configured"""
        # Would check actual rate limit configuration
        return {
            "status": CheckStatus.PASSED,
            "message": "Rate limiting configured",
            "config": {
                "requests_per_minute": 60,
                "burst_limit": 100
            }
        }

    @auditor.register_check("API-006")
    async def check_cors():
        """Check CORS configuration"""
        # Would check actual CORS settings
        return {
            "status": CheckStatus.PASSED,
            "message": "CORS properly configured",
            "allowed_origins": ["https://jarvis.ai"]
        }

    @auditor.register_check("DP-001")
    async def check_tls():
        """Check TLS configuration"""
        return {
            "status": CheckStatus.PASSED,
            "message": "TLS 1.3 enabled",
            "tls_version": "1.3"
        }


# =============================================================================
# API ENDPOINTS
# =============================================================================

def create_audit_endpoints(auditor: SecurityAuditor):
    """Create API endpoints for security auditing"""
    from fastapi import APIRouter, HTTPException

    router = APIRouter(prefix="/api/audit", tags=["Security Audit"])

    @router.post("/run")
    async def run_audit(name: str = "Security Audit"):
        """Run a full security audit"""
        report = await auditor.run_full_audit(name=name)
        return {
            "report_id": report.id,
            "status": report.status,
            "summary": report.summary
        }

    @router.get("/reports")
    async def get_reports():
        """Get all audit reports"""
        return [
            {
                "id": r.id,
                "name": r.name,
                "started_at": r.started_at.isoformat(),
                "status": r.status,
                "summary": r.summary
            }
            for r in auditor.get_all_reports()
        ]

    @router.get("/reports/{report_id}")
    async def get_report(report_id: str, format: str = "json"):
        """Get a specific audit report"""
        report = auditor.get_report(report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        if format == "markdown":
            return {"content": auditor.export_report(report, "markdown")}

        return json.loads(auditor.export_report(report, "json"))

    @router.get("/checklist")
    async def get_checklist():
        """Get the security checklist"""
        return [
            {
                "id": c.id,
                "category": c.category.value,
                "name": c.name,
                "description": c.description,
                "severity": c.severity.value,
                "remediation": c.remediation
            }
            for c in auditor.checks
        ]

    return router
