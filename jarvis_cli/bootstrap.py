"""Bootstrapper for safe startup fixes and validation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from core.startup_validator import StartupValidator, ValidationReport


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class BootstrapResult:
    fixes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    report: Optional[ValidationReport] = None


class Bootstrapper:
    def __init__(self, root: Path = ROOT, venv_dir: str = "venv"):
        self.root = root
        self.venv_path = root / venv_dir
        self.required_dirs = [
            root / "data",
            root / "data" / "secure",
            root / "logs",
            root / "secrets",
        ]

    def ensure_directories(self, result: BootstrapResult) -> None:
        for path in self.required_dirs:
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                result.fixes.append(f"Created directory {path.relative_to(self.root)}")

    def ensure_env_file(self, result: BootstrapResult) -> None:
        env_path = self.root / ".env"
        template_path = self.root / "env.example"
        if not env_path.exists():
            if template_path.exists():
                env_path.write_text(template_path.read_text(encoding="utf-8"), encoding="utf-8")
                result.fixes.append("Created .env from env.example")
            else:
                env_path.write_text("", encoding="utf-8")
                result.fixes.append("Created empty .env")
        else:
            content = env_path.read_text(encoding="utf-8")
            if content and not content.endswith("\n"):
                env_path.write_text(content + "\n", encoding="utf-8")
                result.fixes.append("Normalized .env line endings")

    def ensure_venv(self, result: BootstrapResult) -> None:
        if self.venv_path.exists():
            return
        subprocess.run(
            [sys.executable, "-m", "venv", str(self.venv_path)],
            check=False,
        )
        if self.venv_path.exists():
            result.fixes.append("Created venv")
        else:
            result.errors.append("Failed to create venv")

    def _venv_python(self) -> Path:
        if os.name == "nt":
            return self.venv_path / "Scripts" / "python.exe"
        return self.venv_path / "bin" / "python"

    def install_deps(self, result: BootstrapResult) -> None:
        python = self._venv_python()
        if not python.exists():
            result.errors.append("venv python not found; run jarvis deps")
            return
        requirements = self.root / "requirements.txt"
        if not requirements.exists():
            result.errors.append("requirements.txt missing")
            return
        subprocess.run([str(python), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], check=False)
        subprocess.run([str(python), "-m", "pip", "install", "-r", str(requirements)], check=False)
        result.fixes.append("Installed requirements.txt")

    def run_validation(self) -> ValidationReport:
        validator = StartupValidator()
        return validator.full_validation()

    def write_report(self, result: BootstrapResult) -> None:
        report_path = self.root / "logs" / "startup_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "fixes": result.fixes,
            "warnings": result.warnings,
            "errors": result.errors,
        }
        if result.report:
            payload["validation"] = {
                "passed": result.report.passed,
                "checks_run": result.report.checks_run,
                "checks_passed": result.report.checks_passed,
                "timestamp": result.report.timestamp,
                "issues": [
                    {
                        "category": issue.category,
                        "message": issue.message,
                        "severity": issue.severity.value,
                        "fix_hint": issue.fix_hint,
                        "details": issue.details,
                    }
                    for issue in result.report.issues
                ],
            }
        report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def doctor(self, install_deps: bool = False) -> BootstrapResult:
        result = BootstrapResult()
        self.ensure_directories(result)
        self.ensure_env_file(result)
        self.ensure_venv(result)
        if install_deps:
            self.install_deps(result)
        result.report = self.run_validation()
        self.write_report(result)
        return result
