"""
Structured Error Code Catalog
Reliability Audit Item #18: Centralized error code system

Provides:
- Complete catalog of all error codes
- Consistent error responses across API
- Error categorization and grouping
- Lookup utilities
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Any
import json


class ErrorCategory(Enum):
    """Error category groupings"""
    SYSTEM = "SYS"       # Internal system errors
    VALIDATION = "VAL"   # Input validation errors
    AUTH = "AUTH"        # Authentication errors
    AUTHZ = "AUTHZ"      # Authorization errors
    RATE = "RATE"        # Rate limiting
    PROVIDER = "PROV"    # External provider errors
    TRADING = "TRADE"    # Trading operation errors
    CONFIG = "CFG"       # Configuration errors
    DATABASE = "DB"      # Database errors
    EXTERNAL = "EXT"     # External API errors
    BLOCKCHAIN = "CHAIN" # Blockchain/Solana errors
    WALLET = "WALLET"    # Wallet operation errors
    TREASURY = "TREAS"   # Treasury errors
    BOT = "BOT"          # Bot operation errors


@dataclass(frozen=True)
class ErrorCode:
    """Definition of an error code"""
    code: str
    category: ErrorCategory
    http_status: int
    message: str
    description: str
    recoverable: bool
    retry_hint: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "category": self.category.value,
            "http_status": self.http_status,
            "message": self.message,
            "description": self.description,
            "recoverable": self.recoverable,
            "retry_hint": self.retry_hint,
        }


# =============================================================================
# ERROR CODE CATALOG
# =============================================================================

ERROR_CATALOG: Dict[str, ErrorCode] = {}


def _register(code: ErrorCode):
    """Register an error code"""
    ERROR_CATALOG[code.code] = code
    return code


# -----------------------------------------------------------------------------
# SYSTEM ERRORS (SYS_xxx)
# -----------------------------------------------------------------------------

SYS_001 = _register(ErrorCode(
    code="SYS_001",
    category=ErrorCategory.SYSTEM,
    http_status=500,
    message="Internal server error",
    description="An unexpected internal error occurred",
    recoverable=False,
))

SYS_002 = _register(ErrorCode(
    code="SYS_002",
    category=ErrorCategory.SYSTEM,
    http_status=404,
    message="Resource not found",
    description="The requested resource does not exist",
    recoverable=False,
))

SYS_003 = _register(ErrorCode(
    code="SYS_003",
    category=ErrorCategory.SYSTEM,
    http_status=503,
    message="Service unavailable",
    description="The service is temporarily unavailable",
    recoverable=True,
    retry_hint="Retry after 30 seconds",
))

SYS_004 = _register(ErrorCode(
    code="SYS_004",
    category=ErrorCategory.SYSTEM,
    http_status=504,
    message="Operation timeout",
    description="The operation timed out before completion",
    recoverable=True,
    retry_hint="Retry with a longer timeout",
))

SYS_005 = _register(ErrorCode(
    code="SYS_005",
    category=ErrorCategory.SYSTEM,
    http_status=500,
    message="Kill switch active",
    description="System kill switch is engaged, operations halted",
    recoverable=False,
))

# -----------------------------------------------------------------------------
# VALIDATION ERRORS (VAL_xxx)
# -----------------------------------------------------------------------------

VAL_001 = _register(ErrorCode(
    code="VAL_001",
    category=ErrorCategory.VALIDATION,
    http_status=400,
    message="Invalid input",
    description="The request input failed validation",
    recoverable=False,
))

VAL_002 = _register(ErrorCode(
    code="VAL_002",
    category=ErrorCategory.VALIDATION,
    http_status=400,
    message="Missing required field",
    description="A required field is missing from the request",
    recoverable=False,
))

VAL_003 = _register(ErrorCode(
    code="VAL_003",
    category=ErrorCategory.VALIDATION,
    http_status=400,
    message="Invalid token address",
    description="The provided token address is not valid",
    recoverable=False,
))

VAL_004 = _register(ErrorCode(
    code="VAL_004",
    category=ErrorCategory.VALIDATION,
    http_status=400,
    message="Invalid amount",
    description="The amount specified is invalid or out of range",
    recoverable=False,
))

VAL_005 = _register(ErrorCode(
    code="VAL_005",
    category=ErrorCategory.VALIDATION,
    http_status=400,
    message="Invalid signature",
    description="The provided signature is invalid",
    recoverable=False,
))

# -----------------------------------------------------------------------------
# AUTHENTICATION ERRORS (AUTH_xxx)
# -----------------------------------------------------------------------------

AUTH_001 = _register(ErrorCode(
    code="AUTH_001",
    category=ErrorCategory.AUTH,
    http_status=401,
    message="Authentication required",
    description="This endpoint requires authentication",
    recoverable=False,
))

AUTH_002 = _register(ErrorCode(
    code="AUTH_002",
    category=ErrorCategory.AUTH,
    http_status=401,
    message="Invalid credentials",
    description="The provided credentials are invalid",
    recoverable=False,
))

AUTH_003 = _register(ErrorCode(
    code="AUTH_003",
    category=ErrorCategory.AUTH,
    http_status=401,
    message="Token expired",
    description="The authentication token has expired",
    recoverable=True,
    retry_hint="Refresh your authentication token",
))

AUTH_004 = _register(ErrorCode(
    code="AUTH_004",
    category=ErrorCategory.AUTH,
    http_status=401,
    message="Invalid API key",
    description="The API key is invalid or has been revoked",
    recoverable=False,
))

# -----------------------------------------------------------------------------
# AUTHORIZATION ERRORS (AUTHZ_xxx)
# -----------------------------------------------------------------------------

AUTHZ_001 = _register(ErrorCode(
    code="AUTHZ_001",
    category=ErrorCategory.AUTHZ,
    http_status=403,
    message="Permission denied",
    description="You do not have permission for this operation",
    recoverable=False,
))

AUTHZ_002 = _register(ErrorCode(
    code="AUTHZ_002",
    category=ErrorCategory.AUTHZ,
    http_status=403,
    message="Insufficient tier",
    description="This feature requires a higher subscription tier",
    recoverable=False,
))

AUTHZ_003 = _register(ErrorCode(
    code="AUTHZ_003",
    category=ErrorCategory.AUTHZ,
    http_status=403,
    message="IP not whitelisted",
    description="Your IP address is not in the whitelist",
    recoverable=False,
))

# -----------------------------------------------------------------------------
# RATE LIMITING ERRORS (RATE_xxx)
# -----------------------------------------------------------------------------

RATE_001 = _register(ErrorCode(
    code="RATE_001",
    category=ErrorCategory.RATE,
    http_status=429,
    message="Rate limit exceeded",
    description="Too many requests, please slow down",
    recoverable=True,
    retry_hint="Check Retry-After header for wait time",
))

RATE_002 = _register(ErrorCode(
    code="RATE_002",
    category=ErrorCategory.RATE,
    http_status=429,
    message="Daily quota exceeded",
    description="Daily request quota has been exceeded",
    recoverable=True,
    retry_hint="Quota resets at midnight UTC",
))

RATE_003 = _register(ErrorCode(
    code="RATE_003",
    category=ErrorCategory.RATE,
    http_status=429,
    message="Concurrent limit exceeded",
    description="Too many concurrent requests",
    recoverable=True,
    retry_hint="Wait for pending requests to complete",
))

# -----------------------------------------------------------------------------
# TRADING ERRORS (TRADE_xxx)
# -----------------------------------------------------------------------------

TRADE_001 = _register(ErrorCode(
    code="TRADE_001",
    category=ErrorCategory.TRADING,
    http_status=400,
    message="Trade rejected",
    description="The trade was rejected",
    recoverable=False,
))

TRADE_002 = _register(ErrorCode(
    code="TRADE_002",
    category=ErrorCategory.TRADING,
    http_status=400,
    message="Insufficient balance",
    description="Insufficient balance for this trade",
    recoverable=False,
))

TRADE_003 = _register(ErrorCode(
    code="TRADE_003",
    category=ErrorCategory.TRADING,
    http_status=400,
    message="Position limit exceeded",
    description="Maximum position limit reached",
    recoverable=False,
))

TRADE_004 = _register(ErrorCode(
    code="TRADE_004",
    category=ErrorCategory.TRADING,
    http_status=400,
    message="Trade size too small",
    description="Trade amount is below minimum threshold",
    recoverable=False,
))

TRADE_005 = _register(ErrorCode(
    code="TRADE_005",
    category=ErrorCategory.TRADING,
    http_status=400,
    message="Trade size too large",
    description="Trade amount exceeds maximum threshold",
    recoverable=False,
))

TRADE_006 = _register(ErrorCode(
    code="TRADE_006",
    category=ErrorCategory.TRADING,
    http_status=400,
    message="Slippage exceeded",
    description="Price slippage exceeded tolerance",
    recoverable=True,
    retry_hint="Retry with higher slippage tolerance",
))

TRADE_007 = _register(ErrorCode(
    code="TRADE_007",
    category=ErrorCategory.TRADING,
    http_status=400,
    message="Token not tradeable",
    description="The token cannot be traded at this time",
    recoverable=False,
))

TRADE_008 = _register(ErrorCode(
    code="TRADE_008",
    category=ErrorCategory.TRADING,
    http_status=409,
    message="Position already exists",
    description="A position already exists for this token",
    recoverable=False,
))

TRADE_009 = _register(ErrorCode(
    code="TRADE_009",
    category=ErrorCategory.TRADING,
    http_status=404,
    message="Position not found",
    description="No position found for this token",
    recoverable=False,
))

TRADE_010 = _register(ErrorCode(
    code="TRADE_010",
    category=ErrorCategory.TRADING,
    http_status=409,
    message="Token conflict",
    description="Another operation is in progress for this token",
    recoverable=True,
    retry_hint="Wait for the current operation to complete",
))

# -----------------------------------------------------------------------------
# BLOCKCHAIN ERRORS (CHAIN_xxx)
# -----------------------------------------------------------------------------

CHAIN_001 = _register(ErrorCode(
    code="CHAIN_001",
    category=ErrorCategory.BLOCKCHAIN,
    http_status=502,
    message="RPC error",
    description="Solana RPC node returned an error",
    recoverable=True,
    retry_hint="Retry or try a different RPC endpoint",
))

CHAIN_002 = _register(ErrorCode(
    code="CHAIN_002",
    category=ErrorCategory.BLOCKCHAIN,
    http_status=400,
    message="Transaction failed",
    description="The blockchain transaction failed",
    recoverable=False,
))

CHAIN_003 = _register(ErrorCode(
    code="CHAIN_003",
    category=ErrorCategory.BLOCKCHAIN,
    http_status=408,
    message="Transaction timeout",
    description="Transaction confirmation timed out",
    recoverable=True,
    retry_hint="Check transaction status before retrying",
))

CHAIN_004 = _register(ErrorCode(
    code="CHAIN_004",
    category=ErrorCategory.BLOCKCHAIN,
    http_status=400,
    message="Insufficient SOL for fees",
    description="Not enough SOL to pay transaction fees",
    recoverable=False,
))

CHAIN_005 = _register(ErrorCode(
    code="CHAIN_005",
    category=ErrorCategory.BLOCKCHAIN,
    http_status=502,
    message="Network congested",
    description="Blockchain network is congested",
    recoverable=True,
    retry_hint="Retry with higher priority fee",
))

# -----------------------------------------------------------------------------
# WALLET ERRORS (WALLET_xxx)
# -----------------------------------------------------------------------------

WALLET_001 = _register(ErrorCode(
    code="WALLET_001",
    category=ErrorCategory.WALLET,
    http_status=400,
    message="Invalid wallet address",
    description="The wallet address is not valid",
    recoverable=False,
))

WALLET_002 = _register(ErrorCode(
    code="WALLET_002",
    category=ErrorCategory.WALLET,
    http_status=500,
    message="Wallet signing failed",
    description="Failed to sign the transaction",
    recoverable=False,
))

WALLET_003 = _register(ErrorCode(
    code="WALLET_003",
    category=ErrorCategory.WALLET,
    http_status=500,
    message="Wallet not initialized",
    description="Wallet has not been initialized",
    recoverable=False,
))

# -----------------------------------------------------------------------------
# PROVIDER ERRORS (PROV_xxx)
# -----------------------------------------------------------------------------

PROV_001 = _register(ErrorCode(
    code="PROV_001",
    category=ErrorCategory.PROVIDER,
    http_status=503,
    message="Provider unavailable",
    description="External provider is unavailable",
    recoverable=True,
    retry_hint="Retry after 60 seconds",
))

PROV_002 = _register(ErrorCode(
    code="PROV_002",
    category=ErrorCategory.PROVIDER,
    http_status=502,
    message="Provider error",
    description="External provider returned an error",
    recoverable=True,
))

PROV_003 = _register(ErrorCode(
    code="PROV_003",
    category=ErrorCategory.PROVIDER,
    http_status=504,
    message="Provider timeout",
    description="External provider request timed out",
    recoverable=True,
    retry_hint="Retry with exponential backoff",
))

# -----------------------------------------------------------------------------
# BOT ERRORS (BOT_xxx)
# -----------------------------------------------------------------------------

BOT_001 = _register(ErrorCode(
    code="BOT_001",
    category=ErrorCategory.BOT,
    http_status=500,
    message="Bot not running",
    description="The requested bot is not currently running",
    recoverable=True,
))

BOT_002 = _register(ErrorCode(
    code="BOT_002",
    category=ErrorCategory.BOT,
    http_status=503,
    message="Bot disabled",
    description="The bot has been disabled",
    recoverable=False,
))

BOT_003 = _register(ErrorCode(
    code="BOT_003",
    category=ErrorCategory.BOT,
    http_status=429,
    message="Bot circuit breaker open",
    description="Bot circuit breaker is open due to errors",
    recoverable=True,
    retry_hint="Wait for circuit breaker to reset",
))


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_error(code: str) -> Optional[ErrorCode]:
    """Look up an error code"""
    return ERROR_CATALOG.get(code)


def get_errors_by_category(category: ErrorCategory) -> List[ErrorCode]:
    """Get all errors in a category"""
    return [e for e in ERROR_CATALOG.values() if e.category == category]


def get_recoverable_errors() -> List[ErrorCode]:
    """Get all recoverable errors"""
    return [e for e in ERROR_CATALOG.values() if e.recoverable]


def format_error_response(
    code: str,
    details: Dict[str, Any] = None,
    message_override: str = None,
) -> Dict[str, Any]:
    """
    Format a standardized error response.

    Returns dict suitable for JSON API response.
    """
    error = ERROR_CATALOG.get(code)
    if error is None:
        error = SYS_001

    response = {
        "error": {
            "code": error.code,
            "message": message_override or error.message,
            "description": error.description,
            "recoverable": error.recoverable,
        }
    }

    if error.retry_hint:
        response["error"]["retry_hint"] = error.retry_hint

    if details:
        response["error"]["details"] = details

    return response


def export_catalog() -> str:
    """Export full catalog as JSON"""
    return json.dumps(
        {code: err.to_dict() for code, err in ERROR_CATALOG.items()},
        indent=2,
    )


# =============================================================================
# ERROR COUNT
# =============================================================================

def get_catalog_summary() -> Dict[str, int]:
    """Get summary of error codes by category"""
    summary = {}
    for category in ErrorCategory:
        count = len(get_errors_by_category(category))
        if count > 0:
            summary[category.value] = count
    summary["total"] = len(ERROR_CATALOG)
    return summary
