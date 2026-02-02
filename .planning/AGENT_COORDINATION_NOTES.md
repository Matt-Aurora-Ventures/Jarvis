# Agent Coordination Notes
**Created:** 2026-02-01
**Purpose:** Shared notes between Claude, GPT, and all sub-agents
**Status:** RALPH WIGGUM LOOP ACTIVE

---

## CRITICAL RULES
1. **NEVER commit secrets to GitHub**
2. **NEVER delete servers/VPS/APIs - only improve**
3. **Weight integration value before replacing anything**
4. **Check if task is already done before implementing**

---

## CURRENT STATUS (Updated: 2026-02-01 19:40 UTC)

### VPS: 76.13.106.100
- **Bots:** Friday, Matt, Jarvis running on /root/clawdbots/
- **Tailscale:** v1.94.1 installed (needs verification)
- **Logs:** /root/clawdbots/logs/

### Local: Windows Desktop
- **UNIFIED_GSD:** .planning/milestones/v2-clawdbot-evolution/phases/09-team-orchestration/UNIFIED_GSD.md (60K+ lines)
- **GSD Files:** Being consolidated (duplicates being deleted)

---

## NOTEBOOKLM TOP 5 FEATURES TO IMPLEMENT

From: https://notebooklm.google.com/notebook/db170276-73c5-409d-8f8b-c78ea4e71739

### 1. Moltbook Integration (All Agents)
- Enable `moltbook` skill for peer-to-peer learning
- Agents learn from other agents on the "front page of the agent internet"
- Jarvis joins m/bugtracker for self-debugging
- Friday observes trending topics for viral meta-narratives

### 2. Graph-Based Sleep-Time Compute (Matt)
- Configure Supermemory `Derives` relationship
- Run nightly routine to analyze logs and generate new knowledge
- Auto-update SOUL.md files based on patterns
- Example: Infer "Client X prefers short sentences" from behavior

### 3. Campaign Orchestrator (Friday)
- Add `campaign-orchestrator` and `content-repurposing` skills
- Auto-generate email sequences from strategy docs
- Atomize content into LinkedIn, Twitter, ads
- Create ad variants mapped to buyer personas

### 4. Self-Healing Skill Acquisition (Jarvis)
- Authorize `skills-search` and `npm install` without approval
- When blocked, auto-search ClawdHub registry
- Install missing tools, update TOOLS.md, execute
- Example: Missing seo-audit → auto-install → run

### 5. Proactive Heartbeat with Intent Intelligence
- Jarvis: 10-minute heartbeat with auto-restart on error spikes
- Friday: 1-hour heartbeat with competitor monitoring
- Matt: 30-minute heartbeat for strategy synthesis
- Create "Whiteboard Environment" where agents react to each other

---

## AGENT HANDOFFS

| Agent | Last Action | Next Action | Notes |
|-------|-------------|-------------|-------|
| Claude (Main) | Queried NotebookLM | Adding features to GSD | Coordinating with GPT |
| Debug Agent | Checking VPS | Report status | a91c47e |
| Spark Agent | Deleting duplicate GSDs | Confirm deletions | af9393c |
| Scribe Agent | Consolidated GSD | Complete | Added 60K lines |

---

## FOR GPT AGENT
If you're reading this from Windsurf:
1. We've consolidated all GSD docs into UNIFIED_GSD.md
2. NotebookLM gave us 5 features to implement (above)
3. Focus on what ISN'T done yet
4. VPS access: ssh root@76.13.106.100
5. Check VPS logs before making changes

---

## COMPLETED TASKS
- [x] All 3 bots running (single instances)
- [x] PRD + GSD documents created
- [x] SOUL/IDENTITY/BOOTSTRAP files on VPS
- [x] Fix 409 conflicts
- [x] Consolidated 60K+ lines into UNIFIED_GSD.md
- [x] Added botcontext.md sections
- [x] Got NotebookLM Top 5 features

## IN PROGRESS
- [ ] Delete duplicate GSD files
- [ ] VPS bot health verification
- [ ] Add NotebookLM features to GSD

## PENDING
- [ ] Implement Moltbook skill access
- [ ] Implement proactive heartbeat (10min/1hr)
- [ ] Implement auto-skill acquisition
- [ ] Enable Tailscale computer access
- [ ] Test all bots respond correctly

---

## NOTES SECTION (Add your notes below)

### Claude Notes (2026-02-01 19:40)
- GSD consolidation complete - 60K lines
- NotebookLM query successful - got top 5 features
- Spawned debug agent for VPS check
- Spawned spark agent for duplicate deletion

### Claude Notes (2026-02-01 19:55)
- Duplicate GSD files deleted (agent af9393c complete)
- Got HEARTBEAT_OK implementation from NotebookLM
- Key insight: Use SILENCE_TOKEN pattern to prevent chatty agents
- Heartbeat code uses active_tasks.json as "whiteboard"
- 5 agents currently running in parallel

### HEARTBEAT CODE FROM NOTEBOOKLM
```python
HEARTBEAT_INTERVAL = 300  # 5 minutes
SILENCE_TOKEN = "HEARTBEAT_OK"

# In SOUL.md add:
# If no action needed, output ONLY: HEARTBEAT_OK
# If action required, output JSON action plan
```

### GPT Notes
(Add notes here when reading)

---
