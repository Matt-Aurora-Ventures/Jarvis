# Bot Deployment Checklist
**Created**: 2026-01-31 23:20 UTC
**Status**: ACTIVE - Ralph Wiggum Loop
**Purpose**: Complete deployment of all bot components

---

## 🔴 EMERGENCY P0 - Blocked on Manual Actions

### 1. Treasury Bot (@jarvistrades_bot)
**Status**: ❌ CRASHED (35 consecutive failures, exit code 4294967295)
**Root Cause**: Missing TREASURY_BOT_TOKEN environment variable
**Blocker**: USER MUST CREATE BOT TOKEN

**Steps to Fix**:
```bash
# Step 1: Create bot via Telegram @BotFather
1. Open Telegram → search "@BotFather"
2. Send: /newbot
3. Name: "Treasury Bot"
4. Username: "jarvis_treasury_bot"
5. Copy the token from response

# Step 2: Deploy to VPS
ssh root@72.61.7.126
nano /home/jarvis/Jarvis/lifeos/config/.env

# Add this line:
TREASURY_BOT_TOKEN=<paste_token_here>

# Step 3: Restart supervisor
pkill -f supervisor.py
cd /home/jarvis/Jarvis
nohup python bots/supervisor.py > logs/supervisor.log 2>&1 &

# Step 4: Verify success
tail -f logs/supervisor.log
# Look for: "Using unique treasury bot token (TREASURY_BOT_TOKEN)"
# NO MORE exit code 4294967295
# NO MORE "Conflict: terminated by other getUpdates"
```

**Success Criteria**:
- ✅ Token created and deployed
- ✅ Bot runs without crashes for 10+ minutes
- ✅ No polling conflict errors
- ✅ Treasury trading operational

---

## 🟠 HIGH PRIORITY - Deployments

### 2. @Jarvis_lifeos X Bot (Autonomous Twitter)
**Status**: ⏳ PENDING VERIFICATION
**VPS**: 72.61.7.126
**SSH Issue**: Commands timing out (investigating alternative access)

**Implementation**:
- Code: ✅ bots/twitter/autonomous_engine.py (complete)
- OAuth: ✅ bots/twitter/.oauth2_tokens.json (updated 2026-01-20)
- Supervisor: ✅ Registered as `autonomous_x` (supervisor.py:1380)
- Brand Guide: ✅ docs/marketing/x_thread_ai_stack_jarvis_voice.md

**Verification Steps**:
```bash
# Once SSH is accessible:
ssh root@72.61.7.126

# Check if autonomous_x is running
ps aux | grep autonomous_engine

# Check supervisor logs
tail -100 /home/jarvis/Jarvis/logs/supervisor.log | grep autonomous

# If not running, check supervisor status
pgrep -f supervisor.py

# Manually start if needed
cd /home/jarvis/Jarvis
python bots/twitter/run_autonomous.py
```

**Success Criteria**:
- ✅ Posts to @Jarvis_lifeos hourly
- ✅ Uses brand voice from docs/marketing/
- ✅ No OAuth errors
- ✅ Supervisor auto-restarts on crash

---

### 3. Campee McSquisherton Bot (@McSquishington_bot)
**Status**: ⏳ PENDING
**Server**: Remote (SSH details TBD by user)
**Token**: [STORED LOCALLY - NOT IN GIT]

**Required Files** (location unclear):
- `setup_keys.sh` - Key configuration script
- `run_campee.sh` - Startup script
- Bot token for @McSquishington_bot

**Deployment Steps** (when files located):
```bash
# SSH to remote server (TBD)
ssh user@remote-server

# Upload scripts
scp setup_keys.sh run_campee.sh user@remote-server:~/campee/

# Execute setup
cd ~/campee
chmod +x setup_keys.sh run_campee.sh
./setup_keys.sh

# Start bot
./run_campee.sh

# Verify running
ps aux | grep campee
```

**Success Criteria**:
- ✅ Bot responds in Telegram
- ✅ No polling conflicts
- ✅ Added to group successfully

---

### 4. ClawdMatt Bot (Marketing/PR Filter)
**Status**: ⏳ PENDING
**Code**: ✅ bots/pr_matt/pr_matt_bot.py (MVP complete)
**VPS**: 76.13.106.100 (clawdbot-gateway ready)
**Token**: NEEDS CREATION

**Steps**:
```bash
# Step 1: Create token via @BotFather
1. Open Telegram → "@BotFather"
2. Send: /newbot
3. Name: "ClawdMatt - KR8TIV PR"
4. Username: "clawdmatt_kr8tiv_bot" (or similar)
5. Copy token

# Step 2: Deploy to clawdbot-gateway VPS
ssh root@76.13.106.100

# Configure bot (method TBD - either via clawdbot or standalone)
# Option A: Via clawdbot wrapper
docker exec clawdbot-gateway clawdbot bot add clawdmatt

# Option B: Standalone deployment
# Upload pr_matt_bot.py and run directly
```

**Success Criteria**:
- ✅ Reviews messages before posting
- ✅ Filters inappropriate language
- ✅ Uses brand voice from docs/marketing/
- ✅ No token conflicts

---

### 5. ClawdFriday Bot (Email AI Assistant)
**Status**: ⏳ PENDING
**Code**: ✅ bots/friday/friday_bot.py (MVP complete)
**VPS**: 76.13.106.100
**Token**: NEEDS CREATION

**Steps**:
```bash
# Step 1: Create token via @BotFather
1. Open Telegram → "@BotFather"
2. Send: /newbot
3. Name: "Friday - Email AI"
4. Username: "friday_kr8tiv_bot" (or similar)
5. Copy token

# Step 2: Deploy (similar to ClawdMatt)
ssh root@76.13.106.100
# Deploy via clawdbot or standalone
```

