# Incident Response Runbook

## Quick Reference

| Severity | Response Time | Escalation |
|----------|--------------|------------|
| Critical | 15 min | Immediate page |
| High | 1 hour | Slack alert |
| Medium | 4 hours | Email |
| Low | 24 hours | Ticket |

## Common Incidents

### 1. API Unresponsive (Critical)

**Symptoms:**
- Health check failing
- 5xx error spike
- Timeout errors

**Diagnosis:**
```bash
# Check service status
docker-compose ps

# Check logs
docker-compose logs --tail=100 jarvis-api

# Check resources
docker stats
```

**Resolution:**
1. Restart the service: `docker-compose restart jarvis-api`
2. If persists, check database connectivity
3. If persists, scale up: `docker-compose up -d --scale jarvis-api=3`

### 2. High Latency (High)

**Symptoms:**
- p95 latency > 2s
- Slow dashboard loading
- Timeout errors

**Diagnosis:**
```bash
# Check slow queries
sqlite3 data/jarvis.db "SELECT * FROM sqlite_stat1"

# Check provider latency
curl -w "@curl-format.txt" http://localhost:8000/api/health
```

**Resolution:**
1. Check provider status and switch if needed
2. Clear Redis cache: `redis-cli FLUSHDB`
3. Analyze and optimize slow queries

### 3. Provider Failures (High)

**Symptoms:**
- Provider health check failing
- AI responses failing
- Rate limit errors

**Diagnosis:**
```bash
# Check provider status
curl http://localhost:8000/api/health | jq '.services.providers'

# Check rate limit state
redis-cli GET "ratelimit:provider:*"
```

**Resolution:**
1. Wait for rate limit reset
2. Switch to backup provider
3. Check API key validity

### 4. Memory Leak (Medium)

**Symptoms:**
- Gradual memory increase
- OOM kills
- Slow garbage collection

**Diagnosis:**
```python
from core.performance.memory_monitor import memory_monitor
memory_monitor.start_tracking()
# Wait and collect
print(memory_monitor.get_report())
```

**Resolution:**
1. Identify leaking objects
2. Restart service as temporary fix
3. Deploy fix for root cause

### 5. Database Corruption (Critical)

**Symptoms:**
- SQLite errors
- Data inconsistency
- Read failures

**Resolution:**
1. Stop all services
2. Backup current database
3. Run integrity check: `sqlite3 data/jarvis.db "PRAGMA integrity_check"`
4. Restore from backup if needed

## Escalation Contacts

| Role | Contact | When |
|------|---------|------|
| On-call | PagerDuty | Critical incidents |
| Backend Lead | Slack | API issues |
| DevOps | Slack | Infrastructure |

## Post-Incident

1. Create incident report
2. Update runbook if needed
3. Add monitoring for new failure mode
4. Schedule postmortem if Critical/High

## Mesh Sync and Attestation Degraded Mode

### Symptoms
- Memory writes succeed, but mesh status reports `pending_publish` or `pending_commit`.
- Runtime capability report shows `mesh_sync` or `mesh_attestation` as `degraded`.
- Outbox backlog grows in `data/mesh/outbox.jsonl` (or `JARVIS_MESH_OUTBOX_PATH`).

### Immediate Safety Rules
1. Do not block user-facing memory writes for mesh errors.
2. Keep mesh flags disabled in production unless smoke checks pass.
3. Treat `invalid_envelope` as data-integrity event; do not auto-commit.

### Diagnosis
```bash
# Runtime capability summary
python -c "from core.runtime_capabilities import build_runtime_capability_report as r; import json; print(json.dumps(r(), indent=2))"

# Mesh service status snapshot
python -c "from services.compute.mesh_sync_service import get_mesh_sync_service as s; import json; print(json.dumps(s().get_status(), indent=2))"

# Outbox tail
tail -n 50 data/mesh/outbox.jsonl
```

### Recovery Steps
1. Verify config and dependencies:
   - `JARVIS_USE_MESH_SYNC` / `JARVIS_MESH_SYNC_ENABLED`
   - `JARVIS_USE_MESH_ATTEST` / `JARVIS_MESH_ATTESTATION_ENABLED`
   - `JARVIS_MESH_SHARED_KEY` (or `JARVIS_MESH_SYNC_KEY`)
   - `JARVIS_MESH_NODE_PUBKEY`
   - `JARVIS_MESH_PROGRAM_ID` + keypair path
2. Retry pending events:
```bash
python -c "import asyncio, json; from services.compute.mesh_sync_service import get_mesh_sync_service as s; print(asyncio.run(s().retry_pending_mesh_events(limit=100)))"
```
3. If retries fail repeatedly, disable attestation first, then mesh sync:
   - `JARVIS_USE_MESH_ATTEST=0`
   - `JARVIS_USE_MESH_SYNC=0`
4. Keep system in degraded mode (writes continue) while investigating transport/RPC faults.

### Rollback Playbook
1. Disable flags:
   - `JARVIS_USE_MESH_ATTEST=0`
   - `JARVIS_USE_MESH_SYNC=0`
2. Revert model/provider config if related rollout introduced instability:
   - `lifeos/config/jarvis.json`
3. Roll back deployment image tag to last known stable tag.
4. Restart services and verify:
   - memory writes succeed
   - runtime report no longer shows mesh-related hard failures
