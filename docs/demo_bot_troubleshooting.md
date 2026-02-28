# Demo Bot Troubleshooting Guide

**Version:** 2.0
**Last Updated:** 2026-01-26

## Common Issues

### Trade Execution Failures

#### Symptom: "Trade failed" error

**Possible Causes:**

1. **Insufficient Funds**
   ```
   Error: Insufficient funds
   Required: 0.5 SOL
   Available: 0.3 SOL
   ```
   **Solution:** Add more SOL to wallet or reduce trade size

2. **Slippage Exceeded**
   ```
   Error: Slippage tolerance exceeded
   Expected: 0.1 SOL = 1000 tokens
   Actual: 0.1 SOL = 900 tokens (10% slippage)
   ```
   **Solution:** Increase slippage tolerance or reduce trade size

3. **RPC Timeout**
   ```
   Error: RPC request timed out
   ```
   **Solution:**
   - Check Solana RPC status
   - Retry the trade
   - Switch to backup RPC (automatic)

4. **Token Not Found**
   ```
   Error: Token not found on Jupiter
   ```
   **Solution:**
   - Verify token address is correct
   - Check if token has liquidity
   - Try again later (token may be new)

### Handler Not Responding

#### Symptom: Bot doesn't respond to /demo command

**Debug Steps:**

1. **Check Bot is Running**
   ```bash
   supervisorctl status telegram_bot
   # Should show: RUNNING
   ```

2. **Check Logs**
   ```bash
   tail -f logs/telegram_bot.log
   ```
   Look for errors after sending `/demo`

3. **Verify Handler Registration**
   ```text
   # In tg_bot/bot.py
   from tg_bot.handlers.demo import register_demo_handlers
   register_demo_handlers(app)  # Must be present
   ```

4. **Test Bot Token**
   ```bash
   curl "https://api.telegram.org/bot<YOUR_TOKEN>/getMe"
   ```

### Callback Query Errors

#### Symptom: "Callback query timed out"

**Cause:** Handler took >30 seconds to respond

**Solution:**

```python
# Always answer callback queries immediately
await update.callback_query.answer()

# Then do long operation
result = await long_operation()

# Update message after completion
await update.callback_query.edit_message_text(f"Result: {result}")
```

#### Symptom: "Message is not modified"

**Cause:** Trying to edit message with same content

**Solution:**

```python
# Check if content changed before editing
if new_text != old_text:
    await update.callback_query.edit_message_text(new_text)
else:
    await update.callback_query.answer("No changes")
```

### Database Issues

#### Symptom: "database is locked"

**Cause:** Multiple processes accessing SQLite simultaneously

**Solution:**

```python
# Use proper session management
from core.database import get_session

session = get_session()
try:
    # Do operations
    position = session.query(DemoPosition).filter_by(id=pos_id).first()
    position.pnl = calculate_pnl()
    session.commit()
finally:
    session.close()  # Always close
```

#### Symptom: "Positions not updating"

**Debug:**

```python
from core.database import get_session
from tg_bot.handlers.demo.models import DemoPosition

session = get_session()
positions = session.query(DemoPosition).filter_by(user_id=YOUR_USER_ID).all()
for p in positions:
    print(f"Position: {p.token_address}")
    print(f"Entry: {p.entry_price}, Current: {p.current_price}")
    print(f"PnL: {p.pnl}%")
```

### TP/SL Not Triggering

#### Symptom: Stop-loss reached but position not sold

**Debug Steps:**

1. **Check Monitor is Running**
   ```bash
   ps aux | grep tp_sl_monitor
   ```

2. **Check Order Status**
   ```text
   from core.database import get_session
   from tg_bot.handlers.demo.models import DemoTPSLOrder

   session = get_session()
   orders = session.query(DemoTPSLOrder).filter_by(
       status="pending"
   ).all()

   for order in orders:
       print(f"Order: {order.id}")
       print(f"Type: {order.order_type}")
       print(f"Trigger: {order.trigger_price}")
       print(f"Current: {order.current_price}")
   ```

3. **Check Logs**
   ```bash
   grep "TP/SL" logs/telegram_bot.log | tail -50
   ```

