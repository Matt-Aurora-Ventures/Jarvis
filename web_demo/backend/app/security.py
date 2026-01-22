"""
Security module implementing Burak Eregar's principles:
1. Treat every client as hostile
2. Enforce everything server-side
3. UI restrictions are not security
"""
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from functools import wraps

import bcrypt
import jwt
from fastapi import HTTPException, Security, status, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from slowapi import Limiter
from slowapi.util import get_remote_address
from pydantic import BaseModel, EmailStr, validator

from app.config import settings


# =============================================================================
# Rule #1: Treat Every Client as Hostile
# =============================================================================

class TokenPayload(BaseModel):
    """JWT token payload - NEVER trust client-provided values."""
    sub: str  # User ID (from database, not client)
    exp: datetime
    type: str  # "access" or "refresh"
    role: str  # "user" or "admin" (from database)
    iat: datetime
    jti: str  # Unique token ID for revocation


class UserRegistration(BaseModel):
    """User registration - validate ALL inputs."""
    email: EmailStr
    password: str
    username: str

    @validator("password")
    def validate_password(cls, v):
        """Enforce strong passwords."""
        if len(v) < settings.PASSWORD_MIN_LENGTH:
            raise ValueError(f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain digit")
        return v

    @validator("username")
    def validate_username(cls, v):
        """Sanitize username."""
        if len(v) < 3 or len(v) > 20:
            raise ValueError("Username must be 3-20 characters")
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username can only contain letters, numbers, - and _")
        return v.lower()


# =============================================================================
# Rule #2: Enforce Everything Server-Side
# =============================================================================

class PasswordHasher:
    """Secure password hashing using bcrypt."""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password with bcrypt (12 rounds)."""
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify password against hash."""
        try:
            return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
        except Exception:
            return False


class JWTHandler:
    """JWT token creation and validation - all server-side."""

    @staticmethod
    def create_access_token(user_id: str, role: str) -> str:
        """Create access token (short-lived)."""
        now = datetime.utcnow()
        payload = {
            "sub": user_id,
            "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
            "iat": now,
            "type": "access",
            "role": role,
            "jti": secrets.token_urlsafe(16),
        }
        return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

    @staticmethod
    def create_refresh_token(user_id: str, role: str) -> str:
        """Create refresh token (long-lived)."""
        now = datetime.utcnow()
        payload = {
            "sub": user_id,
            "exp": now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            "iat": now,
            "type": "refresh",
            "role": role,
            "jti": secrets.token_urlsafe(16),
        }
        return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

    @staticmethod
    def decode_token(token: str) -> Dict[str, Any]:
        """
        Decode and validate JWT token.
        Rule #1: Never trust the token - always verify signature.
        """
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_exp": True, "verify_iat": True},
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )


security_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme),
) -> Dict[str, Any]:
    """
    Get current user from JWT token.
    Rule #1: Always verify token server-side, never trust client.
    Rule #2: All authentication enforced here, not in frontend.
    """
    token = credentials.credentials
    payload = JWTHandler.decode_token(token)

    # Verify token type
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    return {
        "user_id": payload["sub"],
        "role": payload["role"],
        "jti": payload["jti"],
    }


async def get_current_admin(
    current_user: Dict[str, Any] = Security(get_current_user),
) -> Dict[str, Any]:
    """
    Verify user is admin.
    Rule #3: Backend enforces role, not frontend hiding of buttons.
    """
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


# =============================================================================
# Rate Limiting (Rule #2: Enforce server-side)
# =============================================================================

limiter = Limiter(key_func=get_remote_address)


def rate_limit(limit: str):
    """
    Rate limiting decorator.
    Rule #2: Enforce rate limits server-side, regardless of client behavior.
    """
    def decorator(func):
        @wraps(func)
        @limiter.limit(limit)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# =============================================================================
# Input Validation (Rule #1: Never trust client input)
# =============================================================================

def validate_solana_address(address: str) -> str:
    """
    Validate Solana address format.
    Rule #1: Client can send anything - we validate server-side.
    """
    if not address or not isinstance(address, str):
        raise ValueError("Invalid address format")

    # Solana addresses are base58 encoded, 32-44 characters
    if len(address) < 32 or len(address) > 44:
        raise ValueError("Invalid address length")

    # Check for valid base58 characters
    valid_chars = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
    if not all(c in valid_chars for c in address):
        raise ValueError("Invalid address characters")

    return address


def validate_amount(amount: float, min_amount: float = 0.0, max_amount: float = None) -> float:
    """
    Validate trading amount.
    Rule #1: Never trust client-provided amounts - validate and cap server-side.
    """
    if not isinstance(amount, (int, float)):
        raise ValueError("Amount must be a number")

    if amount <= min_amount:
        raise ValueError(f"Amount must be greater than {min_amount}")

    if max_amount and amount > max_amount:
        raise ValueError(f"Amount cannot exceed {max_amount}")

    # Check precision (max 9 decimals for SOL)
    if len(str(amount).split(".")[-1]) > 9:
        raise ValueError("Amount has too many decimal places")

    return float(amount)


