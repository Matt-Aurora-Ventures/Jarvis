"""
Security validation middleware for AI and Bags API integrations.
Ensures safe operation with input validation, rate limiting, and monitoring.
"""
import re
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status
from pydantic import BaseModel, validator, Field
import logging

logger = logging.getLogger(__name__)


class TokenAnalysisRequest(BaseModel):
    """Validated request for token analysis."""
    token_address: str = Field(..., min_length=32, max_length=44)
    token_symbol: str = Field(..., min_length=1, max_length=10)
    market_data: Dict[str, Any]
    use_ai: bool = True

    @validator('token_address')
    def validate_solana_address(cls, v):
        """Validate Solana address format."""
        if not re.match(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$', v):
            raise ValueError('Invalid Solana address format')
        return v

    @validator('token_symbol')
    def validate_symbol(cls, v):
        """Validate token symbol."""
        if not re.match(r'^[A-Z0-9]+$', v):
            raise ValueError('Token symbol must be uppercase alphanumeric')
        return v

    @validator('market_data')
    def validate_market_data(cls, v):
        """Validate required market data fields."""
        required_fields = ['price', 'volume_24h', 'liquidity']
        missing = [f for f in required_fields if f not in v]
        if missing:
            raise ValueError(f'Missing required market data fields: {missing}')

        # Validate numeric fields
        for field in required_fields:
            if not isinstance(v[field], (int, float)) or v[field] < 0:
                raise ValueError(f'{field} must be a non-negative number')

        return v


class TradeOutcomeRequest(BaseModel):
    """Validated request for recording trade outcomes."""
    token_address: str = Field(..., min_length=32, max_length=44)
    token_symbol: str = Field(..., min_length=1, max_length=10)
    recommendation_id: str = Field(..., min_length=1, max_length=100)
    outcome: str = Field(..., regex='^(profit|loss|neutral)$')
    entry_price: float = Field(..., gt=0)
    exit_price: Optional[float] = Field(None, gt=0)
    profit_loss_percent: Optional[float] = None
    notes: Optional[str] = Field(None, max_length=500)

    @validator('token_address')
    def validate_solana_address(cls, v):
        if not re.match(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$', v):
            raise ValueError('Invalid Solana address format')
        return v


class SwapQuoteRequest(BaseModel):
    """Validated request for swap quotes."""
    input_mint: str = Field(..., min_length=32, max_length=44)
    output_mint: str = Field(..., min_length=32, max_length=44)
    amount: int = Field(..., gt=0)
    slippage_mode: str = Field(default='auto', regex='^(auto|fixed)$')
    slippage_bps: Optional[int] = Field(None, ge=1, le=10000)  # 0.01% to 100%

    @validator('input_mint', 'output_mint')
    def validate_solana_address(cls, v):
        if not re.match(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$', v):
            raise ValueError('Invalid Solana address format')
        return v

    @validator('amount')
    def validate_amount(cls, v):
        """Validate amount is within reasonable bounds."""
        MAX_AMOUNT = 10_000_000_000_000  # 10 trillion lamports (10,000 SOL)
        if v > MAX_AMOUNT:
            raise ValueError(f'Amount exceeds maximum allowed ({MAX_AMOUNT})')
        return v

    @validator('slippage_bps')
    def validate_slippage(cls, v, values):
        """Validate slippage when mode is fixed."""
        if values.get('slippage_mode') == 'fixed' and v is None:
            raise ValueError('slippage_bps required when slippage_mode is fixed')
        if v is not None and v > 1000:  # 10%
            logger.warning(f'High slippage detected: {v} bps ({v/100}%)')
        return v


class SwapTransactionRequest(BaseModel):
    """Validated request for creating swap transactions."""
    input_mint: str = Field(..., min_length=32, max_length=44)
    output_mint: str = Field(..., min_length=32, max_length=44)
    amount: int = Field(..., gt=0)
    slippage_bps: int = Field(..., ge=1, le=10000)
    user_public_key: str = Field(..., min_length=32, max_length=44)
    priority_fee: Optional[int] = Field(None, ge=0, le=10_000_000)  # Max 0.01 SOL

    @validator('input_mint', 'output_mint', 'user_public_key')
    def validate_solana_address(cls, v):
        if not re.match(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$', v):
            raise ValueError('Invalid Solana address format')
        return v


async def validate_bags_api_key(request: Request):
    """
    Validate that Bags API service has required credentials.
    Called on startup and before critical operations.
    """
    from app.config import settings

    if not settings.BAGS_API_KEY:
        logger.error("BAGS_API_KEY not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Trading service not configured"
        )

    # Don't log the actual key, just confirm it exists
    logger.info("Bags API key validated")


async def validate_ai_configuration(request: Request):
    """
    Validate AI service configuration.
    Ensures at least one AI provider is available.
    """
    from app.config import settings

    has_ollama = settings.OLLAMA_ENABLED and settings.OLLAMA_BASE_URL
    has_claude = settings.XAI_ENABLED and settings.XAI_API_KEY

    if not has_ollama and not has_claude:
        logger.warning("No AI provider configured - AI features will be limited")

    logger.info(f"AI providers available: Ollama={has_ollama}, Claude={has_claude}")


class SecurityMonitor:
    """
    Monitor and log security-relevant events.
    Helps detect abuse, attacks, or misconfigurations.
    """

    def __init__(self):
        self.failed_validations: Dict[str, int] = {}
        self.suspicious_patterns: Dict[str, int] = {}

    def log_validation_failure(self, endpoint: str, error: str, client_ip: str):
        """Log failed validation attempts."""
        key = f"{endpoint}:{client_ip}"
        self.failed_validations[key] = self.failed_validations.get(key, 0) + 1

        logger.warning(
            f"Validation failure: endpoint={endpoint}, error={error}, "
            f"client={client_ip}, count={self.failed_validations[key]}"
        )

        # Alert on repeated failures (possible attack)
        if self.failed_validations[key] >= 10:
            logger.error(
                f"SECURITY ALERT: {client_ip} has {self.failed_validations[key]} "
                f"validation failures on {endpoint}"
            )

    def log_suspicious_behavior(self, pattern: str, details: Dict[str, Any]):
        """Log suspicious patterns."""
        self.suspicious_patterns[pattern] = self.suspicious_patterns.get(pattern, 0) + 1
        logger.warning(f"Suspicious pattern detected: {pattern}, details={details}")

    def check_rate_abuse(self, client_ip: str, endpoint: str, request_count: int,
                        time_window: int) -> bool:
        """
        Check if client is abusing rate limits.

        Args:
            client_ip: Client IP address
            endpoint: API endpoint
            request_count: Number of requests in time window
            time_window: Time window in seconds

        Returns:
            True if abuse detected, False otherwise
        """
        # Conservative thresholds
        if endpoint.startswith('/api/v1/ai'):
            # AI endpoints: max 10 requests per minute
            threshold = 10 if time_window == 60 else (10 * time_window / 60)
        elif endpoint.startswith('/api/v1/bags'):
            # Trading endpoints: max 5 requests per minute
            threshold = 5 if time_window == 60 else (5 * time_window / 60)
        else:
            # Default: max 60 requests per minute
            threshold = 60 if time_window == 60 else (60 * time_window / 60)

        if request_count > threshold:
            logger.error(
                f"RATE ABUSE DETECTED: {client_ip} sent {request_count} requests "
                f"to {endpoint} in {time_window}s (threshold: {threshold})"
            )
            return True

        return False


# Global security monitor instance
security_monitor = SecurityMonitor()


def sanitize_error_message(error: Exception) -> str:
    """
    Sanitize error messages to prevent information leakage.

    Args:
        error: The original exception

    Returns:
        Safe error message for client
    """
    error_str = str(error).lower()

    # Don't leak file paths
    if 'file' in error_str or 'path' in error_str or '/' in error_str or '\\' in error_str:
        return "An internal error occurred"

    # Don't leak database info
    if 'database' in error_str or 'sql' in error_str or 'query' in error_str:
        return "A data processing error occurred"

    # Don't leak API keys or credentials
    if any(keyword in error_str for keyword in ['key', 'token', 'secret', 'password', 'credential']):
        return "A configuration error occurred"

    # Don't leak internal service details
    if any(keyword in error_str for keyword in ['ollama', 'anthropic', 'bags', 'redis', 'postgres']):
        return "A service communication error occurred"

    # Generic validation errors are OK to show
    if isinstance(error, ValueError):
        return str(error)

    # Default safe message
    return "An unexpected error occurred"


async def log_security_event(
    event_type: str,
    severity: str,
    details: Dict[str, Any],
    request: Optional[Request] = None
):
    """
    Log security-relevant events for monitoring and audit.

    Args:
        event_type: Type of security event (e.g., 'validation_failure', 'rate_limit')
        severity: Severity level ('info', 'warning', 'error', 'critical')
        details: Event details
        request: Optional FastAPI request object for context
    """
    event_data = {
        'type': event_type,
        'severity': severity,
        'details': details,
    }

    if request:
        event_data['client_ip'] = request.client.host
        event_data['endpoint'] = request.url.path
        event_data['method'] = request.method

    log_func = getattr(logger, severity, logger.info)
    log_func(f"Security event: {event_data}")
