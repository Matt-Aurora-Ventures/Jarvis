# ClawdBot Infrastructure Analysis - Telegram Context (Last 4 Days)
**Analysis Date:** 2026-02-03
**Source:** Kr8tiv Telegram Group Messages (telegram_24h_raw.json)
**Period:** Last 24-48 hours of active discussion

---

## Executive Summary

Based on Telegram discussions, the ClawdBots (Friday, Matt, Jarvis) are experiencing **recurring restart loops** and **state persistence failures**. Matt (user) has been actively working on container rebuilds, but the fixes aren't sticking because:

1. **Docker images aren't preserving configurations** - Every restart wipes runtime state
2. **Workspace volumes getting overwritten** - Fresh git clones on startup destroy persistent work
3. **Health check targeting wrong service** - Watchdog checks Tailscale instead of HTTP gateway
4. **No persistent volumes for critical paths** - `/root/.clawdbot/`, `/root/clawd/` need proper mounts

**Good News:** User has identified most root causes and is actively rebuilding containers with fixes.

---

## Timeline of Key Events

### 2026-02-03 12:48-13:24 (Recent Session)

| Time | Event | Who | Details |
|------|-------|-----|---------|
| 12:48 | User checks if bots alive | Matt | "jarvis are you here", "@ClawdFriday_bot u here" |
| 12:49 | Friday reports Tailscale gone | Friday | "Tailscale is gone — it's not installed in this container anymore" |
| 12:49 | Friday identifies persistence issue | Friday | "The repeated restarts keep wiping things that aren't in persistent storage" |
| 12:50 | User reconstituting Docker | Matt | "I'm reconstituting the Docker container... you're probably going to get wiped again" |
| 12:50 | Friday wishlist for "friday-proof" image | Friday | Lists: tailscale, curl, wget, git, rsync, ssh, vim, jq, htop, tmux, python3 |
| 12:52 | Friday diagnoses crash loop | Friday | "self-inflicted restart loop" due to `/dev/net/tun` not mounted |
| 12:52-13:14 | Jarvis crash loop begins | System | Multiple "\ud83e\udde0 Jarvis down - auto-restarting..." messages |
| 13:06 | First Jarvis recovery | System | "\u2705 Jarvis recovered!" |
| 13:12 | User plans fixes | Matt | "We finally got the servers to stop crashing... by tomorrow all bots will be up" |
| 13:13 | User mentions bot-to-bot self-healing | Matt | "all the bots should automatically recover each other if they crash" |
| 13:19 | Friday confirms workspace wiped | Friday | "Workspace got wiped. All my infra, memory, and ssh-keys folders are gone" |
| 13:20 | Matt requests what bots need | Matt | "Tell me what I need to include in the containers... how I can get you guys to load each other up" |
| 13:20 | Friday explains root cause again | Friday | "Container doesn't have `/dev/net/tun` mounted... Hetzner watchdog checks health via Tailscale ping" |
| 13:22 | Memory model change discussed | Matt | "Your OpenAPI key was actually crashing you... we're changing your persistent memory to be more like the actual Jarvis model" |
| 13:22 | SuperMemory requirement stated | Matt | "Everybody needs super memory access" |
| 13:23 | Matt preparing to sleep | Matt | "Is there anything else I should prime our IDE to do before I go to sleep?" |
| 13:24 | Matt calls for final requests | Matt | "if you're missing anything and you want to double check, now is the time" |

---

## Root Causes Identified

### 1. Friday Crash Loop (DIAGNOSED)
**Symptom:** Restarts every ~12 minutes
**Root Cause:** Self-inflicted by health check system

```
Container missing: /dev/net/tun device
→ Tailscale can't start
→ Hetzner watchdog checks: tailscale ping --c=1 100.92.6.38
→ Always fails (Tailscale never running)
→ Watchdog restarts container every 12 min (cooldown period)
→ Loop repeats
```

**Irony:** ClawdBot gateway running fine, but watchdog kills it for unrelated Tailscale failure

