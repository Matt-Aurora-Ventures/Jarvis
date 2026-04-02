# SuperMemory Graph Verification Guide

**Status:** Verification Procedures Ready
**Created:** 2026-02-03
**Priority:** Medium (Verify feature working as designed)

---

## Overview

SuperMemory uses a vector-graph hybrid architecture to create a dynamic Knowledge Graph. This guide verifies that the three core graph relationships (Updates, Extends, Derives) are working correctly, along with temporal grounding.

---

## SuperMemory Architecture Recap

### Database Location

**File**: `/root/clawdbots/data/supermemory.db` (on VPS)

**Mounting**: Shared across all 3 bots via docker volume mount:
```yaml
# From docker-compose.clawdbots.yml
volumes:
  - /root/clawdbots/data:/root/clawdbots/data
```

### Configuration

**Environment Variables** (from docker/clawdbot-gateway/.env):
```bash
# Shared API key (set via env; do not commit secrets)
SUPERMEMORY_API_KEY=sm_your_supermemory_api_key_here

# Per-bot namespace (configured in ClawdBot startup)
SUPERMEMORY_USER_PREFIX=friday   # For Friday
SUPERMEMORY_USER_PREFIX=matt     # For Matt
SUPERMEMORY_USER_PREFIX=jarvis   # For Jarvis
```

---

## Graph Relationships to Verify

### 1. Updates (State Mutation)

**Purpose**: Handle contradictions by invalidating old information when new conflicting data arrives.

**Test Case**:
```
Step 1: Store initial fact
  - "Jarvis uses OpenAI for embeddings"
  - timestamp: 2026-01-15

Step 2: Store contradictory fact
  - "Jarvis uses Gemini for embeddings"
  - timestamp: 2026-02-03

Step 3: Query current state
  - Expected: Returns Gemini (latest)
  - Expected: OpenAI entry marked as invalidated/superseded

Step 4: Query historical state
  - Expected: Can retrieve what was true on 2026-01-15 (OpenAI)
```

### 2. Extends (Enrichment)

**Purpose**: Add detail without replacing existing facts.

**Test Case**:
```
Step 1: Store base fact
  - "Friday monitors Matt & Jarvis"

Step 2: Add enrichment
  - "Friday uses Docker socket at /var/run/docker.sock"
  - (EXTENDS previous fact, doesn't replace)

Step 3: Add more enrichment
  - "Friday checks health every 2 minutes"
  - (EXTENDS again)

Step 4: Query "Friday monitors"
  - Expected: Returns ALL related facts:
    - Friday monitors Matt & Jarvis
    - Friday uses Docker socket...
    - Friday checks health every 2 minutes
```

### 3. Derives (Inference)

**Purpose**: Infer new facts from patterns ("sleep-time compute").

**Test Case**:
```
Step 1: Store observations
  - "Jarvis crashes when memory > 2GB"
  - "Extended Thinking uses 3GB RAM"
  - "Jarvis crashed during Extended Thinking"

Step 2: Trigger inference (if automatic)
  - Or manually request: "Why does Jarvis crash?"

Step 3: Verify derived fact
  - Expected: "Extended Thinking causes OOM → crashes"
  - Expected: Marked as DERIVED (not explicitly stated)
```

### 4. Temporal Grounding

**Purpose**: Understand chronology via dual timestamps (documentDate vs eventDate).

**Test Case**:
```
Step 1: Store event that happened in past
  - Event: "KVM8 crashed"
  - eventDate: 2026-02-01
  - documentDate: 2026-02-03 (when reported)

Step 2: Query "When did KVM8 crash?"
  - Expected: Returns eventDate (2026-02-01)
  - NOT documentDate (2026-02-03)

Step 3: Query "What happened before KVM8 crashed?"
  - Expected: Events with eventDate < 2026-02-01
  - Chronological ordering preserved
```

---

## Verification Procedures

### Pre-requisites

1. **VPS Access**: SSH or Hostinger hPanel console
2. **Database Access**: SQLite CLI or SuperMemory API
3. **Bot Running**: At least one ClawdBot active for testing

### Method 1: SuperMemory API (Recommended)

**If SuperMemory exposes an API endpoint:**

