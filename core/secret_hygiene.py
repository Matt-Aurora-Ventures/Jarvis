#!/usr/bin/env python3
"""
Secret Hygiene and Open-Source Safety Module
Ensures no secrets, private data, or proprietary code is exposed
Provides comprehensive scanning and cleaning capabilities
"""

import os
import re
import json
import hashlib
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import ast
import fnmatch

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class SecretFinding:
    """Represents a secret or security finding."""
    file_path: str
    line_number: int
    finding_type: str  # "secret", "private_data", "proprietary", "security_issue"
    severity: str  # "critical", "high", "medium", "low"
    description: str
    matched_pattern: str
    context: str  # The actual line content
    recommendation: str


@dataclass
class ScanResult:
    """Result of a security scan."""
    total_files_scanned: int
    findings: List[SecretFinding]
    scan_duration_seconds: float
    scan_timestamp: datetime
    scan_type: str  # "secrets", "private_data", "proprietary", "comprehensive"
    
    def get_findings_by_severity(self) -> Dict[str, List[SecretFinding]]:
        """Group findings by severity."""
        severity_map = {}
        for finding in self.findings:
            if finding.severity not in severity_map:
                severity_map[finding.severity] = []
            severity_map[finding.severity].append(finding)
        return severity_map
    
    def get_findings_by_type(self) -> Dict[str, List[SecretFinding]]:
        """Group findings by type."""
        type_map = {}
        for finding in self.findings:
            if finding.finding_type not in type_map:
                type_map[finding.finding_type] = []
            type_map[finding.finding_type].append(finding)
        return type_map
    
    def has_critical_findings(self) -> bool:
        """Check if there are any critical findings."""
        return any(f.severity == "critical" for f in self.findings)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get scan summary."""
        severity_counts = self.get_findings_by_severity()
        type_counts = self.get_findings_by_type()
        
        return {
            "total_findings": len(self.findings),
            "critical_findings": len(severity_counts.get("critical", [])),
            "high_findings": len(severity_counts.get("high", [])),
            "medium_findings": len(severity_counts.get("medium", [])),
            "low_findings": len(severity_counts.get("low", [])),
            "secrets_found": len(type_counts.get("secret", [])),
            "private_data_found": len(type_counts.get("private_data", [])),
            "proprietary_found": len(type_counts.get("proprietary", [])),
            "security_issues_found": len(type_counts.get("security_issue", [])),
            "scan_duration": self.scan_duration_seconds,
            "files_scanned": self.total_files_scanned
        }


class SecretScanner:
    """Scans for secrets, private data, and security issues."""
    
    # Secret patterns - comprehensive regex patterns for various secret types
    SECRET_PATTERNS = {
        # API Keys
        "api_key_generic": r"(?i)(api[_-]?key|apikey)\s*[:=]\s*['\"]?[a-zA-Z0-9+/]{20,}['\"]?",
        "aws_access_key": r"AKIA[0-9A-Z]{16}",
        "aws_secret_key": r"[0-9a-zA-Z/+]{40}",
        "google_api_key": r"AIza[0-9A-Za-z_-]{35}",
        "openai_api_key": r"sk-[a-zA-Z0-9]{48}",
        "groq_api_key": r"gsk_[a-zA-Z0-9]{48}",
        "github_token": r"(ghp|gho|ghu|ghs|ghr)_[a-zA-Z0-9]{36}",
        "github_pat": r"github_pat_[a-zA-Z0-9_]{82}",
        
        # Database credentials
        "database_url": r"(?i)(database[_-]?url|db[_-]?url)\s*[:=]\s*['\"]?[a-zA-Z0-9+/:@.-]+['\"]?",
        "mysql_password": r"(?i)(mysql|db)_?password\s*[:=]\s*['\"]?[a-zA-Z0-9+/]{8,}['\"]?",
        "postgres_password": r"(?i)(postgres|postgresql)_?password\s*[:=]\s*['\"]?[a-zA-Z0-9+/]{8,}['\"]?",
        
        # Tokens and secrets
        "jwt_token": r"eyJ[a-zA-Z0-9+/_-]*\.eyJ[a-zA-Z0-9+/_-]*\.[a-zA-Z0-9+/_-]*",
        "bearer_token": r"(?i)bearer\s+[a-zA-Z0-9+/_-]{20,}",
        "oauth_token": r"(?i)oauth[_-]?token\s*[:=]\s*['\"]?[a-zA-Z0-9+/_-]{20,}['\"]?",
        
        # Private keys and certificates
        "private_key": r"-----BEGIN [A-Z]+ PRIVATE KEY-----",
        "rsa_private_key": r"-----BEGIN RSA PRIVATE KEY-----",
        "certificate": r"-----BEGIN [A-Z]+ CERTIFICATE-----",
        
        # Cloud provider secrets
        "azure_secret": r"[a-zA-Z0-9+/]{88}==",
        "digitalocean_token": r"doo_v1_[a-f0-9]{64}",
        "slack_token": r"xox[baprs]-[a-zA-Z0-9-]+",
        
        # Other common secrets
        "password_in_url": r"[a-zA-Z0-9+/:@.-]*:[a-zA-Z0-9+/_-]+@[a-zA-Z0-9.-]+",
        "hex_secret": r"[0-9a-fA-F]{32,}",
        "base64_secret": r"[a-zA-Z0-9+/]{20,}={0,2}",
    }
    
    # Private data patterns
    PRIVATE_DATA_PATTERNS = {
        "email_address": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "phone_number": r"\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}",
        "credit_card": r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3[0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "ip_address": r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b",
        "url_with_credentials": r"https?://[^\s/$.?#].[^\s]*:[^\s/$.?#].[^\s]*@[^\s/$.?#].[^\s]*",
    }
    
    # Proprietary code patterns
    PROPRIETARY_PATTERNS = {
        "copyright_notice": r"©\s*\d{4}\s+.*?All\s+rights\s+reserved",
        "proprietary_license": r"(?i)(proprietary|confidential|trade\s+secret|internal\s+use\s+only)",
        "company_specific": r"(?i)(microsoft|apple|google|amazon|facebook|oracle|sap)\s+(inc|corp|corporation|ltd|limited)",
        "ndc_reference": r"(?i)(nda|non-disclosure)\s+agreement",
    }
    
    # Security issue patterns
    SECURITY_PATTERNS = {
        "hardcoded_password": r"(?i)(password|pwd|pass)\s*[:=]\s*['\"]?[a-zA-Z0-9+/]{4,}['\"]?",
        "sql_injection_risk": r"(?i)(execute|query)\s*\(\s*['\"].*?\+.*?['\"]",
        "eval_usage": r"(?i)eval\s*\(",
        "shell_command": r"(?i)(system|exec|popen)\s*\(",
        "debug_code": r"(?i)(console\.log|print\(|debug\.log)",
        "temp_file": r"(?i)(tempfile|mktemp)\s*\(",
        "weak_crypto": r"(?i)(md5|sha1)\s*\(",
    }
    
    # Files to exclude from scanning
    EXCLUDE_PATTERNS = [
        "*.pyc", "*.pyo", "*.pyd",
        "__pycache__/",
        ".git/",
        "node_modules/",
        ".venv/", "venv/", "env/",
        "*.log",
        "*.tmp", "*.temp",
        ".DS_Store",
        "Thumbs.db",
        "*.swp", "*.swo",
        "*.bak",
        "*.orig",
        "*.rej",
    ]
    
    # File extensions to scan
    SCAN_EXTENSIONS = {
        '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.c', '.cpp', '.h', '.hpp',
        '.cs', '.php', '.rb', '.go', '.rs', '.swift', '.kt', '.scala',
        '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf',
        '.sh', '.bash', '.zsh', '.fish', '.ps1', '.bat', '.cmd',
        '.sql', '.html', '.htm', '.xml', '.css', '.scss', '.less',
        '.md', '.txt', '.rst', '.tex',
        '.env', '.env.example', '.env.local', '.env.development',
    }
    
    def __init__(self):
        self.compiled_patterns = self._compile_patterns()
    
    def _compile_patterns(self) -> Dict[str, Dict[str, re.Pattern]]:
        """Compile all regex patterns for efficiency."""
        compiled = {
            "secrets": {name: re.compile(pattern) for name, pattern in self.SECRET_PATTERNS.items()},
            "private_data": {name: re.compile(pattern) for name, pattern in self.PRIVATE_DATA_PATTERNS.items()},
            "proprietary": {name: re.compile(pattern) for name, pattern in self.PROPRIETARY_PATTERNS.items()},
            "security": {name: re.compile(pattern) for name, pattern in self.SECURITY_PATTERNS.items()},
        }
        return compiled
    
    def scan_file(self, file_path: Path, scan_types: List[str] = None) -> List[SecretFinding]:
        """Scan a single file for secrets and security issues."""
        if scan_types is None:
            scan_types = ["secrets", "private_data", "proprietary", "security"]
        
        findings = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            lines = content.splitlines()
            
            for line_num, line in enumerate(lines, 1):
                # Skip empty lines and comments
                if not line.strip() or line.strip().startswith('#'):
                    continue
                
                # Scan for each type
                for scan_type in scan_types:
                    patterns = self.compiled_patterns.get(scan_type, {})
                    
                    for pattern_name, pattern in patterns.items():
                        matches = pattern.finditer(line)
                        
                        for match in matches:
                            finding = SecretFinding(
                                file_path=str(file_path),
                                line_number=line_num,
                                finding_type=scan_type.rstrip('s'),  # Remove plural 's'
                                severity=self._determine_severity(scan_type, pattern_name),
                                description=self._get_description(scan_type, pattern_name),
                                matched_pattern=pattern.pattern,
                                context=line.strip(),
                                recommendation=self._get_recommendation(scan_type, pattern_name)
                            )
                            
                            findings.append(finding)
        
        except Exception as e:
            # Log error but continue scanning
            print(f"Error scanning file {file_path}: {e}")
        
        return findings
    
    def scan_directory(self, directory: Path, scan_types: List[str] = None, 
                      max_files: int = 1000) -> ScanResult:
        """Scan a directory for secrets and security issues."""
        start_time = datetime.now()
        all_findings = []
        files_scanned = 0
        
        if scan_types is None:
            scan_types = ["secrets", "private_data", "proprietary", "security"]
        
        # Find all files to scan
        files_to_scan = []
        for root, dirs, files in os.walk(directory):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if not self._should_exclude_path(Path(root) / d)]
            
            for file in files:
                file_path = Path(root) / file
                
                if not self._should_exclude_file(file_path):
                    files_to_scan.append(file_path)
        
        # Limit number of files to scan
        if len(files_to_scan) > max_files:
            files_to_scan = files_to_scan[:max_files]
        
        # Scan each file
        for file_path in files_to_scan:
            findings = self.scan_file(file_path, scan_types)
            all_findings.extend(findings)
            files_scanned += 1
        
        scan_duration = (datetime.now() - start_time).total_seconds()
        
        return ScanResult(
            total_files_scanned=files_scanned,
            findings=all_findings,
            scan_duration_seconds=scan_duration,
            scan_timestamp=start_time,
            scan_type="comprehensive" if len(scan_types) == 4 else scan_types[0]
        )
    
    def _should_exclude_path(self, path: Path) -> bool:
        """Check if a path should be excluded from scanning."""
        path_str = str(path)
        
        for pattern in self.EXCLUDE_PATTERNS:
            if fnmatch.fnmatch(path_str, pattern) or fnmatch.fnmatch(path.name, pattern):
                return True
        
        return False
    
    def _should_exclude_file(self, file_path: Path) -> bool:
        """Check if a file should be excluded from scanning."""
        # Check exclude patterns
        if self._should_exclude_path(file_path):
            return True
        
        # Check file extension
        if file_path.suffix.lower() not in self.SCAN_EXTENSIONS:
            return True
        
        # Check file size (skip very large files)
        try:
            if file_path.stat().st_size > 10 * 1024 * 1024:  # 10MB
                return True
        except Exception:
            return True
        
        return False
    
    def _determine_severity(self, scan_type: str, pattern_name: str) -> str:
        """Determine severity of a finding."""
        # Critical findings
        if pattern_name in ["api_key_generic", "aws_access_key", "aws_secret_key", 
                           "private_key", "database_url", "jwt_token"]:
            return "critical"
        
        # High findings
        if pattern_name in ["google_api_key", "openai_api_key", "groq_api_key",
                           "github_token", "bearer_token", "password_in_url"]:
            return "high"
        
        # Medium findings
        if scan_type == "security" or pattern_name in ["email_address", "phone_number"]:
            return "medium"
        
        # Low findings
        return "low"
    
    def _get_description(self, scan_type: str, pattern_name: str) -> str:
        """Get description for a finding."""
        descriptions = {
            "api_key_generic": "Generic API key detected",
            "aws_access_key": "AWS access key detected",
            "aws_secret_key": "AWS secret key detected",
            "google_api_key": "Google API key detected",
            "openai_api_key": "OpenAI API key detected",
            "groq_api_key": "Groq API key detected",
            "github_token": "GitHub personal access token detected",
            "database_url": "Database connection URL with credentials detected",
            "private_key": "Private key detected",
            "jwt_token": "JWT token detected",
            "email_address": "Email address detected",
            "phone_number": "Phone number detected",
            "hardcoded_password": "Hardcoded password detected",
            "sql_injection_risk": "Potential SQL injection vulnerability",
            "eval_usage": "Use of eval() function detected",
            "debug_code": "Debug code detected",
            "copyright_notice": "Copyright notice detected",
            "proprietary_license": "Proprietary license detected",
        }
        
        return descriptions.get(pattern_name, f"{scan_type} pattern matched: {pattern_name}")
    
    def _get_recommendation(self, scan_type: str, pattern_name: str) -> str:
        """Get recommendation for a finding."""
        recommendations = {
            "api_key_generic": "Remove API key and use environment variables or secret management",
            "aws_access_key": "Remove AWS credentials and use IAM roles or environment variables",
            "aws_secret_key": "Remove AWS secret key and use secure credential management",
            "google_api_key": "Remove Google API key and use environment variables",
            "openai_api_key": "Remove OpenAI API key and use environment variables",
            "groq_api_key": "Remove Groq API key and use environment variables",
            "github_token": "Remove GitHub token and use environment variables or SSH keys",
            "database_url": "Remove database credentials and use environment variables",
            "private_key": "Remove private key and use secure key management",
            "jwt_token": "Remove JWT token and use secure token management",
            "email_address": "Remove or mask email address if not public",
            "phone_number": "Remove or mask phone number if not public",
            "hardcoded_password": "Remove hardcoded password and use environment variables",
            "sql_injection_risk": "Use parameterized queries to prevent SQL injection",
            "eval_usage": "Avoid using eval() function, use safer alternatives",
            "debug_code": "Remove debug code before production deployment",
            "copyright_notice": "Review copyright notice for open-source compatibility",
            "proprietary_license": "Replace with open-source license if applicable",
        }
        
        return recommendations.get(pattern_name, "Review and remediate this finding")


class OpenSourceSafetyChecker:
    """Checks for open-source safety and compliance."""
    
    def __init__(self):
        self.secret_scanner = SecretScanner()
    
    def check_license_compliance(self, directory: Path) -> Dict[str, Any]:
        """Check for license compliance issues."""
        license_files = []
        copyright_notices = []
        proprietary_references = []
        
        # Scan for license files
        for file_path in directory.rglob("*"):
            if file_path.is_file() and file_path.name.lower() in [
                "license", "license.txt", "license.md", "copying", "copying.txt"
            ]:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        license_files.append({
                            "file": str(file_path),
                            "content": content[:500],  # First 500 chars
                            "license_type": self._detect_license_type(content)
                        })
                except Exception:  # noqa: BLE001 - intentional catch-all
                    pass
        
        # Scan for copyright notices
        scan_result = self.secret_scanner.scan_directory(
            directory, 
            scan_types=["proprietary"],
            max_files=500
        )
        
        for finding in scan_result.findings:
            if "copyright" in finding.matched_pattern.lower():
                copyright_notices.append({
                    "file": finding.file_path,
                    "line": finding.line_number,
                    "content": finding.context
                })
            elif "proprietary" in finding.matched_pattern.lower():
                proprietary_references.append({
                    "file": finding.file_path,
                    "line": finding.line_number,
                    "content": finding.context
                })
        
        return {
            "license_files": license_files,
            "copyright_notices": copyright_notices,
            "proprietary_references": proprietary_references,
            "compliance_status": self._assess_compliance(license_files, copyright_notices, proprietary_references)
        }
    
    def check_dependencies(self, directory: Path) -> Dict[str, Any]:
        """Check for proprietary or problematic dependencies."""
        dependency_files = []
        problematic_deps = []
        
        # Look for dependency files
        dep_file_patterns = [
            "requirements.txt", "package.json", "Pipfile", "poetry.lock",
            "yarn.lock", "package-lock.json", "go.mod", "Cargo.toml",
            "pom.xml", "build.gradle", "composer.json"
        ]
        
        for pattern in dep_file_patterns:
            for file_path in directory.rglob(pattern):
                if file_path.is_file():
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            dependency_files.append({
                                "file": str(file_path),
                                "content": content[:1000]
                            })
                    except Exception:  # noqa: BLE001 - intentional catch-all
                        pass
        
        # Analyze dependencies for issues
        for dep_file in dependency_files:
            issues = self._analyze_dependencies(dep_file["content"])
            if issues:
                problematic_deps.extend(issues)
        
        return {
            "dependency_files": dependency_files,
            "problematic_dependencies": problematic_deps,
            "dependency_status": "safe" if not problematic_deps else "needs_review"
        }
    
    def _detect_license_type(self, content: str) -> str:
        """Detect license type from content."""
        content_lower = content.lower()
        
        if "mit" in content_lower:
            return "MIT"
        elif "apache" in content_lower:
            return "Apache"
        elif "gpl" in content_lower:
            return "GPL"
        elif "bsd" in content_lower:
            return "BSD"
        elif "proprietary" in content_lower or "confidential" in content_lower:
            return "Proprietary"
        else:
            return "Unknown"
    
    def _assess_compliance(self, license_files: List, copyright_notices: List, 
                         proprietary_references: List) -> str:
        """Assess overall compliance status."""
        if proprietary_references:
            return "non_compliant"
        elif not license_files:
            return "no_license"
        elif copyright_notices:
            return "needs_review"
        else:
            return "compliant"
    
    def _analyze_dependencies(self, content: str) -> List[Dict[str, Any]]:
        """Analyze dependency content for issues."""
        issues = []
        
        # Check for known problematic patterns
        problematic_patterns = [
            "proprietary", "commercial", "license", "trial", "demo"
        ]
        
        lines = content.splitlines()
        for line_num, line in enumerate(lines, 1):
            line_lower = line.lower()
            for pattern in problematic_patterns:
                if pattern in line_lower:
                    issues.append({
                        "line": line_num,
                        "content": line.strip(),
                        "issue": f"Potentially problematic dependency: {pattern}"
                    })
        
        return issues


class SecretCleaner:
    """Cleans and redacts secrets from files."""
    
    def __init__(self):
        self.secret_scanner = SecretScanner()
    
    def clean_file(self, file_path: Path, backup: bool = True) -> Dict[str, Any]:
        """Clean secrets from a file."""
        if backup:
            backup_path = file_path.with_suffix(file_path.suffix + ".backup")
            try:
                import shutil
                shutil.copy2(file_path, backup_path)
            except Exception as e:
                return {"success": False, "error": f"Failed to create backup: {e}"}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Scan for secrets
            findings = self.secret_scanner.scan_file(file_path, ["secrets"])
            
            # Redact secrets
            for finding in findings:
                pattern = re.compile(finding.matched_pattern)
                content = pattern.sub("[REDACTED]", content)
            
            # Write cleaned content
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return {
                "success": True,
                "secrets_found": len(findings),
                "secrets_cleaned": len(findings),
                "backup_created": backup,
                "backup_path": str(backup_path) if backup else None
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def generate_gitignore(self, directory: Path) -> str:
        """Generate a comprehensive .gitignore file."""
        gitignore_content = """# Secrets and credentials
