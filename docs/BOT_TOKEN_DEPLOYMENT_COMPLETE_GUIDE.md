# Complete Bot Token Deployment Guide
**Created**: 2026-01-31 18:35 PST
**Purpose**: Deploy all 5 bot tokens to eliminate Telegram polling conflicts
**Status**: READY FOR DEPLOYMENT

---

## Overview

**Total Bots**: 5
**Tokens Created**: 5/5 ✅
**Tokens Deployed**: 1/5 (X_BOT only)
**Remaining**: 4 tokens need deployment

---

## Token Summary

| Bot | Token ID | Bot Username | Purpose | Status |
|-----|----------|--------------|---------|--------|
| 1. Treasury | `850H068106:...` | @jarvis_treasury_bot | Treasury trading notifications | ⏳ PENDING |
| 2. ClawdMatt | `8288859637:...` | @ClawdMatt_bot | Marketing filter (PR Matt) | ⏳ PENDING |
| 3. ClawdFriday | `7864180H73:...` | @ClawdFriday_bot | Email AI assistant | ⏳ PENDING |
| 4. ClawdJarvis | `8434H11668:...` | @ClawdJarvis_87772_bot | Main orchestrator | ⏳ PENDING |
| 5. X Bot Sync | `7968869100:...` | @X_TELEGRAM_KR8TIV_BOT | Sync @Jarvis_lifeos tweets | ✅ ADDED TO .ENV |

---

## DEPLOYMENT 1: TREASURY_BOT_TOKEN (P0 - CRITICAL)

### Why Critical
- **Fixes**: Exit code 4294967295 (35+ consecutive crashes)
- **Root Cause**: Missing TREASURY_BOT_TOKEN environment variable
- **Impact**: Treasury bot cannot start without this token

### Deployment Steps

**Option A: Manual Deployment** (if SSH works)
```bash
# 1. SSH to VPS
ssh root@72.61.7.126

# 2. Backup current .env
cp /home/jarvis/Jarvis/lifeos/config/.env /home/jarvis/Jarvis/lifeos/config/.env.backup-$(date +%Y%m%d_%H%M%S)

# 3. Add token to .env
nano /home/jarvis/Jarvis/lifeos/config/.env

# Add this line at the end:
TREASURY_BOT_TOKEN=850H068106:AAHoS0GKxl79nPE_2wFjkkmX_T7iXEwOyao

# Save: Ctrl+X, Y, Enter

# 4. Restart supervisor
pkill -f supervisor.py
sleep 2
cd /home/jarvis/Jarvis
nohup python bots/supervisor.py > logs/supervisor.log 2>&1 &

# 5. Verify success
tail -f logs/supervisor.log
# Look for: "Using unique treasury bot token (TREASURY_BOT_TOKEN)"
```

**Option B: Automated Deployment** (using our script)
```bash
# From local machine
bash scripts/deploy_all_bots.sh
```

### Success Criteria
- ✅ No more exit code 4294967295 errors
- ✅ No Telegram polling conflicts for 10+ minutes
- ✅ Treasury bot shows "Using unique treasury bot token" in logs
- ✅ Supervisor health check shows treasury_bot RUNNING

---

## DEPLOYMENT 2: CLAWDBOT SUITE (ClawdMatt, ClawdFriday, ClawdJarvis)

### Current Status
- ✅ **Tokens uploaded to VPS**: /root/clawdbots/tokens.env
- ✅ **Brand guidelines uploaded**: marketing_guide.md, jarvis_voice.md
- ✅ **clawdbot-gateway operational**: ws://127.0.0.1:18789
- ⏳ **BLOCKED**: Need Python bot code location to start processes

### Tokens on VPS (Already Deployed)
```bash
# Located at: /root/clawdbots/tokens.env
CLAWDMATT_BOT_TOKEN=8288859637:AAHbcATe1mgMBGKuf5ceYFpyVpO2rzXYFqH
CLAWDFRIDAY_BOT_TOKEN=7864180H73:AAHN9ROzOdtHRr5JXwliTDpMYQitGEh-BuH
CLAWDJARVIS_BOT_TOKEN=8434H11668:AAHNGOzjHI-rYwBZ2mIM2c7cbZmLGTjekJH
```

