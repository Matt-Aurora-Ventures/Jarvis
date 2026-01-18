# Bot Lock Fix Deployment - Ralph Wiggum Loop Iteration 1

**Date**: 2026-01-18
**Status**: 🔄 READY FOR DEPLOYMENT
**Previous Blocker**: Multiple bot instances causing Telegram Conflict errors
**Solution**: Wait-based lock instead of immediate exit

---

## The Problem (Root Cause Analysis)

### What Was Happening:
1. Supervisor spawns `bot.py` as subprocess with min_backoff=10s
2. Bot acquires file lock OR exits if lock held
3. When bot exits (lock held), supervisor sees it as failure
4. Supervisor waits 10s, spawns NEW bot instance
5. New instance tries to acquire lock, fails, exits
6. **LOOP**: Every 10 seconds, a new instance is spawned, exits, respawned

### Result:
- 3+ bot instances constantly spawning
- Each one trying to call `getUpdates()` on Telegram
- Telegram API returns: **"Conflict: terminated by other getUpdates request"**
- Bot gets killed, supervisor respawns, cycle continues

---

## The Solution

### What Changed:
**File**: `tg_bot/bot.py` lines 26-61

**Old Logic** (BROKEN):
```python
# Exit immediately if lock held
try:
    acquire_lock()
except:
    print("ERROR: lock held")
    time.sleep(5)
    sys.exit(1)  # ← EXIT causes supervisor to respawn!
```

**New Logic** (FIXED):
```python
# Wait up to 30 seconds for lock to become available
max_wait_time = 30
while True:
    try:
        acquire_lock()
        print("✓ Lock acquired")
        break  # Proceed with bot
    except:
        waited += 1
        if waited >= max_wait_time:
            sys.exit(1)  # Only exit after waiting
        time.sleep(1)  # Retry every 1 second
```

### Why This Works:
1. First bot instance acquired lock immediately → runs normally
2. Any supervisor restart spawns new instance → **waits** up to 30s for lock
3. Original bot crashes → lock is released
4. Waiting instance acquires lock → continues running
5. **Result**: Always ONE bot polling, graceful handoff on crash

---

## Commits

| Commit | Change | Message |
|--------|--------|---------|
| 58f03b4 | bot.py | `fix: Change bot lock to wait for availability instead of exiting` |
| 46feadb | redeploy script | `scripts: Add quick redeploy script for bot lock fix` |

---

## Deployment Steps

### On Your Local Machine:
✅ ALREADY DONE:
- [x] Code modified with wait-based lock
- [x] Commits pushed to GitHub
- [x] Redeploy script created and pushed

### On VPS (Run These Commands):

```bash
# SSH into VPS
ssh jarvis@72.61.7.126

# Navigate to Jarvis directory
cd /home/jarvis/Jarvis

# Run the redeploy script
bash scripts/redeploy_bot_fix.sh
```

**OR** Run manually:

```bash
# Kill existing bots
pkill -9 -f "tg_bot.bot"
pkill -9 -f "bot.py"
sleep 2

# Clean lock
rm -f /tmp/jarvis_bot.lock

# Pull latest code
cd /home/jarvis/Jarvis
git pull origin main

# Verify fix is present
grep "max_wait_time = 30" tg_bot/bot.py

# Start bot
nohup /home/jarvis/Jarvis/venv/bin/python -m tg_bot.bot >> logs/tg_bot.log 2>&1 &

# Monitor logs
tail -f logs/tg_bot.log
```

---

## What to Expect

### Deployment Sequence (First 10 seconds):

```
[2026-01-18 14:32:15] Starting bot (1st instance)
[2026-01-18 14:32:15] ✓ Lock acquired by PID: 49071
[2026-01-18 14:32:16] Telegram bot started
[2026-01-18 14:32:17] Status: Polling for messages...

-- If supervisor tries to restart during this time --
[2026-01-18 14:32:20] Starting bot (2nd instance)
[2026-01-18 14:32:20] ⏳ Waiting for bot lock to become available (max 30s)...
[2026-01-18 14:32:21] ⏳ Still waiting (1s/30s)...
...
-- 2nd instance waits, doesn't cause Conflict errors --
```

