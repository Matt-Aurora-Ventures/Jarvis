# Phase 09: ClawdBot Team Orchestration PRD

**Created:** 2026-02-01
**Status:** In Progress (Ralph Wiggum Loop)
**Priority:** CRITICAL

---

## Executive Summary

Transform the three ClawdBots (Friday, Matt, Jarvis) from isolated chatbots into a coordinated autonomous team with:
- **Structural Orchestration**: Dispatcher hierarchy with Friday as COO
- **Shared Memory**: Unified cognitive layer via file-based persistence
- **Heartbeat Engine**: Proactive coordination without human input
- **Security Hardening**: Mitigate the "Lethal Trifecta" risks
- **Computer Access**: Enable bots to access local machine via Tailscale/SSH

---

## Team Architecture

### Roles & Responsibilities

| Bot | Role | LLM Provider | Primary Function |
|-----|------|--------------|------------------|
| **Friday** | COO / Dispatcher | Anthropic Claude Opus 4.5 | Task triage, team coordination, budget management |
| **Matt** | Chief Growth Architect | OpenAI Codex CLI | Marketing, content, social media, growth loops |
| **Jarvis** | CTO / Infra Guard | XAI Grok | Infrastructure, shell access, technical operations |

### Hierarchy

```
         ┌─────────────┐
         │   Friday    │  (Dispatcher/COO)
         │  Claude 4.5 │
         └──────┬──────┘
                │
        ┌───────┴───────┐
        │               │
   ┌────▼────┐    ┌────▼────┐
   │  Matt   │    │ Jarvis  │
   │ Codex   │    │  Grok   │
   └─────────┘    └─────────┘
   (Marketing)    (Technical)
```

---

## Feature Requirements

### 1. Heartbeat Engine (Autonomy)

**Purpose:** Allow bots to wake up periodically and act without human input.

**Implementation:**
```python
# In each bot script
import threading
import time

def heartbeat_monitor():
    while True:
        time.sleep(300)  # 5 minutes
        # Read recent group messages
        # Check for triggers (deployment, errors, etc.)
        # Act if needed

threading.Thread(target=heartbeat_monitor, daemon=True).start()
```

**Triggers:**
- Friday: Monitor team activity, audit logs, budget alerts
- Matt: Detect CTO deployment updates → draft announcements
- Jarvis: System load alerts, error detection, auto-healing

---

### 2. Shared Memory System

**Purpose:** Prevent siloed memory where agents don't know what others did.

**File-Based Implementation (Current):**
```
/root/clawdbots/
├── MEMORY.md              # Shared context (mission, standing orders)
├── active_tasks.json      # Task queue with handoffs
├── CLAWDFRIDAY_SOUL.md   # Friday's personality/directives
├── CLAWDMATT_SOUL.md     # Matt's personality/directives
├── CLAWDJARVIS_SOUL.md   # Jarvis's personality/directives
```

**Memory Schema (active_tasks.json):**
```json
{
  "tasks": [
    {
      "id": "task-001",
      "title": "Deploy new feature",
      "assigned_to": "jarvis",
      "assigned_by": "friday",
      "status": "in_progress",
      "created_at": "2026-02-01T23:00:00Z",
      "notes": []
    }
  ],
  "handoff_log": [
    {
      "from": "friday",
      "to": "jarvis",
      "task_id": "task-001",
      "timestamp": "2026-02-01T23:00:00Z"
    }
  ],
  "last_updated": "2026-02-01T23:00:00Z"
}
```

---

### 3. Dispatcher Protocol (Friday)

**When message arrives:**
1. Friday triages intent
2. Routes to appropriate specialist:
   - Technical/Infrastructure → @ClawdJarvis_87772_bot
   - Marketing/Growth → @ClawdMatt_bot
   - Strategy/General → Handle herself

**Handoff Process:**
1. Write task to `active_tasks.json`
2. Tag the appropriate bot in Telegram
3. Monitor output for safety/quality

**SOUL Directive:**
```markdown
## Routing Rules
1. **Technical tasks** → Tag @ClawdJarvis_87772_bot
2. **Marketing tasks** → Tag @ClawdMatt_bot
3. **Strategy tasks** → Handle myself

## Before Handoff
- Write task to /root/clawdbots/active_tasks.json
- Include clear success criteria
- Monitor specialist output
```

---

### 4. Security Hardening (Lethal Trifecta Mitigation)

**The Risks:**
- **Persistence**: Bots run 24/7 with memory
- **Tools**: Shell access, file operations
- **Autonomy**: Heartbeat allows unprompted action

**Mitigations:**