4. **Manual Trigger**
   ```text
   from tg_bot.handlers.demo.demo_orders import _process_demo_exit_checks

   # Force check for specific position
   await _process_demo_exit_checks(session, position_id)
   ```

### Sentiment Data Not Loading

#### Symptom: "Sentiment unavailable"

**Causes:**

1. **XAI_API_KEY not set**
   ```bash
   echo $XAI_API_KEY
   # Should output your key
   ```

2. **Grok API Rate Limit**
   ```
   Error: Rate limit exceeded
   Retry after: 60 seconds
   ```
   **Solution:** Wait and retry

3. **Token Not Analyzed**
   ```
   Error: No sentiment data for token
   ```
   **Solution:** Token may be too new; analysis takes 1-2 hours

### bags.fm Integration Issues

#### Symptom: "bags.fm API unavailable"

**Debug:**

1. **Check API Key**
   ```bash
   echo $BAGS_FM_API_KEY
   ```

2. **Test API Directly**
   ```bash
   curl -H "Authorization: Bearer $BAGS_FM_API_KEY" \
     https://api.bags.fm/v1/tokens
   ```

3. **Check Fallback**
   ```python
   # Should automatically fall back to Jupiter
   # Check logs for:
   # "bags.fm failed, falling back to Jupiter"
   ```

### Wallet Issues

#### Symptom: "Wallet not found"

**Solution:**

```bash
# Check wallet file exists
ls -la ~/.lifeos/wallets/demo_wallet.json

# Check password is set
echo $DEMO_WALLET_PASSWORD
```

#### Symptom: "Wrong password"

**Solution:**

```bash
# Verify password works
python scripts/verify_wallet.py demo_wallet.json

# Reset wallet if needed (WARNING: loses access to funds)
python scripts/reset_demo_wallet.py
```

## Error Messages Reference

### User-Facing Errors

| Error | Meaning | User Action |
|-------|---------|-------------|
| ❌ Insufficient funds | Not enough SOL | Add funds or reduce amount |
| ❌ Slippage exceeded | Price moved too much | Increase slippage or retry |
| ❌ Trade failed | Transaction rejected | Check logs, retry |
| ❌ Token not found | Invalid token address | Verify address |
| ❌ RPC timeout | Solana network slow | Retry in a few seconds |

### Developer Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `KeyError: 'awaiting_token'` | State not initialized | Check context.user_data.get() |
| `AttributeError: 'NoneType'` | Query returned None | Check .first() is not None |
| `IntegrityError` | Duplicate database entry | Add unique constraint check |
| `asyncio.TimeoutError` | Operation took too long | Add timeout, improve speed |

## Performance Issues

### Symptom: Slow response times

**Debug:**

1. **Profile Handler**
   ```text
   import time

   start = time.time()
   await handler_function()
   elapsed = time.time() - start
   logger.info(f"Handler took {elapsed:.2f}s")
   ```

2. **Check Database Queries**
   ```text
   from sqlalchemy import event
   from sqlalchemy.engine import Engine

   @event.listens_for(Engine, "before_cursor_execute")
   def receive_before_cursor_execute(conn, cursor, statement, params, context, executemany):
       logger.debug(f"Query: {statement}")
   ```

3. **Check API Response Times**
   ```text
   start = time.time()
   response = await api_call()
   elapsed = time.time() - start
   logger.info(f"API call took {elapsed:.2f}s")
   ```

### Symptom: High memory usage

**Solution:**

```python
# Close database sessions
session.close()

# Clear large variables
del large_data_structure

# Use generators instead of lists
positions = (p for p in query.all())  # Generator
# Instead of:
# positions = query.all()  # Loads all into memory
```

## Testing Issues

### Symptom: Tests failing locally

**Debug:**

1. **Check Test Database**
   ```bash
   # Use separate test database
   export DATABASE_URL="sqlite:///test.db"
   pytest
   ```

2. **Reset Test State**
   ```bash
   # Clean test artifacts
   rm -rf .pytest_cache
   rm test.db
   pytest --cache-clear
   ```

