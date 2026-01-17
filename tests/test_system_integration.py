"""
System Integration Tests - M1 through M6 Comprehensive Validation

Validates that all implemented milestones work together correctly:
- M1: MemoryStore interface
- M2: EventBus with backpressure
- M3: Buy intent idempotency
- M4: State backup with atomic writes
- M5: Error handling cleanup
- M6: Unified configuration

Tests:
- Configuration loading with EventBus initialization
- State backup + MemoryStore coordination
- Intent tracking + EventBus event emission
- Full workflow: config → state → intent → event → backup
"""

import pytest
import tempfile
import asyncio
import json
from pathlib import Path
from datetime import datetime, timedelta

from core.config.unified_config import UnifiedConfigLoader
from core.event_bus.event_bus import EventBus, Event, EventType, EventPriority, EventHandler
from core.state_backup.state_backup import StateBackup, set_state_backup
from core.memory.dedup_store import SQLiteMemoryStore, MemoryEntry, MemoryType, set_memory_store
from bots.buy_tracker.intent_tracker import (
    generate_intent_id,
    check_intent_duplicate,
    record_intent_execution,
)


@pytest.fixture
def temp_dirs():
    """Create temporary directories for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        yield {
            "config": tmpdir / "config",
            "state": tmpdir / "state",
            "backups": tmpdir / "backups",
            "memory": tmpdir / "memory",
        }


@pytest.fixture
def config(temp_dirs):
    """Create unified configuration."""
    config_path = temp_dirs["config"] / "config.yaml"
    config_path.parent.mkdir(exist_ok=True)

    config_content = """
trading:
  enabled: false
  max_positions: 50
  dry_run: true

events:
  max_queue_size: 100
  handler_timeout: 5.0

memory:
  duplicate_intent_hours: 1
  backup_retention_hours: 24

state_backup:
  backup_interval_hours: 1
  backup_retention_hours: 24
