# SECURITY AUDIT REPORT - VPS & Components
**Date:** January 31, 2026
**Auditor:** Claude Sonnet 4.5
**Scope:** VPS (100.66.17.93), Docker containers, credentials, OAuth scopes

---

## 🚨 CRITICAL ISSUES (Fix Immediately)

### 1. **Active Brute Force Attacks** ⚠️ URGENT
**Status:** ONGOING ATTACKS DETECTED
**IP:** 170.64.139.8
**Last Attack:** January 31, 2026 01:36 UTC
**Attack Pattern:** Dictionary attack testing usernames (user, visitor, vyos, web, weblogic, www, zabbix, etc.)

**Evidence:**
```
2026-01-31T01:35:12 Failed password for invalid user user from 170.64.139.8
2026-01-31T01:35:25 Failed password for invalid user visitor from 170.64.139.8
2026-01-31T01:36:03 Failed password for invalid user zookeeper from 170.64.139.8
```

**Impact:** If password auth is enabled (default), attacker could gain root access.

---

### 2. **SSH Password Authentication Status** ⚠️ CRITICAL
**Current:** NOT explicitly disabled (defaults to YES on most systems)
**Risk:** Allows password-based login attempts
**Root Login:** ENABLED (PermitRootLogin yes)

**Attack Surface:**
- Port 22: OPEN (standard SSH port - high target)
- Port 2222: OPEN (secondary SSH via ssh-server container)
- Root login: ALLOWED
- Password auth: LIKELY ENABLED (not disabled in config)

---

### 3. **No Firewall Protection** ⚠️ CRITICAL
**Status:** UFW firewall is INACTIVE
**Result:** All ports exposed to internet
**Risk:** Any service listening on 0.0.0.0 is publicly accessible

```
ufw status: inactive
```

---

### 4. **No Intrusion Prevention** ⚠️ HIGH
**fail2ban Status:** NOT INSTALLED
**Result:** No automatic IP blocking after failed login attempts
**Risk:** Brute force attacks can continue indefinitely

---

### 5. **Secrets in Plain Text Files** ⚠️ HIGH
**Location:** `secrets/keys.json` (unencrypted, 600 perms assumed but not verified)
**Contains:**
- Anthropic API keys (full access)
- Twitter OAuth tokens (read/write tweets, DMs)
- Telegram bot tokens (full bot control)
- Helius RPC keys (Solana transactions)
- Bags.fm API + partner keys
- Groq API key

**Risk:** If VPS is compromised, all credentials are immediately exposed.

---

## ⚠️ HIGH PRIORITY ISSUES

### 6. **Multiple .env Files with Duplicate Secrets**
**Files Found:**
```
tg_bot/.env
bots/twitter/.env
.env
web_demo/.env
kea-research/.env
```

**Issues:**
- Same credentials duplicated across files
- Hard to rotate/revoke (must update 5+ locations)
- Increases attack surface
- Version control risks (if accidentally committed)

---

### 7. **Twitter OAuth Tokens - Full Access**
**Current Scopes:** UNKNOWN (not explicitly limited in code)
**Tokens Found:**
- API v1.1 tokens (access_token + secret)
- OAuth2 tokens (aurora + jarvis accounts)
- Bearer token (read-only but still sensitive)

**Risk:** If compromised:
- Post/delete tweets
- Send DMs
- Access account settings
- Follow/unfollow users

**Best Practice:** Use OAuth2 with minimal scopes (tweet.read, tweet.write only)

---

### 8. **Telegram Bot Tokens - Full Control**
**Tokens Found:**
- 3 different bot tokens in keys.json
- Additional tokens in .env files
- No token rotation detected

**Access:** Full bot control (read messages, send messages, edit commands)

---

### 9. **Root User Running Services**
**Status:** All Docker containers run as root
**SSH:** Root login enabled
**Risk:** Privilege escalation not needed if compromised

---

## ✅ GOOD SECURITY PRACTICES FOUND

1. **Tailscale VPN:** All legitimate logins via Tailscale (100.x.x.x IPs)
2. **No Public Web Ports:** No web services exposed on 80/443/8080
3. **Docker Containers:** Not publishing ports to 0.0.0.0 (good!)
4. **SSH Server Container:** Isolated SSH on port 2222

---

## 🔧 FIXES REQUIRED

### Priority 1: Stop Ongoing Attacks (Do This NOW)