3. **Run Single Test**
   ```bash
   pytest tests/unit/test_demo_trading.py::test_specific_function -v
   ```

### Symptom: Mock not working

**Example:**

```python
# Make sure mock is before function call
with patch("module.function") as mock_func:
    mock_func.return_value = "mocked"
    result = function_that_calls_it()
    assert result == "expected"
```

## Deployment Issues

### Symptom: Works locally but fails in production

**Check:**

1. **Environment Variables**
   ```bash
   # On production server
   echo $TELEGRAM_BOT_TOKEN
   echo $DEMO_WALLET_PASSWORD
   ```

2. **File Permissions**
   ```bash
   ls -la ~/.lifeos/wallets/
   # Should be readable by bot user
   ```

3. **Python Version**
   ```bash
   python --version
   # Should be 3.12+
   ```

4. **Dependencies**
   ```bash
   pip list | grep telegram
   # Verify correct versions installed
   ```

## Emergency Procedures

### Kill Switch

**Disable all trading:**

```bash
# Set environment variable
export LIFEOS_KILL_SWITCH=true

# Restart bot
supervisorctl restart telegram_bot

# Verify
curl http://localhost:8000/health
# Should show: {"trading_enabled": false}
```

### Rollback to Legacy

**If modular bot has critical issues:**

1. **Update imports in bot.py:**
   ```text
   # Change from:
   from tg_bot.handlers.demo import register_demo_handlers

   # To:
   from tg_bot.handlers.demo_legacy import register_demo_handlers
   ```

2. **Restart bot:**
   ```bash
   supervisorctl restart telegram_bot
   ```

3. **Monitor:**
   ```bash
   tail -f logs/telegram_bot.log
   ```

### Database Recovery

**If database corrupted:**

```bash
# Backup current database
cp demo_positions.db demo_positions.db.backup

# Restore from backup
cp backups/demo_positions.db.20260126 demo_positions.db

# Restart bot
supervisorctl restart telegram_bot
```

## Getting Help

### Check Logs

```bash
# Recent errors
grep ERROR logs/telegram_bot.log | tail -20

# Specific user
grep "user_id=123456" logs/telegram_bot.log

# Trade executions
grep "Trade executed" logs/telegram_bot.log

# TP/SL triggers
grep "TP/SL" logs/telegram_bot.log
```

### Enable Debug Mode

```python
# In bot.py
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Contact Support

When reporting issues, include:

1. **Error message** (full traceback)
2. **Steps to reproduce**
3. **Expected vs actual behavior**
4. **Environment** (OS, Python version, bot version)
5. **Relevant logs** (last 50 lines)

Example bug report:

```
Issue: Trade fails with "Insufficient funds" despite having enough SOL

Steps:
1. /demo → Buy → 0.1 SOL
2. Enter token address: ABC123...
3. Error: "Insufficient funds"

Environment:
- OS: Ubuntu 22.04
- Python: 3.12.10
- Bot version: 2.0
- User ID: 123456

Logs:
[2026-01-26 12:00:00] ERROR - Insufficient funds: Required 0.15 SOL, Available 0.1 SOL
[2026-01-26 12:00:00] ERROR - Missing network fee calculation in buy amount

Expected: Trade should execute
Actual: Error about insufficient funds

Note: Seems to be missing network fee (0.05 SOL) in amount calculation
```

## Useful Commands

### Check Bot Status

```bash
# Supervisor status
supervisorctl status telegram_bot

# Process list
ps aux | grep telegram_bot

# Port listening
netstat -tulpn | grep 8000
```

### Database Queries

```bash
# SQLite console
sqlite3 demo_positions.db

# Count positions
SELECT COUNT(*) FROM demo_positions WHERE status='open';

# Recent trades
SELECT * FROM demo_positions ORDER BY created_at DESC LIMIT 10;

# Active TP/SL orders
SELECT * FROM demo_tp_sl_orders WHERE status='pending';
```

### API Testing

```bash
# Health check
curl http://localhost:8000/health

# Get position
curl http://localhost:8000/api/positions/<position_id>

# Telegram API test
curl "https://api.telegram.org/bot<TOKEN>/getMe"
```
