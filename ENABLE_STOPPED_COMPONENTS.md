# Enable Stopped Components

## Current Status
From the supervisor health check:
- ✅ **8 components running:** buy_bot, sentiment_reporter, twitter_poster, telegram_bot, autonomous_x, treasury_bot, autonomous_manager, bags_intel
- 🔴 **2 components stopped:** public_trading_bot, ai_supervisor

## Why They're Stopped

### 1. public_trading_bot (STOPPED)

**Reason:** Token conflict with main telegram_bot

**Current Configuration:**
```bash
PUBLIC_BOT_TELEGRAM_TOKEN=<redacted>
TELEGRAM_BOT_TOKEN=<redacted>
```

**Problem:** Both bots use the SAME token → Telegram allows only ONE bot instance per token

**Solution:** Create a separate token for public trading bot

1. Talk to [@BotFather](https://t.me/botfather)
2. Send `/newbot` and create "Jarvis Public Trading Bot"
3. Copy the new token
4. Update `.env`:
```bash
# Keep main bot token
TELEGRAM_BOT_TOKEN=<redacted>

# NEW separate token for public bot
PUBLIC_BOT_TELEGRAM_TOKEN=YOUR_NEW_PUBLIC_BOT_TOKEN_HERE

# Optional: Enable live trading (default is dry-run)
PUBLIC_BOT_LIVE_TRADING=false
PUBLIC_BOT_REQUIRE_CONFIRMATION=true
PUBLIC_BOT_MIN_CONFIDENCE=65.0
PUBLIC_BOT_MAX_DAILY_LOSS=1000.0
```
5. Restart supervisor

**Alternative:** If you don't need public_trading_bot, remove the token:
```bash
# Comment out to disable
# PUBLIC_BOT_TELEGRAM_TOKEN=...
```

---

### 2. ai_supervisor (STOPPED)

**Reason:** Requires Ollama AI runtime integration

**Current Configuration:** None (missing AI runtime)

**Check Status:**
```python
python -c "from core.ai_runtime.integration import get_ai_runtime_manager; print('Available')"
```

If error appears, ai_supervisor cannot start.

**Solution A: Enable Ollama Runtime**

1. Install Ollama: https://ollama.ai/
2. Pull required models:
```bash
ollama pull llama2
# or your preferred model
```
3. Configure `.env`:
```bash
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama2
AI_SUPERVISOR_ENABLED=true
```
4. Restart supervisor

**Solution B: Disable ai_supervisor**

The component is already effectively disabled (it runs but sleeps). No action needed unless you want to remove it from the component list.

To remove from supervisor entirely, edit `bots/supervisor.py`:
```python
# Comment out this line around line 1443:
# supervisor.register("ai_supervisor", create_ai_supervisor, ...)
```

---

## Quick Enable Summary

### For public_trading_bot:
```bash
# Get new token from @BotFather
PUBLIC_BOT_TELEGRAM_TOKEN=<new_token>
# Restart supervisor
```

### For ai_supervisor:
```bash
# Install Ollama + models, then:
OLLAMA_BASE_URL=http://localhost:11434
AI_SUPERVISOR_ENABLED=true
# Restart supervisor
```

## Verification

After changes, restart supervisor and check:
```bash
# Check health
curl http://127.0.0.1:8080/health

# Check logs
tail -f logs/supervisor.log

# Should see:
# public_trading_bot: running (if enabled)
# ai_supervisor: running (if Ollama configured)
```
