# JARVIS Performance Tuning Guide

A comprehensive guide to optimizing JARVIS for production workloads.

---

## Table of Contents

1. [Quick Wins](#quick-wins)
2. [Python Optimization](#python-optimization)
3. [Async Best Practices](#async-best-practices)
4. [Database Optimization](#database-optimization)
5. [Caching Strategies](#caching-strategies)
6. [API Performance](#api-performance)
7. [LLM Optimization](#llm-optimization)
8. [Bot Performance](#bot-performance)
9. [Monitoring & Profiling](#monitoring--profiling)
10. [Resource Sizing](#resource-sizing)

---

## Quick Wins

### Immediate Improvements

1. **Enable connection pooling**
   ```python
   # config.py
   DATABASE_POOL_SIZE = 10
   DATABASE_MAX_OVERFLOW = 20
   ```

2. **Use response caching**
   ```python
   from core.cache import cached

   @cached(ttl=60)
   async def get_token_prices():
       # Expensive API call cached for 60 seconds
       pass
   ```

3. **Enable compression**
   ```python
   # Already in api/middleware/compression.py
   # Gzip responses > 500 bytes
   ```

4. **Batch API requests**
   ```python
   # Instead of N individual requests
   prices = await asyncio.gather(*[
       get_price(token) for token in tokens
   ])
   ```

---

## Python Optimization

### Use Efficient Data Structures

```python
# Use set for membership testing
allowed_tokens = {"SOL", "USDC", "RAY"}  # O(1) lookup
if token in allowed_tokens:
    pass

# Use deque for queues
from collections import deque
message_queue = deque(maxlen=1000)  # Auto-evicts old items

# Use defaultdict to avoid key checks
from collections import defaultdict
user_counts = defaultdict(int)
user_counts[user_id] += 1  # No KeyError
```

### Avoid Common Pitfalls

```python
# BAD: String concatenation in loop
result = ""
for item in items:
    result += str(item)  # Creates new string each time

# GOOD: Join list
result = "".join(str(item) for item in items)

# BAD: List when generator works
sum([x*x for x in range(1000000)])  # Creates full list

# GOOD: Generator expression
sum(x*x for x in range(1000000))  # Memory efficient
```

### Type Hints for Performance

```python
# Slots reduce memory usage
from dataclasses import dataclass

@dataclass(slots=True)
class TradeRecord:
    symbol: str
    amount: float
    price: float
    # ~40% less memory than regular class
```

---

## Async Best Practices

### Proper Concurrent Execution

```python
import asyncio

# BAD: Sequential execution
async def fetch_all_sequential(urls):
    results = []
    for url in urls:
        result = await fetch(url)  # Waits each time
        results.append(result)
    return results

# GOOD: Concurrent execution
async def fetch_all_concurrent(urls):
    return await asyncio.gather(*[fetch(url) for url in urls])

# GOOD: With error handling
async def fetch_all_safe(urls):
    results = await asyncio.gather(
        *[fetch(url) for url in urls],
        return_exceptions=True
    )
    return [r for r in results if not isinstance(r, Exception)]
```

### Avoid Blocking in Async

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)

# BAD: Blocking call in async function
async def bad_read_file(path):
    with open(path) as f:
        return f.read()  # Blocks event loop!

# GOOD: Run blocking code in executor
async def good_read_file(path):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        executor,
        lambda: open(path).read()
    )

# GOOD: Use aiofiles
import aiofiles

async def best_read_file(path):
    async with aiofiles.open(path) as f:
        return await f.read()
```

### Semaphores for Concurrency Control

```python
# Limit concurrent requests
semaphore = asyncio.Semaphore(10)

async def rate_limited_fetch(url):
    async with semaphore:
        return await fetch(url)

# Fetch 100 URLs, max 10 at a time
results = await asyncio.gather(*[
    rate_limited_fetch(url) for url in urls
])
```

---

## Database Optimization

### Connection Pooling

```python
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,          # Base connections
    max_overflow=20,       # Extra under load
    pool_timeout=30,       # Wait for connection
    pool_recycle=1800,     # Refresh connections
    pool_pre_ping=True,    # Validate connections
)
```

### Query Optimization

```python
# BAD: N+1 query problem
async def get_users_with_trades_bad():
    users = await db.fetch_all("SELECT * FROM users")
    for user in users:
        user.trades = await db.fetch_all(
            "SELECT * FROM trades WHERE user_id = :id",
            {"id": user.id}
        )  # N additional queries!
    return users

# GOOD: Single query with join
async def get_users_with_trades_good():
    return await db.fetch_all("""
        SELECT u.*, t.*
        FROM users u
        LEFT JOIN trades t ON u.id = t.user_id
    """)

# GOOD: Use EXPLAIN ANALYZE
# EXPLAIN ANALYZE SELECT * FROM trades WHERE created_at > NOW() - INTERVAL '1 day';
```

### Indexing Strategy

```sql
-- Index for frequent queries
CREATE INDEX idx_trades_user_created
ON trades(user_id, created_at DESC);

-- Partial index for active records
CREATE INDEX idx_users_active
ON users(last_active)
WHERE deleted_at IS NULL;

-- Cover index for common query
CREATE INDEX idx_prices_symbol_time
ON prices(symbol, timestamp DESC)
INCLUDE (price, volume);
```

### Batch Operations

```python
# BAD: Individual inserts
for record in records:
    await db.execute(
        "INSERT INTO logs VALUES (:data)",
        {"data": record}
    )

# GOOD: Batch insert
await db.execute_many(
    "INSERT INTO logs VALUES (:data)",
    [{"data": r} for r in records]
)

# GOOD: Using COPY for bulk inserts
from asyncpg import Connection

async def bulk_insert(conn: Connection, records):
    await conn.copy_records_to_table(
        'logs',
        records=records,
        columns=['timestamp', 'level', 'message']
    )
```

---

## Caching Strategies

### Multi-Level Caching

```python
from core.cache import LocalCache, RedisCache, cached

# L1: In-memory (fastest, limited size)
local_cache = LocalCache(maxsize=1000)

# L2: Redis (shared across instances)
redis_cache = RedisCache()

@cached(ttl=60, cache=local_cache)
async def get_token_info(symbol: str):
    # Check L2 cache
    cached = await redis_cache.get(f"token:{symbol}")
    if cached:
        return cached

    # Fetch from source
    info = await fetch_token_info(symbol)

    # Store in L2
    await redis_cache.set(f"token:{symbol}", info, ttl=300)

    return info
```

### Cache Invalidation

```python
# Time-based expiry (simple)
@cached(ttl=60)
async def get_prices():
    pass

# Event-based invalidation
async def on_trade_executed(trade):
    # Invalidate related caches
    await cache.delete(f"balance:{trade.user_id}")
    await cache.delete(f"positions:{trade.user_id}")

# Version-based invalidation
cache_version = 1

@cached(key=f"data:v{cache_version}:{{id}}")
async def get_data(id):
    pass

# Bump version to invalidate all
cache_version = 2
```

### Cache Warming

```python
async def warm_cache_on_startup():
    """Pre-populate cache with hot data."""
    # Load popular tokens
    popular_tokens = ["SOL", "USDC", "RAY", "ORCA"]
    await asyncio.gather(*[
        get_token_info(t) for t in popular_tokens
    ])

    # Load active user data
    active_users = await db.fetch_all(
        "SELECT id FROM users WHERE last_active > NOW() - INTERVAL '1 hour'"
    )
    await asyncio.gather(*[
        get_user_data(u.id) for u in active_users
    ])
```

---

## API Performance

### Response Optimization

```python
from fastapi import Response
from fastapi.responses import ORJSONResponse

# Use faster JSON library
app = FastAPI(default_response_class=ORJSONResponse)

# Stream large responses
from fastapi.responses import StreamingResponse

@app.get("/export")
async def export_data():
    async def generate():
        async for row in db.iterate("SELECT * FROM logs"):
            yield json.dumps(row) + "\n"

    return StreamingResponse(generate(), media_type="application/ndjson")
```

### Pagination

```python
from fastapi import Query

@app.get("/trades")
async def list_trades(
    cursor: str = None,
    limit: int = Query(default=50, le=100)
):
    # Cursor-based pagination (efficient for large datasets)
    query = "SELECT * FROM trades"
    if cursor:
        query += " WHERE id > :cursor"
    query += " ORDER BY id LIMIT :limit"

    trades = await db.fetch_all(query, {"cursor": cursor, "limit": limit})

    next_cursor = trades[-1].id if len(trades) == limit else None

    return {
        "data": trades,
        "next_cursor": next_cursor
    }
```

### Request Coalescing

```python
from asyncio import Lock
from collections import defaultdict

_pending_requests = defaultdict(list)
_locks = defaultdict(Lock)

async def coalesced_fetch(key: str, fetch_func):
    """Multiple simultaneous requests share one fetch."""
    async with _locks[key]:
        if key in _pending_requests:
            # Another request is fetching, wait for it
            future = asyncio.Future()
            _pending_requests[key].append(future)
            return await future

        _pending_requests[key] = []

    try:
        result = await fetch_func()

        # Notify waiting requests
        for future in _pending_requests[key]:
            future.set_result(result)

        return result
    finally:
        del _pending_requests[key]
```

---

## LLM Optimization

### Token Management

```python
from core.llm.cost_tracker import estimate_tokens

def optimize_prompt(prompt: str, max_tokens: int = 4000) -> str:
    """Keep prompts within token limits."""
    estimated = estimate_tokens(prompt)

    if estimated <= max_tokens:
        return prompt

    # Truncate from middle to preserve context
    lines = prompt.split('\n')
    while estimate_tokens('\n'.join(lines)) > max_tokens:
        mid = len(lines) // 2
        lines.pop(mid)

    return '\n'.join(lines)
```

### Response Caching

```python
import hashlib

def cache_key_for_prompt(prompt: str, model: str) -> str:
    """Generate cache key for LLM responses."""
    content = f"{model}:{prompt}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]

@cached(ttl=3600)
async def cached_completion(prompt: str, model: str = "claude-3"):
    return await llm.complete(prompt, model=model)
```

### Streaming Responses

```python
async def stream_response(prompt: str):
    """Stream LLM response for better UX."""
    async for chunk in llm.stream(prompt):
        yield chunk

# In bot handler
async def handle_question(update, context):
    message = await update.reply_text("Thinking...")

    full_response = ""
    async for chunk in stream_response(update.text):
        full_response += chunk
        if len(full_response) % 100 == 0:  # Update every 100 chars
            await message.edit_text(full_response + "...")

    await message.edit_text(full_response)
```

---

## Bot Performance

### Message Queue

```python
from asyncio import Queue

message_queue = Queue(maxsize=10000)

async def message_producer(update):
    await message_queue.put(update)

async def message_consumer():
    while True:
        updates = []
        # Batch process messages
        while not message_queue.empty() and len(updates) < 100:
            updates.append(await message_queue.get())

        if updates:
            await process_batch(updates)
        else:
            await asyncio.sleep(0.1)
```

### Rate Limit Handling

```python
from core.bot.rate_limiter import BotRateLimiter

limiter = BotRateLimiter()

async def send_with_rate_limit(chat_id: str, text: str):
    result = await limiter.check_limit(chat_id, "chat_message")

    if not result.allowed:
        await asyncio.sleep(result.retry_after)
        return await send_with_rate_limit(chat_id, text)

    return await bot.send_message(chat_id, text)
```

---

## Monitoring & Profiling

### Performance Metrics

```python
from core.monitoring import metrics

@metrics.timer("api_request_duration")
async def handle_request(request):
    pass

# Track custom metrics
metrics.gauge("active_connections", connection_count)
metrics.counter("trades_executed", labels={"symbol": symbol})
```

### Profiling

```python
# CPU profiling
import cProfile
import pstats

def profile_function(func):
    profiler = cProfile.Profile()
    profiler.enable()
    result = func()
    profiler.disable()

    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(20)

    return result

# Memory profiling
from memory_profiler import profile

@profile
def memory_intensive_function():
    pass

# Async profiling
import yappi

yappi.set_clock_type("wall")
yappi.start()
# ... run code ...
yappi.stop()
yappi.get_func_stats().print_all()
```

### Query Logging

```python
import logging

# Enable SQL logging in development
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# Log slow queries
from sqlalchemy import event

@event.listens_for(engine.sync_engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, *args):
    conn.info['query_start_time'] = time.time()

@event.listens_for(engine.sync_engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, *args):
    elapsed = time.time() - conn.info['query_start_time']
    if elapsed > 1.0:  # Log queries > 1 second
        logger.warning(f"Slow query ({elapsed:.2f}s): {statement[:100]}")
```

---

## Resource Sizing

### Memory Guidelines

| Component | Base | Per 1K Users | Max |
|-----------|------|--------------|-----|
| API Server | 256MB | +50MB | 2GB |
| Bot Handler | 128MB | +25MB | 1GB |
| Task Queue | 256MB | +100MB | 4GB |

### Connection Limits

| Resource | Min | Recommended | Max |
|----------|-----|-------------|-----|
| DB Pool | 5 | 10-20 | 50 |
| Redis Pool | 5 | 10 | 30 |
| HTTP Client | 10 | 50 | 100 |

### Scaling Thresholds

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| CPU | 70% | 90% | Scale up |
| Memory | 80% | 95% | Scale up |
| Latency p99 | 500ms | 2s | Investigate |
| Error rate | 1% | 5% | Alert |

---

## Performance Checklist

### Before Deployment

- [ ] Connection pooling enabled
- [ ] Response caching configured
- [ ] Compression enabled
- [ ] Database indexes created
- [ ] Slow query logging enabled
- [ ] Memory limits set
- [ ] Rate limiting configured

### Regular Review

- [ ] Review slow query logs weekly
- [ ] Check cache hit rates
- [ ] Monitor memory trends
- [ ] Review error rates
- [ ] Check latency percentiles

---

## Tools

### Recommended Tools

| Tool | Purpose |
|------|---------|
| `py-spy` | CPU profiling (production safe) |
| `memory_profiler` | Memory analysis |
| `yappi` | Async profiling |
| `pgBadger` | PostgreSQL log analysis |
| `redis-cli --stat` | Redis performance |
| `locust` | Load testing |

### Commands

```bash
# Profile running process
py-spy top --pid $PID

# Memory usage
python -m memory_profiler script.py

# PostgreSQL stats
psql -c "SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"

# Redis memory
redis-cli INFO memory
```
