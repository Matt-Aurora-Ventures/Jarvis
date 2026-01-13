"""Request signing for secure API communication."""
import hmac
import hashlib
import time
import json
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class SignedRequest:
    signature: str
    timestamp: int
    nonce: str


class RequestSigner:
    """Sign and verify API requests."""
    
    def __init__(self, secret_key: bytes, tolerance_seconds: int = 300):
        if isinstance(secret_key, str):
            secret_key = secret_key.encode()
        self.secret_key = secret_key
        self.tolerance_seconds = tolerance_seconds
        self._used_nonces: Dict[str, int] = {}
    
    def sign_request(
        self, 
        method: str, 
        path: str, 
        body: Dict[str, Any] = None,
        timestamp: int = None,
        nonce: str = None
    ) -> str:
        """Sign a request and return the signature."""
        timestamp = timestamp or int(time.time())
        nonce = nonce or self._generate_nonce()
        
        canonical = self._create_canonical_string(method, path, body, timestamp, nonce)
        signature = hmac.new(self.secret_key, canonical.encode(), hashlib.sha256).hexdigest()
        
        return f"{timestamp}.{nonce}.{signature}"
    
    def verify_signature(
        self,
        signature: str,
        method: str,
        path: str,
        body: Dict[str, Any] = None
    ) -> Tuple[bool, str]:
        """Verify a request signature."""
        try:
            parts = signature.split('.')
            if len(parts) != 3:
                return False, "Invalid signature format"
            
            timestamp, nonce, sig = parts
            timestamp = int(timestamp)
            
            current_time = int(time.time())
            if abs(current_time - timestamp) > self.tolerance_seconds:
                return False, "Signature timestamp expired"
            
            if nonce in self._used_nonces:
                if self._used_nonces[nonce] > current_time - self.tolerance_seconds:
                    return False, "Nonce already used"
            
            expected_sig = self.sign_request(method, path, body, timestamp, nonce)
            expected_parts = expected_sig.split('.')
            
            if not hmac.compare_digest(sig, expected_parts[2]):
                return False, "Signature mismatch"
            
            self._used_nonces[nonce] = current_time
            self._cleanup_nonces()
            
            return True, "Valid signature"
        
        except Exception as e:
            return False, f"Verification error: {e}"
    
    def _create_canonical_string(
        self,
        method: str,
        path: str,
        body: Dict[str, Any],
        timestamp: int,
        nonce: str
    ) -> str:
        """Create canonical string for signing."""
        body_str = json.dumps(body, sort_keys=True, separators=(',', ':')) if body else ""
        return f"{method.upper()}\n{path}\n{timestamp}\n{nonce}\n{body_str}"
    
    def _generate_nonce(self) -> str:
        """Generate a unique nonce."""
        import secrets
        return secrets.token_hex(16)
    
    def _cleanup_nonces(self):
        """Remove expired nonces."""
        current_time = int(time.time())
        cutoff = current_time - self.tolerance_seconds
        self._used_nonces = {k: v for k, v in self._used_nonces.items() if v > cutoff}


class RequestSigningMiddleware:
    """FastAPI middleware for request signing."""
    
    def __init__(self, signer: RequestSigner, exempt_paths: list = None):
        self.signer = signer
        self.exempt_paths = exempt_paths or ["/api/health", "/api/docs"]
    
    async def verify_request(self, request) -> Tuple[bool, str]:
        """Verify an incoming request."""
        if request.url.path in self.exempt_paths:
            return True, "Exempt path"
        
        signature = request.headers.get("X-Signature")
        if not signature:
            return False, "Missing signature header"
        
        body = None
        if request.method in ("POST", "PUT", "PATCH"):
            try:
                body = await request.json()
            except Exception:
                body = None
        
        return self.signer.verify_signature(
            signature,
            request.method,
            request.url.path,
            body
        )
