# Logging Migration Guide

This guide explains how to migrate from basic logging to the new structured logging system.

## Overview

The new logging system provides:
- **Correlation IDs**: Track requests across the system
- **JSON formatting**: Machine-parseable logs for analysis
- **Contextual data**: Automatic inclusion of user_id, trade_id, session_id
- **Log rotation**: Automatic log file rotation and cleanup
- **Structured extra data**: Attach custom data to any log

## Quick Start

### 1. Setup Logging (Application Entry Point)

In your main application file (e.g., `bots/supervisor.py`, `core/daemon.py`):

```python
from core.logging_config import setup_logging

# Setup at application startup
setup_logging(
    log_dir="logs",
    log_file="jarvis.log",
    level="INFO",  # or "DEBUG", "WARNING", "ERROR", "CRITICAL"
    json_format=True,  # JSON for production, False for development
    console_output=True,  # Show logs in console
    max_bytes=100 * 1024 * 1024,  # 100MB per file
    backup_count=10,  # Keep 10 backup files
    extra_fields={"service": "jarvis", "environment": "production"}
)
```

### 2. Get a Logger (Module Level)

Replace existing logger initialization:

**Before:**
```python
import logging
logger = logging.getLogger(__name__)
```

**After:**
```python
from core.logging_config import get_logger
logger = get_logger(__name__)
```

### 3. Use the Logger

The new logger supports the same basic methods with enhanced features:

**Basic logging (works as before):**
```python
logger.info("Starting process")
logger.warning("Low balance detected")
logger.error("Failed to execute trade")
```

**With structured data:**
```python
logger.info("Trade executed",
    symbol="SOL",
    amount=100.50,
    price=95.23,
    user_id="user_123"
)

logger.error("API call failed",
    endpoint="/api/trade",
    status_code=500,
    retry_count=3
)
```

**With exception:**
```python
try:
    execute_trade(symbol, amount)
except Exception as e:
    logger.exception("Trade execution failed",
        symbol=symbol,
        amount=amount,
        error_type=type(e).__name__
    )
```

### 4. Add Correlation Context

Use correlation context to track requests/operations:

```python
from core.logging_config import CorrelationContext

# Option 1: With context manager (recommended)
with CorrelationContext(
    correlation_id="trade-123",  # Optional, auto-generated if not provided
    user_id="user_456",
    trade_id="trade_789"
):
    logger.info("Processing trade request")
    process_trade()
    logger.info("Trade completed")

# Option 2: Manual setting
from core.logging_config import set_correlation_id, set_user_context

correlation_id = set_correlation_id()  # Auto-generate
set_user_context(user_id="user_123", trade_id="trade_456")

logger.info("Trade started")
```

## Migration Examples

### Example 1: Supervisor.py

**Before:**
```python
import logging
logger = logging.getLogger("jarvis.supervisor")

async def _run_component(self, name: str):
    logger.info(f"[{name}] Starting component...")
    try:
        await func()
    except Exception as e:
        logger.error(f"[{name}] Component crashed: {e}", exc_info=True)
```

**After:**
```python
from core.logging_config import get_logger, CorrelationContext
logger = get_logger("jarvis.supervisor")

async def _run_component(self, name: str):
    with CorrelationContext(session_id=name):
        logger.info("Starting component", component=name)
        try:
            await func()
        except Exception as e:
            logger.exception("Component crashed",
                component=name,
                restart_count=self.restart_count
            )
```

### Example 2: Trading Module

**Before:**
```python
import logging
logger = logging.getLogger(__name__)

def execute_trade(symbol, amount):
    logger.info(f"Executing trade: {symbol} {amount}")
    try:
        result = jupiter_client.swap(symbol, amount)
        logger.info(f"Trade successful: {result}")
    except Exception as e:
        logger.error(f"Trade failed: {e}")
```

**After:**
```python
from core.logging_config import get_logger, CorrelationContext
logger = get_logger(__name__)

def execute_trade(symbol, amount, user_id=None):
    with CorrelationContext(user_id=user_id, trade_id=f"trade_{uuid.uuid4()}"):
        logger.info("Executing trade",
            symbol=symbol,
            amount=amount,
            exchange="jupiter"
        )
        try:
            result = jupiter_client.swap(symbol, amount)
            logger.info("Trade successful",
                symbol=symbol,
                amount=amount,
                tx_id=result.tx_id,
                execution_time_ms=result.duration
            )
        except Exception as e:
            logger.exception("Trade failed",
                symbol=symbol,
                amount=amount,
                error_type=type(e).__name__
            )
```

### Example 3: Alert Engine

**Before:**
```python
import logging
logger = logging.getLogger(__name__)

async def create_alert(self, alert_type, title, message):
    logger.info(f"Created alert: {alert.alert_id} - {title}")
    await self._deliver_alert(alert)
```