### Deployment Options

**Option A: If ClawdMatt Python code exists on VPS**
```bash
# SSH to VPS
ssh root@76.13.106.100

# Find bot code
find /opt -name "*clawdmatt*" -o -name "*clawd*bot*.py" 2>/dev/null
find /root -name "*clawdmatt*" -o -name "*clawd*bot*.py" 2>/dev/null

# If found, start with environment variable
export TELEGRAM_BOT_TOKEN=$(grep CLAWDMATT_BOT_TOKEN /root/clawdbots/tokens.env | cut -d= -f2)
python3 /path/to/clawdmatt_bot.py

# Repeat for ClawdFriday and ClawdJarvis
```

**Option B: If code is in local recovery backup**
```bash
# Check recovery backup
ls "C:\Users\lucid\OneDrive\Desktop\ClawdMatt recovery files"

# Look for Python bot files
find "C:\Users\lucid\OneDrive\Desktop\ClawdMatt recovery files" -name "*.py"

# Upload to VPS if found
scp /path/to/bot_code.py root@76.13.106.100:/root/clawdbots/
```

**Option C: Use clawdbot-gateway to launch**
```bash
# SSH to VPS
ssh root@76.13.106.100

# Check gateway status
docker ps | grep clawdbot

# Access gateway
docker exec -it clawdbot-gateway bash

# Use clawdbot CLI to configure bots
clawdbot setup
# Follow prompts to configure each bot with tokens from /root/clawdbots/tokens.env
```

### Brand Guidelines Mapping
- **ClawdMatt**: /root/clawdbots/marketing_guide.md (KR8TIV AI Marketing Guide)
- **ClawdFriday**: /root/clawdbots/friday_guide.md (Email AI guide - to be created)
- **ClawdJarvis**: /root/clawdbots/jarvis_voice.md (Jarvis X thread voice)

### Success Criteria
- ✅ All 3 bots show as RUNNING in ps/docker ps
- ✅ No Telegram polling conflicts (each bot uses unique token)
- ✅ Bots respond to Telegram commands
- ✅ No crashes in logs for 30+ minutes

---

## DEPLOYMENT 3: X BOT TELEGRAM SYNC

### Current Status
- ✅ **Token created**: X_TELEGRAM_KR8TIV_BOT (`7968869100:AAEanu...`)
- ✅ **Code updated**: telegram_sync.py uses X_BOT_TELEGRAM_TOKEN
- ✅ **Added to .env**: lifeos/config/.env contains token
- ⏳ **PENDING**: Supervisor restart to load new env var

### Deployment Steps

**On Local Machine** (if supervisor runs locally):
```bash
cd "C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis"

# Verify token in .env
grep X_BOT_TELEGRAM_TOKEN lifeos/config/.env

# Restart supervisor
pkill -f supervisor.py
sleep 2
nohup python bots/supervisor.py > logs/supervisor.log 2>&1 &

# Verify X bot using dedicated token
tail -f logs/supervisor.log | grep "X bot using dedicated"
```

**On VPS** (if supervisor runs on VPS):
```bash
ssh root@72.61.7.126

# Add to .env
nano /home/jarvis/Jarvis/lifeos/config/.env
# Add: X_BOT_TELEGRAM_TOKEN=7968869100:AAEanuTRjH4eHTOGvssn8BV71ChsuPrz6Hc

# Restart supervisor
pkill -f supervisor.py
cd /home/jarvis/Jarvis
nohup python bots/supervisor.py > logs/supervisor.log 2>&1 &
```

### Success Criteria
- ✅ Logs show "X bot using dedicated Telegram token (X_BOT_TELEGRAM_TOKEN) - no polling conflicts"
- ✅ X bot posts to Twitter successfully
- ✅ Tweets sync to Telegram channels without conflicts
- ✅ autonomous_x component shows as RUNNING

---

## VERIFICATION CHECKLIST