### Desired End State:

```bash
# Only ONE process should be polling
$ ps aux | grep "tg_bot.bot"
jarvis   49071  0.1  0.5 123456 78901 ?  Sl  14:32  0:05 /home/jarvis/Jarvis/venv/bin/python -m tg_bot.bot

# NO Conflict errors in logs
$ tail -100 logs/tg_bot.log | grep Conflict
(empty)

# Lock file should exist
$ cat /tmp/jarvis_bot.lock
49071
```

---

## Verification Checklist

After deployment, verify:

- [ ] Only ONE `tg_bot.bot` process in `ps aux`
- [ ] No "Conflict:" errors in logs (check last 100 lines)
- [ ] Lock file exists at `/tmp/jarvis_bot.lock`
- [ ] Bot is polling Telegram (no timeout errors)
- [ ] Sentiment reports are still sending (test in Telegram)
- [ ] Can type commands in Telegram bot (no hanging)

### Check Command:

```bash
# SSH into VPS
ssh jarvis@72.61.7.126

# All in one command:
echo "=== BOT PROCESSES ===" && \
ps aux | grep "tg_bot.bot" | grep -v grep && \
echo "" && \
echo "=== LOCK FILE ===" && \
cat /tmp/jarvis_bot.lock 2>/dev/null || echo "(not found)" && \
echo "" && \
echo "=== RECENT ERRORS ===" && \
tail -50 /home/jarvis/Jarvis/logs/tg_bot.log | grep -E "Conflict|ERROR|Exception" || echo "(none found)"
```

---

## Ralph Wiggum Loop - Iteration 1 Status

### Current Task: ✅ FIX BLOCKER (Multiple instances)

**What this iteration fixes:**
- Multiple bot instances spawning from supervisor respawn loop
- Telegram Conflict errors
- Unstable polling connection

**Next iteration after fix verification:**
- Test Dexter finance Q&A integration
- Verify Grok sentiment weighting
- Monitor response quality
- Iterate on improvements until all Ralph Wiggum loop objectives met

---

## Rollback Plan (If Issues Occur)

If after deployment you experience worse behavior:

```bash
# Revert to previous code
git reset --hard 58f03b4

# Kill bot
pkill -9 -f "tg_bot.bot"
rm -f /tmp/jarvis_bot.lock

# Restart
nohup /home/jarvis/Jarvis/venv/bin/python -m tg_bot.bot >> logs/tg_bot.log 2>&1 &
```

But this shouldn't be necessary - the new logic is backward compatible and only adds waiting time.

---

## Timeline

| When | What |
|------|------|
| 2026-01-18 14:00 | Issue identified: multiple bot instances |
| 2026-01-18 14:15 | Root cause: supervisor respawn loop |
| 2026-01-18 14:30 | Solution: wait-based lock implemented |
| 2026-01-18 14:35 | Commits: 58f03b4, 46feadb pushed to GitHub |
| 2026-01-18 14:45 | **NOW**: Ready for VPS deployment |
| 2026-01-18 15:00 | TARGET: Deployment complete, verified |
| 2026-01-18 15:15 | CONTINUE: Ralph Wiggum loop iteration 2 (Dexter testing) |

---

## Next Steps After Successful Deployment

Once you confirm deployment is successful:

1. Send test message to @Jarviskr8tivbot
2. Verify bot responds (no hanging)
3. Create TODO for Ralph Wiggum iteration 2: **Test Dexter Finance Integration**
4. Ask finance question: "Is SOL bullish right now?"
5. Verify Dexter responds with sentiment analysis
6. Monitor logs for any errors
7. Continue iterating on improvements

---

## Support

If deployment fails:

1. **Check bot process**: `ps aux | grep tg_bot.bot`
2. **Check logs**: `tail -100 /home/jarvis/Jarvis/logs/tg_bot.log`
3. **Check lock**: `cat /tmp/jarvis_bot.lock`
4. **Kill and retry**: `pkill -9 -f tg_bot.bot && rm -f /tmp/jarvis_bot.lock`

---

**Status**: 🟡 AWAITING VPS DEPLOYMENT

Once deployed and verified, we'll continue with Dexter testing in the Ralph Wiggum loop.
