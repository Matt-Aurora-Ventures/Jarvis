"""
Skill vetter for security scanning of local skill packages.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any


class SecuritySeverity(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass(frozen=True)
class SecurityFinding:
    category: str
    severity: SecuritySeverity
    message: str
    file: str
    line: int


@dataclass
class VetResult:
    skill_path: Path
    findings: list[SecurityFinding] = field(default_factory=list)

    @property
    def is_safe(self) -> bool:
        return not any(
            finding.severity in {SecuritySeverity.HIGH, SecuritySeverity.CRITICAL}
            for finding in self.findings
        )


class SkillVetter:
    _secret_patterns: tuple[tuple[str, re.Pattern[str], SecuritySeverity], ...] = (
        (
            "Anthropic-style API key",
            re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}"),
            SecuritySeverity.CRITICAL,
        ),
        (
            "Telegram bot token",
            re.compile(r"\b\d{8,11}:[A-Za-z0-9_-]{20,}\b"),
            SecuritySeverity.CRITICAL,
        ),
        (
            "AWS access key",
            re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
            SecuritySeverity.HIGH,
        ),
        (
            "Hardcoded password",
            re.compile(
                r"(?i)\b(password|passwd|pwd|secret)\b\s*[:=]\s*[\"'][^\"']{6,}[\"']"
            ),
            SecuritySeverity.HIGH,
        ),
    )

    _dangerous_patterns: tuple[tuple[str, re.Pattern[str], SecuritySeverity], ...] = (
        ("eval()", re.compile(r"\beval\s*\("), SecuritySeverity.HIGH),
        ("exec()", re.compile(r"\bexec\s*\("), SecuritySeverity.HIGH),
        ("subprocess call", re.compile(r"\bsubprocess\.(run|Popen|call)\s*\("), SecuritySeverity.HIGH),
        ("os.system()", re.compile(r"\bos\.system\s*\("), SecuritySeverity.HIGH),
        ("pickle.load()", re.compile(r"\bpickle\.load\s*\("), SecuritySeverity.HIGH),
    )

    _dangerous_permissions: tuple[tuple[str, SecuritySeverity], ...] = (
        ("execute:shell", SecuritySeverity.HIGH),
        ("admin:root", SecuritySeverity.CRITICAL),
        ("network:all", SecuritySeverity.HIGH),
        ("filesystem:write", SecuritySeverity.MEDIUM),
    )

    def vet_skill(self, skill_path: Path | str) -> VetResult:
        path = Path(skill_path)
        findings: list[SecurityFinding] = []
        if not path.exists():
            findings.append(
                SecurityFinding(
                    category="validation",
                    severity=SecuritySeverity.HIGH,
                    message=f"Skill path not found: {path}",
                    file=str(path),
                    line=0,
                )
            )
            return VetResult(skill_path=path, findings=findings)

        for file_path in self._iter_scan_files(path):
            text = self._read_text(file_path)
            if text is None:
                continue
            rel = str(file_path.relative_to(path))
            findings.extend(self.check_for_secrets(text, rel))
            findings.extend(self.check_for_dangerous_calls(text, rel))

        manifest = self._load_manifest(path)
        if manifest is not None:
            findings.extend(self.check_permissions(manifest, file_name="config.json"))

        return VetResult(skill_path=path, findings=findings)

    def check_for_secrets(self, code: str, file_name: str) -> list[SecurityFinding]:
        findings: list[SecurityFinding] = []
        for label, pattern, severity in self._secret_patterns:
            for match in pattern.finditer(code):
                findings.append(
                    SecurityFinding(
                        category="secrets",
                        severity=severity,
                        message=f"Potential {label} detected",
                        file=file_name,
                        line=self._line_number(code, match.start()),
                    )
                )
        return findings

    def check_for_dangerous_calls(
        self, code: str, file_name: str
    ) -> list[SecurityFinding]:
        findings: list[SecurityFinding] = []
        for label, pattern, severity in self._dangerous_patterns:
            for match in pattern.finditer(code):
                findings.append(
                    SecurityFinding(
                        category="dangerous_code",
                        severity=severity,
                        message=f"Dangerous call detected: {label}",
                        file=file_name,
                        line=self._line_number(code, match.start()),
                    )
                )
        return findings

    def check_permissions(
        self, manifest: dict[str, Any], file_name: str = "config.json"
    ) -> list[SecurityFinding]:
        findings: list[SecurityFinding] = []
        permissions = manifest.get("permissions", [])
        if not isinstance(permissions, list):
            return findings

        normalized = [str(permission).strip().lower() for permission in permissions]
        for unsafe_permission, severity in self._dangerous_permissions:
            if unsafe_permission in normalized:
                findings.append(
                    SecurityFinding(
                        category="permissions",
                        severity=severity,
                        message=f"Excessive permission requested: {unsafe_permission}",
                        file=file_name,
                        line=1,
                    )
                )
        return findings

    def generate_report(self, skill_path: Path | str, format: str = "text") -> str:
        result = self.vet_skill(skill_path)
        if format.lower() == "json":
            payload = {
                "skill_path": str(result.skill_path),
                "is_safe": result.is_safe,
                "findings": [
                    {
                        "category": finding.category,
                        "severity": finding.severity.name,
                        "message": finding.message,
                        "file": finding.file,
                        "line": finding.line,
                    }
                    for finding in result.findings
                ],
            }
            return json.dumps(payload, indent=2, sort_keys=True)

        lines = [
            f"Skill: {result.skill_path}",
            f"Status: {'SAFE' if result.is_safe else 'FAILED'}",
            f"Findings: {len(result.findings)}",
        ]
        for finding in result.findings:
            lines.append(
                f"- [{finding.severity.name}] {finding.category} {finding.file}:{finding.line} {finding.message}"
            )
        if not result.findings:
            lines.append("- No security findings.")
        return "\n".join(lines)

    def _iter_scan_files(self, skill_path: Path) -> list[Path]:
        allowed_suffixes = {".py", ".js", ".ts", ".tsx", ".jsx", ".md", ".json", ".yaml", ".yml"}
        files: list[Path] = []
        for item in skill_path.rglob("*"):
            if not item.is_file():
                continue
            if item.name.startswith("."):
                continue
            if item.suffix.lower() in allowed_suffixes:
                files.append(item)
        return files

    def _read_text(self, path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return None

    def _load_manifest(self, skill_path: Path) -> dict[str, Any] | None:
        manifest_path = skill_path / "config.json"
        if not manifest_path.exists():
            return None
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if isinstance(payload, dict):
            return payload
        return {}

    @staticmethod
    def _line_number(text: str, offset: int) -> int:
        return text.count("\n", 0, offset) + 1