```bash
# SSH into VPS
ssh root@76.13.106.100

# Test Updates relationship
curl -X POST http://localhost:SUPERMEMORY_PORT/api/memory \
  -H "Authorization: Bearer sm_9C4Awqczh..." \
  -H "Content-Type: application/json" \
  -d '{
    "user_prefix": "test",
    "content": "Jarvis uses OpenAI for embeddings",
    "timestamp": "2026-01-15T12:00:00Z"
  }'

# Store contradictory fact
curl -X POST http://localhost:SUPERMEMORY_PORT/api/memory \
  -H "Authorization: Bearer sm_9C4Awqczh..." \
  -H "Content-Type: application/json" \
  -d '{
    "user_prefix": "test",
    "content": "Jarvis uses Gemini for embeddings",
    "timestamp": "2026-02-03T10:00:00Z"
  }'

# Query current state
curl -X GET "http://localhost:SUPERMEMORY_PORT/api/memory/search?q=jarvis+embeddings&user_prefix=test" \
  -H "Authorization: Bearer sm_9C4Awqczh..."

# Expected response:
# {
#   "results": [
#     {
#       "content": "Jarvis uses Gemini for embeddings",
#       "timestamp": "2026-02-03T10:00:00Z",
#       "relationship": "UPDATES",
#       "supersedes": "Jarvis uses OpenAI for embeddings"
#     }
#   ]
# }
```

### Method 2: SQLite Direct Access

```bash
# SSH into VPS
ssh root@76.13.106.100

# Open database
sqlite3 /root/clawdbots/data/supermemory.db

# List tables
.tables

# Expected tables (varies by implementation):
# - memories
# - graph_relationships
# - embeddings
# - user_profiles

# Query memories
SELECT * FROM memories LIMIT 10;

# Query graph relationships
SELECT * FROM graph_relationships WHERE relationship_type = 'UPDATES';
SELECT * FROM graph_relationships WHERE relationship_type = 'EXTENDS';
SELECT * FROM graph_relationships WHERE relationship_type = 'DERIVES';

# Check temporal grounding
SELECT id, content, event_date, document_date FROM memories
WHERE event_date != document_date
LIMIT 10;

# Exit
.quit
```

### Method 3: Bot Interaction Test

**Use Telegram to test via actual bot interactions:**

```
User (via Telegram to Friday):
> Remember: Jarvis uses OpenAI for embeddings

Friday:
> ✅ Stored in long-term memory

User (next day, via Telegram to Matt):
> Remember: Jarvis uses Gemini for embeddings

Matt:
> ✅ Stored. This updates previous information about embeddings.

User (via Telegram to Jarvis):
> What embeddings provider does Jarvis use?

Jarvis:
> I use Gemini for embeddings. (Previously used OpenAI until 2026-02-03)

# This demonstrates:
# - Cross-bot memory (Friday stored, Matt updated, Jarvis recalled)
# - Updates relationship (contradiction handled)
# - Temporal awareness (knows it changed)
```

---

## Verification Checklist

### ✅ Basic Functionality

- [ ] Database file exists at `/root/clawdbots/data/supermemory.db`
- [ ] Database is readable (not corrupted)
- [ ] All 3 bots can read from shared database
- [ ] All 3 bots can write to shared database
- [ ] Namespace isolation working (Friday's memories ≠ Matt's memories)

### ✅ Graph Relationships

#### Updates (State Mutation)
- [ ] Can store initial fact
- [ ] Can store contradictory fact
- [ ] Latest fact returned by default
- [ ] Old fact marked as superseded/invalidated
- [ ] Can query historical state (what was true then)

#### Extends (Enrichment)
- [ ] Can store base fact
- [ ] Can add enrichments without replacing base
- [ ] Query returns ALL related facts (base + extensions)
- [ ] Extensions linked to base in graph

#### Derives (Inference)
- [ ] Can store multiple observations
- [ ] System infers causal relationship
- [ ] Derived facts marked as inferred (not explicit)
- [ ] Can explain how inference was made

### ✅ Temporal Grounding

- [ ] documentDate captured (when memory stored)
- [ ] eventDate captured (when event occurred)
- [ ] Queries respect eventDate for chronology
- [ ] Can query "what happened before/after X"
- [ ] Temporal conflicts resolved correctly

### ✅ Performance

- [ ] Search latency < 100ms (vector search)
- [ ] Graph traversal latency < 50ms
- [ ] Hybrid search (vector + graph) < 150ms
- [ ] Database size reasonable (< 100MB for first month)

