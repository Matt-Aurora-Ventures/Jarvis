# Emergency Stop Mechanism - Usage Guide

## Overview

The emergency stop mechanism provides multiple levels of trading control to protect capital during:
- Market crashes
- System malfunctions
- Security incidents
- Regulatory concerns
- Suspicious token behavior

## Quick Reference

| Command | Description | Trading Status | Positions |
|---------|-------------|----------------|-----------|
| `/stop SOFT [reason]` | Pause new trades | ❌ Blocked | ✅ Keep open |
| `/stop HARD [reason]` | Close everything gracefully | ❌ Blocked | ⚠️ Unwinding |
| `/stop KILL [reason]` | Emergency halt | 🚨 Immediate halt | 🚨 Close now |
| `/resume` | Resume normal trading | ✅ Allowed | ✅ Active |
| `/stop_status` | Check current state | - | - |
| `/pause_token <mint> [reason]` | Pause specific token | ⚠️ Token blocked | ✅ Others ok |

## Usage Scenarios

### Scenario 1: Market Volatility Spike

**Situation:** Market is extremely volatile, want to pause new trades but keep existing positions.

**Action:**
```
/stop SOFT Market volatility spike - pausing new positions
```

**Result:**
- No new positions opened
- Existing positions remain active
- TP/SL orders still working
- Can manually close positions if needed

**Resume when safe:**
```
/resume
```

### Scenario 2: Risk Limit Breach

**Situation:** Portfolio has hit risk limits, need to close positions in an orderly manner.

**Action:**
```
/stop HARD Risk limit exceeded - closing positions gracefully
```

**Result:**
- No new positions allowed
- Existing positions unwound with limit orders (30min window)
- Tries to get better exit prices than market orders
- Orders cancelled if not filled in time window

**What happens next:**
- System automatically closes positions
- Monitor progress with `/treasury_positions`
- Resume when positions closed: `/resume`

### Scenario 3: Security Incident

**Situation:** Detected unauthorized access or system compromise.

**Action:**
```
/stop KILL Security breach detected - immediate halt
```

**Result:**
- ALL trading halted immediately
- ALL open orders cancelled
- ALL positions closed with market orders
- Critical alerts sent to all channels

**Recovery:**
- Investigate and fix security issue
- Verify no unauthorized trades
- When safe: `/resume`

### Scenario 4: Scam Token Detection

**Situation:** One specific token shows signs of rug pull, but other trading should continue.

**Action:**
```
/pause_token EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v Rug pull indicators detected
```

**Result:**
- Trading blocked for this specific token only
- All other tokens trade normally
- Can close position in this token manually
- Token remains paused until explicitly resumed

**Resume specific token:**
```
/resume_token EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v
```

### Scenario 5: Scheduled Maintenance

**Situation:** Need to shut down trading for system maintenance.

**Action:**
```
/stop HARD Scheduled maintenance - closing positions
```

**Monitor:**
```
/stop_status
/treasury_positions
```

**After maintenance:**
```
/resume
```

## Programmatic Usage

### Python API

```python
from core.trading.emergency_stop import get_emergency_stop_manager, UnwindStrategy

# Get manager instance
emergency = get_emergency_stop_manager()

# Check if trading allowed
allowed, reason = emergency.is_trading_allowed(token_mint)
if not allowed:
    print(f"Trading blocked: {reason}")

# Activate stops
emergency.activate_soft_stop("Pausing for analysis", "system")
emergency.activate_hard_stop("Closing positions", "admin", UnwindStrategy.GRACEFUL)
emergency.activate_kill_switch("EMERGENCY", "security", UnwindStrategy.IMMEDIATE)

# Pause specific token
emergency.pause_token("token_mint_address", "Suspicious activity", "fraud_detector")

# Resume
emergency.resume_trading("admin")
emergency.resume_token("token_mint_address")

# Check status
status = emergency.get_status()
print(f"Level: {status['level']}")
print(f"Trading: {status['trading_allowed']}")
print(f"Unwind: {status['should_unwind']}")
```

### Alert Callbacks

```python
# Register alert callback
async def send_telegram_alert(message: str):
    await bot.send_message(admin_id, message)

emergency.register_alert_callback(send_telegram_alert)

# Now all stop activations/resumes will trigger alert
```

