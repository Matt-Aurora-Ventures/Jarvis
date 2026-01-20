# Graceful Shutdown System

## Overview

The graceful shutdown system ensures that all services stop cleanly when the application is terminated, preventing:
- Database corruption from unclosed connections
- Lost data from unsaved state
- Resource leaks from uncancelled tasks
- Incomplete transactions

## Architecture

### Components

1. **ShutdownManager** (`core/shutdown_manager.py`)
   - Coordinates shutdown across all services
   - Handles SIGTERM and SIGINT signals
   - Executes hooks in phase order
   - Enforces timeouts

2. **DatabaseConnectionManager** (`core/db_connection_manager.py`)
   - Tracks database connections and pools
   - Automatically closes connections on shutdown
   - Provides health checking

3. **Service Mixins**
   - `ShutdownAwareService` - Base class for services
   - `DatabaseShutdownMixin` - Database cleanup
   - `TaskManagerMixin` - Background task cancellation

4. **Telegram Bot Shutdown** (`tg_bot/shutdown_handler.py`)
   - Stops polling gracefully
   - Drains pending updates
   - Saves bot state

## Shutdown Phases

Hooks execute in this order:

| Phase | Purpose | Example Use Cases |
|-------|---------|-------------------|
| **IMMEDIATE** | Stop accepting new work | Stop bot polling, close API endpoints |
| **GRACEFUL** | Complete in-flight work | Finish processing requests, complete trades |
| **PERSIST** | Save state | Write positions to database, save caches |
| **CLEANUP** | Close connections | Close database, disconnect from APIs |
| **FINAL** | Last-resort cleanup | Force-kill stubborn resources |

Within each phase, hooks run in **priority order** (higher priority first).

## Usage

### Basic Service

```python
from core.shutdown_manager import ShutdownAwareService

class MyService(ShutdownAwareService):
    def __init__(self):
        super().__init__(name="my_service")
        self.data = {}

    async def _startup(self):
        """Initialize resources."""
        self.data = await load_data()

    async def _shutdown(self):
        """Clean up resources."""
        await save_data(self.data)

# Usage
service = MyService()
await service.start()  # Automatically registers shutdown hook
```

### Service with Database

```python
from core.shutdown_manager import ShutdownAwareService, DatabaseShutdownMixin

class DatabaseService(DatabaseShutdownMixin, ShutdownAwareService):
    async def _startup(self):
        self.db = await asyncpg.connect(dsn)
        self.register_db_connection(self.db)

    async def _shutdown(self):
        await self._close_db_connections()  # Auto-closes all registered
```

### Service with Background Tasks

```python
from core.shutdown_manager import ShutdownAwareService, TaskManagerMixin

class WorkerService(TaskManagerMixin, ShutdownAwareService):
    async def _startup(self):
        # Tasks are tracked automatically
        self.create_task(self._worker_loop(), name="worker")

    async def _shutdown(self):
        await self._cancel_background_tasks(timeout=5.0)

    async def _worker_loop(self):
        while True:
            await process_work()
```

### Manual Hook Registration

```python
from core.shutdown_manager import get_shutdown_manager, ShutdownPhase

async def cleanup_cache():
    await cache.flush()

# Register hook
manager = get_shutdown_manager()
manager.register_hook(
    name="cache_cleanup",
    callback=cleanup_cache,
    phase=ShutdownPhase.PERSIST,
    timeout=5.0,
    priority=10,
)
```

### Signal Handling

```python
from core.shutdown_manager import get_shutdown_manager

async def main():
    # Install signal handlers
    manager = get_shutdown_manager()
    manager.install_signal_handlers()

    # Run your app
    await run_app()

    # Wait for shutdown signal
    await manager.wait_for_shutdown()

    # Shutdown (runs all hooks)
    await manager.shutdown()
```

### Context Manager

```python
from core.shutdown_manager import managed_shutdown

async def main():
    async with managed_shutdown() as manager:
        # Set up your app
        await setup_services()

        # Run
        await run_forever()

    # Shutdown happens automatically on exit
```

## Integration Points

### Supervisor

The supervisor (`bots/supervisor.py`) integrates shutdown handling:

```python
# Supervisor registers itself
if SHUTDOWN_MANAGER_AVAILABLE:
    self._shutdown_manager = get_shutdown_manager()
    self._shutdown_manager.register_hook(
        name="supervisor",
        callback=self._graceful_shutdown,
        phase=ShutdownPhase.IMMEDIATE,
        priority=100,  # Stop supervisor first
    )
```

### Telegram Bot

The Telegram bot (`tg_bot/bot.py`) uses the shutdown handler:

