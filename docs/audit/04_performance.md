# Performance & Caching Improvements (46-55)

## 46. Redis Caching Layer

```python
# core/cache/redis_cache.py
import redis
import json
from typing import Any, Optional

class RedisCache:
    def __init__(self, url: str = "redis://localhost:6379"):
        self.client = redis.from_url(url)
    
    def get(self, key: str) -> Optional[Any]:
        data = self.client.get(key)
        return json.loads(data) if data else None
    
    def set(self, key: str, value: Any, ttl: int = 300):
        self.client.setex(key, ttl, json.dumps(value))
    
    def delete(self, key: str):
        self.client.delete(key)
    
    def cached(self, key_prefix: str, ttl: int = 300):
        def decorator(func):
            async def wrapper(*args, **kwargs):
                key = f"{key_prefix}:{hash(str(args) + str(kwargs))}"
                cached = self.get(key)
                if cached:
                    return cached
                result = await func(*args, **kwargs)
                self.set(key, result, ttl)
                return result
            return wrapper
        return decorator

cache = RedisCache()
```

## 47. Query Optimization

```python
# core/database/optimized_queries.py
from contextlib import contextmanager

class OptimizedQueryBuilder:
    @staticmethod
    def get_trades_paginated(conn, symbol: str = None, limit: int = 100, offset: int = 0):
        query = """
            SELECT id, symbol, side, amount, price, status, created_at
            FROM trades
            WHERE 1=1
        """
        params = []
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        return conn.execute(query, params).fetchall()
    
    @staticmethod
    def get_position_summary(conn, user_id: str):
        return conn.execute("""
            SELECT symbol, SUM(CASE WHEN side='buy' THEN amount ELSE -amount END) as net_position,
                   AVG(price) as avg_price
            FROM trades WHERE user_id = ? AND status = 'filled'
            GROUP BY symbol HAVING net_position != 0
        """, [user_id]).fetchall()
```

## 48. Lazy Loading for Heavy Modules

```python
# core/lazy_imports.py
from typing import Any
import importlib

class LazyModule:
    def __init__(self, module_name: str):
        self._module_name = module_name
        self._module = None
    
    def _load(self):
        if self._module is None:
            self._module = importlib.import_module(self._module_name)
        return self._module
    
    def __getattr__(self, name: str) -> Any:
        return getattr(self._load(), name)

# Usage - heavy modules loaded only when accessed
numpy = LazyModule('numpy')
pandas = LazyModule('pandas')
torch = LazyModule('torch')
```

## 49. Memory Profiling

```python
# core/profiling/memory.py
import tracemalloc
import functools
import logging

logger = logging.getLogger(__name__)

def profile_memory(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        tracemalloc.start()
        result = func(*args, **kwargs)
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        logger.info(f"{func.__name__}: Current={current/1024:.1f}KB, Peak={peak/1024:.1f}KB")
        return result
    return wrapper

def get_memory_snapshot():
    import psutil
    process = psutil.Process()
    return {
        "rss_mb": process.memory_info().rss / 1024 / 1024,
        "vms_mb": process.memory_info().vms / 1024 / 1024,
        "percent": process.memory_percent()
    }
```

## 50. Request Batching

```python
# core/batching/request_batcher.py
import asyncio
from typing import List, Callable, Any
from collections import defaultdict

class RequestBatcher:
    def __init__(self, batch_fn: Callable, max_batch_size: int = 50, max_wait_ms: int = 10):
        self.batch_fn = batch_fn
        self.max_batch_size = max_batch_size
        self.max_wait_ms = max_wait_ms
        self.pending: dict = defaultdict(list)
        self._lock = asyncio.Lock()
    
    async def add(self, key: str, item: Any) -> Any:
        async with self._lock:
            future = asyncio.Future()
            self.pending[key].append((item, future))
            
            if len(self.pending[key]) >= self.max_batch_size:
                await self._flush(key)
            else:
                asyncio.create_task(self._delayed_flush(key))
        
        return await future
    
    async def _delayed_flush(self, key: str):
        await asyncio.sleep(self.max_wait_ms / 1000)
        async with self._lock:
            if key in self.pending:
                await self._flush(key)
    
    async def _flush(self, key: str):
        items = self.pending.pop(key, [])
        if not items:
            return
        batch_items = [item for item, _ in items]
        results = await self.batch_fn(key, batch_items)
        for (_, future), result in zip(items, results):
            future.set_result(result)
```

## 51. CDN Integration

```python
# core/cdn/cloudflare.py
import hashlib
from pathlib import Path

class CDNManager:
    def __init__(self, base_url: str, local_path: Path):
        self.base_url = base_url.rstrip('/')
        self.local_path = local_path
    
    def get_url(self, filename: str) -> str:
        file_path = self.local_path / filename
        if file_path.exists():
            content_hash = hashlib.md5(file_path.read_bytes()).hexdigest()[:8]
            return f"{self.base_url}/{filename}?v={content_hash}"
        return f"{self.base_url}/{filename}"
    
    def purge_cache(self, urls: list):
        # Cloudflare API call to purge specific URLs
        pass
```

## 52. Database Indexing Strategy

```sql
-- migrations/add_indexes.sql
CREATE INDEX IF NOT EXISTS idx_trades_symbol_created ON trades(symbol, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trades_user_status ON trades(user_id, status);
CREATE INDEX IF NOT EXISTS idx_trades_created_at ON trades(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_positions_user_symbol ON positions(user_id, symbol);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log(actor_id, timestamp DESC);

-- Analyze tables for query optimizer
ANALYZE trades;
ANALYZE positions;
```

## 53. Connection Keep-Alive

```python
# core/http/session.py
import aiohttp
from typing import Optional

class PersistentSession:
    _instance: Optional[aiohttp.ClientSession] = None
    
    @classmethod
    async def get_session(cls) -> aiohttp.ClientSession:
        if cls._instance is None or cls._instance.closed:
            connector = aiohttp.TCPConnector(
                limit=100,
                keepalive_timeout=30,
                enable_cleanup_closed=True
            )
            cls._instance = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return cls._instance
    
    @classmethod
    async def close(cls):
        if cls._instance and not cls._instance.closed:
            await cls._instance.close()
```

## 54. Async I/O Everywhere

```python
# core/io/async_file.py
import aiofiles
import asyncio
from pathlib import Path

async def read_file_async(path: Path) -> str:
    async with aiofiles.open(path, mode='r') as f:
        return await f.read()

async def write_file_async(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(path, mode='w') as f:
        await f.write(content)

async def read_json_async(path: Path) -> dict:
    import json
    content = await read_file_async(path)
    return json.loads(content)

async def write_json_async(path: Path, data: dict):
    import json
    await write_file_async(path, json.dumps(data, indent=2))
```

## 55. Response Streaming

```python
# api/routes/streaming.py
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import asyncio

router = APIRouter()

async def generate_large_response():
    for i in range(1000):
        yield f"data: {i}\n\n"
        await asyncio.sleep(0.01)

@router.get("/api/stream/data")
async def stream_data():
    return StreamingResponse(
        generate_large_response(),
        media_type="text/event-stream"
    )

@router.get("/api/stream/trades")
async def stream_trades(symbol: str):
    async def trade_generator():
        while True:
            trade = await get_latest_trade(symbol)
            yield f"data: {json.dumps(trade)}\n\n"
            await asyncio.sleep(1)
    
    return StreamingResponse(trade_generator(), media_type="text/event-stream")
```
