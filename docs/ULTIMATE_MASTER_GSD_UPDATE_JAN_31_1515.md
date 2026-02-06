# ULTIMATE MASTER GSD (Single Source of Truth)

Last Updated: 2026-02-02
Mode: RALPH WIGGUM LOOP (Continuous Improvement)
Status: ACTIVE

IMPORTANT: This is the ONE and ONLY GSD. All previous GSD files were consolidated and removed by request.

---

## CRITICAL CONSTRAINTS (DO NOT VIOLATE)
1. NEVER delete servers, VPS, bots, APIs, SOUL files, configs, or infrastructure.
2. ONLY improve. No destructive resets. No wiping VPS.
3. Weigh integration value: If current solution is more effective, keep it.
4. Do not overlap configs unless new one is equal or better utility.
5. Do not break dependencies or functionality.
6. Do NOT commit secrets to GitHub or any repo.

---

## CURRENT TEAM ARCHITECTURE
- Matt = COO Orchestrator (GPT-5.2 via Codex CLI only, no API key)
- Friday = CMO (Claude Opus 4.5)
- Jarvis = CTO/CFO (xAI Grok API)

Roles:
- Matt: triage, routing, ops, budget, multi-agent orchestration
- Friday: brand voice, marketing, content governance
- Jarvis: infrastructure, automation, technical execution

---

## LIVE SYSTEM STATUS
VPS: 76.13.106.100 (public) / 100.124.254.81 (Tailscale)
Bots:
- Friday: running (single instance)
- Matt: running (single instance)
- Jarvis: running (single instance, CONVERSATIONAL mode)

Known log issues:
- Matt: older 409 conflict errors (resolved by single-instance process)
- Jarvis: transient Telegram 502 errors (Bad Gateway) - retry logic handles this
- Matt: log shows "No API key for openai" (can ignore; Codex CLI does not require OpenAI API key)

Recent Fixes (2026-02-02):
- ✅ Jarvis xAI model fixed: changed from grok-3-turbo/grok-4.1 to grok-4 (valid model)
- ✅ All 3 bots verified running: Friday (Claude), Matt (Codex CLI), Jarvis (Grok)
- ✅ FULL LIFE CONTROL SYSTEM DEPLOYED (2026-02-02):
  - ClawdJarvis now conversational (natural language, not just commands)
  - Remote control server on Windows (port 8765, auto-start on boot)
  - Browser-Use with real Chrome (CDP port 9222, Google-trusted)
  - Google account logged in with persistent session
  - Commands: /do, /email, /calendar, /drive, /deploy, /firebase, /wallet, /phone
  - Files: life_control_commands.py, browser_agent.py (CDP version), remote_control_server.py

---

## AUTONOMY + CREATIVITY PRIORITY
Primary priority is autonomy, creativity, and utility.
Security/regulatory is secondary, but basic guardrails still apply to protect uptime.

---

## MEMORY & SUPERSTRUCTURE (SUPERMEMORY MODEL)
Graph relationships:
- Updates (state mutation)
- Extends (enrichment)
- Derives (inference)

Tags:
- company_core
- technical_stack
- marketing_creative
- crypto_ops
- ops_logs

Static vs Dynamic context:
- Static: mission, identity, roles
- Dynamic: current projects, mood, active tasks

Temporal reasoning:
- documentDate vs eventDate

---

## HEARTBEAT ENGINE
- Jarvis: 5-15 min
- Matt: 1 hr
- Friday: 4-6 hr

Use HEARTBEAT_OK when no action needed (no spam).

---

## HANDOFF PROTOCOL
- Matt triages and routes tasks to Jarvis or Friday
- Input filtering on handoffs (strip logs/tool outputs)
- Friday can interject on high-risk commands

---

## TAILSCALE + DESKTOP ACCESS
Tailnet status:
- Local desktop (kr8tiv): 100.102.41.120 (online)
- VPS (srv1302498-1): 100.124.254.81 (online, active)
- VPS (clawdbot-vps): 100.66.17.93 (offline)
- Android phone: 100.88.183.6 (for ADB control)

SSH access from VPS to desktop:
- Key generated on VPS: /root/clawdbots/keys/jarvis_id_ed25519
- Key added to C:\Users\lucid\.ssh\authorized_keys
- Still failing auth for user "lucid" from VPS

NEXT REQUIRED STEP (needs admin):
- Add VPS key to C:\ProgramData\ssh\administrators_authorized_keys
- Set correct ACLs

---

## LIFE CONTROL SYSTEM (NEW 2026-02-02)

