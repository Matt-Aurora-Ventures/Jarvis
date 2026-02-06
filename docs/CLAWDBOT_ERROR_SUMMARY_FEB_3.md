# ClawdBot Infrastructure Error Summary - Feb 3, 2026

## Executive Summary
Three ClawdBot gateway containers (Friday, Matt, Jarvis) on VPS 76.13.106.100 experienced repeated crashes and recovery cycles. Root causes identified and partially resolved.

---

## Bot Configuration

| Bot | Role | Model | Port | Auth Method |
|-----|------|-------|------|-------------|
| Friday | CMO | Claude Opus 4.5 | 18789 | OAuth (Anthropic CLI) |
| Matt | COO | Codex/GPT 5.2 | 18800 | OAuth (Codex CLI) |
| Jarvis | CTO | Grok 4.1 | 18801 | XAI API Key |

---

## Root Causes Identified

### 1. OpenAI Quota Exceeded (PRIMARY - Friday crashes)
```
[memory] sync failed: Error: openai embeddings failed: 429
"You exceeded your current quota, please check your plan and billing details"
```
- **Impact**: Friday crashed repeatedly every 5-10 minutes
- **Cause**: Clawdbot's memory feature uses OpenAI embeddings by default
- **The embedded API key** (sk-jlxPcCQpNasj5uD5...) has exhausted quota
- **Fix Applied**: Removed OpenAI Whisper API key from Friday's config

### 2. Docker API Version Mismatch
```
[tools] exec failed: Error response from daemon: client version 1.41 is too old.
Minimum supported API version is 1.44
```
- **Impact**: Friday crashed when trying to use Docker from inside container
- **Cause**: Container's Docker client (v1.41) < Host daemon requirement (v1.44+)
- **Fix Applied**: Set `DOCKER_API_VERSION=1.44` environment variable

### 3. Invalid Bind Parameter (Jarvis)
```
Invalid --bind (use "loopback", "lan", "tailnet", "auto", or "custom")
```
- **Impact**: Jarvis gateway wouldn't start
- **Cause**: Start script used `--bind 0.0.0.0` instead of valid option
- **Fix Applied**: Changed to `--bind lan`

### 4. Slow Recovery Cycles
- **Impact**: Each restart takes ~2 minutes
- **Cause**: npm installs clawdbot fresh on every container start
- **Fix In Progress**: Building pre-cached Docker image `clawdbot-ready`

### 5. XAI Authentication (Jarvis)
```
⚠️ Agent failed before reply: No API key found for provider 'xai'
```
- **Cause**: XAI_API_KEY not passed to container
- **Fix Applied**: Added `-e XAI_API_KEY=...` to docker run command

### 6. Windows CRLF Line Endings
```
/root/clawd/friday/start.sh: line 2: $'\r': command not found
```
- **Cause**: Scripts created on Windows had CRLF endings
- **Fix Applied**: `sed -i 's/\r$//' <script>`

---

## Recovery Infrastructure Deployed

### Layer 1: Docker Restart Policy
- All containers have `--restart=always`
- Docker daemon auto-restarts crashed containers

### Layer 2: VPS Cron Watchdog (every 1 minute)
- Location: `/root/clawd/infra/bot-health-watchdog.sh`
- Checks HTTP health of each gateway
- Restarts unhealthy containers
- After 3 failures, triggers full container rebuild
- Sends Telegram alerts on all recovery events

### Layer 3: External Health API (port 18888)
- Endpoints: `/health`, `/recover/{bot}`, `/recover-all`, `/state`
- Allows remote health monitoring and recovery triggers
- Service: `clawdbot-health-api.service` (systemd)

### Layer 4: Windows External Monitor (every 5 minutes)
- Location: `deploy/clawdbot-redundancy/windows-external-monitor.ps1`
- Runs via Task Scheduler
- Can SSH into VPS if local watchdog fails
- Tries direct IP, falls back to Tailscale

---

## Current Status (as of 11:30 UTC)

```json
{
  "status": "healthy",
  "bots": {
    "friday": "healthy",
    "matt": "healthy",
    "jarvis": "healthy"
  }
}
```

---

## Remaining Issues

1. **Slow restarts**: Still using `node:22-slim` with npm install. Pre-built image ready (`clawdbot-ready`) but not deployed yet.

2. **Memory feature disabled**: Removed OpenAI key, but this disables useful memory/search features.

3. **OpenAI billing**: Need to either:
   - Add credits to OpenAI account
   - Configure alternative embeddings provider
   - Keep memory disabled

4. **Recovery cascade**: When watchdog restarts a bot during startup, can create restart loops.

---

## Recommended Actions

1. **Deploy pre-built image** for instant restarts (~5 seconds vs 2 minutes)
2. **Fix OpenAI billing** or configure alternative embeddings
3. **Increase watchdog grace period** during startup (currently 2 min, may need 3 min)
4. **Add health endpoint** inside containers for more accurate health checks
5. **Consider dedicated VPS resources** if memory pressure causes OOM kills

---

## Key Files

| File | Purpose |
|------|---------|
| `/root/clawd/infra/bot-health-watchdog.sh` | VPS watchdog script |
| `/root/clawd/infra/health-api-handler.sh` | Health API handler |
| `/root/.clawdbot/clawdbot.json` | Friday config |
| `/docker/clawdbot-gateway/config-matt/clawdbot.json` | Matt config |
| `/root/.clawdbot-jarvis/clawdbot.json` | Jarvis config |

---

## Timeline of Events (Feb 3, 2026)

| Time (UTC) | Event |
|------------|-------|
| ~04:54 | Friday automatic recovery failed |
| ~05:00 | Matt gateway unresponsive |
| ~05:06 | Friday down again, recovery failed |
| ~05:12 | Windows monitor detected multiple bots down |
| ~05:13 | Windows monitor SSH recovery successful |
| ~05:18 | Friday crashed again (OpenAI 429 errors) |
| ~11:17 | Identified root cause (OpenAI quota) |
| ~11:27 | Removed OpenAI key from Friday |
| ~11:29 | All 3 bots healthy |

---

## Questions for Analysis

1. Should we pay for OpenAI credits or find alternative embeddings?
2. Is Codex CLI authentication stable enough for Matt, or switch to Opus?
3. What's the acceptable downtime SLA for these bots?
4. Should bots be able to restart each other via Docker socket?
5. Is Tailscale fallback path reliable enough for external monitoring?