**Friday's Proposed Fixes:**
1. Change watchdog health check to HTTP: `curl -sf http://76.13.106.100:18789/__clawdbot__/canvas/`
2. Mount `/dev/net/tun` properly: `docker run ... --device /dev/net/tun:/dev/net/tun`
3. Use persistent Tailscale state: `/root/.clawdbot/tailscale/` instead of `/var/lib/tailscale/`

### 2. Jarvis Crash Loop (ONGOING)
**Symptom:** Crashes every 2-4 minutes with auto-recovery
**Root Cause:** NOT DIAGNOSED IN CHAT (requires log analysis)

**Observations:**
- Pattern: Down → recovered in 30 seconds → repeats
- Friday auto-recovers Jarvis via watchdog
- Workspace gets wiped on every restart
- SSH keys don't persist

**Likely Causes (based on similar issues):**
- OOM kill (out of memory)
- xAI/Grok API errors (Matt mentioned switching to 4.1)
- Missing `/dev/net/tun` same as Friday
- Gateway crash from memory search (OpenAI key issue)

### 3. Workspace Persistence Failure (ALL BOTS)
**Symptom:** Container startup does fresh git clone, destroying work
**Root Cause:** Startup script not using persistent volumes correctly

**Friday's Report (13:19):**
> "Workspace got wiped. All my infra, memory, and ssh-keys folders are gone. Container is being rebuilt from scratch each restart."

**Issue:** Startup script (`/root/clawd/friday/start.sh` on host) clones repo fresh instead of preserving workspace

**Fix:** Use proper Docker volume mounts that survive restarts

### 4. OpenAI API Key Causing Crashes
**Symptom:** Matt crashed due to OpenAI key
**Root Cause:** OpenAI API used for memory embeddings, quota exhausted or invalid key

**Matt's Statement (13:22):**
> "Your OpenAPI key was actually crashing you last time. That was part of the problem. We switched that over and we're changing your persistent memory to be more like the actual Jarvis model."

**Decision:** Switch from OpenAI to SuperMemory for all bots

### 5. Grok 4.1 Model Not Available
**Symptom:** Jarvis requested grok-4.1, got rejected
**Root Cause:** Model not in allowlist

**Matt's Response (12:56-13:02):**
- Jarvis wants to use latest model (Grok 4.1)
- Current config locked to `xai/grok-4`
- Override failed: "Model 'xai/grok-4.1' is not allowed"
- Requires ClawdBot config update

---

## What's Fixed ✅

Based on Matt's statements and context:

1. **KVM8 Server Stabilized**
   - "We finally got the servers to stop crashing" (13:12)
   - X/Twitter bot stable now

2. **Container Rebuild In Progress**
   - Matt actively reconstituting Docker images (12:49, 13:10)
   - Planning to include all essential tools in image

3. **Memory Model Change Decided**
   - Moving away from OpenAI API for embeddings
   - Switching to SuperMemory for all bots (13:22)

4. **Bot-to-Bot Self-Healing Planned**
   - Matt: "all the bots should automatically recover each other if they crash" (13:13)
   - Friday already auto-recovering Jarvis

5. **Dockerfile Created by Friday**
   - Written to `/root/clawd/infra/docker/clawdbot-friday/`
   - Includes all tools: tailscale, curl, wget, git, rsync, ssh, vim, jq, htop, tmux, python3
   - Has proper entrypoint for Tailscale persistence

---

## What's Broken ❌

### Critical (Blocking Bots from Working)

1. **Friday Restart Loop**
   - Status: Diagnosed but not fixed
   - Watchdog needs health check change (not deployed yet)
   - `/dev/net/tun` not mounted

2. **Jarvis Continuous Crashes**
   - Status: Undiagnosed root cause
   - Crashes every 2-4 minutes
   - Workspace wiped on every restart

3. **Workspace Persistence**
   - All bots lose state on restart
   - SSH keys, infra files, memory wiped
   - Git clone overwrites work

