"""API key authentication for FastAPI."""
import secrets
import hashlib
from typing import Optional, Dict, Set
from fastapi import Security, HTTPException, status, Depends
from fastapi.security import APIKeyHeader, APIKeyQuery
import logging

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
api_key_query = APIKeyQuery(name="api_key", auto_error=False)

_valid_keys: Dict[str, dict] = {}
_revoked_keys: Set[str] = set()


def hash_key(key: str) -> str:
    """Hash an API key for secure storage."""
    return hashlib.sha256(key.encode()).hexdigest()


def register_key(key: str, metadata: dict = None):
    """Register a valid API key."""
    key_hash = hash_key(key)
    _valid_keys[key_hash] = metadata or {}


def revoke_key(key: str):
    """Revoke an API key."""
    key_hash = hash_key(key)
    _revoked_keys.add(key_hash)
    _valid_keys.pop(key_hash, None)


def validate_key(key: str) -> Optional[dict]:
    """Validate an API key and return its metadata."""
    if not key:
        return None
    
    key_hash = hash_key(key)
    
    if key_hash in _revoked_keys:
        return None
    
    return _valid_keys.get(key_hash)


async def validate_api_key(
    header_key: str = Security(api_key_header),
    query_key: str = Security(api_key_query)
) -> str:
    """FastAPI dependency to validate API key from header or query param."""
    key = header_key or query_key
    
    if not key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide via X-API-Key header or api_key query param"
        )
    
    metadata = validate_key(key)
    if metadata is None:
        logger.warning(f"Invalid API key attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key"
        )
    
    return key


class APIKeyAuth:
    """API Key authentication manager."""
    
    def __init__(self):
        self.keys: Dict[str, dict] = {}
    
    def generate_key(self, name: str, scopes: list = None) -> str:
        """Generate a new API key."""
        key = secrets.token_urlsafe(32)
        key_hash = hash_key(key)
        
        self.keys[key_hash] = {
            "name": name,
            "scopes": scopes or ["read"],
            "created_at": __import__("time").time()
        }
        
        register_key(key, self.keys[key_hash])
        
        return key
    
    def validate(self, key: str) -> Optional[dict]:
        """Validate a key and return metadata."""
        return validate_key(key)
    
    def revoke(self, key: str):
        """Revoke a key."""
        revoke_key(key)
        key_hash = hash_key(key)
        self.keys.pop(key_hash, None)
    
    def has_scope(self, key: str, scope: str) -> bool:
        """Check if a key has a specific scope."""
        metadata = self.validate(key)
        if not metadata:
            return False
        return scope in metadata.get("scopes", [])