**Integration Needed**:
- [ ] IMAP/SMTP connection for email inbox
- [ ] Calendar integration (future)
- [ ] Task creation (future)

**Success Criteria**:
- ✅ Categorizes emails (9 categories)
- ✅ Generates professional responses
- ✅ Uses brand voice
- ✅ Confidence scoring working

---

### 6. ClawdJarvis Bot (Main Orchestrator)
**Status**: ⏳ PENDING
**VPS**: 76.13.106.100
**Token**: NEEDS CREATION

**Steps**:
```bash
# Step 1: Create token via @BotFather
1. Open Telegram → "@BotFather"
2. Send: /newbot
3. Name: "Jarvis Orchestrator"
4. Username: "clawdjarvis_bot" (or similar)
5. Copy token

# Step 2: Deploy
ssh root@76.13.106.100
# Deploy configuration TBD
```

**Success Criteria**:
- ✅ Coordinates other bots
- ✅ No token conflicts
- ✅ Integrates with supervisor

---

## ✅ COMPLETED DEPLOYMENTS

### 7. clawdbot-gateway
**Status**: ✅ OPERATIONAL
**VPS**: 76.13.106.100
**Services**:
- Gateway: ws://127.0.0.1:18789
- Browser: http://127.0.0.1:18791/
- Heartbeat: Active

**Completed**: 2026-01-31 23:00 UTC

---

## 📋 DEPLOYMENT COORDINATION

### Token Management (CRITICAL)
**Rule**: EVERY BOT NEEDS UNIQUE TOKEN (no sharing!)

**Tokens to Create**:
1. ✅ TELEGRAM_BOT_TOKEN (main Jarvis) - EXISTS
2. ❌ TREASURY_BOT_TOKEN (@jarvistrades_bot) - **NEEDS CREATION**
3. ❌ CLAWDMATT_BOT_TOKEN - **NEEDS CREATION**
4. ❌ CLAWDFRIDAY_BOT_TOKEN - **NEEDS CREATION**
5. ❌ CLAWDJARVIS_BOT_TOKEN - **NEEDS CREATION**
6. ✅ @McSquishington_bot token - **EXISTS (location TBD)**

**Polling Conflict Prevention**:
```bash
# After creating all tokens, verify no duplicates:
cd /home/jarvis/Jarvis
python scripts/check_telegram_tokens.py

# Should show 5+ unique tokens with NO overlaps
```

---

## 🧪 TESTING PROTOCOL

### After Each Bot Deployment:
```bash
# 1. Verify bot responds
# Send /start to bot in Telegram

# 2. Check no polling conflicts
tail -100 logs/supervisor.log | grep -i "conflict\|terminated"
# Should return NOTHING

# 3. Monitor for 10 minutes
tail -f logs/supervisor.log

# 4. Check resource usage
ps aux | grep python | head -10
docker stats --no-stream  # If using containers

# 5. Verify supervisor tracking
# Check supervisor knows about the bot
```

### Integration Testing:
```bash
# Test all bots can run simultaneously
# 1. Start supervisor with all bots
# 2. Monitor for 30 minutes
# 3. Send test messages to each bot
# 4. Verify no crashes or conflicts
# 5. Check resource usage stays reasonable
```

---

## 🚨 TROUBLESHOOTING

### Exit Code 4294967295 (0xFFFFFFFF = -1)
**Cause**: Missing Telegram bot token OR polling conflict
**Fix**: Create unique token, add to .env, restart supervisor

### SSH Timeouts (72.61.7.126)
**Current Issue**: Commands running indefinitely in background
**Workarounds**:
1. Try shorter timeout: `ssh -o ConnectTimeout=5 root@72.61.7.126 "command"`
2. Use systemd/supervisor logs instead: Check local log sync
3. Alternative access: Console/web terminal if available
4. Network check: Verify VPS not under attack/high load

### Polling Conflicts
**Symptoms**: "Conflict: terminated by other getUpdates request"
**Cause**: Two bots using same token
**Fix**: Run `scripts/check_telegram_tokens.py` to identify duplicates

---

## 📊 DEPLOYMENT PROGRESS

**Total Bots**: 7
**Deployed**: 1 (clawdbot-gateway)
**Blocked**: 1 (treasury - awaiting manual token creation)
**Pending**: 5 (@Jarvis_lifeos verification, Campee, ClawdMatt, ClawdFriday, ClawdJarvis)

**Completion**: 14% (1/7)
**Target**: 100% by end of Ralph Wiggum Loop session

---

## 🎯 NEXT ACTIONS (Priority Order)

1. **USER ACTION REQUIRED**: Create TREASURY_BOT_TOKEN via @BotFather → deploy to VPS
2. **Verify @Jarvis_lifeos**: Check if autonomous_x running (once SSH accessible)
3. **Create 3 Telegram tokens**: ClawdMatt, ClawdFriday, ClawdJarvis via @BotFather
4. **Deploy clawdbot suite**: Deploy all 3 bots to clawdbot-gateway VPS
5. **Locate Campee files**: Find setup_keys.sh, run_campee.sh, deploy to remote
6. **Test all bots**: 30-minute simultaneous run, verify no conflicts
7. **Update MASTER_GSD**: Mark completions, update status

---

**Maintained By**: Ralph Wiggum Loop (Claude Sonnet 4.5)
**Last Updated**: 2026-01-31 23:20 UTC
**Next Update**: After completing any deployment or unblocking action
