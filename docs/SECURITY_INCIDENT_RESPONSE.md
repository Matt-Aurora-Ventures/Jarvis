# JARVIS Security Incident Response Plan

A structured approach to handling security incidents in JARVIS.

---

## Quick Response Checklist

**If you suspect a security incident, follow these steps immediately:**

- [ ] 1. **CONTAIN** - Stop the bleeding
- [ ] 2. **ASSESS** - Understand the scope
- [ ] 3. **NOTIFY** - Alert the right people
- [ ] 4. **REMEDIATE** - Fix the issue
- [ ] 5. **RECOVER** - Return to normal
- [ ] 6. **DOCUMENT** - Record everything

---

## Severity Levels

| Level | Name | Description | Response Time |
|-------|------|-------------|---------------|
| P1 | Critical | Active breach, funds at risk, data exfiltration | **Immediate** |
| P2 | High | Vulnerability being exploited, potential data exposure | **1 hour** |
| P3 | Medium | Vulnerability discovered, no active exploitation | **4 hours** |
| P4 | Low | Security improvement needed, no immediate risk | **1 week** |

---

## Incident Response Procedures

### Phase 1: Containment

**Goal: Stop ongoing damage**

#### Treasury-Related Incidents (CRITICAL)

```bash
# IMMEDIATELY trigger emergency shutdown
python -c "
from core.security.emergency_shutdown import trigger_shutdown
import asyncio
asyncio.run(trigger_shutdown(reason='Security incident'))
"

# Or via API (if accessible)
curl -X POST https://api.jarvis/admin/emergency-shutdown \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Or via Telegram (admin only)
/emergency_shutdown
```

#### API-Related Incidents

```bash
# Revoke compromised API keys
UPDATE api_keys SET revoked = true WHERE key_hash = 'compromised_hash';

# Block suspicious IPs
# Add to firewall/WAF blocklist

# Enable enhanced rate limiting
export RATE_LIMIT_EMERGENCY=true
```

#### Bot-Related Incidents

```bash
# Stop bot processes
systemctl stop jarvis-telegram-bot
systemctl stop jarvis-twitter-bot

# Or kill directly
pkill -f "run_bots.py"
```

### Phase 2: Assessment

**Goal: Understand what happened**

#### Questions to Answer

1. **What was compromised?**
   - API keys?
   - User data?
   - Wallet keys?
   - Bot tokens?

2. **How did it happen?**
   - Vulnerability exploited?
   - Credential leak?
   - Social engineering?
   - Insider threat?

3. **What is the scope?**
   - How many users affected?
   - What timeframe?
   - What data accessed?

4. **Is it ongoing?**
   - Still active?
   - Attacker still present?

#### Evidence Collection

```bash
# Collect logs (last 24 hours)
mkdir -p /tmp/incident_$(date +%Y%m%d)
cp -r logs/* /tmp/incident_$(date +%Y%m%d)/

# Database audit
psql -c "SELECT * FROM audit_log WHERE created_at > NOW() - INTERVAL '24 hours'" > audit_export.sql

# Network connections
netstat -an > network_state.txt

# Process list
ps auxf > process_list.txt

# System state
dmesg > kernel_messages.txt
```

### Phase 3: Notification

**Goal: Alert appropriate parties**

#### Internal Notification

| Severity | Notify |
|----------|--------|
| P1 | Everyone immediately |
| P2 | Security lead + Engineering manager |
| P3 | Security lead |
| P4 | Document and track |

#### Notification Template

```
SECURITY INCIDENT ALERT

Severity: [P1/P2/P3/P4]
Time Detected: [YYYY-MM-DD HH:MM UTC]
Status: [Investigating/Contained/Resolved]

Summary:
[Brief description of what happened]

Impact:
- [What systems affected]
- [What data potentially exposed]
- [Number of users affected]

Actions Taken:
1. [First action]
2. [Second action]

Next Steps:
1. [Next action]

Incident Lead: [Name]
Contact: [Phone/Slack]
```

#### External Notification (if required)

- **Users**: If PII exposed
- **Authorities**: If legally required
- **Partners**: If their data affected

### Phase 4: Remediation

**Goal: Fix the vulnerability**

#### Credential Rotation

```bash
# Rotate all API keys
python scripts/rotate_api_keys.py

# Rotate bot tokens (get new from BotFather)
# Update TELEGRAM_BOT_TOKEN in environment

# Rotate encryption keys
python scripts/rotate_encryption_keys.py

# Rotate database passwords
# Update DATABASE_URL
```

#### Patch Vulnerabilities

```bash
# Update dependencies
pip install -U -r requirements.txt

# Apply security patches
git pull origin security-patch

# Redeploy
./deploy.sh
```

#### Strengthen Defenses

- Add additional logging
- Implement additional monitoring
- Update firewall rules
- Add new security controls

### Phase 5: Recovery

**Goal: Return to normal operations**