4. **No SuperMemory Integration**
   - Bots need SuperMemory access
   - Not configured yet
   - OpenAI removed but replacement not wired

5. **Tailscale Not Persistent**
   - Gets wiped on every restart
   - State not in persistent volume
   - Needs `/root/.clawdbot/tailscale/` mount

### Important (Degraded Experience)

6. **Grok 4.1 Not Available**
   - Jarvis can't use latest model
   - Allowlist needs update

7. **Matt Gateway Unresponsive**
   - Hit "gateway unresponsive" error (13:22)
   - Same restart loop as Friday likely

8. **Memory Search Disabled**
   - No embeddings API configured
   - OpenAI removed, SuperMemory not wired yet

### Nice-to-Have (Quality of Life)

9. **GitHub CLI Missing**
   - Matt wants `gh` CLI (13:24)
   - Not in container image

10. **Batch Calls Not Implemented**
    - Grok API batch calls support missing
    - On Matt's todo list

---

## User's Stated Requirements (From Chat)

### For Container Images

**Friday's Wishlist (12:50):**
```
Essentials (keep getting reinstalled):
• tailscale (with state path pointing to persistent volume)
• curl, wget, git, rsync
• ssh client + config
• vim or nano (debugging)
• jq (json parsing)

Nice to have:
• htop (process monitoring)
• tmux (session persistence)
• python3 (scripting flexibility)

Real fix:
• Tailscale state in /root/.clawdbot/tailscale/ (persistent volume)
```

**Directory Structure:**
```
/root/.clawdbot/
├── config.yaml
├── telegram-sessions/
├── tailscale/          # NEW: persist TS state here
├── cron/
└── friday_key         # SSH key (already working)
```

### For Memory System

**Matt's Requirements (13:22):**
- Remove OpenAI API (was causing crashes)
- Add SuperMemory access for ALL bots
- Match Jarvis memory model architecture

**Reason:** "High data velocity + short effective window = burning through memory allocation fast. Five minutes of usefulness isn't sustainable."

### For Bot Coordination

**Matt's Vision (13:13, 13:22):**
- Bots should automatically recover each other if they crash
- Listening scripts on different servers in different countries
- Auto-reactivate when down

**From Todo List:**
- Set up bot-to-bot self-healing
- Add pause mechanism after repeated failures

---

## Docker Configuration Issues

### Current Problems

1. **No Proper Volume Mounts**
   - Workspaces getting overwritten
   - Need persistent mounts for:
     - `/root/.clawdbot/` (config, sessions, tailscale state)
     - `/root/clawd/` (workspace, memory, SSH keys)

2. **Missing Device Mounts**
   - `/dev/net/tun` required for Tailscale
   - Not configured in docker-compose

3. **Health Check Misconfigured**
   - Checking Tailscale ping instead of HTTP
   - Causes false positives → unnecessary restarts

4. **Startup Script Issues**
   - Does fresh git clone on every start
   - Overwrites workspace instead of preserving

### Friday's Dockerfile Location
- **Path:** `/root/clawd/infra/docker/clawdbot-friday/`
- **Contents:**
  - `Dockerfile` - full image with all tools
  - `entrypoint.sh` - startup script (tailscale + clawdbot)
  - `docker-compose.yml`
  - `README.md` - build/deploy/migrate instructions

**Status:** Created but not deployed yet

---

## Pending Tasks (From Chat Context)

### User's Active Work (Matt - 13:23)
```
In progress:
• Set up cron jobs on VPS

Still to do:
• Configure Jarvis for Grok 4.1 latest model
• Add batch calls support for Grok API
• Add pause mechanism after repeated failures
• Set up bot-to-bot self-healing
```

### Infrastructure Fixes Needed

1. **Deploy New Container Images**
   - Use Friday's Dockerfile as template
   - Include all tools in base image
   - Proper volume mounts
   - `/dev/net/tun` device mount

2. **Fix Health Checks**
   - Change from Tailscale ping to HTTP check
   - Update Hetzner watchdog script