```python
from tg_bot.shutdown_handler import setup_telegram_shutdown

app = Application.builder().token(token).build()
setup_telegram_shutdown(app)  # Registers hooks automatically
```

### Database Connections

Use the database manager for automatic cleanup:

```python
from core.db_connection_manager import get_db_manager

# Register connection
db_manager = get_db_manager()
db_manager.register_connection("main_db", conn)

# Automatically closed on shutdown
```

Or use the context manager:

```python
from core.db_connection_manager import managed_db_connection

async def create_conn():
    return await asyncpg.connect(dsn)

async with managed_db_connection(create_conn, "db") as conn:
    await conn.execute("SELECT 1")
# Cleanup via shutdown hook
```

## Testing

### Unit Tests

Tests are in `tests/unit/test_shutdown_manager.py`:

```bash
pytest tests/unit/test_shutdown_manager.py -v
```

Key test scenarios:
- Hook execution order
- Priority handling
- Timeout enforcement
- Error handling
- Multiple shutdown calls

### Integration Tests

Test complete shutdown flow:

```python
@pytest.mark.asyncio
async def test_complete_shutdown():
    manager = ShutdownManager()

    db_closed = False
    async def close_db():
        nonlocal db_closed
        db_closed = True

    manager.register_hook("db", close_db, ShutdownPhase.CLEANUP)
    await manager.shutdown()

    assert db_closed
```

## Best Practices

### 1. Register Early

Register shutdown hooks during initialization:

```python
class MyService:
    def __init__(self):
        # Register immediately
        manager = get_shutdown_manager()
        manager.register_hook("my_service", self._shutdown, ...)
```

### 2. Use Appropriate Phases

- **IMMEDIATE** - Stop accepting new work
- **GRACEFUL** - Complete current work
- **PERSIST** - Save state
- **CLEANUP** - Close connections

### 3. Set Realistic Timeouts

```python
# Quick operations
timeout=1.0

# Database writes
timeout=5.0

# Complex operations
timeout=10.0
```

### 4. Handle Errors

Shutdown hooks should handle errors gracefully:

```python
async def my_shutdown():
    try:
        await save_critical_data()
    except Exception as e:
        logger.error(f"Failed to save: {e}")
        # Don't raise - let other hooks run
```

### 5. Use Priorities

Higher priority = runs first:

```python
# Critical service - shut down first
priority=100

# Normal service
priority=50

# Cleanup tasks - run last
priority=1
```

### 6. Test Shutdown Behavior

Always test that your service shuts down cleanly:

```python
@pytest.mark.asyncio
async def test_service_shutdown():
    service = MyService()
    await service.start()

    # Trigger shutdown
    await service._shutdown_hook()

    # Verify cleanup
    assert service._running is False
    assert service.db is None
```

## Troubleshooting

### Shutdown Hangs

If shutdown hangs, check:

1. **Timeout too long** - Reduce hook timeouts
2. **Uncancellable tasks** - Ensure tasks respond to cancellation
3. **Blocking operations** - Use async I/O

Enable debug logging:

```python
logging.getLogger("core.shutdown_manager").setLevel(logging.DEBUG)
```

### Resources Not Cleaned

If connections stay open:

1. **Not registered** - Ensure connections are registered
2. **Wrong close method** - Check connection interface
3. **Error during close** - Check logs for exceptions

### Signal Not Caught

If Ctrl+C doesn't work:

1. **Handlers not installed** - Call `install_signal_handlers()`
2. **Windows limitation** - Some signals don't work on Windows
3. **Event loop issue** - Ensure running in async context

## Performance

Typical shutdown times:

| Scenario | Time |
|----------|------|
| Simple service | < 1s |
| With database | 1-3s |
| With background tasks | 2-5s |
| Complex system | 5-10s |

Total shutdown time = sum of hook timeouts (max per phase).

## Migration Guide

### From Manual Cleanup

**Before:**
```python
try:
    await run_app()
finally:
    await db.close()
    await stop_tasks()
```

**After:**
```python
class App(DatabaseShutdownMixin, TaskManagerMixin, ShutdownAwareService):
    async def _shutdown(self):
        await self._close_db_connections()
        await self._cancel_background_tasks()
```

### From Signal Handlers

**Before:**
```python
signal.signal(signal.SIGTERM, lambda s, f: cleanup())
```

**After:**
```python
manager = get_shutdown_manager()
manager.install_signal_handlers()
manager.register_hook("cleanup", cleanup, ShutdownPhase.CLEANUP)
```

## See Also

- Example: `core/examples/shutdown_aware_service_example.py`
- Tests: `tests/unit/test_shutdown_manager.py`
- Supervisor integration: `bots/supervisor.py`
- Telegram integration: `tg_bot/shutdown_handler.py`
