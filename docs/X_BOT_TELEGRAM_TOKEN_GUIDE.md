# X Bot Telegram Token - Eliminate Polling Conflict

**Issue**: autonomous_x (X bot) uses same TELEGRAM_BOT_TOKEN as other bots, causing polling conflicts.

**Solution**: Create dedicated X_BOT_TELEGRAM_TOKEN

## Quick Fix (5 minutes)

### 1. Create New Bot via @BotFather

Open Telegram → Search `@BotFather`

```
/newbot
Name: X Sync Bot
Username: jarvis_x_sync_bot
```

Copy the token you receive.

### 2. Add to Local .env

Edit: `C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\.env`

Add this line:
```
X_BOT_TELEGRAM_TOKEN=<paste_your_new_token_here>
```

### 3. Update Code to Use Dedicated Token

The code already supports this! In [bots/supervisor.py:803](bots/supervisor.py#L803):

```python
def _create_autonomous_x_engine(self) -> subprocess.Popen:
    """Create autonomous X posting engine (async)."""
    logger.info("Starting autonomous X engine (Twitter)")

    # Check for unique X bot token first
    x_token = os.environ.get("X_BOT_TELEGRAM_TOKEN", "")

    if x_token:
        logger.info("Using unique X bot token (X_BOT_TELEGRAM_TOKEN)")
    else:
        x_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        logger.warning(
            "X_BOT_TELEGRAM_TOKEN not set - using shared TELEGRAM_BOT_TOKEN "
            "(polling conflict possible)"
        )
```

So the supervisor **already looks for** `X_BOT_TELEGRAM_TOKEN` first!

### 4. Deploy to VPS 72.61.7.126

SSH to VPS:
```bash
ssh root@72.61.7.126
nano /home/jarvis/Jarvis/lifeos/config/.env
```

Add:
```
X_BOT_TELEGRAM_TOKEN=<paste_your_new_token_here>
```

Save and restart supervisor:
```bash
pkill -f supervisor.py
cd /home/jarvis/Jarvis
nohup python bots/supervisor.py > logs/supervisor.log 2>&1 &
tail -f logs/supervisor.log | grep "X bot token"
```

### 5. Verify Success

Look for in logs:
```
Using unique X bot token (X_BOT_TELEGRAM_TOKEN)
```

**NOT**:
```
using shared TELEGRAM_BOT_TOKEN (polling conflict possible)
```

## Why This Matters

The X bot does two things:
1. Posts to Twitter/X using OAuth (working)
2. Syncs tweet notifications to Telegram using a bot token (CONFLICTING)

Without a dedicated token, every time autonomous_x tries to send a Telegram notification about a tweet, it fights with treasury_bot, buy_bot, etc. for the same Telegram connection.

Result: All bots crash with "Conflict: terminated by other getUpdates request"

## OAuth Status

Checked [bots/twitter/.oauth2_tokens.json](bots/twitter/.oauth2_tokens.json):
- ✅ Tokens exist
- ✅ Updated: 2026-01-20
- ✅ Account: @Jarvis_lifeos

OAuth tokens are **not expired**. The issue is purely the Telegram polling conflict.

## Summary

**Create**: New bot via @BotFather → X_BOT_TELEGRAM_TOKEN
**Add**: To local .env and VPS .env
**Restart**: Supervisor
**Verify**: "Using unique X bot token" in logs

This eliminates the last polling conflict blocking autonomous X posting.
