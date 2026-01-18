"""
Security Hardening Module for Jarvis Trading Bot
=================================================

Implements critical security best practices:
- Encrypted API key storage at rest
- IP whitelisting for API keys
- Secrets scanning and hygiene
- Audit logging

References the 3Commas breach (Dec 2022) where unencrypted API keys
led to $22M+ in user losses.

Phase 4 Implementation per Quant Analyst specification.

Usage:
    from core.security_hardening import SecureKeyManager, SecurityAuditor
    
    # Store API key securely
    manager = SecureKeyManager()
    manager.store_key("binance_api", api_key, password="user_password")
    
    # Retrieve key
    api_key = manager.get_key("binance_api", password="user_password")
    
    # Audit for security issues
    auditor = SecurityAuditor()
    issues = auditor.scan_directory("/path/to/code")
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Optional cryptography imports
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    Fernet = None


logger = logging.getLogger(__name__)


# ============================================================================
# Security Constants
# ============================================================================

# Known patterns that indicate secrets
SECRET_PATTERNS = [
    # API Keys
    (r'sk-[a-zA-Z0-9]{32,}', "OpenAI API Key"),
    (r'sk_live_[a-zA-Z0-9]{24,}', "Stripe Live Key"),
    (r'sk_test_[a-zA-Z0-9]{24,}', "Stripe Test Key"),
    (r'AIza[0-9A-Za-z_-]{35}', "Google API Key"),
    (r'ghp_[a-zA-Z0-9]{36}', "GitHub Personal Access Token"),
    (r'gho_[a-zA-Z0-9]{36}', "GitHub OAuth Token"),
    
    # Crypto Exchange Keys
    (r'[a-zA-Z0-9]{64}', "Potential Exchange API Key"),
    (r'0x[a-fA-F0-9]{64}', "Ethereum Private Key"),
    
    # Generic patterns
    (r'api[_-]?key\s*[=:]\s*["\']?[a-zA-Z0-9_-]{16,}["\']?', "API Key Assignment"),
    (r'secret[_-]?key\s*[=:]\s*["\']?[a-zA-Z0-9_-]{16,}["\']?', "Secret Key Assignment"),
    (r'password\s*[=:]\s*["\'][^"\']{8,}["\']', "Password Assignment"),
    (r'private[_-]?key\s*[=:]\s*["\']?[a-zA-Z0-9_-]{32,}["\']?', "Private Key Assignment"),
]

# Files that should never contain secrets
SAFE_EXTENSIONS = {'.md', '.txt', '.rst', '.html', '.css'}

# Files that commonly contain secrets (need extra scrutiny)
SENSITIVE_EXTENSIONS = {'.py', '.js', '.ts', '.json', '.yaml', '.yml', '.env', '.ini', '.cfg'}


# ============================================================================
# Secure Key Manager
# ============================================================================

@dataclass
class EncryptedKey:
    """Represents an encrypted API key."""
    key_id: str
    encrypted_value: bytes
    salt: bytes
    created_at: float
    last_accessed: float
    access_count: int = 0
    ip_whitelist: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "key_id": self.key_id,
            "encrypted_value": base64.b64encode(self.encrypted_value).decode(),
            "salt": base64.b64encode(self.salt).decode(),
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
            "ip_whitelist": self.ip_whitelist,
            "permissions": self.permissions,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EncryptedKey':
        return cls(
            key_id=data["key_id"],
            encrypted_value=base64.b64decode(data["encrypted_value"]),
            salt=base64.b64decode(data["salt"]),
            created_at=data.get("created_at", time.time()),
            last_accessed=data.get("last_accessed", time.time()),
            access_count=data.get("access_count", 0),
            ip_whitelist=data.get("ip_whitelist", []),
            permissions=data.get("permissions", []),
        )


class SecureKeyManager:
    """
    Secure API key storage with encryption at rest.
    
    Security features:
    - Fernet symmetric encryption (AES-128-CBC)
    - PBKDF2 key derivation from user password
    - Per-key salt to prevent rainbow tables
    - IP whitelisting per key
    - Access logging and rate limiting
    
    Lessons from 3Commas breach (Dec 2022):
    - API keys were stored unencrypted
    - No IP whitelisting enforced
    - No access monitoring
    """
    
    def __init__(
        self,
        storage_path: Optional[Path] = None,
        max_access_per_minute: int = 60,
    ):
        self.storage_path = storage_path or Path.home() / ".lifeos" / "secure_keys.json"
        self.max_access_per_minute = max_access_per_minute
        
        self._keys: Dict[str, EncryptedKey] = {}
        self._access_log: List[Dict[str, Any]] = []
        self._load_keys()
    
    def _load_keys(self):
        """Load encrypted keys from storage."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path) as f:
                    data = json.load(f)
                
                for key_id, key_data in data.get("keys", {}).items():
                    self._keys[key_id] = EncryptedKey.from_dict(key_data)
                    
            except Exception as e:
                logger.error(f"Failed to load keys: {e}")
    
    def _save_keys(self):
        """Save encrypted keys to storage."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "keys": {
                key_id: key.to_dict()
                for key_id, key in self._keys.items()
            },
            "updated_at": time.time(),
        }
        
        with open(self.storage_path, "w") as f:
            json.dump(data, f)
        
        # Set restrictive permissions
        os.chmod(self.storage_path, 0o600)
    
    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """Derive encryption key from password using PBKDF2."""
        if not HAS_CRYPTO:
            # Fallback to simple hash (less secure)
            return hashlib.pbkdf2_hmac(
                'sha256',
                password.encode(),
                salt,
                100000,
                dklen=32
            )
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))
    
    def store_key(
        self,
        key_id: str,
        value: str,
        password: str,
        ip_whitelist: Optional[List[str]] = None,
        permissions: Optional[List[str]] = None,
    ) -> bool:
        """
        Store an API key with encryption.
        
        Args:
            key_id: Identifier for the key
            value: The API key value
            password: User password for encryption
            ip_whitelist: Optional list of allowed IPs
            permissions: Optional list of allowed operations
            
        Returns:
            True if stored successfully
        """
        try:
            salt = secrets.token_bytes(16)
            derived_key = self._derive_key(password, salt)
            
            if HAS_CRYPTO:
                fernet = Fernet(derived_key)
                encrypted = fernet.encrypt(value.encode())
            else:
                # Simple XOR encryption fallback (NOT recommended for production)
                logger.warning("Using fallback encryption - install cryptography for better security")
                encrypted = bytes([a ^ b for a, b in zip(
                    value.encode().ljust(len(value) + 16),
                    (derived_key * ((len(value) // 32) + 1))[:len(value) + 16]
                )])
            
            self._keys[key_id] = EncryptedKey(
                key_id=key_id,
                encrypted_value=encrypted,
                salt=salt,
                created_at=time.time(),
                last_accessed=time.time(),
                ip_whitelist=ip_whitelist or [],
                permissions=permissions or ["read", "trade"],
            )
            
            self._save_keys()
            self._log_access(key_id, "store", True)
            
            logger.info(f"Stored encrypted key: {key_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store key {key_id}: {e}")
            self._log_access(key_id, "store", False, str(e))
            return False
    
    def get_key(
        self,
        key_id: str,
        password: str,
        client_ip: Optional[str] = None,
    ) -> Optional[str]:
        """
        Retrieve and decrypt an API key.
        
        Args:
            key_id: Identifier for the key
            password: User password for decryption
            client_ip: Optional client IP for whitelist check
            
        Returns:
            Decrypted API key or None if failed
        """
        if key_id not in self._keys:
            self._log_access(key_id, "get", False, "Key not found")
            return None
        
        key = self._keys[key_id]
        
        # Check IP whitelist
        if client_ip and key.ip_whitelist:
            if client_ip not in key.ip_whitelist:
                self._log_access(key_id, "get", False, f"IP not whitelisted: {client_ip}")
                logger.warning(f"Access denied for {key_id}: IP {client_ip} not whitelisted")
                return None
        
        # Rate limiting
        if not self._check_rate_limit(key_id):
            self._log_access(key_id, "get", False, "Rate limit exceeded")
            return None
        
        try:
            derived_key = self._derive_key(password, key.salt)
            
            if HAS_CRYPTO:
                fernet = Fernet(derived_key)
                value = fernet.decrypt(key.encrypted_value).decode()
            else:
                # Simple XOR decryption fallback
                decrypted = bytes([a ^ b for a, b in zip(
                    key.encrypted_value,
                    (derived_key * ((len(key.encrypted_value) // 32) + 1))[:len(key.encrypted_value)]
                )])
                value = decrypted.rstrip(b'\x00').decode()
            
            # Update access info
            key.last_accessed = time.time()
            key.access_count += 1
            self._save_keys()
            
            self._log_access(key_id, "get", True)
            return value
            
        except Exception as e:
            self._log_access(key_id, "get", False, str(e))
            logger.error(f"Failed to decrypt key {key_id}: {e}")
            return None
    
    def delete_key(self, key_id: str, password: str) -> bool:
        """Delete an API key."""
        # Verify password by attempting decrypt
        if self.get_key(key_id, password) is None:
            return False
        
        del self._keys[key_id]
        self._save_keys()
        self._log_access(key_id, "delete", True)
        return True
    
    def rotate_key(
        self,
        key_id: str,
        old_password: str,
        new_value: str,
        new_password: Optional[str] = None,
    ) -> bool:
        """Rotate an API key (update value and optionally password)."""
        # Get old key to verify access
        old_value = self.get_key(key_id, old_password)
        if old_value is None:
            return False
        
        # Store with new value/password
        key = self._keys[key_id]
        return self.store_key(
            key_id,
            new_value,
            new_password or old_password,
            ip_whitelist=key.ip_whitelist,
            permissions=key.permissions,
        )
    
    def add_ip_whitelist(self, key_id: str, ip: str) -> bool:
        """Add an IP to a key's whitelist."""
        if key_id not in self._keys:
            return False
        
        if ip not in self._keys[key_id].ip_whitelist:
            self._keys[key_id].ip_whitelist.append(ip)
            self._save_keys()
        
        return True
    
    def _check_rate_limit(self, key_id: str) -> bool:
        """Check if key access is within rate limit."""
        cutoff = time.time() - 60
        recent = [
            log for log in self._access_log
            if log["key_id"] == key_id 
            and log["timestamp"] > cutoff
            and log["action"] == "get"
        ]
        return len(recent) < self.max_access_per_minute
    
    def _log_access(
        self,
        key_id: str,
        action: str,
        success: bool,
        error: Optional[str] = None,
    ):
        """Log key access."""
        self._access_log.append({
            "key_id": key_id,
            "action": action,
            "success": success,
            "error": error,
            "timestamp": time.time(),
        })
        
        # Keep last 1000 entries
        if len(self._access_log) > 1000:
            self._access_log = self._access_log[-1000:]
    
    def get_access_log(self, key_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get access log, optionally filtered by key."""
        if key_id:
            return [log for log in self._access_log if log["key_id"] == key_id]
        return self._access_log
    
    def list_keys(self) -> List[Dict[str, Any]]:
        """List all stored keys (metadata only, not values)."""
        return [
            {
                "key_id": k.key_id,
                "created_at": k.created_at,
                "last_accessed": k.last_accessed,
                "access_count": k.access_count,
                "ip_whitelist": k.ip_whitelist,
                "permissions": k.permissions,
            }
            for k in self._keys.values()
        ]


# ============================================================================
# Security Auditor
# ============================================================================

@dataclass
class SecurityIssue:
    """Represents a security issue found during audit."""
    severity: str  # "critical", "high", "medium", "low"
    type: str  # "leaked_secret", "insecure_config", "permission"
    file: str
    line: Optional[int]
    description: str
    pattern: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity,
            "type": self.type,
            "file": self.file,
            "line": self.line,
            "description": self.description,
            "pattern": self.pattern,
        }


class SecurityAuditor:
    """
    Security auditor for codebase scanning.
    
    Scans for:
    - Hardcoded API keys
    - Passwords in code
    - Private keys
    - Insecure configurations
    """
    
    def __init__(
        self,
        exclude_patterns: Optional[List[str]] = None,
        custom_patterns: Optional[List[tuple]] = None,
    ):
        self.exclude_patterns = exclude_patterns or [
            r'\.git/',
            r'__pycache__/',
            r'node_modules/',
            r'\.venv/',
            r'venv/',
        ]
        self.patterns = SECRET_PATTERNS + (custom_patterns or [])
    
    def scan_file(self, file_path: Path) -> List[SecurityIssue]:
        """Scan a single file for security issues."""
        issues = []
        
        if not file_path.exists() or not file_path.is_file():
            return issues
        
        # Skip binary files and safe extensions
        if file_path.suffix in SAFE_EXTENSIONS:
            return issues
        
        try:
            content = file_path.read_text(errors='ignore')
            lines = content.splitlines()
            
            for line_num, line in enumerate(lines, 1):
                for pattern, description in self.patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        # Check if it's actually a false positive
                        if self._is_false_positive(line, pattern):
                            continue
                        
                        issues.append(SecurityIssue(
                            severity="high" if "private" in description.lower() else "medium",
                            type="leaked_secret",
                            file=str(file_path),
                            line=line_num,
                            description=f"Potential {description} found",
                            pattern=pattern,
                        ))
                        
        except Exception as e:
            logger.warning(f"Could not scan {file_path}: {e}")
        
        return issues
    
    def _is_false_positive(self, line: str, pattern: str) -> bool:
        """Check if match is likely a false positive."""
        # Skip comments
        stripped = line.strip()
        if stripped.startswith('#') or stripped.startswith('//'):
            return True
        
        # Skip example/placeholder values
        lower_line = line.lower()
        if any(fp in lower_line for fp in [
            'example', 'placeholder', 'your_', 'xxx', '***',
            'test', 'dummy', 'sample', 'fake', 'mock'
        ]):
            return True
        
        return False
    
    def scan_directory(
        self,
        directory: Path,
        recursive: bool = True,
    ) -> List[SecurityIssue]:
        """Scan a directory for security issues."""
        issues = []
        directory = Path(directory)
        
        if not directory.exists():
            return issues
        
        # Get files to scan
        if recursive:
            files = directory.rglob('*')
        else:
            files = directory.glob('*')
        
        for file_path in files:
            # Skip excluded patterns
            if any(re.search(pat, str(file_path)) for pat in self.exclude_patterns):
                continue
            
            if file_path.is_file():
                issues.extend(self.scan_file(file_path))
        
        return issues
    
    def check_file_permissions(self, path: Path) -> List[SecurityIssue]:
        """Check file permissions for security issues."""
        issues = []
        
        try:
            stat = path.stat()
            mode = stat.st_mode
            
            # Check if world-readable
            if mode & 0o004:
                issues.append(SecurityIssue(
                    severity="medium",
                    type="permission",
                    file=str(path),
                    line=None,
                    description="File is world-readable - consider restricting permissions",
                ))
            
            # Check if world-writable
            if mode & 0o002:
                issues.append(SecurityIssue(
                    severity="high",
                    type="permission",
                    file=str(path),
                    line=None,
                    description="File is world-writable - INSECURE!",
                ))
                
        except Exception:
            pass
        
        return issues
    
    def generate_report(self, issues: List[SecurityIssue]) -> str:
        """Generate a security audit report."""
        if not issues:
            return "✅ No security issues found."
        
        report = ["# Security Audit Report", f"Generated: {datetime.now().isoformat()}", ""]
        
        # Group by severity
        by_severity = {}
        for issue in issues:
            if issue.severity not in by_severity:
                by_severity[issue.severity] = []
            by_severity[issue.severity].append(issue)
        
        for severity in ['critical', 'high', 'medium', 'low']:
            if severity in by_severity:
                report.append(f"## {severity.upper()} ({len(by_severity[severity])})")
                for issue in by_severity[severity]:
                    location = f"{issue.file}"
                    if issue.line:
                        location += f":{issue.line}"
                    report.append(f"- **{location}**: {issue.description}")
                report.append("")
        
        report.append(f"Total issues: {len(issues)}")
        
        return "\n".join(report)


# ============================================================================
# Slippage Tolerance Check
# ============================================================================

class SlippageChecker:
    """
    Slippage tolerance validation for order execution.
    
    Rejects orders if executed price deviates beyond tolerance.
    """
    
    def __init__(
        self,
        default_tolerance_bps: int = 50,  # 0.5%
        strict_mode: bool = True,
    ):
        self.default_tolerance_bps = default_tolerance_bps
        self.strict_mode = strict_mode
        self._rejected_orders: List[Dict[str, Any]] = []
    
    def check(
        self,
        expected_price: float,
        executed_price: float,
        tolerance_bps: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Check if slippage is within tolerance.
        
        Args:
            expected_price: Price at time of order
            executed_price: Actual execution price
            tolerance_bps: Override tolerance in basis points
            
        Returns:
            Dict with 'passed', 'slippage_bps', and 'message'
        """
        tolerance = tolerance_bps or self.default_tolerance_bps
        
        if expected_price <= 0:
            return {
                "passed": False,
                "slippage_bps": 0,
                "message": "Invalid expected price",
            }
        
        slippage = abs(executed_price - expected_price) / expected_price
        slippage_bps = int(slippage * 10000)
        
        passed = slippage_bps <= tolerance
        
        if not passed:
            self._rejected_orders.append({
                "expected": expected_price,
                "executed": executed_price,
                "slippage_bps": slippage_bps,
                "tolerance_bps": tolerance,
                "timestamp": time.time(),
            })
        
        return {
            "passed": passed,
            "slippage_bps": slippage_bps,
            "tolerance_bps": tolerance,
            "message": "OK" if passed else f"Slippage {slippage_bps} bps exceeds tolerance {tolerance} bps",
        }
    
    def get_rejected_orders(self) -> List[Dict[str, Any]]:
        """Get list of rejected orders due to slippage."""
        return self._rejected_orders


# ============================================================================
# Demo
# ============================================================================

if __name__ == "__main__":
    print("=== Security Hardening Demo ===\n")
    
    # 1. Secure Key Manager
    print("1. Secure Key Manager")
    print("-" * 40)
    
    manager = SecureKeyManager(Path("/tmp/test_keys.json"))
    
    # Store a key
    success = manager.store_key(
        "binance_api",
        "sk_test_1234567890abcdef",
        password="my_secure_password",
        ip_whitelist=["127.0.0.1"],
    )
    print(f"  Store key: {'✓' if success else '✗'}")
    
    # Retrieve key
    retrieved = manager.get_key("binance_api", "my_secure_password", client_ip="127.0.0.1")
    print(f"  Retrieve key: {retrieved[:10]}..." if retrieved else "  Retrieve key: FAILED")
    
    # Try with wrong IP
    blocked = manager.get_key("binance_api", "my_secure_password", client_ip="192.168.1.1")
    print(f"  Wrong IP blocked: {'✓' if blocked is None else '✗'}")
    
    # List keys
    keys = manager.list_keys()
    print(f"  Stored keys: {len(keys)}")
    
    # 2. Security Auditor
    print("\n2. Security Auditor")
    print("-" * 40)
    
    auditor = SecurityAuditor()
    
    # Create a test file with a "secret"
    test_file = Path("/tmp/test_secret.py")
    test_file.write_text("""
    # This is a test file
    API_KEY = "sk-1234567890abcdefghijklmnopqrstuv"  # Bad! secret-scan:ignore
    password = "example_password"  # Detected but filtered
    """)
    
    issues = auditor.scan_file(test_file)
    print(f"  Issues found: {len(issues)}")
    for issue in issues:
        print(f"    - {issue.severity}: {issue.description}")
    
    # Generate report
    report = auditor.generate_report(issues)
    print(f"\n  Report preview: {report[:100]}...")
    
    # Cleanup
    test_file.unlink()
    
    # 3. Slippage Checker
    print("\n3. Slippage Checker")
    print("-" * 40)
    
    checker = SlippageChecker(default_tolerance_bps=50)
    
    # Good execution
    result = checker.check(expected_price=100.0, executed_price=100.3)
    print(f"  100.0 → 100.3: {result['message']} ({result['slippage_bps']} bps)")
    
    # Bad execution
    result = checker.check(expected_price=100.0, executed_price=101.0)
    print(f"  100.0 → 101.0: {result['message']} ({result['slippage_bps']} bps)")
    
    rejected = checker.get_rejected_orders()
    print(f"  Rejected orders: {len(rejected)}")
    
    print("\n✓ Security hardening module ready")
    print("  For better encryption: pip install cryptography")