### Architecture
```
Telegram → ClawdJarvis (VPS) → Remote Control Server (Windows) → Chrome/Computer
                                      ↓
                              Browser-Use + Real Chrome (CDP)
                                      ↓
                              Google Services (logged in)
```

### Components
| Component | Location | Port | Status |
|-----------|----------|------|--------|
| ClawdJarvis (conversational) | VPS | Telegram | Running |
| Remote Control Server | Windows | 8765 | Running |
| Chrome with Jarvis Profile | Windows | 9222 (CDP) | Running |
| Browser-Use Agent | Windows | - | Available |

### Key Files
- `core/automation/browser_agent.py` - LLM browser automation via real Chrome CDP
- `core/automation/remote_control_server.py` - HTTP API for VPS access
- `bots/shared/computer_capabilities.py` - VPS client for remote control
- `bots/shared/life_control_commands.py` - Telegram command handlers
- `bots/clawdjarvis/clawdjarvis_conversational.py` - Natural language bot

### Persistent Sessions
- Chrome profile: `C:\Users\lucid\.jarvis\chrome_profile`
- Google accounts: logged in (Gmail, Calendar, Drive, Cloud, Firebase)
- Session survives reboots

### Startup (Windows Boot)
- `C:\Users\lucid\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\jarvis_remote_control.vbs`
- Starts Chrome with debugging port + remote control server

### Available Commands (via Telegram)
- `/do <anything>` - Natural language control
- `/email [request]` - Gmail operations
- `/calendar [request]` - Calendar management
- `/drive [request]` - Drive/Docs/Sheets
- `/deploy [request]` - Website deployment
- `/firebase [request]` - Firebase/Cloud
- `/wallet [request]` - Solana wallet
- `/phone [command]` - Android control
- Or just talk naturally: "check my email", "what's on my calendar"

---

## CONSOLIDATED TASK INDEX (ACTIVE)

### HIGH PRIORITY
1. ~~Friday Email AI Bot~~ - REMOVED per user request (2026-02-02)

2. Sentiment Reports Investigation
   - Status: DONE (2026-02-02)
   - Fixed: keys.json xAI format (string→dict), added XAI_API_KEY to .env
   - Reports now generating and posting to Telegram

3. Twitter OAuth Fix
   - Status: DONE (2026-02-02)
   - Fixed client_secret mismatch between .env and keys.json
   - OAuth2 tokens refreshed for @Jarvis_lifeos
   - Posting capability verified

### MEDIUM
- Review last 48 hours of messages (IN PROGRESS)
- UI for livestream (BLOCKED - need details)

### COMPLETED
- Twitter OAuth (DONE 2026-02-02) - @Jarvis_lifeos tokens refreshed, posting verified
- VPS ClawdBots Fixed (DONE 2026-02-02) - Jarvis model updated to grok-4
- Sentiment Reports (DONE 2026-02-02) - keys.json + XAI key fix
- Bags.app Token Report (DONE)
- Skills Installation (DONE)
- Supermemory Config (DONE)
- Whisper Voice Transcription (DONE)
- Full Life Control System (DONE 2026-02-02):
  - ✅ Browser-Use installed with real Chrome CDP connection
  - ✅ Remote control server on Windows (Tailscale accessible)
  - ✅ Conversational ClawdJarvis (natural language intent detection)
  - ✅ Google account logged in (Gmail, Calendar, Drive, Cloud, Firebase)
  - ✅ Auto-start on Windows boot (VBS + batch script in Startup folder)
  - ✅ Life control commands: /do, /email, /calendar, /drive, /deploy, /firebase, /wallet, /phone

---

## DEBUGGING LESSONS (DO NOT FORGET)
1. 409 Conflicts = multiple bot instances. Fix by pkill before start.
2. Use absolute paths when starting bots.
3. Matt uses Codex CLI; no OpenAI API key required.
4. Group Privacy must be disabled for all bots.
5. Logs at /root/clawdbots/logs/

---

## GRU-INSPIRED ENHANCEMENTS
- Multi-agent spawning for parallel tasks
- Personal Knowledge Graph
- Self-healing diagnostics
- Action confirmation system
- Admin allowlist controls
- Morning briefings
- MCP plugin extensibility
- SQLite local storage

---

## N8N INTEGRATION (OPTIONAL)
- Use n8n for deterministic workflows
- OpenClaw for ad-hoc reasoning
- Integrate n8n skill for agent-controlled automation

---

