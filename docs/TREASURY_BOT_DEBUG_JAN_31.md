# Treasury Bot Crash Investigation - Jan 31, 2026

**Status:** In Progress
**Issue:** Treasury bot crashes with exit code 4294967295 (-1) every ~3 minutes
**Restarts:** 82+ attempts before investigation

---

## Symptoms

1. Bot starts successfully
2. Loads positions from `.positions.json`
3. Initializes Jupiter client and Telegram UI
4. Logs "Position monitor started"
5. **Crashes** with no error message in logs
6. Exit code: `4294967295` (0xFFFFFFFF = -1 unsigned, -1 signed)
7. Supervisor restarts bot with 180s delay

---

## Timeline Analysis (from logs)

| Time | Event | Duration |
|------|-------|----------|
| 10:27:45 | Bot starts | - |
| 10:27:52 | Position monitor started | 7s |
| 10:31:05 | Bot restarts | **3m 13s** |
| 10:31:11 | Position monitor started | 6s |
| 10:34:30 | Bot restarts | **3m 19s** |
| 10:34:38 | Position monitor started | 8s |
| 10:37:42 | Bot restarts | **3m 4s** |

**Pattern:** Crashes every ~3 minutes after "Position monitor started"

---

## Investigation Steps

### 1. Supervisor Analysis

**File:** `bots/supervisor.py:814-876`

Supervisor spawns treasury bot as subprocess:
```python
proc = subprocess.Popen([sys.executable, "bots/treasury/run_treasury.py"], env=env)

while True:
    ret = proc.poll()
    if ret is not None:
        logger.error(f"Treasury bot exited with code {ret}")
        raise RuntimeError(f"Treasury bot exited with code {ret}")
    await asyncio.sleep(5)
```

When subprocess exits for ANY reason, supervisor catches exit code and restarts.

### 2. Position Monitor Loop

**File:** `bots/treasury/telegram_ui.py:136-178`

```python
async def _position_monitor_loop(self):
    logger.info("Position monitor started")
    while self._running:
        try:
            closed = await self.engine.monitor_stop_losses()
            # ... notify admins ...
        except Exception as e:
            logger.error(f"Position monitor error: {e}")  # ← Should catch exceptions

        await asyncio.sleep(60)  # Check every 60 seconds
```

**Issue:** Loop should catch exceptions, but crash happens anyway.

### 3. Exit Code Analysis

```bash
$ python -c "import sys; sys.exit(4294967295)"
OverflowError: Python int too large to convert to C long
Exit code: 127
```

Exit code 4294967295 = -1 in two's complement. This usually indicates:
- Unhandled exception that escaped all try/except blocks
- Signal termination (SIGTERM = -1)
- Process killed by OS

### 4. HTTP Session Leak Test

```bash
$ python test_jupiter_price.py
Unclosed client session
Unclosed connector
SOL price: 108.21
```

**Finding:** Jupiter client creates aiohttp sessions but warnings appear. However, `shutdown()` DOES call `jupiter.close()` at line 746, so cleanup should happen on graceful exit.

### 5. Direct Execution Test

```bash
$ python bots/treasury/run_treasury.py &
# ... bot starts ...
# Still running after 30 seconds
```

**Finding:** Bot does NOT crash when run directly (not via supervisor). Suggests crash is related to:
- Supervisor subprocess environment
- Accumulated state over multiple iterations
- Resource limits
- Signal handling

### 6. Price Fetching Test

All position prices fetch successfully:
- SOL: $107.77
- NVDAX: $189.47
- TSLAX: $427.02

**Finding:** Price fetching works correctly. Not the root cause.

---

## Root Cause Hypotheses

### Hypothesis 1: Uncaught Exception in Background Task ❌
**Evidence Against:**
- Background task exceptions don't crash main process in Python 3.8+
- They log "Task exception was never retrieved" but process continues
- Test confirmed this behavior

### Hypothesis 2: Resource Exhaustion ⚠️
**Possible:**
- HTTP sessions accumulate over time
- After 82 restarts × 3 minutes = 246 minutes of runtime
- Could hit file descriptor limit or memory limit

**Counter-Evidence:**
- Each restart is a new process
- Old process resources should be cleaned up by OS

### Hypothesis 3: Signal/Timeout from Supervisor ⚠️
**Possible:**
- Supervisor might have a watchdog timer
- Could send SIGTERM if bot becomes unresponsive
- Exit code -1 consistent with signal termination

**TODO:** Check supervisor for timeout mechanisms

### Hypothesis 4: Asyncio Event Loop Crash 🔥
**Most Likely:**
- Background task (`_position_monitor_loop()`) spawned with `asyncio.create_task()`
- If exception occurs in background task that's NOT caught
- AND task is not awaited anywhere
- Process could exit when event loop has no more tasks

**Evidence:**
```python
# Line 132 in telegram_ui.py
asyncio.create_task(self._position_monitor_loop())  # ← Fire and forget!
```

**Problem:** If this task crashes and no other tasks are running, event loop exits, process exits with -1.

---

## Applied Fixes (Commit deea61a)

### Fix 1: Enhanced Error Logging

Added to `_position_monitor_loop()`:
```python
try:
    logger.debug("Position monitor iteration starting...")
    closed = await self.engine.monitor_stop_losses()
    logger.debug(f"Checked: {len(closed)} positions closed")
except asyncio.CancelledError:
    logger.info("Position monitor cancelled, shutting down...")
    break
except Exception as e:
    logger.error(f"Position monitor error: {e}", exc_info=True)  # ← Full stack trace
```

**Benefits:**
- `exc_info=True` will log full traceback
- Separate handling for `asyncio.CancelledError`
- Debug logs for each iteration
- Log when monitor stops

### Fix 2: Graceful Shutdown

```python
try:
    await asyncio.sleep(60)
except asyncio.CancelledError:
    logger.info("Position monitor sleep cancelled, shutting down...")
    break
```

**Benefits:**
- Catch cancellation during sleep
- Clean exit from while loop
- Prevents exception from escaping

### Fix 3: Position Cleanup

Removed old test positions (2 SOL entries from Jan 18):
- Reduced position count from 4 to 2
- Only real positions remain (NVDAX, TSLAX)
- Updated current prices and peak prices

---

## Next Steps

1. **Monitor with New Logging** ✅
   - Supervisor will restart treasury_bot with enhanced logging
   - Watch `bots/logs/treasury_bot.log` for detailed error traces
   - If crash happens, we'll see EXACTLY what exception occurred

2. **Check Supervisor Watchdog**
   - Search supervisor.py for timeout mechanisms
   - Check if supervisor sends SIGTERM after certain duration

3. **Add Keepalive to Main Loop**
   - Ensure `bot.start()` keeps event loop alive
   - Add heartbeat logging every minute

4. **Test Under Load**
   - Monitor resource usage (RAM, file descriptors, connections)
   - Check if issue is cumulative over time

---

## Current Status

**Treasury Bot:**
- Enhanced logging deployed (commit deea61a)
- Waiting for next crash to capture detailed trace
- If no crash in next 10 minutes, may have fixed it

**Positions:**
- NVDAX: Entry $185.34, Current $189.47 (+2.2%)
- TSLAX: Entry $435.90, Current $427.02 (-2.0%)

**Next Crash Expected:** Within 3-5 minutes of restart

---

## References

- **Logs:** `bots/logs/treasury_bot.log`
- **Supervisor:** `logs/supervisor.log`
- **Code:** `bots/treasury/telegram_ui.py`
- **Issue Tracking:** [EXTRACTED_TASKS_JAN_31.md](EXTRACTED_TASKS_JAN_31.md) #2