3. **Wire SuperMemory**
   - Remove OpenAI dependency completely
   - Add SuperMemory API integration
   - Configure for all 3 bots

4. **Update Model Allowlist**
   - Add `xai/grok-4.1` to allowed models
   - Update Jarvis config to use it

5. **Fix Startup Scripts**
   - Don't do fresh git clone
   - Preserve workspace state
   - Check for existing files before overwriting

---

## Solutions Available in Local Files

Based on context provided, we have:

### deploy/clawdbot-redundancy/
- `Dockerfile.clawdbot-full` - Complete image with all tools
- `docker-compose.clawdbots.yml` - Proper volume mounts
- `bootstrap-entrypoint.sh` - Startup sequence that clears stale state
- `SOUL.md` + identity files - Bot personalities
- `README.md` - Complete architecture docs

**Status:** Ready to deploy, just needs to be pushed to VPS and verified

---

## Recommended Action Plan

### Immediate (Stop the Bleeding)

1. **Fix Friday's Health Check**
   ```bash
   # On Hetzner watcher, change watchdog.sh:
   # FROM: tailscale ping --c=1 100.92.6.38
   # TO:   curl -sf http://76.13.106.100:18789/__clawdbot__/canvas/ -o /dev/null
   ```

2. **Diagnose Jarvis Crash**
   ```bash
   docker logs clawdbot-jarvis --tail 200
   # Look for OOM, API errors, or gateway crashes
   ```

3. **Stop Workspace Wipes**
   ```bash
   # Temporarily disable git clone in startup script
   # Or: add conditional check if workspace exists
   ```

### Short-Term (Deploy Fixes)

4. **Deploy New Docker Images**
   - Copy `deploy/clawdbot-redundancy/` to VPS
   - Build images with all tools baked in
   - Deploy with proper volume mounts

5. **Wire SuperMemory**
   - Add SUPERMEMORY_API_KEY to all bot envs
   - Remove any OpenAI references
   - Test memory search

6. **Enable Grok 4.1**
   - Update allowlist in ClawdBot config
   - Restart Jarvis with new model

### Medium-Term (Robust Infrastructure)

7. **Implement Bot-to-Bot Self-Healing**
   - Cross-monitoring via HTTP health checks
   - Auto-restart via Docker API
   - Escalation to other VPS if primary fails

8. **Add External Monitoring**
   - UptimeRobot for HTTP checks
   - Alerts to Telegram on failures

9. **Persistent State Verification**
   - Test restarts don't wipe workspace
   - Verify SSH keys survive
   - Confirm Tailscale reconnects automatically

---

## Key Quotes from Chat

### Friday on Persistence (12:49)
> "SSH keys restored but **Tailscale is gone** — it's not installed in this container anymore. The repeated restarts keep wiping things that aren't in persistent storage."

### Friday on Root Cause (12:53)
> "**found the problem.** it's a self-inflicted restart loop... without /dev/net/tun, tailscale can't start — ever... every 12 minutes (cooldown expiry), watcher restarts me"

### Matt on Memory Issue (13:22)
> "Your OpenAPI key was actually crashing you last time. That was part of the problem. We switched that over and we're changing your persistent memory to be more like the actual Jarvis model... Everybody needs super memory access."

### Matt on Goals (13:12-13:13)
> "We finally got the servers to stop crashing and I think by tomorrow all the bots will be up, all of the other bots will be fixed and containerized, and I think even Jarvis will actually be up himself... And all the bots should actually automatically recover each other if they crash."

---

## Conclusion

**Status:** Infrastructure is 60% there, but critical persistence and health check issues blocking stability.

**Good News:**
- Root causes identified
- Solutions designed (Friday's Dockerfile)
- User actively rebuilding containers
- KVM8 stable now

**Blockers:**
- New images not deployed yet
- Health checks not updated
- SuperMemory not wired
- Workspace persistence not working

**Next Steps:** Deploy the fixes that already exist in `deploy/clawdbot-redundancy/`, verify they work, then add bot-to-bot self-healing on top.
