# Security Features - JARVIS Web Demo

This document outlines the security measures implemented to protect the AI and trading integrations.

## Overview

The web demo implements defense-in-depth security across multiple layers:

1. **Input Validation** - All user inputs validated before processing
2. **Error Sanitization** - Internal errors never leaked to clients
3. **Rate Monitoring** - Detect and alert on abuse patterns
4. **Audit Logging** - All security events logged for review
5. **API Key Protection** - Credentials validated on startup and critical operations
6. **Data Privacy** - Sensitive data truncated in logs

## Input Validation

### Solana Address Validation
All Solana addresses (wallets, token mints) are validated against the Base58 format:
```
Pattern: ^[1-9A-HJ-NP-Za-km-z]{32,44}$
```

### Amount Validation
Trading amounts are validated to prevent:
- Zero or negative amounts
- Extremely large amounts (> 10,000 SOL worth)
- Invalid decimal values

### Slippage Validation
Slippage settings are validated to:
- Range: 0.01% to 100% (1 to 10,000 basis points)
- Warning logged for high slippage (> 10%)
- Required when using "fixed" slippage mode

### Token Symbol Validation
- Must be uppercase alphanumeric
- 1-10 characters
- Example: SOL, USDC, BONK

## Error Handling

### Error Sanitization
All errors are sanitized before being sent to clients to prevent information leakage:

**What's Hidden:**
- File paths and internal directories
- Database connection strings and queries
- API keys and credentials
- Internal service names (Ollama, Anthropic, Bags, Redis, Postgres)

**What's Shown:**
- Generic error categories (e.g., "A configuration error occurred")
- Validation errors (e.g., "Invalid Solana address format")
- User-actionable messages

**Implementation:**
```python
from app.middleware.security_validator import sanitize_error_message

try:
    # ... operation ...
except Exception as e:
    safe_message = sanitize_error_message(e)
    raise HTTPException(status_code=500, detail=safe_message)
```

## Security Monitoring

### SecurityMonitor Class
Tracks and alerts on suspicious activity:

**Validation Failures:**
- Logs all failed input validations
- Alerts when single client exceeds 10 failures
- Records client IP, endpoint, and error type

**Rate Abuse Detection:**
```python
# Conservative thresholds per minute:
AI endpoints:      10 requests/minute
Trading endpoints:  5 requests/minute
Other endpoints:   60 requests/minute
```

**Suspicious Patterns:**
- High slippage requests (> 10%)
- Repeated validation failures
- Unusual token addresses

### Security Event Logging

All security-relevant events are logged with structured data:

**Event Types:**
- `ai_analysis_success` - Successful AI token analysis
- `ai_analysis_error` - AI analysis failure
- `trade_outcome_recorded` - Trade outcome logged for learning
- `quote_success` - Swap quote generated
- `quote_error` - Quote generation failed
- `swap_created` - Swap transaction created
- `swap_error` - Swap creation failed

**Log Format:**
```json
{
  "type": "swap_created",
  "severity": "info",
  "details": {
    "user_wallet": "8aB7cD...",
    "input_mint": "So11111...",
    "output_mint": "EPjFWdd..."
  },
  "client_ip": "192.168.1.100",
  "endpoint": "/api/v1/bags/swap",
  "method": "POST",
  "timestamp": "2026-01-22T10:30:00Z"
}
```

## API Key Protection

### Bags API Key Validation
The Bags API key is validated:
- On application startup (via `validate_security_settings()`)
- Before each quote/swap operation (via `validate_bags_api_key()`)

**Security:**
- Key never logged (existence confirmed only)
- 503 Service Unavailable if key missing
- Generic error message: "Trading service not configured"

### AI Provider Configuration
AI providers (Ollama/Claude) are validated on first use:
- Checks if at least one provider is configured
- Warns if no AI providers available
- Continues with rule-based analysis as fallback

## Data Privacy

### Truncated Logging
Sensitive data is truncated in logs to prevent leakage:

**Token Addresses:**
```python
# Full address: So11111111111111111111111111111111111111112
# Logged as:    So11111...
request.input_mint[:8] + "..."
```

**Wallet Addresses:**
```python
# Full wallet: 8aBcDeFgHiJkLmNoPqRsTuVwXyZ123456789
# Logged as:   8aBcDeF...
request.user_public_key[:8] + "..."
```

### User ID Privacy
User IDs are logged for audit purposes but never exposed in error messages.

## Request Validation Models

### TokenAnalysisRequest
Validates AI analysis requests:
- Token address (Solana Base58)
- Token symbol (uppercase alphanumeric)
- Market data (non-negative numbers)

