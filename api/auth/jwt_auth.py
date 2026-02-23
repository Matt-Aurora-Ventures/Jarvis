"""JWT authentication for FastAPI."""
import os
import time
import jwt
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY environment variable is required")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

security = HTTPBearer(auto_error=False)


class TokenPayload(BaseModel):
    sub: str
    exp: int
    type: str
    scopes: list = []


def create_access_token(data: Dict[str, Any], expires_delta: timedelta = None) -> str:
    """Create a new access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    
    to_encode.update({
        "exp": int(expire.timestamp()),
        "type": "access",
        "iat": int(datetime.utcnow().timestamp())
    })
    
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create a new refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({
        "exp": int(expire.timestamp()),
        "type": "refresh",
        "iat": int(datetime.utcnow().timestamp())
    })
    
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str, expected_type: str = "access") -> Optional[TokenPayload]:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        if payload.get("type") != expected_type:
            logger.warning(f"Token type mismatch: expected {expected_type}, got {payload.get('type')}")
            return None
        
        return TokenPayload(**payload)
    
    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        return None


class JWTAuth:
    """JWT authentication handler."""
    
    def __init__(self, auto_error: bool = True):
        self.auto_error = auto_error
    
    async def __call__(
        self, 
        credentials: HTTPAuthorizationCredentials = Depends(security)
    ) -> Optional[TokenPayload]:
        if not credentials:
            if self.auto_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Missing authentication token",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            return None
        
        token = credentials.credentials
        payload = verify_token(token)
        
        if not payload:
            if self.auto_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            return None
        
        return payload
    
    def has_scope(self, payload: TokenPayload, scope: str) -> bool:
        """Check if token has required scope."""
        return scope in payload.scopes


def refresh_access_token(refresh_token: str) -> Dict[str, str]:
    """Exchange a refresh token for new access and refresh tokens."""
    payload = verify_token(refresh_token, expected_type="refresh")
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    new_access = create_access_token({"sub": payload.sub, "scopes": payload.scopes})
    new_refresh = create_refresh_token({"sub": payload.sub, "scopes": payload.scopes})
    
    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer"
    }


jwt_auth = JWTAuth()
jwt_auth_optional = JWTAuth(auto_error=False)
