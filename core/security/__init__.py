"""
JARVIS Security Framework

Comprehensive security auditing, key management, and protection systems.
"""

from .audit import (
    SecurityAuditor,
    AuditResult,
    SecurityCheck,
    AuditSeverity,
    run_security_audit,
)
from .key_vault import (
    KeyVault,
    SecureStorage,
    get_key_vault,
)
from .rate_limiter import (
    RateLimiter,
    check_rate_limit,
)
from .sanitizer import sanitize_string, sanitize_filename, sanitize_dict
from .session_manager import SecureSessionManager
from .two_factor import TwoFactorAuth
from .audit_trail import AuditTrail, AuditEventType
from .rbac import rbac, Permission, Role, User, require_permission, require_role
from .wallet_validation import validate_solana_address, validate_ethereum_address
from .request_signing import RequestSigner
from .sensitive_filter import SensitiveDataFilter

__all__ = [
    # Audit
    "SecurityAuditor",
    "AuditResult",
    "SecurityCheck",
    "AuditSeverity",
    "run_security_audit",
    # Key Vault
    "KeyVault",
    "SecureStorage",
    "get_key_vault",
    # Rate Limiting
    "RateLimiter",
    "check_rate_limit",
    # Sanitization
    "sanitize_string",
    "sanitize_filename",
    "sanitize_dict",
    # Session Management
    "SecureSessionManager",
    # 2FA
    "TwoFactorAuth",
    # Audit Trail
    "AuditTrail",
    "AuditEventType",
    # RBAC
    "rbac",
    "Permission",
    "Role",
    "User",
    "require_permission",
    "require_role",
    # Wallet Validation
    "validate_solana_address",
    "validate_ethereum_address",
    # Request Signing
    "RequestSigner",
    # Sensitive Data
    "SensitiveDataFilter",
    # Credential Loading
    "CredentialLoader",
    "get_credential_loader",
    "XCredentials",
    "TelegramCredentials",
]

# Credential loader (lazy import)
try:
    from .credential_loader import (
        CredentialLoader,
        get_credential_loader,
        XCredentials,
        TelegramCredentials,
    )
except ImportError:
    pass