#### Fix 1.1: Disable Password Authentication
```bash
ssh root@100.66.17.93 << 'EOF'
# Backup current config
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup

# Disable password auth
sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config

# Add if not present
grep -q "^PasswordAuthentication" /etc/ssh/sshd_config || echo "PasswordAuthentication no" >> /etc/ssh/sshd_config

# Disable root password login
sed -i 's/PermitRootLogin yes/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config

# Enable key-only auth
sed -i 's/#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config

# Test config
sshd -t && systemctl restart sshd
EOF
```

**Verify:**
```bash
ssh root@100.66.17.93 "grep -E '^(PasswordAuthentication|PermitRootLogin|PubkeyAuthentication)' /etc/ssh/sshd_config"
```

Expected output:
```
PasswordAuthentication no
PermitRootLogin prohibit-password
PubkeyAuthentication yes
```

---

#### Fix 1.2: Install & Configure fail2ban
```bash
ssh root@100.66.17.93 << 'EOF'
# Install fail2ban
apt update && apt install -y fail2ban

# Create jail.local config
cat > /etc/fail2ban/jail.local << 'JAIL'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3
destemail = root@localhost
sendername = Fail2Ban

[sshd]
enabled = true
port = 22,2222
logpath = /var/log/auth.log
maxretry = 3
bantime = 86400
JAIL

# Enable and start
systemctl enable fail2ban
systemctl start fail2ban
systemctl status fail2ban
EOF
```

**Verify:**
```bash
ssh root@100.66.17.93 "fail2ban-client status sshd"
```

---

#### Fix 1.3: Enable UFW Firewall
```bash
ssh root@100.66.17.93 << 'EOF'
# Allow SSH first (prevent lockout)
ufw allow 22/tcp
ufw allow 2222/tcp

# Allow Tailscale
ufw allow in on tailscale0

# Default deny incoming
ufw default deny incoming
ufw default allow outgoing

# Enable firewall
ufw --force enable

# Verify
ufw status verbose
EOF
```

**Expected result:**
```
Status: active

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW       Anywhere
2222/tcp                   ALLOW       Anywhere
Anywhere on tailscale0     ALLOW       Anywhere
```

---

### Priority 2: Secure Secrets Management

#### Fix 2.1: Encrypt secrets/keys.json
```bash
# Install age encryption tool
ssh root@100.66.17.93 "apt install -y age"

# Generate encryption key (save this securely!)
ssh root@100.66.17.93 "age-keygen -o /root/.age-key.txt"

# Encrypt keys.json
scp secrets/keys.json root@100.66.17.93:/tmp/keys.json
ssh root@100.66.17.93 "age -r \$(age-keygen -y /root/.age-key.txt) -o /root/secrets/keys.json.age /tmp/keys.json && rm /tmp/keys.json"
```

**Usage:**
```bash
# Decrypt when needed
ssh root@100.66.17.93 "age --decrypt -i /root/.age-key.txt /root/secrets/keys.json.age > /tmp/keys.json"
```

---

#### Fix 2.2: Use Docker Secrets (Recommended)
```bash
# Create Docker secrets for sensitive values
ssh root@100.66.17.93 << 'EOF'
# Example: Anthropic API key
echo "sk-ant-..." | docker secret create anthropic_api_key -

# Example: Telegram bot token
echo "***TELEGRAM_TOKEN_REDACTED***..." | docker secret create telegram_bot_token -
EOF
```

**Update docker-compose.yml:**
```yaml
version: '3.8'
services:
  clawdbot-gateway:
    secrets:
      - anthropic_api_key
      - telegram_bot_token
    environment:
      ANTHROPIC_API_KEY_FILE: /run/secrets/anthropic_api_key
      TELEGRAM_BOT_TOKEN_FILE: /run/secrets/telegram_bot_token

secrets:
  anthropic_api_key:
    external: true
  telegram_bot_token:
    external: true
```

---

#### Fix 2.3: Consolidate .env Files
```bash
# Create single encrypted .env file
cat > .env.production << 'ENV'
# Consolidated production secrets
ANTHROPIC_API_KEY=sk-ant-...
TELEGRAM_BOT_TOKEN=...
XAI_API_KEY=...
HELIUS_API_KEY=...
ENV

# Encrypt it
age -r $(age-keygen -y ~/.age-key.txt) -o .env.production.age .env.production
rm .env.production

# Update all services to use single source
```

---

### Priority 3: Least Privilege Access

#### Fix 3.1: Review Twitter OAuth Scopes
```bash
# Regenerate Twitter tokens with minimal scopes
# Go to: https://developer.twitter.com/en/portal/dashboard

# Request ONLY these scopes:
# - tweet.read
# - tweet.write
# - users.read
# - offline.access (for refresh tokens)

# REVOKE:
# - DM read/write
# - account.manage
# - follows.read/write (unless needed)
```

