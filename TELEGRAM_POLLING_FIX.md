# Telegram Polling Lock Fix

## Problem
Multiple bots attempting to poll same Telegram API with one token causes:
- 409 Conflict errors from Telegram
- Blocks conversation audit and message access
- Bot instability

## Root Cause
The issue occurs when multiple bot processes try to poll with the **same token**.

Current token configuration:
1. `TELEGRAM_BOT_TOKEN` - Main Telegram bot (tg_bot/bot.py)
2. `PUBLIC_BOT_TELEGRAM_TOKEN` - Public trading bot
3. `TREASURY_BOT_TOKEN` - Treasury bot (separate process)

## Solution Options

### Option A: Separate Bot Tokens (RECOMMENDED)
**Best practice**: Each bot gets its own Telegram bot token.

**Steps:**
1. Create separate bots via @BotFather:
   - @JarvisMainBot (existing - TELEGRAM_BOT_TOKEN)
   - @JarvisPublicBot (needs token - PUBLIC_BOT_TELEGRAM_TOKEN)
   - @JarvisTreasuryBot (needs token - TREASURY_BOT_TOKEN)

2. Set environment variables:
   ```bash
   TELEGRAM_BOT_TOKEN=<main_bot_token>
   PUBLIC_BOT_TELEGRAM_TOKEN=<public_bot_token>
   TREASURY_BOT_TOKEN=<treasury_bot_token>
   ```

3. Each bot polls independently with no conflicts

**Pros:**
- Clean separation
- No code changes needed
- Industry standard approach
- No polling conflicts

**Cons:**
- Need to create 2 more bots
- Users need to start different bots

### Option B: Polling Coordinator (IMPLEMENTED)
**Fallback**: Single process polls, distributes updates to handlers.

**Status:**
- Coordinator implemented in `core/telegram_polling_coordinator.py`
- Can be integrated if separate tokens aren't feasible

**How it works:**
1. One process acquires polling lock
2. All bot handlers register with coordinator
3. Coordinator routes updates to appropriate handlers
4. No polling conflicts

**Pros:**
- One bot from user perspective
- All features in single interface

**Cons:**
- More complex architecture
- Single point of failure
- Requires refactoring

## Current Implementation

The supervisor already has safety checks (lines 826-832):
```python
main_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
public_token = os.environ.get("PUBLIC_BOT_TELEGRAM_TOKEN", "")
if treasury_token in (main_token, public_token):
    logger.warning("Treasury bot token matches another bot token; skipping to avoid polling conflict")
    return
```

## Recommended Fix

**Immediate action**: Ensure each bot has unique token in `.env`:

```bash
# .env
TELEGRAM_BOT_TOKEN=<main_bot_token_here>
PUBLIC_BOT_TELEGRAM_TOKEN=<different_token_here>
TREASURY_BOT_TOKEN=<another_different_token_here>
```

If any tokens are missing, that bot will skip startup automatically.

## Verification

After fix, check logs for:
```
✅ Telegram polling started
```

And ensure no messages like:
```
❌ Telegram polling lock held by another process
❌ Treasury bot token matches another bot token
```

## Testing

1. Start supervisor: `python bots/supervisor.py`
2. Check logs for each bot startup
3. Send test message to each bot
4. Verify no 409 Conflict errors
5. Verify conversation audit works

## Status

- [x] Root cause identified
- [x] Polling coordinator created (fallback)
- [x] Token validation checks in place
- [ ] Separate bot tokens configured in environment
- [ ] Testing completed