*.key
*.pem
*.p12
*.pfx
*.crt
*.p7b
*.p7c
*.p12
*.pfx
*.pem
*.key
*.crt
*.cer
*.der
*.p7b
*.p7c
*.p12
*.pfx

# Environment files
.env
.env.local
.env.development
.env.test
.env.production
.env.*.local

# API keys and secrets
secrets/
credentials/
api_keys/
tokens/

# Database files
*.db
*.sqlite
*.sqlite3

# Log files with sensitive data
*.log
logs/

# Backup files
*.backup
*.bak
*.orig
*.rej

# Temporary files
*.tmp
*.temp
temp/
tmp/

# OS generated files
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# IDE files
.vscode/
.idea/
*.swp
*.swo
*~

# Node modules
node_modules/

# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
.venv/
pip-log.txt
pip-delete-this-directory.txt

# Private data
private/
sensitive/
confidential/

# Certificates
certs/
certificates/
ssl/
"""
        
        gitignore_path = directory / ".gitignore"
        
        try:
            with open(gitignore_path, 'w', encoding='utf-8') as f:
                f.write(gitignore_content)
            return str(gitignore_path)
        except Exception as e:
            return f"Error creating .gitignore: {e}"


# Global instances
_secret_scanner = None
_safety_checker = None
_secret_cleaner = None

def get_secret_scanner() -> SecretScanner:
    """Get the global secret scanner instance."""
    global _secret_scanner
    if _secret_scanner is None:
        _secret_scanner = SecretScanner()
    return _secret_scanner

def get_safety_checker() -> OpenSourceSafetyChecker:
    """Get the global safety checker instance."""
    global _safety_checker
    if _safety_checker is None:
        _safety_checker = OpenSourceSafetyChecker()
    return _safety_checker

def get_secret_cleaner() -> SecretCleaner:
    """Get the global secret cleaner instance."""
    global _secret_cleaner
    if _secret_cleaner is None:
        _secret_cleaner = SecretCleaner()
    return _secret_cleaner


if __name__ == "__main__":
    # Test the secret scanner
    scanner = get_secret_scanner()
    
    # Scan current directory
    print("Scanning for secrets...")
    result = scanner.scan_directory(ROOT, max_files=100)
    
    print(f"Scanned {result.total_files_scanned} files in {result.scan_duration_seconds:.2f} seconds")
    print(f"Found {len(result.findings)} potential issues")
    
    # Print summary
    summary = result.get_summary()
    print("\nSummary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    # Print critical findings
    if result.has_critical_findings():
        print("\nCRITICAL FINDINGS:")
        for finding in result.findings:
            if finding.severity == "critical":
                print(f"  {finding.file_path}:{finding.line_number} - {finding.description}")
    
    # Test safety checker
    print("\nChecking open-source safety...")
    safety_checker = get_safety_checker()
    
    license_check = safety_checker.check_license_compliance(ROOT)
    print(f"License compliance: {license_check['compliance_status']}")
    
    dep_check = safety_checker.check_dependencies(ROOT)
    print(f"Dependency status: {dep_check['dependency_status']}")
    
    # Generate .gitignore
    cleaner = get_secret_cleaner()
    gitignore_result = cleaner.generate_gitignore(ROOT)
    print(f"\nGenerated .gitignore: {gitignore_result}")