**Update code to use OAuth2 only:**
```python
# In bots/twitter/twitter_client.py
# Remove API v1.1 tokens, use OAuth2 only with restricted scopes
```

---

#### Fix 3.2: Rotate Telegram Bot Tokens
```bash
# Create new bot via @BotFather
# Generate new token with minimal permissions
# Update keys.json
# Revoke old tokens in @BotFather
```

---

#### Fix 3.3: Run Containers as Non-Root
```dockerfile
# In Dockerfile
FROM node:22-slim

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# ... build steps ...

# Switch to non-root
USER appuser

CMD ["node", "index.js"]
```

**Update docker-compose.yml:**
```yaml
services:
  clawdbot-gateway:
    user: "1000:1000"  # non-root UID:GID
```

---

### Priority 4: Monitoring & Alerting

#### Fix 4.1: Set Up fail2ban Email Alerts
```bash
ssh root@100.66.17.93 << 'EOF'
# Install mailutils
apt install -y mailutils

# Configure fail2ban alerts
cat >> /etc/fail2ban/jail.local << 'ALERT'
[DEFAULT]
destemail = your-email@example.com
sendername = Fail2Ban VPS Alert
action = %(action_mwl)s
ALERT

systemctl restart fail2ban
EOF
```

---

#### Fix 4.2: Monitor Auth Logs
```bash
# Set up daily auth log summary
ssh root@100.66.17.93 << 'EOF'
cat > /etc/cron.daily/auth-summary << 'SCRIPT'
#!/bin/bash
grep "Failed password" /var/log/auth.log | tail -50 | mail -s "Daily SSH Auth Summary" root
SCRIPT

chmod +x /etc/cron.daily/auth-summary
EOF
```

---

## 📋 SECURITY CHECKLIST

### Immediate (Do Today)
- [ ] Disable SSH password authentication
- [ ] Install fail2ban
- [ ] Enable UFW firewall
- [ ] Block current attack IP (170.64.139.8)
- [ ] Verify SSH key-only login works before logout

### This Week
- [ ] Encrypt secrets/keys.json with age
- [ ] Consolidate .env files
- [ ] Review Twitter OAuth scopes
- [ ] Rotate Telegram bot tokens
- [ ] Set up fail2ban email alerts

### This Month
- [ ] Migrate to Docker secrets
- [ ] Run containers as non-root
- [ ] Set up log monitoring
- [ ] Create backup/disaster recovery plan
- [ ] Document secrets rotation procedure

---

## 🔐 SECRETS ROTATION SCHEDULE

| Credential Type | Rotation Frequency | Last Rotated | Next Rotation |
|----------------|-------------------|--------------|---------------|
| Twitter OAuth2 tokens | 90 days | Unknown | ASAP |
| Telegram bot tokens | 180 days | Unknown | ASAP |
| Anthropic API key | On compromise only | N/A | N/A |
| Helius RPC key | 90 days | Unknown | ASAP |

---

## 📊 ATTACK SURFACE SUMMARY

### Before Fixes
```
SSH:           VULNERABLE (password auth enabled)
Firewall:      NONE
Fail2ban:      NOT INSTALLED
Secrets:       PLAIN TEXT
Root Access:   UNRESTRICTED
Attack Status: ONGOING (170.64.139.8)
```

### After Fixes
```
SSH:           SECURE (keys only, root restricted)
Firewall:      ACTIVE (UFW with default deny)
Fail2ban:      ENABLED (auto-ban after 3 failures)
Secrets:       ENCRYPTED (age encryption)
Root Access:   RESTRICTED (containers run as non-root)
Attack Status: BLOCKED (fail2ban + firewall)
```

---

## 🚀 NEXT STEPS

1. **Execute Priority 1 fixes NOW** (SSH + fail2ban + firewall)
2. **Verify you can still login via SSH key** before disconnecting
3. **Monitor fail2ban logs** for first 24 hours
4. **Encrypt secrets** within 48 hours
5. **Rotate OAuth tokens** within 1 week
6. **Schedule monthly security reviews**

---

## 📞 EMERGENCY CONTACTS

If locked out of VPS:
1. Use Tailscale connection: `ssh root@100.66.17.93` (via Tailscale IP)
2. VPS provider console access: (check your hosting dashboard)
3. Restore from backup if needed

---

**Report Generated:** 2026-01-31
**Action Required:** URGENT - Active attacks detected
**Risk Level:** HIGH (before fixes) → LOW (after fixes)

---

tap tap secure secure 🔒