#### A. Command Blocklist (Jarvis only)
```python
FORBIDDEN_COMMANDS = [
    'rm -rf /',
    'mkfs',
    ':(){ :|:& };:',  # Fork bomb
    'dd if=/dev/zero',
    'chmod -R 777 /',
]

def is_safe_command(cmd):
    for forbidden in FORBIDDEN_COMMANDS:
        if forbidden in cmd:
            return False
    return True
```

#### B. Bot Ignore List (Prevent infinite loops)
```python
BOT_USERNAMES = ['ClawdFriday_87772_bot', 'ClawdMatt_bot', 'ClawdJarvis_87772_bot']

def should_respond(message):
    # Never respond to other bots
    if message.from_user.username in BOT_USERNAMES:
        return False
    # ... other logic
```

#### C. Cost Monitoring
- Track API costs per agent
- Alert if daily spend exceeds threshold
- Auto-pause heartbeat if budget exhausted

---

### 5. Computer Access (Tailscale/SSH)

**Purpose:** Allow bots to access user's local machine for tasks.

**Setup:**
1. Tailscale VPN mesh already installed on VPS
2. Join user's desktop to same Tailscale network
3. Configure SSH keys for passwordless access

**Jarvis Capabilities:**
- Execute commands on user's machine via SSH
- Transfer files between VPS and desktop
- Run local development commands

**Security:**
- Only Jarvis has shell access
- All commands logged to audit trail
- Destructive commands require confirmation

---

### 6. Error Handling

**All bot scripts must have:**
```python
@bot.message_handler(func=lambda m: True)
async def handle_message(message):
    try:
        if not should_respond(message):
            return
        response = await llm.ask(message.text)
        await bot.reply_to(message, response)
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        # Don't crash - just log and continue
```

---

## Implementation Tasks

### Phase 9.1: Core Infrastructure
- [x] All 3 bots running on VPS
- [x] SOUL files with team hierarchy
- [x] Basic shared memory (MEMORY.md, active_tasks.json)
- [x] Group Privacy disabled for all bots
- [ ] Error handling in all bot scripts
- [ ] Bot ignore list (prevent bot-to-bot crashes)

### Phase 9.2: Heartbeat Engine
- [ ] Add heartbeat thread to Friday
- [ ] Add heartbeat thread to Matt
- [ ] Add heartbeat thread to Jarvis
- [ ] Configure trigger keywords
- [ ] Test autonomous coordination

### Phase 9.3: Dispatcher Protocol
- [ ] Update Friday's SOUL with routing rules
- [ ] Implement task handoff to active_tasks.json
- [ ] Test Friday → Matt handoff
- [ ] Test Friday → Jarvis handoff
- [ ] Monitor handoff success rate

### Phase 9.4: Security Hardening
- [ ] Add command blocklist to Jarvis
- [ ] Implement cost monitoring
- [ ] Add audit logging
- [ ] Test security boundaries

### Phase 9.5: Computer Access
- [ ] Join desktop to Tailscale network
- [ ] Configure SSH keys on VPS
- [ ] Test Jarvis → Desktop commands
- [ ] Add desktop access to Jarvis SOUL

### Phase 9.6: Testing & Validation
- [ ] Test all bots respond to mentions
- [ ] Test dispatcher routing accuracy
- [ ] Test heartbeat triggers
- [ ] Test shared memory read/write
- [ ] Load test with concurrent messages

---

## Success Criteria

- [ ] All 3 bots respond correctly to direct mentions
- [ ] Friday successfully routes tasks to specialists
- [ ] Heartbeat engine triggers autonomous actions
- [ ] Shared memory persists across bot restarts
- [ ] Security blocklist prevents dangerous commands
- [ ] Jarvis can access user's desktop via Tailscale
- [ ] No infinite bot-to-bot loops
- [ ] Error handling prevents crashes

---

## Technical Specifications

### VPS Details
- **IP:** 76.13.106.100
- **OS:** Ubuntu
- **Bot Directory:** /root/clawdbots/
- **Tailscale:** Installed (v1.94.1)

### Bot Configurations
| Bot | Token Env Var | LLM Key | Port |
|-----|---------------|---------|------|
| Friday | CLAWDFRIDAY_BOT_TOKEN | ANTHROPIC_API_KEY | N/A |
| Matt | CLAWDMATT_BOT_TOKEN | via Codex CLI | N/A |
| Jarvis | CLAWDJARVIS_BOT_TOKEN | XAI_API_KEY | N/A |

---

## References

- NotebookLM: Structural Orchestration of Autonomous Multi-Agent Systems
- OpenClaw Documentation
- Supermemory API Documentation
- Telegram Bot API