#### Pre-Recovery Checklist

- [ ] Vulnerability patched
- [ ] Credentials rotated
- [ ] No attacker presence detected
- [ ] Monitoring enhanced
- [ ] Backups verified

#### Recovery Steps

```bash
# Verify system integrity
python scripts/verify_integrity.py

# Start services in order
systemctl start jarvis-api
systemctl start jarvis-telegram-bot
systemctl start jarvis-twitter-bot

# Verify health
curl https://api.jarvis/health

# Monitor closely for 24 hours
```

### Phase 6: Post-Incident

**Goal: Learn and improve**

#### Post-Mortem Meeting

Schedule within 48 hours of resolution.

Agenda:
1. Timeline of events
2. What went well
3. What could be improved
4. Action items

#### Documentation

Complete the [Incident Report Template](#incident-report-template) below.

---

## Incident Report Template

```markdown
# Security Incident Report

## Summary
- **Incident ID**: SEC-YYYY-NNN
- **Severity**: P1/P2/P3/P4
- **Status**: Resolved/Ongoing
- **Date Detected**: YYYY-MM-DD HH:MM UTC
- **Date Resolved**: YYYY-MM-DD HH:MM UTC
- **Duration**: X hours/days

## Timeline

| Time (UTC) | Event |
|------------|-------|
| HH:MM | First suspicious activity detected |
| HH:MM | Alert triggered |
| HH:MM | Incident confirmed |
| HH:MM | Containment initiated |
| HH:MM | Root cause identified |
| HH:MM | Remediation complete |
| HH:MM | Recovery confirmed |

## Impact Assessment

### Systems Affected
- [ ] API
- [ ] Database
- [ ] Telegram Bot
- [ ] Twitter Bot
- [ ] Treasury/Wallet
- [ ] User Data

### Data Exposure
- **Types of data**: [list data types]
- **Number of records**: [count]
- **Users affected**: [count]

### Financial Impact
- **Direct losses**: $X
- **Remediation costs**: $X
- **Business impact**: [description]

## Root Cause Analysis

### What Happened
[Detailed technical description]

### Why It Happened
[Contributing factors]

### How It Was Detected
[Detection method and timing]

## Response Actions

### Containment
1. [Action taken]
2. [Action taken]

### Remediation
1. [Action taken]
2. [Action taken]

### Recovery
1. [Action taken]
2. [Action taken]

## Lessons Learned

### What Went Well
- [Item]
- [Item]

### What Could Be Improved
- [Item]
- [Item]

## Action Items

| Action | Owner | Due Date | Status |
|--------|-------|----------|--------|
| [Action] | [Name] | YYYY-MM-DD | Open |

## Appendix

### Evidence Collected
- [List of logs, screenshots, etc.]

### External Communications
- [List of notifications sent]
```

---

## Common Incident Scenarios

### Scenario 1: Leaked API Key

**Indicators:**
- Unusual API traffic patterns
- Requests from unknown IPs
- Usage spikes

**Response:**
1. Immediately revoke the key
2. Identify where it was leaked (GitHub, logs, etc.)
3. Rotate all related credentials
4. Review access logs for unauthorized actions
5. Update secret management practices

### Scenario 2: Wallet Compromise

**Indicators:**
- Unauthorized transactions
- Balance changes
- Unknown signatures

**Response:**
1. **EMERGENCY SHUTDOWN** immediately
2. Move remaining funds to secure wallet
3. Preserve transaction logs
4. Analyze attack vector
5. Generate new wallet keys
6. Update all systems with new keys

### Scenario 3: Bot Account Takeover

**Indicators:**
- Messages not from you
- Unknown commands executed
- Token used from unknown location

**Response:**
1. Revoke bot token with BotFather
2. Generate new token
3. Update environment variables
4. Restart bot with new token
5. Notify users if spam was sent

### Scenario 4: Data Breach

**Indicators:**
- Unusual database queries
- Large data exports
- Unauthorized access logs

**Response:**
1. Isolate affected systems
2. Preserve evidence
3. Assess data exposed
4. Notify affected users
5. Report to authorities if required
6. Implement additional controls

---

## Emergency Contacts

| Role | Contact | Backup |
|------|---------|--------|
| Security Lead | [internal] | [internal] |
| Engineering Manager | [internal] | [internal] |
| Legal | [internal] | [internal] |
| Communications | [internal] | [internal] |

---

## Tools & Resources

### Monitoring Dashboards
- Grafana: http://grafana.internal:3000
- Log aggregation: http://logs.internal:5601

### Runbooks
- [Deployment Runbook](runbooks/DEPLOYMENT.md)
- [Emergency Shutdown](runbooks/EMERGENCY_SHUTDOWN.md)

### External Resources
- [CVE Database](https://cve.mitre.org/)
- [NIST Incident Handling Guide](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-61r2.pdf)

---

## Revision History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-01-13 | Initial version | JARVIS Team |
