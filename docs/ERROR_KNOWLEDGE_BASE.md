# Jarvis Bot Error Knowledge Base

**Last Updated**: 2026-01-24
**Purpose**: Persistent error tracking and solutions for all bot components

---

## Common Issues & Solutions

### 1. Telegram Bot Exit Code 1

**Symptoms**:
- Bot crashes with "Telegram bot exited with code 1"
- Consecutive failures: 5+
- Bot restarts repeatedly

**Root Causes** ([Source](https://github.com/python-telegram-bot/python-telegram-bot/wiki/Exception-Handling)):
1. Missing error handlers → unhandled exceptions crash bot
2. Network/connection timeouts
3. Missing dependencies (base58, pynacl, etc.)
4. Import errors from missing modules

**Solutions**:
```python
# Add error handler
async def error_handler(update, context):
    logger.exception(f"Exception: {context.error}")

application.add_error_handler(error_handler)

# Enable logging
import logging
logging.basicConfig(level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
```

---

### 2. Missing Python Dependencies

**Symptoms**:
- `ModuleNotFoundError: No module named 'base58'`
- Components fail to import

**Required Dependencies** ([Source](https://rpcfast.com/blog/solana-trading-bot-guide)):
```bash
# Core Solana
base58>=2.1.1
pynacl>=1.5.0
bip-utils>=2.7.0
solana-py

# Telegram
python-telegram-bot>=20.7
aiohttp>=3.9.0

# Trading
anthropic>=0.32.0
requests>=2.31.0
```

**Fix**:
```bash
pip3 install base58 pynacl bip-utils --break-system-packages
```

---

### 3. Solana RPC Rate Limiting

**Symptoms** ([Source](https://rpcfast.com/blog/real-time-rpc-on-solana)):
- Error 429 storms
- `sendTransaction()` fails silently
- Outdated account data (>3 slot lag)

**Root Cause**:
- Public RPC endpoints throttle during high volume
- Shared endpoints de-prioritize bot traffic

**Solutions**:
1. **Use Premium RPC**: Switch from public to paid RPC (Helius, QuickNode)
2. **Implement Retry Logic**:
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def send_transaction(tx):
    # Transaction logic
    pass
```

3. **Add Circuit Breaker**:
```python
if consecutive_failures > 5:
    await asyncio.sleep(60)  # Cool down
    consecutive_failures = 0
```

---

### 4. Multiple Bot Instances

**Symptoms**:
- Duplicate supervisors running
- Port conflicts (8080 address in use)
- Competing processes

**Solution - Add Process Lock**:
```python
import fcntl
import os

LOCK_FILE = "/tmp/jarvis_supervisor.lock"

def acquire_lock():
    lock = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock.write(str(os.getpid()))
        return lock
    except IOError:
        print("Another instance is running")
        sys.exit(1)
```

---

### 5. Jarvis XAI API Errors

**Symptoms**:
- "Technical error: <error detail>"
- XAI rate limiting
- Authentication failures

**Common Errors**:
1. `401 Unauthorized` - Invalid API key
2. `429 Too Many Requests` - Rate limit hit
3. `503 Service Unavailable` - XAI down

**Solutions**:
```python
# Check API key validity
import os
xai_key = os.getenv("XAI_API_KEY")
if not xai_key or len(xai_key) < 20:
    raise ValueError("Invalid XAI_API_KEY")

# Add exponential backoff
from openai import OpenAI
client = OpenAI(
    api_key=xai_key,
    base_url="https://api.x.ai/v1",
    max_retries=3,
    timeout=30.0
)
```

---

### 6. X-Bot Not Posting

**Symptoms**:
- No tweets from @Jarvis_lifeos
- Twitter client errors
- `tweepy not installed` warnings

**Root Causes**:
1. Missing Twitter API credentials
2. Missing tweepy library
3. X_BOT_ENABLED=false

**Fix**:
```bash
# Install tweepy
pip3 install tweepy --break-system-packages

# Check credentials
python3 << EOF
import os
print("Twitter API Key:", bool(os.getenv("TWITTER_API_KEY")))
print("X Bot Enabled:", os.getenv("X_BOT_ENABLED", "true"))
EOF
```

---

## Prevention Strategies

### 1. Comprehensive Logging

Add to ALL bot components:
```python
import logging
import traceback

logger = logging.getLogger(__name__)

try:
    # Bot logic
    pass
except Exception as e:
    logger.exception(f"Critical error in {__name__}: {e}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    # Continue running
```

### 2. Health Monitoring

```python
class HealthMonitor:
    def __init__(self):
        self.last_success = {}
        self.error_counts = {}

    def record_success(self, component):
        self.last_success[component] = time.time()
        self.error_counts[component] = 0

    def record_failure(self, component, error):
        self.error_counts[component] += 1
        logger.error(f"{component} failed: {error}")

        if self.error_counts[component] > 10:
            # Alert admin
            pass
```

### 3. Dependency Check on Startup

```python
def check_dependencies():
    required = ['base58', 'pynacl', 'telegram', 'anthropic', 'aiohttp']
    missing = []
    for module in required:
        try:
            __import__(module)
        except ImportError:
            missing.append(module)

    if missing:
        raise RuntimeError(f"Missing dependencies: {missing}")
```

---

## Research Sources

- [Solana Trading Bot Guide 2026](https://rpcfast.com/blog/solana-trading-bot-guide)
- [Python Telegram Bot Exception Handling](https://github.com/python-telegram-bot/python-telegram-bot/wiki/Exception-Handling)
- [Solana RPC Rate Limiting Solutions](https://rpcfast.com/blog/real-time-rpc-on-solana)
- [Common Solana Bot Mistakes](https://coincodecap.com/common-mistakes-to-avoid-with-solana-telegram-trading-bots)

---

## Incident Log

### 2026-01-23 Session - Multiple Critical Fixes

#### 1. Syntax Error in bot_core.py (FIXED)
- **Timestamp**: 2026-01-23 ~20:00 UTC
- **Issue**: Lines 1900-1908 contained actual newline characters instead of `\n\n` escape sequences
- **Symptom**: Bot crashed on startup with SyntaxError
- **Root Cause**: File corruption during manual editing or deployment
- **Fix**: Deployed correct file from local to VPS using scp
- **Prevention**:
  - Always test syntax before deployment: `python -m py_compile bot_core.py`
  - Use file integrity checks (hash comparison) before deployment
  - Implement automated deployment pipeline

#### 2. Demo.py IndexError (FIXED)
- **Timestamp**: 2026-01-23 ~20:30 UTC
- **Issue**: 13 instances of unsafe `.split(":")[index]` without bounds checking
- **Symptom**: `IndexError: list index out of range` when parsing commands
- **Root Cause**: User input didn't contain expected `:` delimiter
- **Fix**: Added bounds checking pattern:
```python
# BEFORE (unsafe)
token = action.split(":")[1]

# AFTER (safe)
parts = action.split(":")
token = parts[1] if len(parts) > 1 else ""
```
- **Prevention**:
  - Never assume list/array bounds without checking
  - Use defensive parsing for all user input
  - Add validation before accessing indices

#### 3. Demo.py AttributeError (FIXED)
- **Timestamp**: 2026-01-23 ~20:45 UTC
- **Issue**: `update.message` accessed without null check
- **Symptom**: `AttributeError: 'NoneType' object has no attribute 'message'`
- **Root Cause**: Telegram callback queries don't have `.message` attribute
- **Fix**: Added null check at function entry:
  ```python
  async def demo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
      if not update or not update.message:
          return
      # Safe to use update.message now
  ```
- **Prevention**:
  - Always validate Telegram Update objects before use
  - Check both `update` and `update.message` existence
  - Use type guards for optional attributes

#### 4. Single Instance Lock (IMPLEMENTED)
- **Timestamp**: 2026-01-23 ~21:00 UTC
- **Issue**: Multiple supervisor instances running simultaneously
- **Symptom**: Duplicate processes, port conflicts (8080 address in use)
- **Root Cause**: No process locking mechanism in supervisor.py
- **Fix**: Added SingleInstanceLock to supervisor.py main():
  ```python
  from core.utils import SingleInstanceLock

  def main():
      lock = SingleInstanceLock("/tmp/jarvis_supervisor.lock")
      if not lock.acquire():
          print("Another instance is running. Exiting.")
          sys.exit(1)

      try:
          # Run supervisor
          pass
      finally:
          lock.release()
  ```
- **Lock File**: `/tmp/jarvis_supervisor.lock`
- **Prevention**:
  - Always use process locks for singleton services
  - Check for running instances before starting
  - Clean up lock files on graceful shutdown

#### 5. Transaction Amount Display (FIXED)
- **Timestamp**: 2026-01-23 ~21:30 UTC
- **Issue**: Showing planned SOL amount instead of actual blockchain transaction amount
- **Symptom**: Reports showed "Spent 0.001 SOL" but blockchain showed 0.02 SOL
- **Root Cause**: Using `amount` parameter (user input) instead of `sol_cost` (actual transaction)
- **Fix**: Updated buy/sell report format to show both:
  ```python
  # Buy report
  f"💰 Spent {sol_cost:.4f} SOL (planned: {amount:.4f})"

  # Sell report
  f"💰 Received {sol_received:.4f} SOL (sold: {amount_sold:.4f} tokens)"
  ```
- **Prevention**:
  - Always display actual blockchain amounts, not planned amounts
  - Show both planned vs actual for verification
  - Add validation to alert if actual differs significantly from planned

---

### 2026-01-24 03:00 UTC
- **Issue**: Telegram bot crash loop (exit code 1)
- **Cause**: Missing base58 dependency
- **Fix**: Installed base58, added error logging
- **Prevention**: Added dependency checker to supervisor

### 2026-01-24 02:54 UTC
- **Issue**: Multiple supervisor instances
- **Cause**: No process locking mechanism
- **Fix**: Kill all instances, start one
- **Prevention**: TODO - Add file lock

---

#### 6. X-Bot Double Posting to Telegram (FIXED)
- **Timestamp**: 2026-01-24 ~04:00 UTC
- **Issue**: Every X/Twitter post was being sent to Telegram TWICE
- **Symptom**: Duplicate messages in Telegram chat for each tweet
- **Root Cause**: Two sync calls in autonomous_engine.py:
  1. Line 3943: `await sync_tweet_to_telegram(...)` after posting
  2. Line 3752: `await sync_tweet_to_telegram(...)` in broadcast loop
- **Fix**: Removed duplicate call at line 3752
  ```python
  # REMOVED duplicate sync:
  # await sync_tweet_to_telegram(content, tweet_url, "Jarvis_lifeos")

  # KEPT only the post-tweet sync at line 3943
  ```
- **Prevention**:
  - Search for duplicate function calls in async workflows
  - Use event-driven architecture instead of multiple manual calls
  - Add deduplication check in sync functions

#### 7. Telegram Polling Conflicts (RESOLVED)
- **Timestamp**: 2026-01-24 ~04:30 UTC
- **Issue**: "Conflict: terminated by other getUpdates request"
- **Symptom**: Telegram bot couldn't receive messages, constant 409 errors
- **Root Cause**: Stale polling sessions on Telegram's servers
- **Fix**: Cleared webhook and deleted all lock files:
  ```bash
  curl -X POST "https://api.telegram.org/bot<TOKEN>/deleteWebhook?drop_pending_updates=true"
  rm -f /tmp/jarvis_*.lock
  rm -f /root/.local/state/jarvis/locks/*.lock
  ```
- **Prevention**:
  - Always clear webhooks before starting polling mode
  - Clean up lock files on graceful shutdown
  - Add startup check to detect orphaned sessions

#### 8. Docker Multi-Container Architecture (IMPLEMENTED)
- **Timestamp**: 2026-01-24 ~05:00 UTC
- **Achievement**: Created comprehensive multi-service Docker architecture
- **Services Created**:
  - `supervisor` - Lightweight orchestrator
  - `telegram-bot` - Main Telegram interface
  - `buy-tracker` - KR8TIV token tracking bot
  - `twitter-bot` - Autonomous X posting
  - `treasury` - Trading engine
  - `sentiment-reporter` - Market sentiment analysis
  - `bags-intel` - bags.fm graduation monitoring
  - `redis` - Shared cache and state
  - `prometheus` + `grafana` - Optional monitoring
- **Benefits**:
  - Service isolation - one container crash won't affect others
  - Resource limits per service
  - Independent scaling
  - Health checks per container
  - Separate logging per service
- **Files Created**:
  - `Dockerfile.telegram`, `Dockerfile.buy-tracker`, `Dockerfile.twitter`
  - `Dockerfile.treasury`, `Dockerfile.sentiment`, `Dockerfile.bags`
  - `docker-compose-multi.yml` - Full multi-container orchestration
  - `.env.multi.example` - Environment configuration template
- **Usage**:
  ```bash
  # Start all core services
  docker-compose -f docker-compose-multi.yml up -d

  # Start with monitoring
  docker-compose -f docker-compose-multi.yml --profile monitoring up -d

  # Start with bags intel
  docker-compose -f docker-compose-multi.yml --profile full up -d
  ```

---

## TODO - Improvements Needed

- [x] Add process file lock to supervisor (COMPLETED 2026-01-23)
- [x] Fix X-Bot double posting (COMPLETED 2026-01-24)
- [x] Implement Docker multi-container architecture (COMPLETED 2026-01-24)
- [ ] Deploy Docker setup to VPS
- [ ] Implement health monitoring with alerts
- [ ] Add dependency checker on startup
- [ ] Migrate from public to premium Solana RPC
- [ ] Add circuit breaker for RPC failures
- [ ] Create automated error recovery system
- [ ] Add NotebookLM integration for error pattern learning
- [ ] Add automated deployment pipeline with syntax checking
- [ ] Implement file integrity validation (hash checking)
- [ ] Configure separate Telegram tokens for each bot (optional)