### SwapQuoteRequest
Validates swap quote requests:
- Input/output mints (Solana addresses)
- Amount (positive, reasonable bounds)
- Slippage mode (auto/fixed)
- Slippage BPS (1-10,000)

### SwapTransactionRequest
Validates swap transaction creation:
- Input/output mints (Solana addresses)
- Amount (positive, reasonable)
- User public key (Solana address)
- Priority fee (0-0.01 SOL max)

## Rate Limiting

Rate limiting is enforced server-side via the `RATE_LIMIT_*` settings in [`config.py`](backend/app/config.py:34-40):

```python
RATE_LIMIT_ENABLED: bool = True
RATE_LIMIT_PER_MINUTE: int = 60
RATE_LIMIT_READ_ENDPOINTS: int = 10
RATE_LIMIT_WRITE_ENDPOINTS: int = 5
RATE_LIMIT_TRADE_ENDPOINTS: int = 3
RATE_LIMIT_AUTH_ENDPOINTS: int = 5
```

**Enforcement:**
- Implemented via FastAPI middleware (TODO: add middleware)
- Per-IP address tracking
- 429 Too Many Requests response
- Logged for abuse monitoring

## CORS Security

CORS is strictly configured in production:

```python
# Development
CORS_ORIGINS: ["http://localhost:3000"]

# Production
CORS_ORIGINS: ["https://jarvislife.io"]
```

**Security Checks:**
- Localhost not allowed in production
- Only specific origins whitelisted
- Credentials allowed for authenticated requests

## Security Headers

Configured via [`config.py`](backend/app/config.py:92-94):

```python
ENABLE_SECURITY_HEADERS: bool = True
HSTS_MAX_AGE: int = 31536000  # 1 year
```

**Headers Added (TODO: implement middleware):**
- `Strict-Transport-Security`: Force HTTPS
- `X-Content-Type-Options`: Prevent MIME sniffing
- `X-Frame-Options`: Prevent clickjacking
- `X-XSS-Protection`: Enable XSS filtering
- `Content-Security-Policy`: Restrict resource loading

## Wallet Security

User wallets are never stored on the backend. All wallet operations follow the "sign on client" pattern:

1. Backend creates unsigned transaction
2. Frontend sends to user's wallet (Phantom, Solflare, etc.)
3. User reviews and signs in their wallet
4. Signed transaction sent to blockchain

**Your keys, your crypto** - we never touch them.

## Monitoring Best Practices

### Check Security Logs
```bash
# View security events
docker logs jarvis-demo-backend | grep "Security event"

# Filter by severity
docker logs jarvis-demo-backend | grep "severity.*error"

# Check validation failures
docker logs jarvis-demo-backend | grep "Validation failure"
```

### Monitor for Abuse
```bash
# Check rate abuse alerts
docker logs jarvis-demo-backend | grep "RATE ABUSE DETECTED"

# Check for repeated validation failures (attack indicator)
docker logs jarvis-demo-backend | grep "SECURITY ALERT"
```

### Audit Trail
All trading activity is logged to the supervisor bridge for cross-component monitoring:

```python
# Events published to supervisor
- quote_requested
- swap_initiated
- trade_outcome
- ai_recommendation
```

Query shared state for audit:
```bash
cat ~/.lifeos/shared_state/web_demo_state.json | jq '.events'
```

## Security Checklist

Before deploying to production:

- [ ] Set strong `SECRET_KEY` (32+ random characters)
- [ ] Set strong `JWT_SECRET` (32+ random characters, different from SECRET_KEY)
- [ ] Set `DEBUG=false` in production
- [ ] Remove localhost from `CORS_ORIGINS`
- [ ] Enable `HSTS` with 1 year max age
- [ ] Configure `BAGS_API_KEY` (production key)
- [ ] Use PostgreSQL (not SQLite) for database
- [ ] Enable SSL/TLS for all connections
- [ ] Set up log monitoring and alerts
- [ ] Review security logs weekly
- [ ] Test rate limiting
- [ ] Verify error messages don't leak info

## Vulnerability Reporting

If you discover a security vulnerability:

1. **DO NOT** create a public GitHub issue
2. Email: security@jarvislife.io (TODO: set up email)
3. Include:
   - Description of vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We'll respond within 48 hours and work with you to resolve the issue.

## Security Updates

This security system is continuously improved based on:
- Security audit findings
- Community feedback
- Emerging threat patterns
- Industry best practices

Last updated: 2026-01-22

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Solana Security Best Practices](https://docs.solana.com/developers)
- [Bags.fm Security](https://bags.fm/docs/security)
