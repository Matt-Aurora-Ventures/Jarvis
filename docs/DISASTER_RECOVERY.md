# JARVIS Disaster Recovery Plan

Comprehensive disaster recovery procedures for JARVIS infrastructure.

---

## Table of Contents

1. [Overview](#overview)
2. [Recovery Objectives](#recovery-objectives)
3. [Disaster Categories](#disaster-categories)
4. [Recovery Procedures](#recovery-procedures)
5. [Backup Strategy](#backup-strategy)
6. [Communication Plan](#communication-plan)
7. [Testing & Validation](#testing--validation)

---

## Overview

This document outlines disaster recovery (DR) procedures for JARVIS. It covers:
- System failures and data loss
- Security breaches
- Infrastructure outages
- Data corruption

### Key Contacts

| Role | Contact |
|------|---------|
| Incident Commander | [Primary Contact] |
| Technical Lead | [Tech Lead] |
| Security Lead | [Security] |
| Infrastructure | [Infra Team] |

---

## Recovery Objectives

### Recovery Time Objective (RTO)

Maximum acceptable downtime:

| Service | RTO |
|---------|-----|
| API (read-only) | 15 minutes |
| API (full) | 1 hour |
| Telegram Bot | 30 minutes |
| Treasury Operations | 4 hours |
| Analytics | 24 hours |

### Recovery Point Objective (RPO)

Maximum acceptable data loss:

| Data Type | RPO |
|-----------|-----|
| Trading transactions | 0 (no loss) |
| User data | 1 hour |
| Bot conversations | 24 hours |
| Analytics | 7 days |
| Logs | 24 hours |

---

## Disaster Categories

### Category 1: Service Degradation
- Single service failure
- Increased latency
- Partial functionality loss

**Response Time:** 15 minutes
**Severity:** Low to Medium

### Category 2: Service Outage
- Complete service unavailable
- Database connection issues
- Infrastructure problems

**Response Time:** Immediate
**Severity:** High

### Category 3: Data Loss/Corruption
- Database corruption
- Backup failure
- Accidental deletion

**Response Time:** Immediate
**Severity:** Critical

### Category 4: Security Breach
- Unauthorized access
- Data exfiltration
- Compromised credentials

**Response Time:** Immediate
**Severity:** Critical

---

## Recovery Procedures

### Procedure 1: Service Recovery

#### 1.1 API Service Failure

```bash
# 1. Check service status
kubectl get pods -l app=jarvis-api

# 2. Check recent events
kubectl describe pod <pod-name>

# 3. Check logs
kubectl logs <pod-name> --tail=100

# 4. Restart pods if needed
kubectl rollout restart deployment jarvis-api

# 5. Verify recovery
curl https://api.jarvis.local/health
```

#### 1.2 Bot Service Failure

```bash
# 1. Check bot status
kubectl get pods -l app=jarvis-telegram-bot

# 2. Check for errors
kubectl logs -l app=jarvis-telegram-bot --tail=200

# 3. Restart bot
kubectl delete pod -l app=jarvis-telegram-bot

# 4. Verify Telegram webhook
curl "https://api.telegram.org/bot${TOKEN}/getWebhookInfo"
```

### Procedure 2: Database Recovery

#### 2.1 Connection Issues

```bash
# 1. Check database status
pg_isready -h ${DB_HOST} -p 5432

# 2. Check connection pool
kubectl exec -it jarvis-api-xxx -- python -c "
from core.db.pool import get_pool
pool = get_pool()
print(f'Connections: {pool.size()}/{pool.maxsize}')
"

# 3. Reset connection pool
kubectl rollout restart deployment jarvis-api
```

#### 2.2 Database Restore

```bash
# 1. List available backups
python scripts/db/backup.py list

# 2. Stop services
kubectl scale deployment jarvis-api --replicas=0
kubectl scale deployment jarvis-telegram-bot --replicas=0

# 3. Restore from backup
python scripts/db/backup.py restore --backup-id <backup-id>

# 4. Verify data integrity
python scripts/db/verify_integrity.py

# 5. Restart services
kubectl scale deployment jarvis-api --replicas=2
kubectl scale deployment jarvis-telegram-bot --replicas=1
```

#### 2.3 Point-in-Time Recovery

```bash
# For AWS RDS
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier jarvis-prod-postgres \
  --target-db-instance-identifier jarvis-prod-postgres-recovery \
  --restore-time 2024-01-13T10:00:00Z
```

### Procedure 3: Treasury Emergency

#### 3.1 Emergency Shutdown

```bash
# 1. Trigger emergency shutdown
python -c "
from core.security.emergency_shutdown import trigger_shutdown
import asyncio
asyncio.run(trigger_shutdown(reason='DR procedure'))
"

# 2. Verify trading halted
kubectl logs -l app=jarvis-treasury-bot --tail=50

# 3. Secure wallet keys
# (Move to cold storage if physical access available)
```

#### 3.2 Wallet Recovery

```bash
# 1. Verify wallet integrity
python scripts/treasury/verify_wallet.py

# 2. Check on-chain transactions
python scripts/treasury/audit_transactions.py --last=100

# 3. Generate recovery report
python scripts/treasury/recovery_report.py > recovery_report.txt
```

### Procedure 4: Security Breach Response

#### 4.1 Immediate Actions

1. **Contain**
   ```bash
   # Block all external access
   kubectl apply -f k8s/emergency/block-ingress.yaml

   # Trigger emergency shutdown
   python -c "from core.security.emergency_shutdown import emergency_stop; emergency_stop()"
   ```

2. **Assess**
   - Check audit logs
   - Review access logs
   - Identify compromised components

3. **Eradicate**
   ```bash
   # Rotate all credentials
   ./scripts/rotate_all_secrets.sh

   # Redeploy from known-good state
   helm upgrade jarvis ./helm/jarvis \
     --set image.tag=<known-good-version>
   ```

4. **Recover**
   - Restore from pre-breach backup
   - Validate data integrity
   - Re-enable services gradually

---

## Backup Strategy

### Database Backups

| Type | Frequency | Retention | Location |
|------|-----------|-----------|----------|
| Full | Daily | 30 days | S3 |
| Incremental | Hourly | 7 days | S3 |
| Transaction logs | Continuous | 7 days | S3 |

### Backup Commands

```bash
# Manual backup
python scripts/db/backup.py create --type=full

# Verify backup
python scripts/db/backup.py verify --backup-id <id>

# List backups
python scripts/db/backup.py list --days=30
```

### Configuration Backups

```bash
# Backup Kubernetes configs
kubectl get all -o yaml > k8s-backup-$(date +%Y%m%d).yaml

# Backup secrets (encrypted)
kubectl get secrets -o yaml | sops -e > secrets-backup.yaml
```

### Wallet Backups

- Cold storage of master keys
- Multi-signature setup
- Geographic distribution

---

## Communication Plan

### Internal Communication

1. **Slack/Teams Alert**
   - #jarvis-incidents channel
   - @here for active incidents

2. **Escalation Path**
   - On-call engineer → Tech Lead → Management

### External Communication

1. **Status Page Updates**
   - https://status.jarvis.local
   - Update every 15 minutes during incidents

2. **User Notification**
   - Telegram broadcast for extended outages
   - Email for data-affecting incidents

### Templates

#### Initial Alert
```
🚨 JARVIS INCIDENT - [SEVERITY]

Impact: [Brief description]
Status: Investigating
ETA: [If known]

Updates will follow every 15 minutes.
```

#### Resolution
```
✅ JARVIS INCIDENT RESOLVED

Duration: [X hours Y minutes]
Impact: [Summary]
Root Cause: [Brief explanation]

Post-mortem to follow within 48 hours.
```

---

## Testing & Validation

### DR Drill Schedule

| Test Type | Frequency | Last Test | Next Test |
|-----------|-----------|-----------|-----------|
| Backup restore | Monthly | - | - |
| Service failover | Quarterly | - | - |
| Full DR exercise | Annually | - | - |

### DR Drill Checklist

- [ ] Notify stakeholders
- [ ] Document start time
- [ ] Execute recovery procedure
- [ ] Measure recovery time
- [ ] Validate data integrity
- [ ] Document issues found
- [ ] Update procedures as needed

### Validation Scripts

```bash
# Validate backup integrity
python scripts/dr/validate_backups.py

# Test failover (staging)
python scripts/dr/test_failover.py --env=staging

# Full system health check
python scripts/dr/health_check.py --comprehensive
```

---

## Appendix

### A. Runbook Quick Reference

| Scenario | Runbook |
|----------|---------|
| API down | [RUNBOOK-001](runbooks/api-recovery.md) |
| Database issue | [RUNBOOK-002](runbooks/database-recovery.md) |
| Security breach | [RUNBOOK-003](runbooks/security-incident.md) |
| Treasury emergency | [RUNBOOK-004](runbooks/treasury-emergency.md) |

### B. Infrastructure Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      Load Balancer                          │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│   API Pod 1   │   │   API Pod 2   │   │   API Pod 3   │
└───────────────┘   └───────────────┘   └───────────────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                              │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  PostgreSQL   │   │    Redis      │   │   S3 Backups  │
│   (Primary)   │   │   (Cluster)   │   │               │
└───────────────┘   └───────────────┘   └───────────────┘
        │
        ▼
┌───────────────┐
│  PostgreSQL   │
│   (Replica)   │
└───────────────┘
```

### C. Recovery Time Estimates

| Component | Cold Start | Warm Failover |
|-----------|------------|---------------|
| API service | 5 minutes | 30 seconds |
| Database | 30 minutes | 5 minutes |
| Redis cache | 2 minutes | 30 seconds |
| Full system | 1 hour | 15 minutes |

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2024-01-13 | Team | Initial version |