## REMOTE LOG MONITORING
- Control UI via Tailscale (port 18789)
- Docker CLI logs
- clawdbot-logs skill
- Gotify/Uptime Kuma alerts

---

## SELF-IMPROVEMENT LOOP (AUTONOMOUS KAIZEN)
- Correction Loop (Updates)
- Strategy Loop (Weekly Synthesis)
- Capability Loop (Skill acquisition)
- Cohesion Loop (shared awareness)

---

## MEMORY EXPLOSION PREVENTION
- Updates relationship (state mutation)
- Static/Dynamic separation
- /compact routine
- Temporal decay filters

---

## JARVIS TOOLSET (RECOMMENDED)
- linux-service-triage
- process-watch
- clawdbot-diagnostics
- docker/pm2
- tailscale

---

## AGENT NOTES / HANDOFFS
Track all inter-agent decisions here:
- Date:
- Agent:
- Action:
- Outcome:

---

## DO NOT DELETE / REPLACE LIST
- SOUL files
- IDENTITY.md
- BOOTSTRAP.md
- active_tasks.json
- llm_client.py
- start_bots.sh
- VPS infrastructure

---

## RUN LOOP (Ralph Wiggum)
Always iterate:
1. Check bots + logs
2. Fix errors
3. Update GSD
4. Add skills
5. Test with real prompts
6. Repeat

---

# UNIFIED GSD - NEW ADDITIONS FROM BOTCONTEXT.MD

## N8N INTEGRATION (NEW)

### Controlling n8n FROM OpenClaw Agents
The Power Move: You can control n8n FROM your OpenClaw agent.
By enabling the n8n skill, agents can:
- Manage workflows
- Check execution status
- Trigger automations via API

| Feature | OpenClaw (The Agent) | n8n (The Pipeline) |
|---------|----------------------|--------------------|
| Trigger | Natural Language: "Check server status" | Event-Based: Webhook, Schedule, Email |
| Logic | Probabilistic: LLM decides HOW to solve | Deterministic: Steps execute exactly as defined |
| Use Case | Ad-hoc tasks, research, dynamic decisions | Repeatable, high-volume business processes |

### n8n Setup Checklist
- [ ] Provision VPS: Ubuntu 24.04, 2+ vCPU, 4GB+ RAM
- [ ] Install via Docker Compose or 1-Click Template
- [ ] Configure Reverse Proxy (Traefik/NGINX) with Let\'s Encrypt SSL
- [ ] Connect via OpenClaw n8n skill to bridge agent with automation pipeline

---

## REMOTE LOG MONITORING (NEW)

| Method | Use Case | Setup Requirement |
|--------|----------|-------------------|
| Control UI via Tailscale | Daily overview & session tracking | Tailscale + Web Browser |
| Docker CLI | Diagnosing crashes (e.g., Jarvis startup errors) | SSH Access |
| clawdbot-logs Skill | Quick health checks via Chat | Skill Installation |
| Gotify/Uptime Kuma | Receiving alerts while sleeping | External Service |

### Native Control UI Access
- Port: 18789 (default)
- NEVER expose to public internet
- Access via Tailscale: http://[VPS-Tailscale-IP]:18789/?token=YOUR_TOKEN

### Docker Logs Command
```
docker logs -f --tail 100 <container_name>
```
- -f: Follow in real-time
- --tail 100: Last 100 lines

---

## SELF-IMPROVEMENT LOOP - AUTONOMOUS KAIZEN (NEW)

### The Four Loop Types
| Loop Type | Frequency | Action | Technical Component |
|-----------|-----------|--------|---------------------|
| Correction | Real-time | Update Memory | Updates relationship replaces old facts |
| Strategy | Weekly | Derive Insights | weekly-synthesis skill aggregates logs into rules |
| Capability | On-Demand | Install Skills | clawdhub CLI fetches new tools from registry |
| Cohesion | Continuous | Shared Context | requireMention: false allows agents to learn from team chat |

### 1. Correction Loop (Real-Time)
Trigger: Jarvis deploys container, fails due to port conflict
Self-Improvement Way:
1. Jarvis runs diagnostics
2. Writes to technical_stack using Updates relationship
3. Next deployment: Jarvis queries memory, sees update, runs port check first

### 2. Strategy Loop (Weekly - Matt)
Cron job weekly-synthesis (Sunday 08:00)
1. Ingest logs
2. Pattern recognition
3. Derive rule into company_core
4. Friday enforces

### 3. Capability Loop (On-Demand)
1. Identify missing skill
2. Query registry
3. Propose install
4. Install after approval