**After:**
```python
from core.logging_config import get_logger
logger = get_logger(__name__)

async def create_alert(self, alert_type, title, message):
    logger.info("Alert created",
        alert_id=alert.alert_id,
        alert_type=alert_type.value,
        title=title,
        priority=priority.value,
        recipients=len(subscriptions)
    )
    await self._deliver_alert(alert)
```

## Log Output Examples

### JSON Format (Production)

```json
{
  "timestamp": "2026-01-19T18:30:45.123456Z",
  "level": "INFO",
  "logger": "jarvis.trading",
  "message": "Trade executed",
  "module": "trading",
  "function": "execute_trade",
  "line": 145,
  "thread": 12345,
  "thread_name": "MainThread",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user_123",
  "trade_id": "trade_456",
  "service": "jarvis",
  "environment": "production",
  "extra": {
    "symbol": "SOL",
    "amount": 100.5,
    "price": 95.23
  }
}
```

### Structured Format (Console/Development)

```
[2026-01-19 18:30:45] [INFO] [jarvis.trading] Trade executed [correlation_id=550e8400, user_id=user_123, trade_id=trade_456]
```

## Benefits

### 1. Request Tracing
Track a single request/trade through multiple modules:

```python
# In API handler
with CorrelationContext(correlation_id=request_id, user_id=user.id):
    logger.info("API request received")
    result = await trading_service.execute(params)
    logger.info("API request completed")

# In trading service (automatically inherits correlation_id)
async def execute(params):
    logger.info("Executing trade")  # Has same correlation_id
    # ...
```

### 2. Log Analysis
Query JSON logs with tools like `jq`:

```bash
# Find all trades for a user
cat logs/jarvis.log | jq 'select(.user_id == "user_123")'

# Find all errors in the last hour
cat logs/jarvis.log | jq 'select(.level == "ERROR" and .timestamp > "2026-01-19T17:00:00Z")'

# Count trades by symbol
cat logs/jarvis.log | jq 'select(.extra.symbol) | .extra.symbol' | sort | uniq -c
```

### 3. Performance Monitoring
Add timing data to logs:

```python
import time

start = time.time()
with CorrelationContext(trade_id=trade_id):
    result = await execute_trade(symbol, amount)
    duration_ms = (time.time() - start) * 1000

    logger.info("Trade completed",
        symbol=symbol,
        duration_ms=duration_ms,
        success=True
    )
```

## Migration Checklist

- [ ] Add `setup_logging()` to main entry points (`bots/supervisor.py`, `core/daemon.py`)
- [ ] Replace `logging.getLogger(__name__)` with `get_logger(__name__)` in modules
- [ ] Add `CorrelationContext` to request handlers and major operations
- [ ] Convert f-string logs to structured logs with keyword arguments
- [ ] Replace `.error(..., exc_info=True)` with `.exception(...)`
- [ ] Add structured data (user_id, trade_id, etc.) to important logs
- [ ] Test log output format (check both JSON and console)
- [ ] Update log analysis scripts/tools to parse JSON format

## Common Patterns

### Pattern 1: API Request Handler
```python
@app.post("/trade")
async def trade_endpoint(request: TradeRequest, user: User):
    with CorrelationContext(
        correlation_id=request.headers.get("X-Request-ID"),
        user_id=user.id
    ):
        logger.info("Trade request received",
            symbol=request.symbol,
            amount=request.amount
        )

        result = await trading_service.execute(request)

        logger.info("Trade request completed",
            success=result.success,
            tx_id=result.tx_id
        )

        return result
```

### Pattern 2: Background Task
```python
async def process_batch():
    batch_id = str(uuid.uuid4())

    with CorrelationContext(session_id=f"batch_{batch_id}"):
        logger.info("Batch processing started", batch_size=len(items))

        for item in items:
            try:
                await process_item(item)
                logger.debug("Item processed", item_id=item.id)
            except Exception as e:
                logger.exception("Item processing failed", item_id=item.id)

        logger.info("Batch processing completed",
            total=len(items),
            succeeded=success_count,
            failed=error_count
        )
```

### Pattern 3: Error Handling with Retry
```python
def retry_with_logging(func, max_retries=3):
    for attempt in range(1, max_retries + 1):
        try:
            logger.debug("Attempting operation", attempt=attempt, max_retries=max_retries)
            return func()
        except Exception as e:
            if attempt == max_retries:
                logger.exception("Operation failed after max retries",
                    attempts=attempt,
                    error_type=type(e).__name__
                )
                raise

            logger.warning("Operation failed, retrying",
                attempt=attempt,
                remaining=max_retries - attempt,
                error=str(e)
            )
            time.sleep(2 ** attempt)  # Exponential backoff
```

## Notes

- The structured logger is backward-compatible with existing logging code
- JSON formatting is recommended for production (easier to parse/analyze)
- Structured formatting is recommended for development (easier to read)
- Correlation IDs automatically propagate in async contexts
- Log rotation happens automatically based on file size
- All timestamps are in UTC