### After All Deployments Complete

**1. Check Supervisor Health**
```bash
# All components should show RUNNING
# No components with >5 restarts
# No exit code 4294967295 errors
```

**2. Test Telegram Polling**
```bash
# Send test command to each bot
# Each should respond independently
# No "Conflict: terminated by other getUpdates" errors
```

**3. Monitor for 30 Minutes**
```bash
# Treasury bot: stable, no crashes
# ClawdMatt/Friday/Jarvis: responding to commands
# X bot: posting tweets, syncing to Telegram
# No polling conflicts in any logs
```

**4. Check Token Uniqueness**
```bash
# Verify each bot uses different token
grep -r "TELEGRAM_BOT_TOKEN" /home/jarvis/Jarvis/lifeos/config/.env
grep -r "BOT_TOKEN" /root/clawdbots/tokens.env

# Should see 5 unique tokens (no duplicates)
```

---

## TROUBLESHOOTING

### Issue: "Conflict: terminated by other getUpdates request"
**Cause**: Multiple bots sharing same Telegram token
**Fix**: Verify each bot uses unique token, restart all bots

### Issue: "TREASURY_BOT_TOKEN not set"
**Cause**: Token not in .env or supervisor not restarted
**Fix**: Add to .env, restart supervisor, verify with `env | grep TREASURY`

### Issue: "ClawdBot not responding"
**Cause**: Bot process not started
**Fix**: Find bot code, start process with correct token from tokens.env

### Issue: "X bot still using TELEGRAM_BOT_TOKEN"
**Cause**: X_BOT_TELEGRAM_TOKEN not set in .env
**Fix**: Add to .env, restart supervisor, check logs for "using dedicated token"

---

## DEPLOYMENT ORDER (Recommended)

1. **X Bot Sync** (already done) - local restart only
2. **Treasury Bot** (P0 critical) - fixes 35+ crashes
3. **ClawdMatt** - marketing filter
4. **ClawdFriday** - email AI
5. **ClawdJarvis** - main orchestrator
6. **Test all bots for 30 min** - verify no conflicts

---

## BLOCKERS & DEPENDENCIES

### Current Blockers
1. **Treasury**: Needs SSH to 72.61.7.126 or manual deployment
2. **ClawdBots**: Need Python bot code location
3. **OAuth tokens**: Need updated tokens for X posting (separate from Telegram sync)

### Dependencies
- All bots depend on unique Telegram tokens (DONE ✅)
- Treasury depends on .env edit + supervisor restart
- ClawdBots depend on Python code location + process startup
- X bot depends on supervisor restart to load new env var

---

## FILES REFERENCE

**Local Files**:
- Token storage: `secrets/bot_tokens_DEPLOY_ONLY.txt`
- Environment: `lifeos/config/.env`
- Deployment script: `scripts/deploy_all_bots.sh`

**VPS Files** (srv1302498.hstgr.cloud):
- ClawdBot tokens: `/root/clawdbots/tokens.env`
- Brand guides: `/root/clawdbots/*.md`

**VPS Files** (72.61.7.126):
- Environment: `/home/jarvis/Jarvis/lifeos/config/.env`
- Supervisor logs: `/home/jarvis/Jarvis/logs/supervisor.log`

---

## NEXT STEPS

**Immediate** (User Manual Action Required):
1. SSH to 72.61.7.126 and deploy TREASURY_BOT_TOKEN to .env
2. Restart supervisor on 72.61.7.126
3. Verify treasury bot no longer crashes

**After Treasury Deployed**:
1. Locate ClawdMatt Python bot code (check Desktop recovery files)
2. Start ClawdMatt, ClawdFriday, ClawdJarvis processes
3. Run 30-minute integration test (all bots, no conflicts)

**Final Verification**:
1. All 5 bots operational
2. Zero Telegram polling conflicts
3. Update MASTER_GSD with deployment success
4. Archive this deployment guide

---

**Document Status**: READY FOR USE
**Last Updated**: 2026-01-31 18:35 PST
**Ralph Wiggum Loop**: Continuing autonomous execution...