### 4. Cohesion Loop (Continuous)
Agents overhear each other in Telegram
Example: Jarvis posts cost spike alert, Friday updates own constraints

---

## FRIDAY ANTI-HALLUCINATION CONFIG (NEW)

| File | Hallucination Trigger | Defense Mechanism |
|------|------------------------|------------------|
| SOUL.md | People Pleasing | Explicit instruction: accuracy over agreeableness |
| IDENTITY.md | Domain Drift | Reject technical code from Matt; reject ad copy from Jarvis |
| BOOTSTRAP.md | Context Amnesia | Mandatory log reading on startup |
| Supermemory | False Memories | Verify claims against memory tags |

### Trust but Verify Directive
1. No silent assumptions
2. If data missing, state "Data Missing"
3. Fact-check against marketing/technical tags

---

## MEMORY EXPLOSION PREVENTION (NEW)

| Strategy | Mechanism | Implementation |
|----------|-----------|----------------|
| Mutation | Updates Relationship | Overwrites old facts instead of stacking duplicates |
| Separation | User Profiles | Splits always-known facts from searchable history |
| Compression | /compact Routine | Summarizes session logs into dense narratives |
| Hygiene | Input Filtering | Strips chat history during handoffs |
| Relevance | Temporal Decay | Filters out obsolete vectors |

Daily Log Rotation:
- memory/YYYY-MM-DD.md = daily logs
- MEMORY.md = curated long-term facts

Clean Slate Protocol:
- Use /new when task is distinct
- Pass only structured Task Brief

---

## JARVIS SERVER FIXING TOOLSET (NEW)

Diagnostics:
- linux-service-triage
- process-watch
- clawdbot-diagnostics
- uptime-kuma

Remediation:
- Shell access
- docker/portainer
- pm2
- npm-proxy

Network:
- tailscale
- sysadmin-toolbox

Install:
```
npx clawdhub@latest install linux-service-triage process-watch docker pm2 tailscale
```

---

## JARVIS SOLANA TRADING STACK (NEW)

| Skill/Feature | Role |
|--------------|------|
| xai | Grok 4.1 decision logic |
| search-x | Sentiment signals |
| Shell | Executes Solana CLI |
| dexter | Financial research |
| gotify | Alerts |

Lethal Trifecta Warning:
Shell + Memory + Autonomy = HIGH RISK
Use hot wallet only

---

## POLLING BLOCK DIAGNOSTIC (NEW)

Symptom: Bot exits with Code 0 immediately

Check:
```
tail -n 20 /root/clawdbots/clawdjarvis_telegram_bot.py
```

Correct block:
```
if __name__ == "__main__":
    bot.infinity_polling()
```

Empty file check:
```
wc -l /root/clawdbots/clawdjarvis_telegram_bot.py
```

---

## FRIDAY HANDOFF CAPABILITIES (NEW)

| Feature | Friday Action | Tech Component |
|---------|--------------|----------------|
| Routing | Direct tasks to Matt/Jarvis | handoffs=[agent_list] |
| Sanitization | Clean context | input_filter |
| Oversight | Pause for approval | on_handoff callback |
| Reporting | Summaries | RunConfig.nest_handoff_history |

---

## FRIDAY AUDIT TOOLKIT (NEW)

| Audit Type | Method | Implementation |
|-----------|--------|----------------|
| Live Oversight | Passive Listening | requireMention:false |
| Retroactive | Supermemory Query | query technical_stack + marketing_ops |
| Scheduled | Heartbeat Review | 30-60 min loop |
| Security | Log Analysis | clawdbot-logs skill |

Log anomalies:
- Commands executed while asleep
- Failed auth attempts
- Forbidden commands

---

## VECTOR + GRAPH HYBRID RETRIEVAL (NEW)

| Step | Component | Action | Result |
|------|-----------|--------|--------|
| 1 | Vector Store | Find similar concepts | Retrieves old + new facts |
| 2 | Graph Store | Updates relationship | Invalidates obsolete facts |
| 3 | Graph Store | Extends relationship | Enrich context |
| 4 | Context | Inject final data | Accurate answer |

---

## KEY LOCATIONS (PATHS ONLY — NO SECRETS)
Windows (found):
- C:\Users\lucid\.env
- C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\.env
- C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\bots\twitter\.oauth2_tokens.json
- C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\bots\twitter\.env
- C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\lifeos\config\.env
- C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\web_demo\.env
- C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\tg_bot\.env
- C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis-clean\config\environments\development.env
- C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis-clean\config\environments\staging.env
- C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis-clean\config\environments\production.env
- C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis-by-Kr8tiv-Website-main\.env
- C:\Users\lucid\Continuous-Claude-v3\opc\.env
- C:\Users\lucid\.codex\auth.json (Codex CLI auth exists)