## State File

Emergency stop state is persisted to:
```
~/.lifeos/trading/emergency_stop.json
```

Example state:
```json
{
  "level": "HARD_STOP",
  "activated_at": "2026-01-19T12:34:56.789Z",
  "activated_by": "telegram_user_12345",
  "reason": "Market crash - unwinding positions",
  "paused_tokens": [
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "So11111111111111111111111111111111111111112"
  ],
  "unwind_strategy": "GRACEFUL",
  "auto_resume_at": null
}
```

**Important:** State persists across bot restarts. If bot crashes during emergency stop, the stop remains active when bot restarts.

## Unwind Strategies

### IMMEDIATE
- Market orders
- Close positions NOW
- Accept slippage up to 5%
- Use for: Security incidents, kill switch

### GRACEFUL
- Limit orders at better prices
- 30 minute time window
- Falls back to market if not filled
- Use for: Controlled shutdowns, hard stop

### SCHEDULED
- Close positions over extended period
- Multiple attempts at optimal prices
- Use for: Non-urgent exits

### MANUAL
- Don't auto-close positions
- Admin manually closes each position
- Use for: Complex positions requiring judgment

## Best Practices

1. **Start with SOFT stop** when uncertain
   - Gives time to assess situation
   - Can always escalate to HARD/KILL if needed

2. **Use token pause for single-token issues**
   - Don't halt entire trading for one bad token
   - Keep other revenue flowing

3. **Document reasons clearly**
   - Include reason in stop command
   - Helps with post-incident analysis

4. **Monitor during HARD stop**
   - Watch positions closing
   - Verify unwinding completes
   - Check for stuck orders

5. **Test in dry-run mode first**
   - Verify alerts work
   - Confirm state persistence
   - Practice activation procedures

6. **Have escalation plan**
   ```
   1. Detect issue
   2. Activate SOFT stop
   3. Assess severity
   4. Escalate to HARD if needed
   5. Use KILL only for critical emergencies
   ```

## Monitoring

### Check Status Regularly
```
/stop_status
```

### Monitor Active Stops
- Level: Current stop level
- Activated: When and by whom
- Reason: Why stop was activated
- Paused tokens: List of blocked tokens

### Position Monitoring During Unwind
```
/treasury_positions  # Watch positions closing
/treasury_trades     # See completed exits
```

## Troubleshooting

### "Emergency stop system not available"
**Solution:** Module not imported correctly. Check:
```python
from core.trading.emergency_stop import get_emergency_stop_manager
```

### State not persisting
**Solution:** Check file permissions on `~/.lifeos/trading/`
```bash
ls -la ~/.lifeos/trading/emergency_stop.json
```

### Alert callbacks not firing
**Solution:** Callbacks must be async functions or regular functions
```python
# Good
async def alert(msg):
    await send_alert(msg)

# Also good
def alert(msg):
    print(msg)

# Bad - will fail
def alert(msg):
    await something()  # Can't await in non-async
```

### Trading still blocked after resume
**Solution:** Check state file manually
```bash
cat ~/.lifeos/trading/emergency_stop.json
# Should show "level": "NONE"
```

## Security Considerations

1. **Admin-only access** - All commands require admin privileges
2. **Audit trail** - All activations logged with who/when/why
3. **Cannot bypass** - Trading checks happen before any execution
4. **Persistent** - Cannot be cleared by restart (must explicitly resume)
5. **Multiple callbacks** - Alerts sent to all registered channels

## Testing

Run comprehensive test suite:
```bash
pytest tests/unit/trading/test_emergency_stop.py -v
```

Test specific scenario:
```bash
pytest tests/unit/trading/test_emergency_stop.py::TestStopLevels::test_soft_stop_blocks_new_trades -v
```

## Support

For issues or questions:
1. Check `/stop_status` for current state
2. Review logs: `~/.lifeos/logs/trading.log`
3. Inspect state file: `~/.lifeos/trading/emergency_stop.json`
4. Run tests to verify system working

## Emergency Contact

If emergency stop mechanism itself fails:
1. Kill trading bot process
2. Manually close positions via exchange UI
3. Report bug with logs and state file

**Remember:** This is a safety system. False positives are acceptable. False negatives are not.
