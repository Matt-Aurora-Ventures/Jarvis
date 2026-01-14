# JARVIS Deployment Runbook

## Overview

This runbook covers the deployment procedures for JARVIS,
including pre-deployment checks, deployment steps, and rollback procedures.

---

## Table of Contents

1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Deployment Procedures](#deployment-procedures)
3. [Post-Deployment Verification](#post-deployment-verification)
4. [Rollback Procedures](#rollback-procedures)
5. [Emergency Procedures](#emergency-procedures)
6. [Monitoring During Deployment](#monitoring-during-deployment)

---

## Pre-Deployment Checklist

### Code Quality
- [ ] All tests passing (`pytest tests/`)
- [ ] No critical security issues (`bandit -r core/`)
- [ ] Type checking passes (`mypy core/`)
- [ ] Code formatted (`black --check core/`)
- [ ] Linting passes (`ruff core/`)

### Environment
- [ ] Environment variables documented and available
- [ ] Secrets rotated if needed
- [ ] Database migrations prepared
- [ ] Dependencies updated in requirements.txt

### Communication
- [ ] Team notified of deployment window
- [ ] Stakeholders aware of any expected downtime
- [ ] On-call engineer identified

### Infrastructure
- [ ] Sufficient resources available
- [ ] Backup completed
- [ ] Monitoring dashboards accessible

---

## Deployment Procedures

### Standard Deployment

#### 1. Prepare the Deployment

```bash
# Pull latest code
git checkout main
git pull origin main

# Create deployment branch (optional)
git checkout -b deploy/$(date +%Y%m%d-%H%M)

# Verify version
cat VERSION
```

#### 2. Run Pre-Deployment Tests

```bash
# Run full test suite
pytest tests/ -v --tb=short

# Run security scan
python scripts/security_scan.py

# Check for breaking changes
python scripts/check_migrations.py
```

#### 3. Build and Deploy

##### Docker Deployment

```bash
# Build images
docker-compose build

# Run migrations (if any)
docker-compose run --rm api python -m scripts.db.migrate

# Deploy with zero downtime
docker-compose up -d --scale api=2

# Wait for health checks
sleep 30

# Verify deployment
curl -f http://localhost:8000/health
```

##### Manual Deployment

```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
python -m scripts.db.migrate

# Restart services
sudo systemctl restart jarvis-api
sudo systemctl restart jarvis-bots

# Verify
curl -f http://localhost:8000/health
```

#### 4. Verify Deployment

```bash
# Check health endpoints
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/health/ready
curl http://localhost:8000/api/v1/health/live

# Check logs for errors
tail -f logs/jarvis.log | grep -i error

# Monitor metrics
open http://localhost:3000/d/jarvis-overview
```

---

## Post-Deployment Verification

### Immediate Checks (0-5 minutes)

- [ ] Health endpoints responding 200
- [ ] No errors in application logs
- [ ] Database connections established
- [ ] Redis cache connected
- [ ] Bots responding (Telegram, Twitter)

### Short-Term Checks (5-30 minutes)

- [ ] API response times normal
- [ ] Error rate below threshold (<1%)
- [ ] No memory leaks detected
- [ ] Scheduled tasks running
- [ ] Trading functionality verified

### Extended Checks (30-60 minutes)

- [ ] LLM providers responding
- [ ] Trading signals processing
- [ ] Webhook deliveries successful
- [ ] User traffic patterns normal

---

## Rollback Procedures

### Quick Rollback (Docker)

```bash
# Roll back to previous image
docker-compose down
docker tag jarvis-api:previous jarvis-api:latest
docker-compose up -d

# Or use specific version
docker-compose -f docker-compose.yml \
  -f docker-compose.rollback.yml up -d
```

### Quick Rollback (Manual)

```bash
# Switch to previous release
cd /opt/jarvis
git checkout $PREVIOUS_VERSION

# Reinstall dependencies
pip install -r requirements.txt

# Restart services
sudo systemctl restart jarvis-api
sudo systemctl restart jarvis-bots
```

### Database Rollback

```bash
# CAUTION: Only if migrations were applied

# Run migration rollback
python -m scripts.db.migrate --rollback 1

# Verify database state
python -m scripts.db.verify
```

### When to Rollback

Rollback immediately if:
- Error rate exceeds 5%
- Health checks failing
- Critical functionality broken
- Database corruption detected
- Security vulnerability discovered

---

## Emergency Procedures

### Total System Failure

1. **Activate Emergency Shutdown**
   ```bash
   python -m core.security.emergency_shutdown --activate
   ```

2. **Notify stakeholders**
   - Alert team via Slack/Discord
   - Update status page

3. **Preserve evidence**
   - Export logs: `docker logs jarvis-api > emergency-logs.txt`
   - Capture metrics snapshot

4. **Begin recovery**
   - Follow rollback procedure
   - Investigate root cause

### Security Incident

1. **Isolate affected systems**
   ```bash
   # Block external access
   iptables -A INPUT -p tcp --dport 8000 -j DROP
   ```

2. **Rotate credentials**
   ```bash
   python scripts/rotate_secrets.py --all
   ```

3. **Review audit logs**
   ```bash
   python scripts/export_audit_logs.py --since "1 hour ago"
   ```

### Database Emergency

1. **Stop writes**
   ```bash
   # Enable read-only mode
   curl -X POST http://localhost:8000/admin/read-only-mode
   ```

2. **Backup current state**
   ```bash
   python scripts/db/backup.py --emergency
   ```

3. **Assess damage**
   ```bash
   python scripts/db/verify.py --full
   ```

---

## Monitoring During Deployment

### Key Metrics to Watch

| Metric | Normal | Warning | Critical |
|--------|--------|---------|----------|
| Error Rate | <1% | 1-5% | >5% |
| Response Time (p99) | <500ms | 500-1000ms | >1000ms |
| CPU Usage | <70% | 70-85% | >85% |
| Memory Usage | <80% | 80-90% | >90% |
| Active Connections | <1000 | 1000-1500 | >1500 |

### Dashboard URLs

- **Grafana Overview**: http://localhost:3000/d/jarvis-overview
- **API Metrics**: http://localhost:3000/d/jarvis-api
- **Bot Health**: http://localhost:3000/d/jarvis-bots
- **Trading**: http://localhost:3000/d/jarvis-trading

### Log Locations

```bash
# Application logs
/var/log/jarvis/app.log

# Error logs
/var/log/jarvis/error.log

# Access logs
/var/log/jarvis/access.log

# Bot logs
/var/log/jarvis/bots.log
```

---

## Deployment Schedule

### Preferred Windows

- **Production**: Tuesday-Thursday, 10:00-16:00 UTC
- **Staging**: Any time
- **Hotfixes**: As needed, with approval

### Blackout Periods

- Friday 14:00 UTC - Monday 06:00 UTC
- Major market events
- Scheduled maintenance windows

---

## Contact Information

### On-Call

- Primary: Check PagerDuty schedule
- Secondary: Check Slack #oncall channel

### Escalation Path

1. On-call engineer
2. Tech lead
3. Engineering manager
4. CTO (critical incidents only)

---

## Appendix

### Environment Variables

See `env.example` for required variables.

### Health Check Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/health` | Basic health |
| `/health/ready` | Readiness probe |
| `/health/live` | Liveness probe |
| `/health/startup` | Startup probe |

### Common Issues

| Issue | Solution |
|-------|----------|
| Database connection refused | Check DATABASE_URL, restart DB |
| Redis connection timeout | Check REDIS_URL, increase timeout |
| LLM provider errors | Check API keys, fallback to backup |
| Bot not responding | Check tokens, restart bot service |
