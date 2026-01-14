# JARVIS Troubleshooting Guide

Common issues and their solutions.

## Quick Diagnostics

Run the health check:

```bash
python -c "
import asyncio
from core.monitoring import get_health_monitor
async def check():
    health = await get_health_monitor().check_health()
    print(f'Status: {health.status.value}')
    for name, comp in health.components.items():
        print(f'  {name}: {comp.status.value} - {comp.message}')
asyncio.run(check())
"
```

## API Issues

### API returns 500 Internal Server Error

**Symptoms:** All API calls fail with 500 error.

**Check:**
1. View logs for stack trace:
   ```bash
   LOG_LEVEL=DEBUG python -m api.fastapi_app
   ```

2. Verify database connection:
   ```bash
   python scripts/db/backup.py status
   ```

3. Check if all dependencies are installed:
   ```bash
   pip install -r requirements.txt --quiet
   ```

### API returns 429 Too Many Requests

**Symptoms:** Getting rate limited.

**Solution:**
- Wait for rate limit window to reset (check `Retry-After` header)
- Reduce request frequency
- If using API key, ensure higher limits are applied

### API returns 503 Service Unavailable

**Symptoms:** Service is shutting down.

**Solution:**
- Wait for service restart
- If during deployment, normal behavior

## Database Issues

### "Database is locked"

**Symptoms:** SQLite error about database being locked.

**Solutions:**
1. Stop other processes accessing the database
2. Check for zombie processes:
   ```bash
   lsof data/*.db  # Linux/macOS
   ```
3. Increase busy timeout in connection

### Migration Failures

**Symptoms:** Migration fails to apply.

**Solution:**
```bash
# Check migration status
python scripts/db/migrate.py status

# If partially applied, rollback
python scripts/db/migrate.py down

# Re-apply
python scripts/db/migrate.py up
```

### Data Corruption

**Symptoms:** Unexpected query results or SQLite errors.

**Solution:**
1. Restore from backup:
   ```bash
   python scripts/db/backup.py list
   python scripts/db/backup.py restore <backup_file>
   ```

2. If no backup, run integrity check:
   ```bash
   sqlite3 data/jarvis.db "PRAGMA integrity_check"
   ```

## Bot Issues

### Telegram Bot Not Responding

**Symptoms:** Bot doesn't reply to messages.

**Check:**
1. Verify bot token is valid:
   ```python
   import os
   import requests
   token = os.getenv("TELEGRAM_BOT_TOKEN")
   r = requests.get(f"https://api.telegram.org/bot{token}/getMe")
   print(r.json())
   ```

2. Check if bot is running:
   ```bash
   ps aux | grep tg_bot  # Linux/macOS
   ```

3. Check bot health:
   ```python
   from core.monitoring import get_bot_health_checker
   checker = get_bot_health_checker()
   print(checker.get_summary())
   ```

### Twitter Bot Rate Limited

**Symptoms:** Twitter API errors about rate limits.

**Solution:**
- Check rate limit status in logs
- Twitter API has strict limits; wait for reset
- Consider upgrading API tier

### Bot Crashes Repeatedly

**Symptoms:** Bot restarts in a loop.

**Solution:**
1. Check error logs for root cause
2. Verify all required environment variables
3. Test individual components:
   ```bash
   python -c "from bots.telegram import config; print(config)"
   ```

## LLM Provider Issues

### "API key invalid"

**Symptoms:** Authentication errors from LLM providers.

**Check:**
1. Verify key in environment:
   ```bash
   echo $GROQ_API_KEY  # Should not be empty
   ```

2. Test API key directly:
   ```python
   from core.llm import quick_generate
   response = await quick_generate("Hello")
   print(response)
   ```

### High LLM Costs

**Symptoms:** Unexpectedly high API bills.

**Check:**
```python
from core.llm import get_cost_tracker
tracker = get_cost_tracker()
print(tracker.get_stats(hours=24))
print(tracker.get_top_models())
```

**Solutions:**
- Use cheaper models for simple tasks
- Implement caching for repeated queries
- Set budget alerts:
  ```python
  tracker.add_budget_alert("daily", 10.0, "daily")
  ```

### LLM Response Timeout

**Symptoms:** Requests hang and eventually timeout.

**Solutions:**
1. Use a different provider as fallback:
   ```python
   from core.llm import get_llm
   llm = await get_llm()
   response = await llm.generate(prompt, fallback_providers=["groq", "ollama"])
   ```

2. Check provider status pages

## Trading/Treasury Issues

### Trade Execution Failures

**Symptoms:** Trades fail to execute.

**Check:**
1. Wallet balance:
   ```python
   from core.treasury import get_wallet
   wallet = get_wallet()
   print(await wallet.get_balance())
   ```

2. RPC connection:
   ```python
   from core.monitoring import get_health_monitor
   health = await get_health_monitor().check_component("solana_rpc")
   print(health)
   ```

3. Transaction logs:
   ```bash
   grep "trade" data/logs/*.log | tail -50
   ```

### High Slippage

**Symptoms:** Trades execute at worse prices than expected.

**Solutions:**
- Reduce trade size
- Increase slippage tolerance for volatile tokens
- Check market liquidity before trading

## Monitoring Issues

### Grafana Not Showing Data

**Symptoms:** Dashboards are empty.

**Check:**
1. Verify Prometheus is collecting metrics
2. Check data source configuration
3. Verify time range in Grafana

### Alerts Not Firing

**Symptoms:** Conditions met but no alerts.

**Check:**
```python
from core.monitoring import get_metrics_collector
collector = get_metrics_collector()
print(collector.get_summary())
```

## Performance Issues

### Slow Response Times

**Symptoms:** API responses take > 1 second.

**Solutions:**
1. Enable caching:
   ```python
   from core.cache import cached
   @cached(ttl=60)
   async def slow_operation():
       ...
   ```

2. Check database indexes:
   ```bash
   sqlite3 data/jarvis.db ".indices"
   ```

3. Profile slow endpoints:
   ```python
   from core.performance import profiler
   profiler.enable()
   # Run slow code
   profiler.print_stats()
   ```

### Memory Leaks

**Symptoms:** Memory usage grows over time.

**Check:**
```python
import tracemalloc
tracemalloc.start()
# Run code
snapshot = tracemalloc.take_snapshot()
for stat in snapshot.statistics('lineno')[:10]:
    print(stat)
```

## Deployment Issues

### Container Won't Start

**Check:**
1. View container logs:
   ```bash
   docker logs jarvis-api
   ```

2. Verify environment variables are passed

3. Check port bindings

### Graceful Shutdown Stuck

**Symptoms:** Service takes too long to shut down.

**Solution:**
```python
from core.lifecycle import get_shutdown_manager
status = get_shutdown_manager().get_status()
print(f"Phase: {status.phase}")
print(f"In-flight: {status.in_flight_requests}")
```

## Getting Help

If none of the above solutions work:

1. **Gather diagnostics:**
   ```bash
   python -c "
   from core.monitoring import get_health_monitor
   import asyncio
   import json
   async def diag():
       health = await get_health_monitor().check_health()
       return {
           'status': health.status.value,
           'components': {k: v.status.value for k, v in health.components.items()}
       }
   print(json.dumps(asyncio.run(diag()), indent=2))
   "
   ```

2. **Check logs:**
   ```bash
   tail -100 data/logs/jarvis.log
   ```

3. **Open an issue** with:
   - Python version: `python --version`
   - OS: `uname -a` or `ver`
   - Error message and stack trace
   - Steps to reproduce
