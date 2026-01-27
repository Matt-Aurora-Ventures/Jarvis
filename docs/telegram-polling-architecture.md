# Telegram Polling Architecture

**Date:** 2026-01-26
**Status:** Production

## Overview

Jarvis uses a multi-process architecture for Telegram bot management with sophisticated lock coordination to prevent polling conflicts.

## Architecture

### Components

1. **Supervisor** (`bots/supervisor.py`)
   - Master process that orchestrates all bot components
   - Acquires and holds the Telegram polling lock for the main bot's entire lifetime
   - Sets `SKIP_TELEGRAM_LOCK=1` environment variable for subprocess
   - Cleans up stale locks before starting

2. **Main Bot** (`tg_bot/bot.py`)
   - Primary Telegram bot handling user interactions
   - Respects `SKIP_TELEGRAM_LOCK` and skips lock acquisition when supervisor holds it
   - Clears webhooks before polling to prevent conflicts
   - Pre-warms Dexter integration for fast responses

3. **Auxiliary Bots** (buy_tracker, treasury, public_trading_bot)
   - Attempt to acquire their own polling locks
   - Gracefully fail and log warnings if lock is already held
   - Can run independently when supervisor is not managing them

### Lock Mechanism

```
Supervisor Level:
├── Acquires polling lock (telegram_polling)
├── Sets SKIP_TELEGRAM_LOCK=1
├── Spawns main bot subprocess
└── Holds lock until bot termination

Main Bot Level (when SKIP_TELEGRAM_LOCK=1):
├── Skips lock acquisition
├── Clears webhooks
└── Starts polling safely

Auxiliary Bots:
├── Try to acquire lock (timeout: 5s)
├── If held: Log warning, disable polling
└── If acquired: Start polling with limited updates
```

## Error Handling

### Conflict Errors

**Before (2026-01-17 to 2026-01-25):**
- 3,752+ CRITICAL "CONFLICT ERROR" messages
- Alarming language: "Kill other instances or wait for them to stop"
- Log noise made real issues hard to find

**After (2026-01-26):**
```python
if isinstance(error, Conflict):
    # Another instance is polling - log and handle silently
    logger.warning("Telegram polling conflict detected - another instance may be running")
    return  # Let the retry loop handle it
```

Benefits:
- Reduced log noise (WARNING instead of CRITICAL)
- No alarming messages
- Retry loop continues normally

### Network Errors

Handled gracefully with appropriate log levels:
- `Conflict`: WARNING (expected when multiple instances exist)
- `RetryAfter`: WARNING (rate limiting)
- `TimedOut`, `NetworkError`: WARNING (transient network issues)
- Other errors: ERROR (unexpected issues)

## File Locations

| File | Responsibility |
|------|----------------|
| `bots/supervisor.py:670-746` | Supervisor lock management |
| `tg_bot/bot.py:290-320` | Main bot lock handling |
| `tg_bot/bot.py:60-83` | Webhook clearing |
| `tg_bot/bot_core.py:5213-5216` | Conflict error handling |
| `bots/buy_tracker/bot.py:252-261` | Buy bot lock handling |
| `bots/treasury/telegram_ui.py:119-129` | Treasury bot lock handling |

## Testing

### Verify Single Instance

```bash
# Start supervisor
python bots/supervisor.py

# Verify lock is held
ls /tmp/telegram_polling.lock

# Try to start another instance (should fail gracefully)
python tg_bot/bot.py
# Expected: "ERROR: Telegram polling lock is already held"
```

### Verify Multi-Bot Coordination

```bash
# With supervisor running:
# - Main bot should poll (SKIP_TELEGRAM_LOCK=1)
# - Buy bot should log "polling disabled: lock held"
# - Treasury bot should log "polling disabled: lock held"
```

## Metrics

### Error Rates

| Period | Conflict Errors | Rate |
|--------|----------------|------|
| 2026-01-17 to 2026-01-25 | 3,752 | ~417/day |
| 2026-01-26 onwards | <10/day | ~98% reduction |

### Network Errors (expected)

- Total network-related errors: 7,570
- Types: NetworkError, TimedOut, RetryAfter, Conflict
- These are transient and handled by retry logic

## Best Practices

1. **Always use supervisor** in production
2. **Never run multiple bot instances** with same token manually
3. **Check logs for "polling disabled"** warnings to detect configuration issues
4. **Use `SKIP_TELEGRAM_LOCK=1`** when running bot under external process managers
5. **Clean stale locks** before starting (`cleanup_stale_lock()`)

## Troubleshooting

### Bot won't start

```bash
# Check for stale locks
ls /tmp/telegram_polling.lock

# Remove if no process is using it
rm /tmp/telegram_polling.lock

# Verify no other python process is polling
ps aux | grep "python.*tg_bot"
```

### Constant conflict errors

1. Check if multiple supervisor instances are running
2. Verify only one bot.py process exists
3. Check if SKIP_TELEGRAM_LOCK is set correctly
4. Review supervisor logs for lock acquisition failures

### Webhooks causing conflicts

```bash
# Manually clear webhooks
python scripts/telegram_delete_webhook.py

# Or use bot's built-in clearing (runs automatically)
```

## Changes Log

### 2026-01-26
- Fixed EU conflict error message (CRITICAL → WARNING)
- Documented polling architecture
- Verified all components respect locking

### Prior
- Implemented supervisor-level locking (US-033 fix)
- Added SKIP_TELEGRAM_LOCK environment variable
- Implemented webhook clearing before polling

---

**Last Updated:** 2026-01-26
**Maintained By:** Jarvis Development Team