def validate_percentage(percentage: float) -> float:
    """
    Validate percentage (0-100).
    Rule #1: Client could send any value - validate server-side.
    """
    if not isinstance(percentage, (int, float)):
        raise ValueError("Percentage must be a number")

    if percentage < 0 or percentage > 100:
        raise ValueError("Percentage must be between 0 and 100")

    return float(percentage)


def sanitize_string(text: str, max_length: int = 1000) -> str:
    """
    Sanitize user input strings.
    Rule #1: Assume client input is malicious - sanitize everything.
    """
    if not isinstance(text, str):
        raise ValueError("Input must be a string")

    # Trim whitespace
    text = text.strip()

    # Check length
    if len(text) > max_length:
        raise ValueError(f"Input too long (max {max_length} characters)")

    # Remove null bytes and control characters
    text = "".join(char for char in text if ord(char) >= 32 or char == "\n")

    return text


# =============================================================================
# Request Validation (Rule #2: Prevent replay attacks)
# =============================================================================

def verify_request_timestamp(timestamp: Optional[int], max_age_seconds: int = 300) -> None:
    """
    Verify request timestamp to prevent replay attacks.
    Rule #2: Assume requests can be replayed - validate timestamp.
    """
    if not timestamp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request timestamp required",
        )

    current_time = int(datetime.utcnow().timestamp())
    age = current_time - timestamp

    if age < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request timestamp is in the future",
        )

    if age > max_age_seconds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Request too old (max {max_age_seconds}s)",
        )


def generate_nonce() -> str:
    """Generate a unique nonce for request validation."""
    return secrets.token_urlsafe(32)


# =============================================================================
# CSRF Protection (Rule #2: Enforce server-side)
# =============================================================================

class CSRFProtection:
    """CSRF token validation for state-changing requests."""

    @staticmethod
    def generate_csrf_token() -> str:
        """Generate CSRF token."""
        return secrets.token_urlsafe(32)

    @staticmethod
    def verify_csrf_token(token: str, expected: str) -> None:
        """Verify CSRF token."""
        if not secrets.compare_digest(token, expected):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid CSRF token",
            )


# =============================================================================
# Security Headers Middleware (Rule #2: Enforce security policies)
# =============================================================================

async def add_security_headers(request: Request, call_next):
    """
    Add security headers to all responses.
    Rule #3: Security policies enforced by server, not client cooperation.
    """
    response = await call_next(request)

    if settings.ENABLE_SECURITY_HEADERS:
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # XSS protection
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Force HTTPS
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = (
                f"max-age={settings.HSTS_MAX_AGE}; includeSubDomains; preload"
            )

        # Content Security Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' https://api.mainnet-beta.solana.com https://quote-api.jup.ag; "
            "frame-ancestors 'none';"
        )

        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=()"
        )

    return response


# =============================================================================
# Ownership Verification (Rule #2: Check ownership server-side)
# =============================================================================

def verify_ownership(resource_owner_id: str, current_user_id: str) -> None:
    """
    Verify user owns the resource.
    Rule #2: Check ownership on every request - assume client can forge IDs.
    """
    if resource_owner_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource",
        )


def verify_admin_or_owner(resource_owner_id: str, current_user: Dict[str, Any]) -> None:
    """Verify user is admin or owns the resource."""
    if current_user["role"] != "admin" and resource_owner_id != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource",
        )


# =============================================================================
# Session Management
# =============================================================================

class SessionManager:
    """Manage user sessions in Redis."""

    def __init__(self, redis_client):
        self.redis = redis_client

    async def create_session(self, user_id: str, token_jti: str, metadata: Dict[str, Any]) -> None:
        """Create session in Redis."""
        session_key = f"session:{user_id}:{token_jti}"
        await self.redis.setex(
            session_key,
            settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            metadata,
        )

    async def revoke_session(self, user_id: str, token_jti: str) -> None:
        """Revoke session (logout)."""
        session_key = f"session:{user_id}:{token_jti}"
        await self.redis.delete(session_key)

    async def verify_session(self, user_id: str, token_jti: str) -> bool:
        """Verify session is still valid."""
        session_key = f"session:{user_id}:{token_jti}"
        return await self.redis.exists(session_key)


# Export public API
__all__ = [
    "TokenPayload",
    "UserRegistration",
    "PasswordHasher",
    "JWTHandler",
    "get_current_user",
    "get_current_admin",
    "limiter",
    "rate_limit",
    "validate_solana_address",
    "validate_amount",
    "validate_percentage",
    "sanitize_string",
    "verify_request_timestamp",
    "generate_nonce",
    "CSRFProtection",
    "add_security_headers",
    "verify_ownership",
    "verify_admin_or_owner",
    "SessionManager",
]
