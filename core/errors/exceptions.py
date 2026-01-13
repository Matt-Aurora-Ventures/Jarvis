"""Custom exception hierarchy."""
from typing import Optional, Dict, Any


class JarvisError(Exception):
    """Base exception for all Jarvis errors."""
    code: str = "SYS_001"
    status_code: int = 500
    
    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "details": self.details}


class ValidationError(JarvisError):
    """Input validation failed."""
    code = "VAL_001"
    status_code = 400


class AuthenticationError(JarvisError):
    """Authentication failed."""
    code = "AUTH_001"
    status_code = 401


class AuthorizationError(JarvisError):
    """Authorization/permission denied."""
    code = "AUTHZ_001"
    status_code = 403


class NotFoundError(JarvisError):
    """Resource not found."""
    code = "SYS_002"
    status_code = 404


class RateLimitError(JarvisError):
    """Rate limit exceeded."""
    code = "RATE_001"
    status_code = 429
    
    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(message, {"retry_after": retry_after})
        self.retry_after = retry_after


class ProviderError(JarvisError):
    """External provider/service error."""
    code = "PROV_001"
    status_code = 503
    
    def __init__(self, message: str, provider: str = None):
        super().__init__(message, {"provider": provider})
        self.provider = provider


class TradingError(JarvisError):
    """Trading operation error."""
    code = "TRADE_001"
    status_code = 400
    
    def __init__(self, message: str, symbol: str = None, order_id: str = None):
        super().__init__(message, {"symbol": symbol, "order_id": order_id})


class ConfigurationError(JarvisError):
    """Configuration error."""
    code = "CFG_001"
    status_code = 500


class DatabaseError(JarvisError):
    """Database operation error."""
    code = "DB_001"
    status_code = 500


class ExternalAPIError(JarvisError):
    """External API call failed."""
    code = "EXT_001"
    status_code = 502