WSL: search timed out (WSL not responding to commands). Need to reattempt once WSL is responsive.

---
## LIVE OPS UPDATE (2026-02-02)
- Telegram monitoring tool missing: scripts/telegram_fetch.py not found in repo. Need to install/restore telegram_dl helper or add script.
- Jarvis model updated to grok-4.1 in /root/clawdbots/llm_client.py; Jarvis restarted to apply.
- Recent Jarvis errors (grok-3-turbo 404) were from pre-restart logs; watch for new errors after restart.
- Matt running on GPT-5.2 Codex CLI; no OpenAI API key warning in recent logs.

### Telegram Monitoring Plan
- Restore telegram_fetch utility (telethon-based) in scripts/.
- Verify setup with: `python scripts/telegram_fetch.py setup`
- Then: list chats, unread, recent from ClawdBots group

### Do-Not-Delete Confirmation
- No servers/VPS/bot configs deleted. Only improvements.

## TELEGRAM MONITORING TOOL (RESTORED)
- Added scripts/telegram_fetch.py (Telethon-based)
- Uses TELEGRAM_API_ID / TELEGRAM_API_HASH from env or .env
- Stores session at ~/.telegram_dl/session
- Commands: setup, list, recent, search, unread, send

Next: run `py -3 scripts/telegram_fetch.py setup` and log in once to create session.

## TELEGRAM MONITORING BLOCKER (2026-02-02)
- TELEGRAM_API_ID / TELEGRAM_API_HASH not found in any local .env or config.
- telegram_fetch.py cannot run without these.
- Action: locate creds (likely in WSL env or external secrets) and export to env/.env.
- WSL commands are hanging; WSL reset pending.

## ERROR-BASED FIXES (2026-02-02)
- Matt 409 conflicts traced to webhook/getUpdates overlap. Cleared Matt webhook via Bot API; no new 409s after 02:52.
  Command: deleteWebhook?drop_pending_updates=true (token read from /root/clawdbots/tokens.env)
- Jarvis restarted; grok-3-turbo errors are historical. Current model set to grok-4 in llm_client.py (grok-4.1 was invalid).
- Friday stable; heartbeats normal.

## LOG WATCHER (NON-STOP)
- Added scripts/log_watch.py (tails bot logs every 5 min)
- Deployed to VPS: /root/clawdbots/log_watch.py
- Running via nohup, logging to /root/clawdbots/logs/log_watch.log

## Responsiveness Fix (2026-02-02)
- Increased LLM client retries to 4 and timeouts (default 90s, OpenAI 180s) in /root/clawdbots/llm_client.py.
- NOTE: change applies on next bot restart (no restart performed).
- Webhooks cleared for all bots to reduce 409 conflicts.

---

## CRITICAL NON-NEGOTIABLES (2026-02-02)
- DO NOT delete bots, servers, configs, SOUL files, or VPS data. Improve only.
- Never wipe the VPS.
- Never commit secrets to GitHub or any repo.
- Weight integration value: if current solution is equal/better, keep it untouched.
- Before changing anything, confirm it is not already done or improved.

## MODEL LOCK (AUTHORITATIVE)
- Matt: GPT-5.2 via Codex CLI ONLY (no OpenAI API key dependency)
- Friday: Claude Opus 4.5
- Jarvis: xAI Grok 4.1 (fallback chain allowed)

## NOTEBOOKLM GUIDANCE (SOURCE: USER-PASTED SUMMARY)
- Telegram 409 conflicts = multiple polling instances. Fix: ensure single instance per bot.
- Use retry/backoff and CLI skills where possible; enable model fallback when provider fails.
- Grok model ID updates: use Grok 4.1 primary, fallback to stable model if 404s.
- HEARTBEAT_OK token to keep bots silent unless action is required.
- Monitor via Tailscale + internal diagnostics (no public exposure).

## TELEGRAM BOT RELIABILITY (CURRENT STATUS)
- Single instances running per bot (verify before actions).
- 409 conflicts resolved by kill duplicates + deleteWebhook + single start.
- Logs live in /root/clawdbots/logs/ on VPS.

## ACTION RULE: INTEGRATION SAFETY
- Do NOT overlap/replace a working config unless the new config has equal or higher utility.
- Preserve dependencies. No breaking changes.

