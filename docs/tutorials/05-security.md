# Tutorial: Security Best Practices

Protect your trading operations and private keys.

## Overview

Security is critical for a trading platform. This tutorial covers:
1. Wallet security
2. API key management
3. Access control
4. Key rotation
5. Incident response

## Part 1: Wallet Security

### How JARVIS Protects Keys

JARVIS uses multiple layers of encryption:

1. **PBKDF2 Key Derivation**: Password converted to encryption key
   - 100,000 iterations
   - SHA256 hash
   - Unique salt per wallet

2. **Fernet Encryption**: AES-128-CBC encryption
   - Authenticated encryption
   - Prevents tampering

3. **Secure Storage**: Encrypted keys stored in SQLite
   - File permissions restricted
   - No plaintext keys ever stored

### Encryption Flow

```
Password → PBKDF2(100k iterations) → Encryption Key
Private Key + Encryption Key → Fernet Encrypt → Encrypted Blob
Encrypted Blob → Database Storage
```

### Best Practices

1. **Use Strong Passwords**
   - Minimum 12 characters
   - Mix of letters, numbers, symbols
   - Don't reuse passwords

2. **Backup Seed Phrases**
   - Write down offline
   - Store in secure location
   - Never share digitally

3. **Limit Wallet Funds**
   - Only keep trading capital in hot wallet
   - Main holdings in hardware wallet

4. **Regular Audits**
   - Review wallet activity weekly
   - Check for unauthorized transactions

## Part 2: API Key Management

### Environment Variables

Store all secrets in environment variables:

```bash
# .env file (NEVER commit this!)
TELEGRAM_BOT_TOKEN=your_token
GROQ_API_KEY=your_key
XAI_API_KEY=your_key
X_API_KEY=your_key
```

### .gitignore Rules

Ensure secrets are never committed:

```gitignore
# .gitignore
.env
.env.local
.env.*.local
*.key
*.pem
credentials.json
secrets/
```

### API Key Scoping

Use minimal permissions for each key:

| Key | Permissions | Scope |
|-----|-------------|-------|
| Telegram Bot | Read messages, send messages | Bot only |
| X/Twitter | Read, post | Single account |
| Groq/LLM | API calls | Read only |

### Detecting Leaked Keys

JARVIS scans for leaked secrets:

```
/admin security scan
```

**Response:**

```
SECURITY SCAN RESULTS

Checked: 150 files
Issues Found: 0

Patterns Checked:
- API keys
- Private keys
- Seed phrases
- Passwords
- Tokens

Status: CLEAN
```

## Part 3: Access Control

### User Roles

JARVIS has role-based access:

| Role | Capabilities |
|------|-------------|
| Admin | Full access, code execution, settings |
| Trader | Trading, portfolio, analysis |
| Viewer | Read-only, reports only |

### Admin Verification

Admin actions require verification:

```python
ADMIN_USER_ID = int(os.environ.get("JARVIS_ADMIN_USER_ID"))

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_USER_ID
```

### Dangerous Command Protection

Certain commands are restricted:

```
/execute - Admin only
/withdraw - Requires confirmation
/settings - Admin only
/restart - Admin only
```

### Session Management

- Sessions timeout after inactivity
- Re-authentication required for sensitive operations
- Concurrent session limits

## Part 4: Key Rotation

### When to Rotate Keys

Rotate keys when:
- Team member leaves
- Suspected compromise
- Regular schedule (quarterly)

### How to Rotate

1. **Telegram Bot Token**
   ```
   1. Go to @BotFather
   2. Select your bot
   3. /revoke
   4. /newbot (create new)
   5. Update .env with new token
   6. Restart JARVIS
   ```

2. **API Keys**
   ```
   1. Generate new key in provider dashboard
   2. Update .env
   3. Restart JARVIS
   4. Revoke old key
   ```

