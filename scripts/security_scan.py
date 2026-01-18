#!/usr/bin/env python3
"""Security scanning utilities."""
import subprocess
import json
import re
import sys
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SecurityFinding:
    """A security finding."""
    severity: str
    category: str
    description: str
    file: str
    line: int = 0
    recommendation: str = ""


class DependencyScanner:
    """Scan dependencies for vulnerabilities."""
    
    def scan_python(self) -> List[SecurityFinding]:
        """Scan Python dependencies."""
        findings = []
        
        try:
            # Try pip-audit
            result = subprocess.run(
                ["pip-audit", "--format", "json"],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0 and result.stdout:
                vulns = json.loads(result.stdout)
                for vuln in vulns:
                    findings.append(SecurityFinding(
                        severity="high" if "critical" in vuln.get("severity", "").lower() else "medium",
                        category="dependency",
                        description=f"{vuln.get('name')}: {vuln.get('description', 'Vulnerability found')}",
                        file="requirements.txt",
                        recommendation=f"Upgrade to {vuln.get('fixed_in', 'latest version')}"
                    ))
        except FileNotFoundError:
            logger.warning("pip-audit not installed, skipping Python dependency scan")
        
        return findings
    
    def scan_npm(self) -> List[SecurityFinding]:
        """Scan NPM dependencies."""
        findings = []
        
        frontend_path = Path("frontend")
        if not frontend_path.exists():
            return findings
        
        try:
            result = subprocess.run(
                ["npm", "audit", "--json"],
                capture_output=True,
                text=True,
                cwd=frontend_path
            )
            
            if result.stdout:
                audit = json.loads(result.stdout)
                for vuln_id, vuln in audit.get("vulnerabilities", {}).items():
                    findings.append(SecurityFinding(
                        severity=vuln.get("severity", "medium"),
                        category="dependency",
                        description=f"{vuln_id}: {vuln.get('title', 'NPM vulnerability')}",
                        file="frontend/package.json",
                        recommendation=vuln.get("recommendation", "Update package")
                    ))
        except FileNotFoundError:
            logger.warning("npm not found, skipping NPM dependency scan")
        except json.JSONDecodeError:
            pass
        
        return findings


class SecretScanner:
    """Scan for hardcoded secrets."""
    
    PATTERNS = [
        (r'api[_-]?key\s*[=:]\s*["\'][^"\']{10,}["\']', "API Key"),
        (r'secret[_-]?key\s*[=:]\s*["\'][^"\']{10,}["\']', "Secret Key"),
        (r'password\s*[=:]\s*["\'][^"\']{4,}["\']', "Password"),
        (r'aws_access_key_id\s*[=:]\s*["\']?[A-Z0-9]{20}["\']?', "AWS Access Key"),
        (r'aws_secret_access_key\s*[=:]\s*["\']?[A-Za-z0-9/+=]{40}["\']?', "AWS Secret Key"),
        (r'ghp_[A-Za-z0-9]{36}', "GitHub Token"),
        (r'sk-[A-Za-z0-9]{48}', "OpenAI API Key"),
        (r'-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----', "Private Key"),
        (r'Bearer\s+[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+', "JWT Token"),
    ]
    
    IGNORE_PATHS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
    IGNORE_EXTENSIONS = {".pyc", ".pyo", ".so", ".dll", ".exe", ".bin", ".jpg", ".png", ".gif"}
    
    def scan(self, root: Path = None) -> List[SecurityFinding]:
        """Scan files for secrets."""
        root = root or Path(".")
        findings = []
        
        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
            
            # Skip ignored paths
            if any(part in self.IGNORE_PATHS for part in file_path.parts):
                continue
            
            # Skip ignored extensions
            if file_path.suffix.lower() in self.IGNORE_EXTENSIONS:
                continue
            
            try:
                content = file_path.read_text(errors="ignore")
                
                for pattern, secret_type in self.PATTERNS:
                    for match in re.finditer(pattern, content, re.IGNORECASE):
                        # Find line number
                        line_num = content[:match.start()].count("\n") + 1
                        
                        findings.append(SecurityFinding(
                            severity="critical",
                            category="secret",
                            description=f"Possible {secret_type} found",
                            file=str(file_path),
                            line=line_num,
                            recommendation=f"Remove hardcoded {secret_type} and use environment variables"
                        ))
            except Exception:
                continue
        
        return findings


class CodeScanner:
    """Scan code for security issues."""
    
    PATTERNS = [
        (r'eval\s*\(', "Use of eval()", "high"),
        (r'exec\s*\(', "Use of exec()", "high"),
        (r'subprocess\.call\s*\([^)]*shell\s*=\s*True', "Shell injection risk", "high"),
        (r'os\.system\s*\(', "Use of os.system()", "medium"),
        (r'pickle\.loads?\s*\(', "Unsafe deserialization", "high"),
        (r'yaml\.load\s*\([^)]*Loader\s*=\s*None', "Unsafe YAML loading", "high"),
        (r'\.format\s*\([^)]*\)\s*$', "Potential format string issue", "low"),
        (r'SELECT.*%s', "Potential SQL injection", "high"),
        (r'innerHTML\s*=', "Potential XSS via innerHTML", "medium"),
    ]
    
    def scan(self, root: Path = None) -> List[SecurityFinding]:
        """Scan code for security issues."""
        root = root or Path(".")
        findings = []
        
        for file_path in root.rglob("*.py"):
            if "__pycache__" in str(file_path) or ".venv" in str(file_path):
                continue
            
            try:
                content = file_path.read_text()
                
                for pattern, description, severity in self.PATTERNS:
                    for match in re.finditer(pattern, content):
                        line_num = content[:match.start()].count("\n") + 1
                        
                        findings.append(SecurityFinding(
                            severity=severity,
                            category="code",
                            description=description,
                            file=str(file_path),
                            line=line_num,
                            recommendation="Review and fix security issue"
                        ))
            except Exception:
                continue
        
        return findings


def run_full_scan() -> Dict[str, Any]:
    """Run all security scans."""
    results = {
        "findings": [],
        "summary": {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0
        }
    }
    
    # Dependency scan
    logger.info("Scanning dependencies...")
    dep_scanner = DependencyScanner()
    results["findings"].extend(dep_scanner.scan_python())
    results["findings"].extend(dep_scanner.scan_npm())
    
    # Secret scan
    logger.info("Scanning for secrets...")
    secret_scanner = SecretScanner()
    results["findings"].extend(secret_scanner.scan())
    
    # Code scan
    logger.info("Scanning code...")
    code_scanner = CodeScanner()
    results["findings"].extend(code_scanner.scan())
    
    # Summarize
    for finding in results["findings"]:
        results["summary"][finding.severity] = results["summary"].get(finding.severity, 0) + 1
    
    return results


if __name__ == "__main__":
    results = run_full_scan()
    
    print("\n" + "=" * 60)
    print("Security Scan Results")
    print("=" * 60)
    
    for finding in results["findings"]:
        print(f"\n[{finding.severity.upper()}] {finding.category}")
        print(f"  File: {finding.file}:{finding.line}")
        print(f"  {finding.description}")
        if finding.recommendation:
            print(f"  -> {finding.recommendation}")
    
    print("\n" + "-" * 60)
    print("Summary:")
    for severity, count in results["summary"].items():
        if count > 0:
            print(f"  {severity.capitalize()}: {count}")
    
    # Exit with error if critical findings
    if results["summary"].get("critical", 0) > 0:
        sys.exit(1)
