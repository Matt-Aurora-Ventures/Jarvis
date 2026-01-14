# JARVIS Security Guidelines

Comprehensive security guidelines for developing and operating JARVIS safely.

---

## Table of Contents

1. [Security Principles](#security-principles)
2. [Secret Management](#secret-management)
3. [Authentication & Authorization](#authentication--authorization)
4. [Input Validation](#input-validation)
5. [API Security](#api-security)
6. [Treasury Security](#treasury-security)
7. [Bot Security](#bot-security)
8. [Data Protection](#data-protection)
9. [Logging & Monitoring](#logging--monitoring)
10. [Incident Response](#incident-response)

---

## Security Principles

### Defense in Depth
- Multiple layers of security controls
- No single point of failure
- Assume any layer can be bypassed

### Least Privilege
- Minimum necessary permissions
- Time-limited access
- Regular access reviews

### Secure by Default
- Deny by default, allow by exception
- Secure configuration out of the box
- No default passwords

---

## Secret Management

### Environment Variables

```python
# GOOD: Load from environment
import os
api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    raise ValueError("ANTHROPIC_API_KEY not set")

# BAD: Hardcoded secrets
api_key = "sk-ant-..."  # NEVER DO THIS
```

### Required Environment Variables

| Variable | Description | Security Level |
|----------|-------------|----------------|
| `ANTHROPIC_API_KEY` | LLM provider key | HIGH |
| `OPENAI_API_KEY` | Fallback LLM key | HIGH |
| `TELEGRAM_BOT_TOKEN` | Telegram bot auth | HIGH |
| `TWITTER_BEARER_TOKEN` | Twitter API auth | HIGH |
| `SOLANA_PRIVATE_KEY` | Treasury wallet key | CRITICAL |
| `DATABASE_URL` | Database connection | HIGH |
| `ENCRYPTION_KEY` | Data encryption key | CRITICAL |

### Encrypted Storage

For highly sensitive data, use encrypted storage:

```python
from core.security.encrypted_storage import EncryptedStorage

storage = EncryptedStorage()

# Store encrypted
storage.store("wallet_key", private_key)

# Retrieve decrypted
key = storage.get("wallet_key")
```

### Secret Rotation

- Rotate API keys every 90 days
- Rotate encryption keys annually
- Immediate rotation on suspected compromise
- Document rotation procedures

---

## Authentication & Authorization

### API Authentication

```python
from fastapi import Depends, HTTPException
from core.security import verify_api_key

@app.get("/api/v1/protected")
async def protected_endpoint(
    api_key: str = Depends(verify_api_key)
):
    # Only authenticated requests reach here
    pass
```

### Role-Based Access Control

```python
from core.security.rbac import require_role, Role

@require_role(Role.ADMIN)
async def admin_only_action():
    pass

@require_role(Role.TRADER)
async def trading_action():
    pass
```

### Permission Levels

| Role | Permissions |
|------|-------------|
| `VIEWER` | Read public data only |
| `USER` | Basic bot commands |
| `TRADER` | Trading operations |
| `ADMIN` | Full system access |
| `OWNER` | Treasury operations |

### Session Management

- Session timeout: 24 hours max
- Idle timeout: 1 hour
- Secure session tokens (256-bit)
- HTTP-only, secure cookies

---

## Input Validation

### Always Validate External Input

```python
from core.validation import (
    validate_solana_address,
    validate_telegram_user_id,
    sanitize_user_input
)

# Validate addresses
if not validate_solana_address(wallet_address):
    raise ValueError("Invalid Solana address")

# Sanitize text input
safe_message = sanitize_user_input(user_message)

# Validate numeric ranges
if not 0 < amount <= MAX_TRADE_AMOUNT:
    raise ValueError(f"Amount must be between 0 and {MAX_TRADE_AMOUNT}")
```

### SQL Injection Prevention

```python
# GOOD: Parameterized queries
await db.execute(
    "SELECT * FROM users WHERE id = :user_id",
    {"user_id": user_id}
)

# BAD: String concatenation
await db.execute(f"SELECT * FROM users WHERE id = {user_id}")
```

### Command Injection Prevention

```python
# GOOD: Use subprocess with list arguments
import subprocess
result = subprocess.run(["git", "status"], capture_output=True)

# BAD: Shell=True with user input
subprocess.run(f"git {user_command}", shell=True)  # NEVER
```

---

## API Security

### Rate Limiting

```python
from core.api.rate_limit import rate_limit

@app.get("/api/v1/data")
@rate_limit(requests=100, window=60)  # 100 req/min
async def get_data():
    pass

@app.post("/api/v1/trade")
@rate_limit(requests=5, window=60)  # 5 req/min for trades
async def execute_trade():
    pass
```

### Request Validation

```python
from pydantic import BaseModel, validator

class TradeRequest(BaseModel):
    symbol: str
    amount: float
    side: str

    @validator('symbol')
    def validate_symbol(cls, v):
        if not v.isalnum() or len(v) > 20:
            raise ValueError('Invalid symbol')
        return v.upper()

    @validator('amount')
    def validate_amount(cls, v):
        if v <= 0 or v > 1000000:
            raise ValueError('Invalid amount')
        return v
```

### Response Security Headers

```python
# Applied automatically by middleware
{
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000",
    "Content-Security-Policy": "default-src 'self'"
}
```

---

## Treasury Security

### Critical Protections

The treasury module handles real funds. Extra protections required:

1. **Transaction Limits**
   ```python
   MAX_SINGLE_TRADE_USD = 1000
   MAX_DAILY_VOLUME_USD = 10000
   MAX_POSITION_SIZE_PERCENT = 10
   ```

2. **Multi-Signature (Future)**
   - Require multiple approvals for large transactions
   - Time-delayed execution for withdrawals

3. **Emergency Shutdown**
   ```python
   from core.security.emergency_shutdown import trigger_shutdown

   # Immediately halt all trading
   await trigger_shutdown(reason="Security alert")
   ```

4. **Wallet Security**
   - Private keys encrypted at rest
   - Never log wallet addresses with balances
   - Separate hot/cold wallets

### Trading Safeguards

```python
from core.treasury.risk import RiskManager

risk = RiskManager()

# Check before every trade
if not await risk.check_trade(trade_params):
    raise RiskLimitExceeded("Trade exceeds risk parameters")

# Automatic position limits
if await risk.get_exposure() > MAX_EXPOSURE:
    await risk.reduce_positions()
```

---

## Bot Security

### Admin-Only Commands

```python
from core.bot.auth import admin_only

@admin_only
async def handle_admin_command(update, context):
    # Only admins can reach here
    pass

# Admin users defined in environment
ADMIN_USER_IDS = os.getenv("ADMIN_USER_IDS", "").split(",")
```

### Rate Limiting Users

```python
from core.bot.rate_limiter import rate_limit

@rate_limit(limit_type="user_command")
async def handle_command(update, context):
    # Rate limited per user
    pass
```

### Input Sanitization

```python
def sanitize_command_input(text: str) -> str:
    """Sanitize user input from bot commands."""
    # Remove control characters
    text = ''.join(c for c in text if c.isprintable() or c.isspace())
    # Limit length
    text = text[:1000]
    # Strip leading/trailing whitespace
    return text.strip()
```

### Anti-Spam Measures

- Command cooldowns
- Message deduplication
- User reputation scoring
- Automatic temp bans for abuse

---

## Data Protection

### Sensitive Data Handling

```python
# Mask sensitive data in logs
def mask_sensitive(value: str, visible: int = 4) -> str:
    """Mask all but last N characters."""
    if len(value) <= visible:
        return "*" * len(value)
    return "*" * (len(value) - visible) + value[-visible:]

# Usage
logger.info(f"Processing wallet {mask_sensitive(wallet_address)}")
# Output: Processing wallet ****************************x4Kp
```

### PII Protection

- Minimize PII collection
- Encrypt PII at rest
- Hash user identifiers in logs
- Data retention limits

### Encryption Standards

| Data Type | Encryption | Key Size |
|-----------|------------|----------|
| API Keys | Fernet | 256-bit |
| Wallet Keys | Fernet + HSM | 256-bit |
| User Data | AES-GCM | 256-bit |
| Passwords | Argon2id | N/A |

---

## Logging & Monitoring

### Secure Logging

```python
import logging
from core.logging.secure import SecureLogger

logger = SecureLogger(__name__)

# Automatically redacts sensitive patterns
logger.info(f"Request from user {user_id}")  # OK
logger.info(f"Using key {api_key}")  # Auto-redacted
```

### Never Log

- Private keys
- API keys
- Passwords
- Full wallet addresses with balances
- Session tokens
- Personal information

### Audit Logging

```python
from core.audit import audit_log

@audit_log(action="trade_executed")
async def execute_trade(trade_params):
    # Automatically logged with timestamp, user, action
    pass
```

### Security Monitoring

Monitor for:
- Failed authentication attempts
- Rate limit violations
- Unusual trading patterns
- Error rate spikes
- Unauthorized access attempts

---

## Incident Response

### Severity Levels

| Level | Description | Response Time |
|-------|-------------|---------------|
| P1 | Active breach, funds at risk | Immediate |
| P2 | Security vulnerability found | 1 hour |
| P3 | Suspicious activity | 4 hours |
| P4 | Security improvement needed | 1 week |

### Immediate Response (P1)

1. **Contain**
   ```bash
   # Trigger emergency shutdown
   python -c "from core.security.emergency_shutdown import emergency_stop; emergency_stop()"
   ```

2. **Assess**
   - What was compromised?
   - Are funds at risk?
   - Is it ongoing?

3. **Remediate**
   - Rotate all compromised credentials
   - Block attack vectors
   - Restore from known good state

4. **Document**
   - Timeline of events
   - Actions taken
   - Lessons learned

### Contact Information

- Security Lead: [internal contact]
- On-call: [internal contact]
- Emergency: [internal contact]

---

## Security Checklist

### Before Deployment

- [ ] All secrets in environment variables
- [ ] No debug mode in production
- [ ] Rate limiting configured
- [ ] HTTPS enforced
- [ ] Logging configured (no secrets)
- [ ] Error pages don't leak info
- [ ] Dependencies scanned for vulnerabilities

### Regular Audits

- [ ] Monthly dependency updates
- [ ] Quarterly access review
- [ ] Annual security audit
- [ ] Penetration testing (annual)

---

## Vulnerability Reporting

Found a security issue? Please report responsibly:

1. **Do NOT** create a public GitHub issue
2. Email security concerns to [internal email]
3. Include:
   - Description of vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will respond within 48 hours.

---

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE/SANS Top 25](https://cwe.mitre.org/top25/)
- [Python Security Best Practices](https://python.org/dev/security/)
- [Solana Security Guidelines](https://docs.solana.com/security)