3. **Wallet Keys**
   ```
   1. Generate new wallet: /wallets generate
   2. Transfer funds to new wallet
   3. Delete old wallet: /wallets delete <address>
   ```

### Rotation Schedule

| Key Type | Rotation Frequency |
|----------|-------------------|
| Telegram Token | Quarterly |
| API Keys | Quarterly |
| Wallet Keys | Only if compromised |
| Admin Password | Monthly |

## Part 5: Audit Logging

### What's Logged

JARVIS logs all security-relevant events:

| Event | Details Logged |
|-------|----------------|
| Trade Execution | User, token, amount, timestamp |
| Login Attempt | User ID, success/failure |
| Admin Action | Command, parameters, result |
| Key Access | What key, who accessed |
| Error | Full stack trace, context |

### Log Location

```
logs/
  audit.jsonl           # Security audit trail
  trading.jsonl         # Trade records
  errors.jsonl          # Error events
```

### Log Format (JSONL)

```json
{"timestamp":"2026-01-18T10:30:00Z","event":"TRADE_EXECUTED","user_id":8527130908,"token":"SOL","amount":50.0,"status":"success"}
```

### Viewing Audit Logs

```
/admin logs audit 10
```

Shows last 10 audit events.

### Log Retention

| Log Type | Retention |
|----------|-----------|
| Audit | 7 years (regulatory) |
| Trading | 3 years |
| Errors | 1 year |
| General | 30 days |

## Part 6: Incident Response

### If You Suspect Compromise

1. **Immediate Actions**
   ```
   /admin killswitch on
   ```
   This stops all trading immediately.

2. **Rotate All Keys**
   - Change all API keys
   - Generate new Telegram token
   - Transfer funds to new wallets

3. **Review Logs**
   ```
   /admin logs audit 100
   ```
   Look for unauthorized actions.

4. **Assess Damage**
   - Check wallet balances
   - Review trade history
   - Check API usage

5. **Report**
   - Document the incident
   - Report to relevant parties
   - File reports if required

### Emergency Contacts

- **Security Issues**: security@jarvis.ai
- **Telegram Support**: @BotSupport
- **Provider Support**: Check provider docs

## Part 7: Security Checklist

### Daily

- [ ] Check system health: `/status`
- [ ] Review recent trades: `/history 10`
- [ ] Check for errors: `/admin logs errors 10`

### Weekly

- [ ] Review all positions: `/portfolio`
- [ ] Check wallet balances: `/balance`
- [ ] Review audit logs: `/admin logs audit 50`
- [ ] Verify no unauthorized access

### Monthly

- [ ] Rotate admin password
- [ ] Review user permissions
- [ ] Update dependencies: `pip install -r requirements.txt --upgrade`
- [ ] Backup database

### Quarterly

- [ ] Rotate API keys
- [ ] Rotate Telegram token
- [ ] Security audit
- [ ] Penetration testing (if applicable)

## Security Configuration

### Recommended Settings

```bash
# .env security settings

# Enable rate limiting
RATE_LIMIT_ENABLED=true

# Require trade confirmation
PUBLIC_BOT_REQUIRE_CONFIRMATION=true

# Set spending limits
MAX_TRADE_USD=100
MAX_DAILY_USD=500

# Enable audit logging
AUDIT_LOGGING_ENABLED=true

# Restrict admin access
JARVIS_ADMIN_USER_ID=your_telegram_id
```

## Summary

Key security principles:
1. **Encrypt everything** - Keys, passwords, sensitive data
2. **Least privilege** - Only grant necessary permissions
3. **Rotate regularly** - Change keys on schedule
4. **Log everything** - Full audit trail
5. **Respond quickly** - Have incident response plan

## Next Steps

- [Fee Structure](./06-revenue.md)
- [Security Guidelines](../SECURITY_GUIDELINES.md)
- [Incident Response](../SECURITY_INCIDENT_RESPONSE.md)

---

**Last Updated**: 2026-01-18
