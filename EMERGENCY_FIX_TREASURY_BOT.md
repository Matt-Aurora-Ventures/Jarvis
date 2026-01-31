# 🚨 EMERGENCY FIX: Treasury Bot Crash (Exit Code 4294967295)

**Status:** ROOT CAUSE IDENTIFIED - IMMEDIATE ACTION REQUIRED
**Date:** 2026-01-31 14:30
**Severity:** CRITICAL - Hammering VPS CPU, months-long issue

---

## ROOT CAUSE DISCOVERED

**Treasury bot crashes with exit code 4294967295 because `TREASURY_BOT_TOKEN` is NOT SET**, causing it to fall back to the same `TELEGRAM_BOT_TOKEN` used by the main Telegram bot.

### Evidence Chain

1. **Supervisor logs** (`logs/supervisor.log` line 78-84):
   ```
   telegram.error.Conflict: terminated by other getUpdates request
   ```

2. **Code analysis** (`bots/treasury/run_treasury.py` lines 103-120):
   ```python
   # OLD CODE (BROKEN):
   bot_token = os.environ.get('TREASURY_BOT_TOKEN') or os.environ.get('TREASURY_BOT_TELEGRAM_TOKEN')
   if not bot_token:
       bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')  # ← CAUSES CONFLICT!
   ```

3. **What happens:**
   - Main `telegram_bot` polls with `TELEGRAM_BOT_TOKEN`
   - Treasury bot falls back to same `TELEGRAM_BOT_TOKEN`
   - Both bots try to call `getUpdates()` simultaneously
   - Telegram API returns HTTP 409 Conflict
   - python-telegram-bot crashes with exit code -1 (4294967295 unsigned)
   - Supervisor restarts bot → infinite crash loop

### Why This Took Months to Find

- Background task exception handlers (added earlier) masked the real error
- Exit code 4294967295 is generic (-1)
- Polling conflicts only show up in Telegram API errors, not Python tracebacks
- Previous fixes targeted symptoms (crash handling) not root cause (token conflict)

---

## ✅ CODE FIX APPLIED

**File:** `bots/treasury/run_treasury.py` lines 103-126

**Before:**
```python
bot_token = os.environ.get('TREASURY_BOT_TOKEN') or os.environ.get('TREASURY_BOT_TELEGRAM_TOKEN')
if not bot_token:
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')  # DANGEROUS FALLBACK
```

**After:**
```python
bot_token = os.environ.get('TREASURY_BOT_TOKEN') or os.environ.get('TREASURY_BOT_TELEGRAM_TOKEN')

if not bot_token:
    logger.error(
        "CRITICAL ERROR: TREASURY_BOT_TOKEN not set!\n"
        "Treasury bot MUST have its own unique Telegram bot token.\n"
        "DO NOT share TELEGRAM_BOT_TOKEN - this causes polling conflicts!\n"
        "Exit code 4294967295 = Telegram polling conflict\n"
        "TO FIX: See TELEGRAM_BOT_TOKEN_GENERATION_GUIDE.md"
    )
    raise ValueError("TREASURY_BOT_TOKEN not set - polling conflict will occur!")
```

**Result:** Bot will now FAIL HARD with clear error message instead of silently falling back and crashing.

---

## 🎯 IMMEDIATE ACTION REQUIRED (User)

### Step 1: Create Unique Bot Token via @BotFather

**Using Telegram Web (RECOMMENDED):**

1. Open Telegram (web.telegram.org or mobile app)
2. Search for `@BotFather` (verified bot with blue checkmark)
3. Send: `/newbot`
4. Enter bot name: `JARVIS Treasury Bot`
5. Enter username: `jarvis_treasury_bot` (must end with 'bot')
6. **Copy the token** @BotFather sends you (format: `123456789:ABCdefGHI...`)

**Alternative - Using Existing Bot:**

If you already have a treasury bot created:
1. Send to @BotFather: `/mybots`
2. Select your treasury bot
3. Click "API Token" → "Regenerate Token"
4. Copy the new token

### Step 2: Add Token to Environment

**On Local Machine:**

Edit `lifeos/config/.env`:
```bash
# Add this line:
TREASURY_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz

# Keep existing:
TELEGRAM_BOT_TOKEN=<main_bot_token>  # Don't change this!
```

**On VPS:**

```bash
ssh user@your-vps
cd /path/to/jarvis
nano lifeos/config/.env  # or vim

# Add the line:
TREASURY_BOT_TOKEN=<your_token_here>

# Save and exit
```

### Step 3: Test Token Works

```bash
# Verify token is valid:
curl https://api.telegram.org/bot<TREASURY_BOT_TOKEN>/getMe

# Should return JSON with bot info, not error
```

### Step 4: Deploy Fix to VPS

**Option A: Git Pull (if code is pushed):**

```bash
# On VPS:
cd /path/to/jarvis
git fetch origin main
git pull origin main

# Restart supervisor
pkill -f supervisor.py
python bots/supervisor.py
```

**Option B: Manual File Transfer:**

```bash
# On local machine:
scp bots/treasury/run_treasury.py user@vps:/path/to/jarvis/bots/treasury/

# On VPS:
pkill -f supervisor.py
python bots/supervisor.py
```

### Step 5: Monitor for Success

```bash
# On VPS, watch logs:
tail -f logs/supervisor.log

# Should see:
# "Using unique treasury bot token (TREASURY_BOT_TOKEN)"
# NOT: "falling back to TELEGRAM_BOT_TOKEN"

# Monitor for 10 minutes - NO crashes = success!
```

---

## 🔍 VERIFY OTHER BOTS

