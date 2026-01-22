"""
Bus Authentication Utilities

Provides HMAC-based authentication for the message bus.
"""
import hmac
import hashlib
import secrets
from typing import Optional


def generate_bus_key() -> str:
    """Generate a secure random key for bus authentication."""
    return secrets.token_hex(32)


def verify_hmac(message: bytes, signature: str, key: bytes) -> bool:
    """Verify HMAC signature for a message."""
    expected = hmac.new(key, message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def create_hmac(message: bytes, key: bytes) -> str:
    """Create HMAC signature for a message."""
    return hmac.new(key, message, hashlib.sha256).hexdigest()
