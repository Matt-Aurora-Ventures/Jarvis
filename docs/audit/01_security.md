# Security & Authentication Improvements (1-15)

## 1. Add Rate Limiting Middleware to FastAPI

```python
# api/middleware/rate_limit.py
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from core.rate_limiter import get_rate_limiter

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        limiter = get_rate_limiter()
        client_ip = request.client.host
        allowed, wait_time = limiter.acquire("api_global", scope_key=client_ip)
        if not allowed:
            raise HTTPException(status_code=429, detail=f"Rate limit exceeded. Retry after {wait_time:.1f}s")
        return await call_next(request)
```

## 2. API Key Authentication

```python
# api/auth/api_key.py
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def validate_api_key(api_key: str = Security(api_key_header)) -> str:
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")
    # Validate against stored keys
    return api_key
```

## 3. JWT Token Refresh

```python
# api/routes/auth.py
@router.post("/refresh")
async def refresh_token(refresh_token: str):
    payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=["HS256"])
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")
    return {"access_token": create_access_token({"sub": payload.get("sub")})}
```

## 4. CSRF Protection

```python
# api/middleware/csrf.py
class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in ("POST", "PUT", "DELETE"):
            csrf_token = request.headers.get("X-CSRF-Token")
            if csrf_token != request.cookies.get("csrf_token"):
                raise HTTPException(status_code=403, detail="CSRF validation failed")
        return await call_next(request)
```

## 5. Input Sanitization

```python
# core/security/sanitizer.py
import html
def sanitize_string(value: str, max_length: int = 10000) -> str:
    return html.escape(value.replace('\x00', ''))[:max_length]
```

## 6. Secret Rotation

```python
# core/security/secret_rotation.py
class SecretRotationManager:
    def check_and_rotate(self, secret_name: str):
        metadata = self.vault.get(f"rotation:{secret_name}")
        if datetime.now() - metadata["last_rotation"] > timedelta(days=90):
            new_secret = self.rotation_handlers[secret_name]()
            self.vault.set(f"rotation:{secret_name}", {"last_rotation": datetime.now().isoformat()})
```

## 7. Wallet Address Validation

```python
# core/security/wallet_validation.py
import base58
def validate_solana_address(address: str) -> tuple[bool, str]:
    try:
        decoded = base58.b58decode(address)
        return (len(decoded) == 32, "Valid" if len(decoded) == 32 else "Invalid length")
    except Exception as e:
        return False, f"Invalid: {e}"
```

## 8. Request Signing

```python
# core/security/request_signing.py
import hmac, hashlib
class RequestSigner:
    def sign_request(self, method: str, path: str, body: dict, timestamp: int) -> str:
        canonical = f"{method}\n{path}\n{timestamp}\n{json.dumps(body, sort_keys=True)}"
        return f"{timestamp}.{hmac.new(self.secret_key, canonical.encode(), hashlib.sha256).hexdigest()}"
```

## 9. IP Allowlist for Admin

```python
# api/middleware/ip_allowlist.py
class IPAllowlistMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/admin"):
            if request.client.host not in self.allowed_ips:
                raise HTTPException(status_code=403, detail="Access denied")
        return await call_next(request)
```

## 10. Secure Session Management

```python
# core/security/session_manager.py
class SecureSessionManager:
    def create_session(self, user_id: str, ip_address: str) -> str:
        session_id = secrets.token_urlsafe(32)
        self.sessions[session_id] = Session(user_id=user_id, ip_address=ip_address)
        return session_id
```

## 11. Security Headers

```python
# api/middleware/security_headers.py
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        return response
```

## 12. Audit Trail

```python
# core/security/audit_trail.py
class AuditTrail:
    def log(self, event_type: str, actor_id: str, action: str, resource_id: str):
        event = {"timestamp": time.time(), "actor": actor_id, "action": action, "resource": resource_id}
        with open(self.log_path, "a") as f:
            f.write(json.dumps(event) + "\n")
```

## 13. Two-Factor Authentication

```python
# core/security/two_factor.py
import pyotp
class TwoFactorAuth:
    def setup_2fa(self, user_id: str) -> tuple[str, str]:
        secret = pyotp.random_base32()
        self.vault.set(f"2fa:{user_id}", {"secret": secret, "enabled": False})
        return secret, pyotp.TOTP(secret).provisioning_uri(user_id, issuer_name="Jarvis")
    
    def verify_2fa(self, user_id: str, code: str) -> bool:
        data = self.vault.get(f"2fa:{user_id}")
        return pyotp.TOTP(data["secret"]).verify(code, valid_window=1)
```

## 14. CSP Nonces

```python
# api/middleware/csp_nonce.py
class CSPNonceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        nonce = secrets.token_urlsafe(16)
        request.state.csp_nonce = nonce
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = f"script-src 'self' 'nonce-{nonce}'"
        return response
```

## 15. Sensitive Data Masking in Logs

```python
# core/logging/sensitive_filter.py
import re, logging
class SensitiveDataFilter(logging.Filter):
    PATTERNS = [(re.compile(r'(api_key.*?[:=]\s*["\']?)(\w{20,})'), r'\1***MASKED***')]
    def filter(self, record):
        for pattern, replacement in self.PATTERNS:
            record.msg = pattern.sub(replacement, str(record.msg))
        return True
```
