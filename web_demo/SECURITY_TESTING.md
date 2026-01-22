# JARVIS Web Demo - Security Testing & Penetration Testing Guide

**Comprehensive security validation framework for production readiness.**

This guide covers all security testing requirements, including Solana-specific attack vectors.

---

## 🛡️ Table of Contents

1. [Pre-Deployment Security Checklist](#pre-deployment-security-checklist)
2. [Automated Security Tests](#automated-security-tests)
3. [Manual Security Tests](#manual-security-tests)
4. [Penetration Testing](#penetration-testing)
5. [Solana-Specific Security](#solana-specific-security)
6. [Web3 Wallet Security](#web3-wallet-security)
7. [API Security Testing](#api-security-testing)
8. [Infrastructure Security](#infrastructure-security)
9. [Continuous Security Monitoring](#continuous-security-monitoring)

---

## Pre-Deployment Security Checklist

### Critical Configuration

- [ ] **Secrets Management**
  - [ ] `SECRET_KEY` is 32+ characters random string
  - [ ] `JWT_SECRET` is 32+ characters random string
  - [ ] No secrets in source code or version control
  - [ ] Environment variables properly set
  - [ ] `.env` files in `.gitignore`

- [ ] **Production Settings**
  - [ ] `APP_ENV=production`
  - [ ] `DEBUG=False`
  - [ ] HTTPS enabled
  - [ ] HSTS enabled with 1-year max-age
  - [ ] Security headers enabled
  - [ ] CORS limited to production domain only

- [ ] **Database Security**
  - [ ] Strong database password (20+ chars)
  - [ ] Database not exposed to public internet
  - [ ] Regular backups configured
  - [ ] Connection pooling enabled
  - [ ] Prepared statements/ORM used (no raw SQL)

- [ ] **Wallet Security**
  - [ ] AES-256-GCM encryption enabled
  - [ ] Argon2 key derivation configured
  - [ ] Wallet files have 700 permissions
  - [ ] Master passwords never logged

- [ ] **API Security**
  - [ ] Rate limiting enabled
  - [ ] JWT tokens short-lived (15 min)
  - [ ] Refresh tokens properly secured
  - [ ] Input validation on all endpoints
  - [ ] CSRF protection enabled

---

## Automated Security Tests

### 1. Static Analysis

```bash
# Backend - Python Security
cd backend

# Bandit (security issues scanner)
pip install bandit
bandit -r app/ -f json -o security_report.json

# Safety (dependency vulnerabilities)
pip install safety
safety check --json

# Semgrep (security patterns)
pip install semgrep
semgrep --config auto app/
```

### 2. Dependency Scanning

```bash
# Backend dependencies
pip-audit

# Frontend dependencies
cd frontend
npm audit
npm audit fix
```

### 3. Secret Scanning

```bash
# TruffleHog (finds secrets in code/history)
docker run --rm -v $(pwd):/repo trufflesecurity/trufflehog \
  git file:///repo --json

# GitLeaks
docker run --rm -v $(pwd):/path zricethezav/gitleaks:latest \
  detect --source /path --verbose
```

### 4. Container Scanning

```bash
# Trivy (Docker image scanning)
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image jarvis-demo-backend:latest

docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image jarvis-demo-frontend:latest
```

### 5. SAST (Static Application Security Testing)

```bash
# SonarQube
docker run -d --name sonarqube -p 9000:9000 sonarqube:latest

# CodeQL (GitHub)
# Run via GitHub Actions or locally
```

---

## Manual Security Tests

### 1. Authentication Testing

#### Test Cases

**Test 1.1: Weak Password Rejection**
```bash
# Attempt registration with weak password
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@test.com", "password": "weak", "username": "test"}'

# Expected: 400 Bad Request with validation error
```

**Test 1.2: JWT Expiration**
```bash
# Get token
TOKEN=$(curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@test.com", "password": "ValidPass123!"}' \
  | jq -r '.access_token')

# Wait 16 minutes (token expires after 15)
sleep 960

# Try to use expired token
curl http://localhost:8000/api/wallet/balance \
  -H "Authorization: Bearer $TOKEN"

# Expected: 401 Unauthorized
```

**Test 1.3: Token Tampering**
```bash
# Get valid token and modify payload
TOKEN=$(curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@test.com", "password": "ValidPass123!"}' \
  | jq -r '.access_token')

# Manually modify JWT payload (change user_id or role)
TAMPERED_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.TAMPERED_PAYLOAD.signature"

curl http://localhost:8000/api/wallet/balance \
  -H "Authorization: Bearer $TAMPERED_TOKEN"

# Expected: 401 Unauthorized (signature verification fails)
```

### 2. Authorization Testing

**Test 2.1: Vertical Privilege Escalation**
```bash
# Login as regular user
USER_TOKEN=$(curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@test.com", "password": "ValidPass123!"}' \
  | jq -r '.access_token')

# Attempt admin endpoint
curl http://localhost:8000/api/admin/users \
  -H "Authorization: Bearer $USER_TOKEN"

# Expected: 403 Forbidden
```

**Test 2.2: Horizontal Privilege Escalation**
```bash
# User A creates position
POSITION_ID="123"

# User B attempts to access User A's position
curl http://localhost:8000/api/positions/$POSITION_ID \
  -H "Authorization: Bearer $USER_B_TOKEN"

# Expected: 403 Forbidden (ownership verification fails)
```

**Test 2.3: IDOR (Insecure Direct Object Reference)**
```bash
# Enumerate other users' resources
for ID in {1..100}; do
  curl -s http://localhost:8000/api/positions/$ID \
    -H "Authorization: Bearer $TOKEN" \
    | jq '.user_id'
done

# Expected: 403 Forbidden for all IDs not owned by user
```

### 3. Input Validation Testing

**Test 3.1: SQL Injection**
```bash
# Attempt SQL injection in token search
curl -X POST http://localhost:8000/api/trading/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "test\"; DROP TABLE users; --"}'

# Expected: 400 Bad Request (input validation blocks)
```

**Test 3.2: XSS (Cross-Site Scripting)**
```bash
# Attempt XSS in username
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "xss@test.com", "password": "ValidPass123!", "username": "<script>alert(1)</script>"}'

# Expected: 400 Bad Request (username validation blocks)
```

**Test 3.3: Path Traversal**
```bash
# Attempt directory traversal
curl http://localhost:8000/api/files?path=../../../etc/passwd \
  -H "Authorization: Bearer $TOKEN"

# Expected: 400 Bad Request or 404 Not Found
```

**Test 3.4: Command Injection**
```bash
# Attempt command injection in token address
curl -X POST http://localhost:8000/api/trading/analyze \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"address": "test; cat /etc/passwd"}'

# Expected: 400 Bad Request (address validation blocks)
```

### 4. Rate Limiting Testing

**Test 4.1: Authentication Rate Limit**
```bash
# Brute force login attempts
for i in {1..10}; do
  curl -X POST http://localhost:8000/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email": "test@test.com", "password": "wrong"}' \
    -w "\nStatus: %{http_code}\n"
  sleep 1
done

# Expected: 429 Too Many Requests after 5 attempts
```

**Test 4.2: Trading Rate Limit**
```bash
# Rapid trade attempts
for i in {1..10}; do
  curl -X POST http://localhost:8000/api/trading/buy \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"token_address": "...", "amount": 0.1}' \
    -w "\nStatus: %{http_code}\n"
done

# Expected: 429 Too Many Requests after 3 requests/minute
```

### 5. Session Management Testing

**Test 5.1: Session Fixation**
```bash
# Get session ID before login
SESSION_ID=$(curl -i http://localhost:8000/ | grep Set-Cookie | cut -d= -f2 | cut -d; -f1)

# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Cookie: session_id=$SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@test.com", "password": "ValidPass123!"}'

# Check if session ID changed
NEW_SESSION_ID=$(curl -i http://localhost:8000/api/wallet/balance \
  -H "Authorization: Bearer $TOKEN" | grep Set-Cookie | cut -d= -f2 | cut -d; -f1)

# Expected: Session ID should change after login
```

**Test 5.2: Concurrent Session Handling**
```bash
# Login from two different locations
TOKEN_1=$(curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@test.com", "password": "ValidPass123!"}' \
  | jq -r '.access_token')

TOKEN_2=$(curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@test.com", "password": "ValidPass123!"}' \
  | jq -r '.access_token')

# Both tokens should be valid (unless single session policy)
```

---

## Penetration Testing

### OWASP Top 10 Coverage

#### 1. Broken Access Control
- [ ] Test all admin endpoints without admin token
- [ ] Test accessing other users' resources
- [ ] Test modifying other users' positions
- [ ] Test wallet operations on other users' wallets
- [ ] Test bypassing authorization via parameter tampering

#### 2. Cryptographic Failures
- [ ] Test if wallet encryption is AES-256-GCM
- [ ] Test if passwords use bcrypt with 12+ rounds
- [ ] Test if JWTs use strong signing algorithm (HS256/RS256)
- [ ] Test if HTTPS is enforced
- [ ] Test if sensitive data is encrypted at rest

#### 3. Injection
- [ ] SQL injection in all input fields
- [ ] NoSQL injection (if using MongoDB)
- [ ] Command injection in system calls
- [ ] LDAP injection (if applicable)
- [ ] XPath injection (if using XML)

#### 4. Insecure Design
- [ ] Test business logic flaws (negative amounts, etc.)
- [ ] Test race conditions (double-spend attempts)
- [ ] Test transaction replay attacks
- [ ] Test time-based attacks (timestamp manipulation)

#### 5. Security Misconfiguration
- [ ] Check for debug mode in production
- [ ] Check for default credentials
- [ ] Check for unnecessary services running
- [ ] Check for verbose error messages
- [ ] Check for directory listing enabled

#### 6. Vulnerable Components
- [ ] Run dependency scanners
- [ ] Check for outdated libraries
- [ ] Check for known CVEs in dependencies

#### 7. Authentication Failures
- [ ] Brute force attacks
- [ ] Credential stuffing
- [ ] Session hijacking
- [ ] Weak password policy bypass

#### 8. Data Integrity Failures
- [ ] Test unsigned/unencrypted serialized data
- [ ] Test CI/CD pipeline security
- [ ] Test auto-update mechanisms

#### 9. Security Logging Failures
- [ ] Test if failed logins are logged
- [ ] Test if admin actions are logged
- [ ] Test if suspicious activity triggers alerts

#### 10. Server-Side Request Forgery (SSRF)
- [ ] Test if external URLs can be supplied
- [ ] Test access to internal services
- [ ] Test metadata endpoint access (AWS IMDSv2)

---

## Solana-Specific Security

### 1. Solana RPC Security

**Test 1.1: RPC URL Manipulation**
```bash
# Attempt to change RPC endpoint via client
# Client should NEVER be able to control RPC endpoint

# Expected: Server uses hardcoded RPC URL
```

**Test 1.2: Transaction Simulation Before Send**
```bash
# Server should simulate transactions before sending
# Test that failed simulations are caught

# Attempt a transaction that would fail
curl -X POST http://localhost:8000/api/trading/buy \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"token_address": "invalid", "amount": 100000}'

# Expected: 400 Bad Request (simulation fails before sending)
```

### 2. Transaction Security

**Test 2.1: Transaction Replay**
```bash
# Capture a valid transaction signature
TX_SIG="5iFe..."

# Attempt to replay the same transaction
curl -X POST http://localhost:8000/api/trading/confirm \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"signature": "$TX_SIG"}'

# Expected: Transaction fails (already confirmed) or server rejects replay
```

**Test 2.2: Front-Running Protection**
```bash
# Test that transactions use current market prices
# Not client-provided "expected prices"

# Attempt to specify old (better) price
curl -X POST http://localhost:8000/api/trading/buy \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"token_address": "...", "amount": 1.0, "expected_price": 0.0001}'

# Expected: Server fetches current price and ignores expected_price
```

**Test 2.3: Slippage Manipulation**
```bash
# Attempt to set extreme slippage
curl -X POST http://localhost:8000/api/trading/buy \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"token_address": "...", "amount": 1.0, "slippage": 50.0}'

# Expected: Server enforces MAX_SLIPPAGE_BPS (1%) and rejects
```

### 3. Wallet Security

**Test 3.1: Private Key Exposure**
```bash
# Check if private keys ever appear in logs
grep -r "private_key" logs/

# Check if private keys appear in error messages
curl -X POST http://localhost:8000/api/wallet/export \
  -H "Authorization: Bearer $TOKEN"

# Expected: Errors never expose private keys
```

**Test 3.2: Wallet Ownership Verification**
```bash
# User A creates wallet
WALLET_A="address123"

# User B attempts to export User A's wallet
curl -X POST http://localhost:8000/api/wallet/export \
  -H "Authorization: Bearer $USER_B_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"address": "$WALLET_A"}'

# Expected: 403 Forbidden
```

### 4. Jupiter DEX Integration Security

**Test 4.1: Route Manipulation**
```bash
# Attempt to provide custom swap route
curl -X POST http://localhost:8000/api/trading/buy \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"token_address": "...", "amount": 1.0, "custom_route": {...}}'

# Expected: Server ignores custom_route and fetches from Jupiter API
```

**Test 4.2: Amount Verification**
```bash
# Client says "buy 1 SOL", but sends transaction for 100 SOL
# Server should verify amounts before signing

# Expected: Transaction rejected (amount mismatch)
```

---

## Web3 Wallet Security

### 1. Wallet Adapter Security

**Test 1.1: Signature Verification**
```bash
# Test that server verifies wallet signatures
# Not just trusts client-provided wallet addresses

# Attempt to submit trade without wallet signature
curl -X POST http://localhost:8000/api/trading/buy \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"token_address": "...", "amount": 1.0, "wallet_address": "fake123"}'

# Expected: Server requires signature or uses backend wallet only
```

**Test 1.2: Message Signing**
```bash
# Test that login messages are signed by wallet
# And server verifies signature on-chain

# Expected: Server verifies ed25519 signature
```

### 2. Phantom Wallet Integration

**Test 2.1: XSS via Wallet Extension**
```bash
# Test if malicious scripts can interact with wallet
# Via XSS vulnerabilities

# Expected: CSP headers prevent inline scripts
```

**Test 2.2: Phishing Protection**
```bash
# Test that site displays correct domain when requesting signatures
# Phantom shows the domain - make sure it matches

# Expected: Domain verification in wallet popup
```

---

## API Security Testing

### 1. REST API Fuzzing

```bash
# Install Wfuzz
pip install wfuzz

# Fuzz API endpoints
wfuzz -c -z file,/usr/share/wordlists/dirb/common.txt \
  --hc 404 http://localhost:8000/api/FUZZ

# Fuzz parameters
wfuzz -c -z file,params.txt \
  -d "FUZZ=test" \
  --hc 400 \
  http://localhost:8000/api/trading/buy
```

### 2. GraphQL Security (if applicable)

```bash
# Introspection query
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{\n  __schema {\n    types {\n      name\n    }\n  }\n}"}'

# Expected: Introspection disabled in production
```

### 3. WebSocket Security (if applicable)

```bash
# Test WebSocket authentication
wscat -c ws://localhost:8000/ws

# Expected: Requires authentication token
```

---

## Infrastructure Security

### 1. Network Security

**Test 1.1: Port Scanning**
```bash
# Nmap scan
nmap -sV -sC -oA nmap_scan localhost

# Expected: Only ports 80, 443 open in production
```

**Test 1.2: SSL/TLS Configuration**
```bash
# Test SSL configuration
sslscan jarvislife.io

# Test for weak ciphers
testssl.sh jarvislife.io

# Expected: A+ rating, TLS 1.2+ only, strong ciphers
```

### 2. Docker Security

**Test 2.1: Container Breakout**
```bash
# Test if containers run as root
docker exec jarvis-demo-backend whoami

# Expected: Non-root user (jarvis)
```

**Test 2.2: Volume Permissions**
```bash
# Check volume permissions
docker exec jarvis-demo-backend ls -la /app/wallets

# Expected: 700 permissions, owned by non-root user
```

### 3. Database Security

**Test 3.1: Direct Database Access**
```bash
# Attempt to connect to database from internet
psql -h production-db-host -U jarvis -d jarvis_demo

# Expected: Connection refused (not exposed to internet)
```

**Test 3.2: SQL Injection via ORM**
```bash
# Test if ORM prevents SQL injection
# Even with dangerous input

# Expected: Prepared statements protect against injection
```

---

## Continuous Security Monitoring

### 1. Real-Time Monitoring

```yaml
# Prometheus alerts
groups:
  - name: security_alerts
    rules:
      - alert: HighFailedLoginRate
        expr: rate(failed_logins[5m]) > 10
        for: 5m
        annotations:
          summary: "High failed login rate detected"

      - alert: UnauthorizedAccessAttempt
        expr: rate(http_403_responses[5m]) > 20
        for: 5m
        annotations:
          summary: "Multiple unauthorized access attempts"

      - alert: SuspiciousTradeActivity
        expr: rate(trades[1m]) > 100
        for: 1m
        annotations:
          summary: "Unusual trade volume detected"
```

### 2. Log Monitoring

```bash
# Monitor for suspicious patterns
tail -f /var/log/jarvis-demo/access.log | grep -E '(admin|wallet|export|private)'

# Alert on specific patterns
tail -f /var/log/jarvis-demo/error.log | grep -E '(SQLAlchemy|Exception|Error)' \
  | while read line; do
    echo "ALERT: $line" | mail -s "Security Alert" security@jarvislife.io
done
```

### 3. Intrusion Detection

```bash
# Install Fail2ban
apt-get install fail2ban

# Configure for FastAPI
cat > /etc/fail2ban/filter.d/jarvis-demo.conf <<EOF
[Definition]
failregex = ^.*"POST /api/auth/login HTTP.*" 401.*$
ignoreregex =
EOF

# Enable jail
cat > /etc/fail2ban/jail.local <<EOF
[jarvis-demo]
enabled = true
port = http,https
filter = jarvis-demo
logpath = /var/log/jarvis-demo/access.log
maxretry = 5
bantime = 3600
EOF

systemctl restart fail2ban
```

---

## Security Testing Tools

### Recommended Tools

| Tool | Purpose | Usage |
|------|---------|-------|
| **OWASP ZAP** | Web app security scanner | `zap-cli quick-scan http://localhost:8000` |
| **Burp Suite** | Web vulnerability scanner | GUI-based testing |
| **Nuclei** | Vulnerability scanner | `nuclei -u http://localhost:8000` |
| **SQLMap** | SQL injection testing | `sqlmap -u "http://localhost:8000/api/..."` |
| **Wfuzz** | Web fuzzer | `wfuzz -c -z file,wordlist.txt ...` |
| **Nmap** | Network scanner | `nmap -sV localhost` |
| **Metasploit** | Penetration testing | `msfconsole` |
| **Nikto** | Web server scanner | `nikto -h localhost` |

---

## Security Testing Schedule

### Pre-Release (Before Production)
- [ ] Complete all automated tests
- [ ] Complete all manual tests
- [ ] Run penetration testing
- [ ] External security audit (if budget allows)
- [ ] Fix all Critical and High severity issues

### Post-Release (Production)
- **Daily**: Automated dependency scanning
- **Weekly**: Automated security scans (OWASP ZAP)
- **Monthly**: Manual penetration testing
- **Quarterly**: External security audit
- **Continuous**: Real-time monitoring and alerting

---

## Bug Bounty Program

Consider launching a bug bounty program:

```markdown
# Security Disclosure Policy

We take security seriously. If you discover a security vulnerability:

1. **Do NOT** disclose publicly
2. Email security@jarvislife.io with details
3. Allow 90 days for fix before public disclosure

## Rewards

- **Critical**: $1000 - $5000
- **High**: $500 - $1000
- **Medium**: $100 - $500
- **Low**: Recognition

## Scope

- Production app (jarvislife.io)
- API endpoints
- Wallet security
- Authentication/Authorization
- Data leaks

## Out of Scope

- Social engineering
- DDoS attacks
- Physical attacks
```

---

## Incident Response Plan

### 1. Detection
- Monitor alerts from security tools
- Review logs for suspicious activity
- User reports of security issues

### 2. Containment
- Isolate affected systems
- Revoke compromised credentials
- Block malicious IPs
- Disable compromised features

### 3. Investigation
- Identify attack vector
- Determine scope of breach
- Collect evidence

### 4. Remediation
- Fix vulnerability
- Deploy patches
- Restore from backups if needed

### 5. Recovery
- Verify fix effectiveness
- Re-enable services
- Monitor for repeat attacks

### 6. Post-Incident
- Document incident
- Update security measures
- Notify affected users (if required)
- Report to authorities (if required)

---

## Compliance & Standards

### Industry Standards
- **OWASP Top 10**: Full coverage
- **CWE Top 25**: Mitigations implemented
- **PCI DSS**: If handling payments
- **SOC 2 Type II**: If enterprise customers
- **ISO 27001**: Information security management

### Privacy Regulations
- **GDPR**: If EU users
- **CCPA**: If California users
- **Data Protection**: User data encryption, right to deletion

---

## Conclusion

Security is not a one-time task—it's an ongoing process. This guide should be:
- Executed before every production deployment
- Updated as new threats emerge
- Integrated into CI/CD pipeline
- Reviewed quarterly

**Remember**: The security of user funds depends on thorough testing and continuous vigilance.

---

**Last Updated**: 2026-01-22
**Next Review**: 2026-04-22