---

## Expected Behavior (Success Criteria)

| Test | Success Criteria |
|------|------------------|
| **Updates** | Latest fact returned, old fact marked superseded, historical queries work |
| **Extends** | All related facts returned, graph links preserved |
| **Derives** | Causal inference created, marked as derived |
| **Temporal** | Events ordered by eventDate, not documentDate |
| **Cross-bot** | Friday stores, Matt updates, Jarvis recalls correctly |
| **Performance** | Search < 100ms, graph < 50ms, hybrid < 150ms |

---

## Troubleshooting

### Issue 1: Database not found

**Symptom**: `/root/clawdbots/data/supermemory.db` doesn't exist

**Solution**:
```bash
# Check if directory exists
ls -la /root/clawdbots/data/

# Check docker volume mount
docker inspect clawdbot-friday | grep -A 10 "Mounts"

# If missing, create directory and let bots initialize
mkdir -p /root/clawdbots/data
chown -R 1000:1000 /root/clawdbots/data
docker restart clawdbot-friday clawdbot-matt clawdbot-jarvis
```

### Issue 2: "Permission denied" on database

**Symptom**: Bots can't write to supermemory.db

**Solution**:
```bash
# Fix permissions
chmod 666 /root/clawdbots/data/supermemory.db
chown 1000:1000 /root/clawdbots/data/supermemory.db
```

### Issue 3: Graph relationships not working

**Symptom**: Updates/Extends/Derives not functioning

**Diagnosis**:
```bash
# Check SuperMemory version
docker exec clawdbot-friday pip list | grep supermemory

# Check if SuperMemory API is accessible
curl http://localhost:SUPERMEMORY_PORT/health

# Check logs for SuperMemory errors
docker logs clawdbot-friday | grep -i supermemory
```

**Solution**: May need SuperMemory API server running (check if separate service)

### Issue 4: Embeddings not working

**Symptom**: Semantic search returns no results

**Cause**: No embedding provider configured (OpenAI removed)

**Solution**: Verify Gemini configured or SuperMemory native embeddings enabled

```bash
# Check for Gemini API key
docker exec clawdbot-friday env | grep GOOGLE_AI_KEY

# Should show: GOOGLE_AI_KEY=<REDACTED>
```

---

## Current Status

### ✅ Confirmed (from Context)
- SuperMemory DB exists: `/root/clawdbots/data/supermemory.db`
- SUPERMEMORY_API_KEY configured: `sm_9C4Awqczh...`
- Per-bot namespace prefixes: friday, matt, jarvis
- All 3 bots verified with Supermemory active
- Docker volume mounts configured correctly

### ⏳ Pending Verification
- Graph relationships (Updates, Extends, Derives) functional
- Temporal grounding (dual timestamps) working
- Cross-bot memory sharing operational
- Performance metrics within targets

### 🔒 Blocked
- VPS SSH access timing out (use Hostinger hPanel console)
- Can't run verification tests until VPS accessible

---

## Next Steps (When VPS Accessible)

1. **SSH into VPS**: `ssh root@76.13.106.100`
2. **Verify database exists**: `ls -la /root/clawdbots/data/supermemory.db`
3. **Test basic access**: Use Method 2 (SQLite) or Method 3 (Bot interaction)
4. **Run graph relationship tests**: Execute test cases for Updates, Extends, Derives
5. **Verify temporal grounding**: Check documentDate vs eventDate
6. **Measure performance**: Time searches and graph traversals
7. **Document findings**: Update this guide with actual results

---

## References

- **SuperMemory Deep Dive**: `ARCHITECTURAL_CONTEXT_INTEGRATION.md` (Section: SuperMemory Deep Dive - Iteration 3)
- **Docker Compose**: `docker-compose.clawdbots.yml` (line 62: shared volume mount)
- **Environment Variables**: `docker/clawdbot-gateway/.env` (line 29: SUPERMEMORY_API_KEY)
- **User Context**: User-provided SuperMemory documentation (graph relationships, temporal grounding)
- **Infrastructure Status**: All 3 bots confirmed with SuperMemory active

---

**Last Updated:** 2026-02-03 (Iteration 3)
**Status:** Verification procedures ready, pending VPS access
