# Master Setup - Complete System

This directory contains the complete secure automation system with dual backups and embedded learnings.

## 🎯 Quick Start

### 1. Local Windows Setup (Run First)
```powershell
cd c:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\scripts
.\setup_local_automation.ps1
```

This will:
- ✅ Grant agent full automation access
- ✅ Install Puppeteer, Python libs, C++ tools
- ✅ Setup scheduled backups (every 6 hours)
- ✅ Run initial backup
- ✅ Create authorization file

### 2. VPS Setup (Transfer & Run)
```bash
# On VPS:
cd /root/clawd/scripts

# Transfer all scripts
scp user@windows-machine:/c/Users/lucid/OneDrive/Desktop/Projects/Jarvis/scripts/*.sh .
chmod +x *.sh

# Set environment
export TELEGRAM_BOT_TOKEN="<real_token>"
export MAIN_CHAT_ID="<id>"
export FRIDAY_CHAT_ID="<id>"
export JARVIS_CHAT_ID="<id>"

# Run gateway fix
./ralph_wiggum_secure_gateway_fix.sh

# Run task extraction & execution
./ralph_wiggum_secure_tasks.sh
```

### 3. Embed Learnings (Local)
```bash
cd c:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\scripts
python embed_learnings.py
```

This creates:
- `.claude/learnings/YYYYMMDD/` with all lessons
- Individual markdown files per learning
- INDEX.md for easy reference
- Stores in OPC memory system

---

## 📦 Scripts Overview

### Local Windows Scripts

| Script | Purpose | Frequency |
|--------|---------|-----------|
| `setup_local_automation.ps1` | Grant full automation access | One-time |
| `local_backup_system.ps1` | Backup critical paths | Every 6 hours (scheduled) |
| `embed_learnings.py` | Extract & embed session learnings | After major changes |

### VPS Scripts

| Script | Purpose | Frequency |
|--------|---------|-----------|
| `ralph_wiggum_secure_gateway_fix.sh` | Fix gateway config persistence | Until working |
| `ralph_wiggum_secure_tasks.sh` | Extract & execute all tasks | Continuous loop |
| `vps_backup_system.sh` | Backup VPS critical paths | Every 6 hours (cron) |

### Coordination

Both systems sync backups:
- **Local → VPS**: `scp local_backup/ root@vps:/root/clawd/backups/from_windows/`
- **VPS → Local**: `scp vps_backup/ user@windows:/c/Users/lucid/Backups/from_vps/`

---

## 🔒 Security Features

### ✅ Implemented
- SHA256 checksums on all backups
- Command sanitization (no `;|$()`)
- Dangerous command blocking
- Timeout enforcement (300s)
- Failure detection (pause after 3)
- Credential validation
- File permissions (600/700)
- WebSocket loopback binding

### ✅ Backup Strategy
- **Dual backups** (local + VPS)
- **Bidirectional sync**
- **Keep last 10** (auto-cleanup)
- **Checksum verification**
- **No downtime** (live backups)

### ✅ Authorization
- Full local access granted via `local_automation_auth.json`
- No confirmation required for agent actions
- Unrestricted downloads, execution, file operations

---

## 📚 Key Learnings Embedded

1. **Gateway Config Persistence**
   - Problem: Gateway strips unknown keys on startup
   - Fix: WebSocket binding + RPC config.apply
   - Location: `.claude/learnings/gateway_config_persistence.md`

2. **Backup Strategy**
   - Dual system: local + VPS with checksums
   - Location: `.claude/learnings/backup_strategy.md`

3. **Security Requirements**
   - Command sanitization, timeout enforcement
   - Location: `.claude/learnings/security_requirements.md`

4. **Ralph Wiggum Pattern**
   - Continuous loop: task → complete → next → repeat
   - Location: `.claude/learnings/ralph_wiggum_pattern.md`

5. **Task Extraction**
   - Scan ALL Telegram channels + voice transcripts
   - Location: `.claude/learnings/telegram_task_extraction.md`

6. **Agent Coordination**
   - VPS + local separation with sync points
   - Location: `.claude/learnings/coordination_between_agents.md`

---

## 🔄 Ralph Wiggum Loop Explained

**Concept**: Don't stop after one task - keep iterating until user says stop.

**Flow**:
```
1. Extract all tasks from Telegram + voice
2. Execute Task 1
3. Mark complete → Find Task 2
4. Execute Task 2
5. Mark complete → Find Task 3
...
N. All done → Re-scan for new tasks (wait 60s)
∞. Repeat forever
```

**Stop Condition**: User says "stop" or Ctrl+C

**Benefits**:
- Handles open-ended goals
- Discovers new work during execution
- Maintains momentum
- Auto-resumes when new tasks arrive

---

## 🚀 What's Running Now

### Local (Windows)
- ✅ Scheduled backup task (every 6 hours)
- ✅ Agent has full automation access
- ✅ Puppeteer, Python, C++ libs installed

### VPS (After Setup)
- 🔄 Gateway fixed and running
- 🔄 Task extraction loop running
- 🔄 VPS backup scheduled (cron)

### Sync
- 📡 Local backups → VPS
- 📡 VPS backups → Local

---

## 📊 Monitoring

### Check Local Status
```powershell
# Backup status
Get-Content $env:USERPROFILE\.claude\agent_status.json | ConvertFrom-Json

# View backups
ls C:\Users\lucid\Backups

# View learnings
ls .claude\learnings
```

### Check VPS Status
```bash
# Task list
cat /root/clawd/MASTER_TASK_LIST.md

# Completed tasks
tail -f /root/clawd/COMPLETED_TASKS.md

# Gateway status
curl http://127.0.0.1:8080/health

# Backups
ls -lt /root/clawd/backups
```

---

## 🛠️ Troubleshooting

### Gateway keeps wiping config
- ✅ **Fixed**: Use RPC, not file editing
- See: `ralph_wiggum_secure_gateway_fix.sh`

### Backups not syncing
- Check SSH keys: `ssh-copy-id user@host`
- Set env vars: `VPS_HOST`, `VPS_USER`, `WINDOWS_HOST`, `WINDOWS_USER`

### Task loop stopped
- Check logs: `/root/clawd/COMPLETED_TASKS.md`
- Restart: `./ralph_wiggum_secure_tasks.sh`

### Agent needs permission
- Local: Already granted full access
- VPS: Agent has root access via `clawdbot` account

---

## 🎓 Next Steps

1. ✅ **Setup complete** - All scripts ready
2. 🔄 **VPS agent** - Follow [AGENT_INSTRUCTIONS_SECURE.md](AGENT_INSTRUCTIONS_SECURE.md)
3. 📚 **Review learnings** - Read `.claude/learnings/INDEX.md`
4. 🚀 **Start loop** - Agent extracts & executes all tasks
5. 💤 **Sit back** - System runs autonomously until you say stop

---

**Status**: ✅ Ready to deploy
**Last Updated**: 2026-01-28
**Session**: Gateway fix + dual backup + learnings embedded
