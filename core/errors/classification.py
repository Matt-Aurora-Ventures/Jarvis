"""Error classification system."""
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Type


class ErrorCategory(str, Enum):
    VALIDATION = "VAL"
    AUTHENTICATION = "AUTH"
    AUTHORIZATION = "AUTHZ"
    PROVIDER = "PROV"
    SYSTEM = "SYS"
    NETWORK = "NET"
    DATABASE = "DB"
    TRADING = "TRADE"
    RATE_LIMIT = "RATE"
    EXTERNAL = "EXT"


@dataclass
class ClassifiedError:
    code: str
    category: ErrorCategory
    message: str
    recoverable: bool
    retry_after: Optional[int] = None
    log_level: str = "error"


ERROR_DEFINITIONS = {
    "VAL_001": ClassifiedError("VAL_001", ErrorCategory.VALIDATION, "Invalid input", True, log_level="warning"),
    "VAL_002": ClassifiedError("VAL_002", ErrorCategory.VALIDATION, "Missing required field", True, log_level="warning"),
    "AUTH_001": ClassifiedError("AUTH_001", ErrorCategory.AUTHENTICATION, "Invalid credentials", True, log_level="warning"),
    "AUTH_002": ClassifiedError("AUTH_002", ErrorCategory.AUTHENTICATION, "Token expired", True, log_level="info"),
    "AUTHZ_001": ClassifiedError("AUTHZ_001", ErrorCategory.AUTHORIZATION, "Permission denied", False, log_level="warning"),
    "PROV_001": ClassifiedError("PROV_001", ErrorCategory.PROVIDER, "Provider unavailable", True, 30),
    "PROV_002": ClassifiedError("PROV_002", ErrorCategory.PROVIDER, "Provider rate limited", True, 60),
    "SYS_001": ClassifiedError("SYS_001", ErrorCategory.SYSTEM, "Internal error", False),
    "SYS_002": ClassifiedError("SYS_002", ErrorCategory.SYSTEM, "Resource not found", True, log_level="warning"),
    "NET_001": ClassifiedError("NET_001", ErrorCategory.NETWORK, "Connection failed", True, 5),
    "NET_002": ClassifiedError("NET_002", ErrorCategory.NETWORK, "Timeout", True, 10),
    "DB_001": ClassifiedError("DB_001", ErrorCategory.DATABASE, "Database error", True, 5),
    "TRADE_001": ClassifiedError("TRADE_001", ErrorCategory.TRADING, "Insufficient balance", True, log_level="warning"),
    "TRADE_002": ClassifiedError("TRADE_002", ErrorCategory.TRADING, "Invalid order", True, log_level="warning"),
    "RATE_001": ClassifiedError("RATE_001", ErrorCategory.RATE_LIMIT, "Rate limit exceeded", True, 60, log_level="warning"),
}


def classify_error(exception: Exception) -> ClassifiedError:
    """Classify an exception into a standard error."""
    from core.errors.exceptions import JarvisError
    
    if isinstance(exception, JarvisError):
        return ERROR_DEFINITIONS.get(exception.code, ERROR_DEFINITIONS["SYS_001"])
    
    exc_str = str(exception).lower()
    exc_type = type(exception).__name__.lower()
    
    if "timeout" in exc_str or "timed out" in exc_str:
        return ERROR_DEFINITIONS["NET_002"]
    if "connection" in exc_str or "refused" in exc_str:
        return ERROR_DEFINITIONS["NET_001"]
    if "authentication" in exc_str or "unauthorized" in exc_str:
        return ERROR_DEFINITIONS["AUTH_001"]
    if "permission" in exc_str or "forbidden" in exc_str:
        return ERROR_DEFINITIONS["AUTHZ_001"]
    if "rate limit" in exc_str or "too many" in exc_str:
        return ERROR_DEFINITIONS["RATE_001"]
    if "validation" in exc_str or "invalid" in exc_str:
        return ERROR_DEFINITIONS["VAL_001"]
    if "database" in exc_type or "sqlite" in exc_type:
        return ERROR_DEFINITIONS["DB_001"]
    
    return ERROR_DEFINITIONS["SYS_001"]


def get_error_code(code: str) -> Optional[ClassifiedError]:
    """Get error definition by code."""
    return ERROR_DEFINITIONS.get(code)