**Check these bots for same issue:**

### Buy Tracker Bot

```bash
grep -A5 "TELEGRAM_BOT_TOKEN" bots/buy_tracker/bot.py
grep -A5 "TELEGRAM_BOT_TOKEN" bots/buy_tracker/sentiment_report.py
```

**Fix if needed:** Create `BUY_TRACKER_BOT_TOKEN` via @BotFather

### Sentiment Reporter Bot

```bash
grep -A5 "TELEGRAM_BOT_TOKEN" bots/sentiment_reporter.py
```

**Fix if needed:** Create `SENTIMENT_REPORTER_BOT_TOKEN` via @BotFather

---

## 📊 VALIDATION CHECKLIST

- [ ] TREASURY_BOT_TOKEN created via @BotFather
- [ ] Token added to lifeos/config/.env (local)
- [ ] Token added to .env on VPS
- [ ] Code fix committed to GitHub
- [ ] Code deployed to VPS
- [ ] Supervisor restarted
- [ ] Logs show "Using unique treasury bot token"
- [ ] No crashes for 10+ minutes
- [ ] No "Conflict: terminated by other getUpdates" errors
- [ ] CPU usage normal (not hammering VPS)
- [ ] Check buy_tracker and sentiment_reporter bots
- [ ] Create separate tokens for other bots if needed

---

## 🔬 TECHNICAL DEEP DIVE

### Why Exit Code 4294967295?

- Python returns -1 for unhandled exceptions
- Windows represents -1 as unsigned 32-bit: `0xFFFFFFFF` = 4,294,967,295
- Telegram `Conflict` exception wasn't caught → Python exits with -1

### Telegram getUpdates Polling

- Telegram API allows only ONE active `getUpdates` request per bot token
- When second request arrives, Telegram returns HTTP 409 Conflict
- This is by design - prevents multiple bot instances racing for messages
- **Solution:** Each bot component MUST have unique token

### Why Fallback Was Dangerous

```python
# DANGEROUS PATTERN:
bot_token = os.environ.get('SPECIFIC_TOKEN') or os.environ.get('GENERIC_TOKEN')
```

- Seems "safe" - provides fallback if specific token missing
- **Reality:** Silent failure mode that causes hard-to-debug issues
- **Better:** Fail hard with clear error message

---

## 📚 RESEARCH SOURCES

**Telegram Bot Polling Conflicts:**
- [Telegram Polling Errors and Resolution](https://medium.com/@ratulkhan.jhenidah/telegram-polling-errors-and-resolution-4726d5eae895)
- [python-telegram-bot Issue #4499](https://github.com/python-telegram-bot/python-telegram-bot/issues/4499)
- [Render Community: Conflict Error](https://community.render.com/t/telegram-error-conflict-conflict-terminated-by-other-getupdates-request-make-sure-that-only-one-bot-instance-is-running/37443)

**Exit Code 4294967295:**
- [Microsoft Q&A: Error code 4294967295](https://learn.microsoft.com/en-us/answers/questions/1359356/error-code-4294967295-(0xffffff))
- [Process Exited with Code 4294967295](https://www.partitionwizard.com/partitionmagic/4294967295.html)

**Asyncio Exception Handling:**
- [Quantlane: Ensure asyncio task exceptions get logged](https://quantlane.com/blog/ensure-asyncio-task-exceptions-get-logged/)
- [Super Fast Python: Handle Asyncio Task Exceptions](https://superfastpython.com/asyncio-task-exceptions/)

---

## ✅ SUCCESS CRITERIA

**This issue is PERMANENTLY FIXED when:**

1. ✅ Treasury bot has unique `TREASURY_BOT_TOKEN`
2. ✅ Code removes fallback to `TELEGRAM_BOT_TOKEN`
3. ✅ Bot runs for 24+ hours with ZERO crashes
4. ✅ Logs show NO "Conflict: terminated by other getUpdates" errors
5. ✅ VPS CPU usage remains normal (no hammering)
6. ✅ All other bots checked and fixed if needed

**Failure Indicators:**

- ❌ Bot crashes with exit code 4294967295
- ❌ Logs show "Conflict: terminated by other getUpdates"
- ❌ Logs show "falling back to TELEGRAM_BOT_TOKEN"
- ❌ VPS CPU spikes during restarts

---

## 🔄 IF ISSUE PERSISTS

If treasury bot STILL crashes after this fix:

**1. Verify token is actually set:**
```bash
# On VPS:
python -c "import os; from dotenv import load_dotenv; load_dotenv('lifeos/config/.env'); print(os.environ.get('TREASURY_BOT_TOKEN')[:20] if os.environ.get('TREASURY_BOT_TOKEN') else 'NOT SET')"
```

**2. Check for webhook conflicts:**
```bash
curl https://api.telegram.org/bot<TREASURY_BOT_TOKEN>/getWebhookInfo
# Should return: "url": ""
# If webhook set, delete it:
curl https://api.telegram.org/bot<TREASURY_BOT_TOKEN>/deleteWebhook
```

**3. Check for duplicate supervisor processes:**
```bash
ps aux | grep supervisor.py
# Should see only ONE process
# If multiple, kill all and restart:
pkill -f supervisor.py
python bots/supervisor.py
```

**4. Review full logs:**
```bash
tail -200 logs/supervisor.log | grep -A10 -B10 treasury
```

---

**Fix Created:** 2026-01-31 14:30
**Implemented By:** Claude Sonnet 4.5 (Emergency Response)
**Verified By:** Sleuth agent (ae83f17)
**Severity:** CRITICAL - Production impacting
**Priority:** P0 - Immediate deployment required