"""
    config_path.write_text(config_content)
    return UnifiedConfigLoader(config_path)


@pytest.fixture
async def event_bus(config):
    """Create event bus from config."""
    bus = EventBus(
        max_queue_size=config.get_int("events.max_queue_size", 100),
        handler_timeout=config.get_float("events.handler_timeout", 5.0),
    )
    await bus.start()
    yield bus
    await bus.stop()


@pytest.fixture
def memory_store(temp_dirs):
    """Create memory store."""
    db_path = temp_dirs["memory"] / "memory.db"
    store = SQLiteMemoryStore(db_path=str(db_path))
    set_memory_store(store)
    return store


@pytest.fixture
def state_backup(temp_dirs):
    """Create state backup system."""
    backup = StateBackup(state_dir=temp_dirs["state"])
    set_state_backup(backup)
    return backup


class IntegrationHandler(EventHandler):
    """Test handler for integration tests."""

    def __init__(self, name: str):
        self._name = name
        self.events = []

    @property
    def name(self) -> str:
        return self._name

    def handles(self, event_type: EventType) -> bool:
        return True

    async def handle(self, event: Event):
        self.events.append(event)
        return True, None


# ============================================================================
# M1 + M2: MemoryStore + EventBus Integration
# ============================================================================

@pytest.mark.asyncio
async def test_memory_store_with_event_bus(memory_store, event_bus):
    """Test that MemoryStore and EventBus can work together."""
    handler = IntegrationHandler("memory_test_handler")
    event_bus.register_handler(handler, [EventType.DUPLICATE_DETECTED])

    # Store something in memory
    entry = MemoryEntry(
        content="test_content",
        memory_type=MemoryType.DUPLICATE_INTENT,
        entity_id="token1",
        entity_type="token",
        fingerprint="abc123",
    )
    entry_id = await memory_store.store(entry)
    assert entry_id is not None

    # Emit event
    event = Event(
        event_type=EventType.DUPLICATE_DETECTED,
        data={"entry_id": entry_id},
        priority=EventPriority.HIGH,
    )
    result = await event_bus.emit(event)
    assert result is True

    # Wait for processing
    await asyncio.sleep(0.1)

    # Verify handler received event
    assert len(handler.events) == 1


# ============================================================================
# M2 + M4: EventBus + State Backup Integration
# ============================================================================

@pytest.mark.asyncio
async def test_state_backup_with_event_bus(state_backup, event_bus):
    """Test that StateBackup and EventBus coordinate properly."""
    handler = IntegrationHandler("state_test_handler")
    event_bus.register_handler(handler, [EventType.TRADE_EXECUTED])

    # Write state
    positions = [{"token": "KR8TIV", "amount": 10.0}]
    success = state_backup.write_atomic("positions.json", {"positions": positions}, create_backup=True)
    assert success is True

    # Verify backup was created
    backups = state_backup.get_backup_list("positions.json")
    assert len(backups) > 0

    # Emit event
    event = Event(
        event_type=EventType.TRADE_EXECUTED,
        data={"positions_count": len(positions)},
    )
    result = await event_bus.emit(event)
    assert result is True

    await asyncio.sleep(0.1)
    assert len(handler.events) == 1


# ============================================================================
# M3 + M1: Intent Tracking + MemoryStore Integration
# ============================================================================

@pytest.mark.asyncio
async def test_intent_tracking_with_memory_store(memory_store):
    """Test that intent idempotency uses MemoryStore correctly."""
    symbol = "KR8TIV"
    amount = 10.0
    entry = 0.001
    tp = 0.0011
    sl = 0.0009
    user_id = 12345

    # Generate intent ID (deterministic)
    intent_id = generate_intent_id(symbol, amount, entry, tp, sl, user_id)

    # First check - should not be duplicate
    is_dup, reason = await check_intent_duplicate(intent_id, symbol)
    assert is_dup is False

    # Record execution
    await record_intent_execution(intent_id, symbol, True, "sig123")

    # Second check - should now be duplicate
    is_dup, reason = await check_intent_duplicate(intent_id, symbol)
    assert is_dup is True


# ============================================================================
# M4 + M1: State Backup + MemoryStore Integration
# ============================================================================

@pytest.mark.asyncio
async def test_state_backup_and_memory_store_both_track_state(state_backup, memory_store):
    """Test that both systems can track and recover state."""
    # Write to state backup
    data = {"balance": 100.0, "trades": 5}
    state_backup.write_atomic("treasury.json", data, create_backup=True)

    # Store reference in memory
    entry = MemoryEntry(
        content="treasury_state",
        memory_type=MemoryType.TRADE_LEARNINGS,
        entity_id="treasury",
        entity_type="system",
        metadata={"balance": 100.0},
    )
    await memory_store.store(entry)

    # Simulate corruption - corrupt the state file
    state_file = state_backup.state_dir / "treasury.json"
    state_file.write_text("{ corrupted")

    # read_safe should recover from backup
    recovered = state_backup.read_safe("treasury.json", default={})
    assert recovered["balance"] == 100.0


# ============================================================================
# Full System Integration: Config → State → Intent → Event → Backup
# ============================================================================

@pytest.mark.asyncio
async def test_full_system_workflow(config, memory_store, event_bus, state_backup):
    """Test complete workflow: config, state, intent, event, backup."""
    # 1. Load configuration
    assert config.get("trading.enabled") is False
    assert config.get_int("trading.max_positions") == 50

    # 2. Initialize state backup
    positions = [
        {"token": "KR8TIV", "amount": 10.0, "entry": 0.001},
        {"token": "SOL", "amount": 5.0, "entry": 200.0},
    ]
    state_backup.write_atomic("positions.json", {"positions": positions}, create_backup=True)

    # 3. Record intents in memory
    intent1 = generate_intent_id("KR8TIV", 10.0, 0.001, 0.0011, 0.0009, 123)
    await record_intent_execution(intent1, "KR8TIV", True, "sig1")

    intent2 = generate_intent_id("SOL", 5.0, 200.0, 220.0, 180.0, 123)
    await record_intent_execution(intent2, "SOL", True, "sig2")

    # 4. Emit events
    class TradeHandler(EventHandler):
        def __init__(self):
            self.trades = []

        @property
        def name(self) -> str:
            return "trade_handler"

        def handles(self, event_type: EventType) -> bool:
            return event_type == EventType.TRADE_EXECUTED

        async def handle(self, event: Event):
            self.trades.append(event.data)
            return True, None

    handler = TradeHandler()
    event_bus.register_handler(handler, [EventType.TRADE_EXECUTED])

    for position in positions:
        event = Event(
            event_type=EventType.TRADE_EXECUTED,
            data={"token": position["token"], "amount": position["amount"]},
            priority=EventPriority.HIGH,
        )
        await event_bus.emit(event)

    await asyncio.sleep(0.1)

    # 5. Verify everything worked
    # - Positions backed up
    backups = state_backup.get_backup_list("positions.json")
    assert len(backups) > 0

    # - Intents tracked
    is_dup1, _ = await check_intent_duplicate(intent1, "KR8TIV")
    assert is_dup1 is True

    # - Events processed
    assert len(handler.trades) == 2
    assert handler.trades[0]["token"] == "KR8TIV"
    assert handler.trades[1]["token"] == "SOL"


# ============================================================================
# M5: Error Handling Validation
# ============================================================================

def test_no_bare_excepts_in_core_modules():
    """Verify no bare except statements in core modules."""
    import re

    # Check key files
    files_to_check = [
        "core/state_backup/state_backup.py",
        "core/event_bus/event_bus.py",
        "core/config/unified_config.py",
        "bots/buy_tracker/intent_tracker.py",
    ]

    bare_except_pattern = r"except\s*:\s*(?!.*noqa)"

    for file_path in files_to_check:
        path = Path(file_path)
        if not path.exists():
            continue

        content = path.read_text()
        # Look for bare except without noqa comment
        matches = re.finditer(bare_except_pattern, content)
        matches_list = list(matches)

        # Should have no bare excepts (or they should have noqa)
        assert len(matches_list) == 0, f"Found bare except in {file_path}"


# ============================================================================
# M6: Configuration Validation
# ============================================================================

def test_config_loading_and_validation(config):
    """Test configuration loading and access patterns."""
    # Test all access methods
    assert config.get("trading.enabled") is False
    assert config.get_int("trading.max_positions") == 50
    assert config.get_bool("trading.dry_run") is True
    assert config.get_float("events.handler_timeout") == 5.0

    # Test with defaults
    assert config.get("nonexistent.key", "default") == "default"

    # Test section access
    trading_section = config.get_section("trading")
    assert "trading.enabled" in trading_section
    assert "trading.max_positions" in trading_section


# ============================================================================
# Recovery & Resilience Tests
# ============================================================================

@pytest.mark.asyncio
async def test_system_recovery_from_corrupted_state(state_backup, event_bus, memory_store):
    """Test system recovery when state is corrupted."""
    # 1. Write initial state
    data = {"trades": 10, "pnl": 1000.0}
    state_backup.write_atomic("trading.json", data, create_backup=True)

    # 2. Corrupt the file
    corrupt_file = state_backup.state_dir / "trading.json"
    corrupt_file.write_text("CORRUPTED")

    # 3. System should recover
    recovered = state_backup.read_safe("trading.json", default={"trades": 0, "pnl": 0})
    assert recovered["trades"] == 10  # Recovered from backup
    assert recovered["pnl"] == 1000.0

    # 4. EventBus should continue working
    class TestHandler(EventHandler):
        def __init__(self):
            self.count = 0

        @property
        def name(self) -> str:
            return "test_handler"

        def handles(self, event_type: EventType) -> bool:
            return True

        async def handle(self, event: Event):
            self.count += 1
            return True, None

    handler = TestHandler()
    event_bus.register_handler(handler, [EventType.ERROR])

    event = Event(EventType.ERROR, {"msg": "test"})
    await event_bus.emit(event)
    await asyncio.sleep(0.1)

    assert handler.count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
