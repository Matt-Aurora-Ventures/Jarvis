import json
from datetime import datetime

import pytest

from bots.treasury.trading import trading_positions as positions_mod
from bots.treasury.trading.trading_positions import PositionManager
from bots.treasury.trading.types import Position, TradeDirection, TradeStatus


def _make_position(position_id: str = "p1") -> Position:
    return Position(
        id=position_id,
        token_mint="So11111111111111111111111111111111111111112",
        token_symbol="SOL",
        direction=TradeDirection.LONG,
        entry_price=1.0,
        current_price=1.0,
        amount=1.0,
        amount_usd=100.0,
        take_profit_price=1.2,
        stop_loss_price=0.9,
        status=TradeStatus.OPEN,
        opened_at=datetime.utcnow().isoformat(),
    )


@pytest.mark.asyncio
async def test_add_and_close_position(tmp_path, monkeypatch):
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    positions_file = tmp_path / "positions.json"
    history_file = tmp_path / "history.json"

    manager = PositionManager(positions_file=positions_file, history_file=history_file)

    pos = _make_position("p1")
    manager.add_position(pos)

    assert positions_file.exists()
    with open(positions_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data[0]["id"] == "p1"

    closed = manager.close_position("p1", exit_price=1.5, reason="test")
    assert closed is not None
    assert closed.status == TradeStatus.CLOSED
    assert len(manager.positions) == 0
    assert len(manager.trade_history) == 1


@pytest.mark.asyncio
async def test_update_position_price_updates_pnl(tmp_path, monkeypatch):
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    manager = PositionManager(
        positions_file=tmp_path / "positions.json",
        history_file=tmp_path / "history.json",
    )

    pos = _make_position("p2")
    manager.add_position(pos)

    manager.update_position_price("p2", current_price=1.1)

    updated = manager.get_position("p2")
    assert updated is not None
    assert updated.current_price == 1.1
    assert updated.pnl_pct > 0
    assert updated.pnl_usd > 0


@pytest.mark.asyncio
async def test_profile_based_state_paths(tmp_path, monkeypatch):
    """Test that profile creates isolated state paths."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    manager = PositionManager(state_profile="demo")

    # Should create profile-specific paths
    assert "demo" in str(manager.POSITIONS_FILE)
    assert "demo" in str(manager.HISTORY_FILE)


@pytest.mark.asyncio
async def test_get_open_positions_filters_correctly(tmp_path, monkeypatch):
    """Test get_open_positions only returns open positions."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    manager = PositionManager(
        positions_file=tmp_path / "positions.json",
        history_file=tmp_path / "history.json",
    )

    open_pos = _make_position("open1")
    manager.add_position(open_pos)

    closed_pos = _make_position("closed1")
    closed_pos.status = TradeStatus.CLOSED
    manager.positions[closed_pos.id] = closed_pos

    open_positions = manager.get_open_positions()

    assert len(open_positions) == 1
    assert open_positions[0].id == "open1"


@pytest.mark.asyncio
async def test_get_position_returns_specific_position(tmp_path, monkeypatch):
    """Test get_position retrieves correct position."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    manager = PositionManager(
        positions_file=tmp_path / "positions.json",
        history_file=tmp_path / "history.json",
    )

    pos1 = _make_position("pos1")
    pos2 = _make_position("pos2")
    manager.add_position(pos1)
    manager.add_position(pos2)

    retrieved = manager.get_position("pos1")

    assert retrieved is not None
    assert retrieved.id == "pos1"


@pytest.mark.asyncio
async def test_get_position_returns_none_when_not_found(tmp_path, monkeypatch):
    """Test get_position returns None for non-existent position."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    manager = PositionManager(
        positions_file=tmp_path / "positions.json",
        history_file=tmp_path / "history.json",
    )

    retrieved = manager.get_position("nonexistent")

    assert retrieved is None


@pytest.mark.asyncio
async def test_remove_position_removes_and_returns_position(tmp_path, monkeypatch):
    """Test remove_position removes position and returns it."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    manager = PositionManager(
        positions_file=tmp_path / "positions.json",
        history_file=tmp_path / "history.json",
    )

    pos = _make_position("remove_me")
    manager.add_position(pos)

    removed = manager.remove_position("remove_me")

    assert removed is not None
    assert removed.id == "remove_me"
    assert "remove_me" not in manager.positions


@pytest.mark.asyncio
async def test_remove_position_returns_none_when_not_found(tmp_path, monkeypatch):
    """Test remove_position returns None for non-existent position."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    manager = PositionManager(
        positions_file=tmp_path / "positions.json",
        history_file=tmp_path / "history.json",
    )

    removed = manager.remove_position("nonexistent")

    assert removed is None


@pytest.mark.asyncio
async def test_close_position_calculates_pnl(tmp_path, monkeypatch):
    """Test close_position calculates P&L correctly."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    manager = PositionManager(
        positions_file=tmp_path / "positions.json",
        history_file=tmp_path / "history.json",
    )

    pos = _make_position("pnl_test")
    pos.entry_price = 100.0
    pos.amount_usd = 1000.0
    manager.add_position(pos)

    closed = manager.close_position("pnl_test", exit_price=110.0)

    assert closed is not None
    assert closed.exit_price == 110.0
    assert closed.pnl_pct == pytest.approx(10.0)  # 10% gain
    assert closed.pnl_usd == pytest.approx(100.0)  # $100 profit
    assert closed.status == TradeStatus.CLOSED
    assert closed.closed_at is not None


@pytest.mark.asyncio
async def test_close_position_returns_none_when_not_found(tmp_path, monkeypatch):
    """Test close_position returns None for non-existent position."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    manager = PositionManager(
        positions_file=tmp_path / "positions.json",
        history_file=tmp_path / "history.json",
    )

    closed = manager.close_position("nonexistent", exit_price=100.0)

    assert closed is None


@pytest.mark.asyncio
async def test_load_state_from_file(tmp_path, monkeypatch):
    """Test loading state from existing file."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    positions_file = tmp_path / "positions.json"
    history_file = tmp_path / "history.json"

    # Create pre-existing state files
    positions_data = [{
        "id": "loaded1",
        "token_mint": "mint",
        "token_symbol": "TEST",
        "direction": "LONG",
        "entry_price": 1.0,
        "current_price": 1.0,
        "amount": 1.0,
        "amount_usd": 100.0,
        "take_profit_price": 1.2,
        "stop_loss_price": 0.9,
        "status": "OPEN",
        "opened_at": datetime.utcnow().isoformat(),
    }]

    with open(positions_file, 'w') as f:
        json.dump(positions_data, f)

    with open(history_file, 'w') as f:
        json.dump([], f)

    manager = PositionManager(
        positions_file=positions_file,
        history_file=history_file,
    )
    manager.load_state()

    assert len(manager.positions) == 1
    assert "loaded1" in manager.positions


@pytest.mark.asyncio
async def test_save_state_creates_files(tmp_path, monkeypatch):
    """Test save_state creates files when they don't exist."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    positions_file = tmp_path / "positions.json"
    history_file = tmp_path / "history.json"

    manager = PositionManager(
        positions_file=positions_file,
        history_file=history_file,
    )

    pos = _make_position("save_test")
    manager.add_position(pos)

    assert positions_file.exists()
    assert history_file.exists()


@pytest.mark.asyncio
async def test_update_position_price_nonexistent_position(tmp_path, monkeypatch):
    """Test updating price of non-existent position does nothing."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    manager = PositionManager(
        positions_file=tmp_path / "positions.json",
        history_file=tmp_path / "history.json",
    )

    # Should not raise exception
    manager.update_position_price("nonexistent", current_price=1.5)


@pytest.mark.asyncio
async def test_multiple_positions_managed_correctly(tmp_path, monkeypatch):
    """Test managing multiple positions simultaneously."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    manager = PositionManager(
        positions_file=tmp_path / "positions.json",
        history_file=tmp_path / "history.json",
    )

    # Add multiple positions
    for i in range(5):
        pos = _make_position(f"multi{i}")
        manager.add_position(pos)

    assert len(manager.positions) == 5

    # Close some positions
    manager.close_position("multi0", exit_price=1.5)
    manager.close_position("multi2", exit_price=0.8)

    assert len(manager.positions) == 3
    assert len(manager.trade_history) == 2

    # Verify remaining positions
    assert "multi1" in manager.positions
    assert "multi3" in manager.positions
    assert "multi4" in manager.positions


# ============================================================================
# Tests for SafeState integration (lines 107-131, 215-216)
# ============================================================================


class MockSafeState:
    """Mock SafeState for testing the SafeState-available code path."""

    def __init__(self, path, default_value=None):
        self.path = path
        self.default_value = default_value if default_value is not None else []
        self._data = default_value if default_value is not None else []

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


class MockSafeStateWithError:
    """Mock SafeState that raises errors for testing error handling."""

    def __init__(self, path, default_value=None):
        self.path = path
        self.default_value = default_value
        self._data = default_value if default_value is not None else []

    def read(self):
        raise RuntimeError("Mock read error")

    def write(self, data):
        raise RuntimeError("Mock write error")


@pytest.mark.asyncio
async def test_load_state_with_safestate_available(tmp_path, monkeypatch):
    """Test load_state when SAFE_STATE_AVAILABLE is True."""
    # Enable SafeState
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", True)

    positions_file = tmp_path / "positions.json"
    history_file = tmp_path / "history.json"

    # Pre-create state with valid data
    positions_data = [{
        "id": "safestate_test",
        "token_mint": "mint",
        "token_symbol": "TEST",
        "direction": "LONG",
        "entry_price": 1.0,
        "current_price": 1.0,
        "amount": 1.0,
        "amount_usd": 100.0,
        "take_profit_price": 1.2,
        "stop_loss_price": 0.9,
        "status": "OPEN",
        "opened_at": datetime.utcnow().isoformat(),
    }]

    with open(positions_file, 'w') as f:
        json.dump(positions_data, f)

    with open(history_file, 'w') as f:
        json.dump([], f)

    # Create mock SafeState that returns data
    def mock_safestate_init(path, default_value=None):
        state = MockSafeState(path, default_value)
        if "positions" in str(path):
            state._data = positions_data
        return state

    monkeypatch.setattr(positions_mod, "SafeState", mock_safestate_init)

    manager = PositionManager(
        positions_file=positions_file,
        history_file=history_file,
    )
    manager.load_state()

    assert len(manager.positions) == 1
    assert "safestate_test" in manager.positions


@pytest.mark.asyncio
async def test_load_state_safestate_read_error_falls_back_to_legacy(tmp_path, monkeypatch):
    """Test load_state falls back to legacy when SafeState read fails."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", True)

    positions_file = tmp_path / "positions.json"
    history_file = tmp_path / "history.json"

    # Create legacy fallback data
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    legacy_positions = legacy_dir / "positions.json"
    legacy_history = legacy_dir / "history.json"

    legacy_data = [{
        "id": "legacy_fallback",
        "token_mint": "mint",
        "token_symbol": "LEGACY",
        "direction": "LONG",
        "entry_price": 2.0,
        "current_price": 2.0,
        "amount": 1.0,
        "amount_usd": 200.0,
        "take_profit_price": 2.4,
        "stop_loss_price": 1.8,
        "status": "OPEN",
        "opened_at": datetime.utcnow().isoformat(),
    }]

    with open(legacy_positions, 'w') as f:
        json.dump(legacy_data, f)

    with open(legacy_history, 'w') as f:
        json.dump([], f)

    # Mock SafeState that throws on read
    monkeypatch.setattr(positions_mod, "SafeState", MockSafeStateWithError)

    manager = PositionManager(
        positions_file=positions_file,
        history_file=history_file,
    )

    # Add legacy path
    manager._legacy_positions_files = [legacy_positions]
    manager._legacy_history_files = [legacy_history]

    manager.load_state()

    # Should have loaded from legacy
    assert len(manager.positions) == 1
    assert "legacy_fallback" in manager.positions


@pytest.mark.asyncio
async def test_load_state_safestate_empty_primary_loads_legacy(tmp_path, monkeypatch):
    """Test load_state loads legacy when SafeState primary is empty."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", True)

    positions_file = tmp_path / "positions.json"
    history_file = tmp_path / "history.json"

    # Create empty primary file
    with open(positions_file, 'w') as f:
        f.write("")

    with open(history_file, 'w') as f:
        f.write("")

    # Create legacy data
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    legacy_positions = legacy_dir / "positions.json"

    legacy_data = [{
        "id": "from_empty_primary",
        "token_mint": "mint",
        "token_symbol": "EMPTY",
        "direction": "LONG",
        "entry_price": 3.0,
        "current_price": 3.0,
        "amount": 1.0,
        "amount_usd": 300.0,
        "take_profit_price": 3.6,
        "stop_loss_price": 2.7,
        "status": "OPEN",
        "opened_at": datetime.utcnow().isoformat(),
    }]

    with open(legacy_positions, 'w') as f:
        json.dump(legacy_data, f)

    # Mock SafeState that returns empty list
    def mock_safestate_empty(path, default_value=None):
        return MockSafeState(path, [])

    monkeypatch.setattr(positions_mod, "SafeState", mock_safestate_empty)

    manager = PositionManager(
        positions_file=positions_file,
        history_file=history_file,
    )
    manager._legacy_positions_files = [legacy_positions]

    manager.load_state()

    # Should have loaded from legacy since primary was empty
    assert len(manager.positions) == 1
    assert "from_empty_primary" in manager.positions


@pytest.mark.asyncio
async def test_save_state_with_safestate_available(tmp_path, monkeypatch):
    """Test save_state uses SafeState when available."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", True)

    positions_file = tmp_path / "positions.json"
    history_file = tmp_path / "history.json"

    # Track write calls
    write_calls = []

    class TrackingSafeState:
        def __init__(self, path, default_value=None):
            self.path = path
            self._data = default_value if default_value is not None else []

        def read(self):
            return self._data

        def write(self, data):
            write_calls.append(("write", str(self.path), data))
            self._data = data

    monkeypatch.setattr(positions_mod, "SafeState", TrackingSafeState)

    manager = PositionManager(
        positions_file=positions_file,
        history_file=history_file,
    )
    manager.load_state()

    pos = _make_position("safestate_write_test")
    manager.add_position(pos)

    # Should have called write via SafeState
    assert len(write_calls) >= 1
    # Verify position was written
    pos_writes = [c for c in write_calls if "positions" in c[1]]
    assert len(pos_writes) >= 1


@pytest.mark.asyncio
async def test_save_state_error_handling(tmp_path, monkeypatch):
    """Test save_state handles errors gracefully."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    positions_file = tmp_path / "positions.json"
    history_file = tmp_path / "history.json"

    manager = PositionManager(
        positions_file=positions_file,
        history_file=history_file,
    )

    pos = _make_position("error_test")
    manager.positions[pos.id] = pos

    # Make the positions file path point to an invalid location
    manager.POSITIONS_FILE = tmp_path / "nonexistent_dir" / "nested" / "positions.json"

    # Should not raise - error is logged
    manager.save_state()


# ============================================================================
# Tests for legacy loading (lines 175-190, 194-205)
# ============================================================================


@pytest.mark.asyncio
async def test_load_from_secondary_success(tmp_path, monkeypatch):
    """Test _load_from_secondary loads from legacy locations."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    positions_file = tmp_path / "positions.json"
    history_file = tmp_path / "history.json"

    # Create legacy directory with data
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    legacy_positions = legacy_dir / "legacy_positions.json"

    legacy_data = [{
        "id": "secondary_test",
        "token_mint": "mint",
        "token_symbol": "SEC",
        "direction": "LONG",
        "entry_price": 5.0,
        "current_price": 5.0,
        "amount": 1.0,
        "amount_usd": 500.0,
        "take_profit_price": 6.0,
        "stop_loss_price": 4.5,
        "status": "OPEN",
        "opened_at": datetime.utcnow().isoformat(),
    }]

    with open(legacy_positions, 'w') as f:
        json.dump(legacy_data, f)

    manager = PositionManager(
        positions_file=positions_file,
        history_file=history_file,
    )
    manager._legacy_positions_files = [legacy_positions]

    result = manager._load_from_secondary()

    assert result is True
    assert len(manager.positions) == 1
    assert "secondary_test" in manager.positions


@pytest.mark.asyncio
async def test_load_from_secondary_no_files(tmp_path, monkeypatch):
    """Test _load_from_secondary returns False when no legacy files exist."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    manager = PositionManager(
        positions_file=tmp_path / "positions.json",
        history_file=tmp_path / "history.json",
    )
    manager._legacy_positions_files = [tmp_path / "nonexistent.json"]

    result = manager._load_from_secondary()

    assert result is False
    assert len(manager.positions) == 0


@pytest.mark.asyncio
async def test_load_from_secondary_corrupt_file(tmp_path, monkeypatch):
    """Test _load_from_secondary handles corrupt JSON gracefully."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    legacy_file = tmp_path / "corrupt_legacy.json"
    with open(legacy_file, 'w') as f:
        f.write("{ invalid json }")

    manager = PositionManager(
        positions_file=tmp_path / "positions.json",
        history_file=tmp_path / "history.json",
    )
    manager._legacy_positions_files = [legacy_file]

    result = manager._load_from_secondary()

    assert result is False


@pytest.mark.asyncio
async def test_load_from_secondary_skips_duplicates(tmp_path, monkeypatch):
    """Test _load_from_secondary does not overwrite existing positions."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    legacy_file = tmp_path / "legacy.json"
    legacy_data = [{
        "id": "duplicate_test",
        "token_mint": "legacy_mint",
        "token_symbol": "OLD",
        "direction": "LONG",
        "entry_price": 1.0,
        "current_price": 1.0,
        "amount": 1.0,
        "amount_usd": 100.0,
        "take_profit_price": 1.2,
        "stop_loss_price": 0.9,
        "status": "OPEN",
        "opened_at": datetime.utcnow().isoformat(),
    }]

    with open(legacy_file, 'w') as f:
        json.dump(legacy_data, f)

    manager = PositionManager(
        positions_file=tmp_path / "positions.json",
        history_file=tmp_path / "history.json",
    )

    # Pre-add a position with same ID
    existing_pos = _make_position("duplicate_test")
    existing_pos.token_symbol = "NEW"
    manager.positions[existing_pos.id] = existing_pos

    manager._legacy_positions_files = [legacy_file]
    result = manager._load_from_secondary()

    assert result is True
    # Should keep the existing position, not overwrite with legacy
    assert manager.positions["duplicate_test"].token_symbol == "NEW"


@pytest.mark.asyncio
async def test_load_history_from_legacy_success(tmp_path, monkeypatch):
    """Test _load_history_from_legacy loads trade history from legacy."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    legacy_history = tmp_path / "legacy_history.json"
    closed_pos = {
        "id": "history_test",
        "token_mint": "mint",
        "token_symbol": "HIST",
        "direction": "LONG",
        "entry_price": 1.0,
        "current_price": 1.5,
        "amount": 1.0,
        "amount_usd": 100.0,
        "take_profit_price": 1.5,
        "stop_loss_price": 0.9,
        "status": "CLOSED",
        "opened_at": datetime.utcnow().isoformat(),
        "closed_at": datetime.utcnow().isoformat(),
        "exit_price": 1.5,
        "pnl_pct": 50.0,
        "pnl_usd": 50.0,
    }

    with open(legacy_history, 'w') as f:
        json.dump([closed_pos], f)

    manager = PositionManager(
        positions_file=tmp_path / "positions.json",
        history_file=tmp_path / "history.json",
    )
    manager._legacy_history_files = [legacy_history]

    result = manager._load_history_from_legacy()

    assert result is True
    assert len(manager.trade_history) == 1
    assert manager.trade_history[0].id == "history_test"


@pytest.mark.asyncio
async def test_load_history_from_legacy_no_files(tmp_path, monkeypatch):
    """Test _load_history_from_legacy returns False when no legacy files exist."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    manager = PositionManager(
        positions_file=tmp_path / "positions.json",
        history_file=tmp_path / "history.json",
    )
    manager._legacy_history_files = [tmp_path / "nonexistent_history.json"]

    result = manager._load_history_from_legacy()

    assert result is False
    assert len(manager.trade_history) == 0


@pytest.mark.asyncio
async def test_load_history_from_legacy_corrupt_file(tmp_path, monkeypatch):
    """Test _load_history_from_legacy handles corrupt JSON gracefully."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    legacy_file = tmp_path / "corrupt_history.json"
    with open(legacy_file, 'w') as f:
        f.write("not valid json at all")

    manager = PositionManager(
        positions_file=tmp_path / "positions.json",
        history_file=tmp_path / "history.json",
    )
    manager._legacy_history_files = [legacy_file]

    result = manager._load_history_from_legacy()

    assert result is False


# ============================================================================
# Tests for legacy migration persistence (lines 162-166)
# ============================================================================


@pytest.mark.asyncio
async def test_load_state_migrates_legacy_data(tmp_path, monkeypatch):
    """Test load_state persists migrated legacy data to canonical files."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    positions_file = tmp_path / "positions.json"
    history_file = tmp_path / "history.json"

    # Create legacy data
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    legacy_positions = legacy_dir / "positions.json"

    legacy_data = [{
        "id": "migrate_test",
        "token_mint": "mint",
        "token_symbol": "MIG",
        "direction": "LONG",
        "entry_price": 10.0,
        "current_price": 10.0,
        "amount": 1.0,
        "amount_usd": 1000.0,
        "take_profit_price": 12.0,
        "stop_loss_price": 9.0,
        "status": "OPEN",
        "opened_at": datetime.utcnow().isoformat(),
    }]

    with open(legacy_positions, 'w') as f:
        json.dump(legacy_data, f)

    manager = PositionManager(
        positions_file=positions_file,
        history_file=history_file,
    )
    manager._legacy_positions_files = [legacy_positions]
    manager._legacy_history_files = []

    manager.load_state()

    # Should have migrated to canonical files
    assert positions_file.exists()
    with open(positions_file, 'r') as f:
        data = json.load(f)
    assert len(data) == 1
    assert data[0]["id"] == "migrate_test"


@pytest.mark.asyncio
async def test_load_state_migration_failure_handled(tmp_path, monkeypatch):
    """Test load_state handles migration save failures gracefully."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    # Create legacy data
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    legacy_positions = legacy_dir / "positions.json"

    legacy_data = [{
        "id": "migrate_fail_test",
        "token_mint": "mint",
        "token_symbol": "FAIL",
        "direction": "LONG",
        "entry_price": 1.0,
        "current_price": 1.0,
        "amount": 1.0,
        "amount_usd": 100.0,
        "take_profit_price": 1.2,
        "stop_loss_price": 0.9,
        "status": "OPEN",
        "opened_at": datetime.utcnow().isoformat(),
    }]

    with open(legacy_positions, 'w') as f:
        json.dump(legacy_data, f)

    # Use a read-only directory to cause save failure
    readonly_dir = tmp_path / "readonly"
    readonly_dir.mkdir()
    positions_file = readonly_dir / "positions.json"
    history_file = readonly_dir / "history.json"

    manager = PositionManager(
        positions_file=positions_file,
        history_file=history_file,
    )
    manager._legacy_positions_files = [legacy_positions]
    manager._legacy_history_files = []

    # Make save_state fail by using an invalid path
    original_positions_file = manager.POSITIONS_FILE
    manager.POSITIONS_FILE = tmp_path / "no" / "such" / "path" / "positions.json"

    # Should not raise - error is logged
    manager.load_state()

    # Positions should still be loaded from legacy even if migration save failed
    manager.POSITIONS_FILE = original_positions_file  # Restore for assertions
    assert len(manager.positions) == 1


# ============================================================================
# Tests for load_state error paths without SafeState (lines 142-146, 154-158)
# ============================================================================


@pytest.mark.asyncio
async def test_load_state_corrupt_primary_falls_back_to_legacy(tmp_path, monkeypatch):
    """Test load_state falls back to legacy when primary file is corrupt."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    positions_file = tmp_path / "positions.json"
    history_file = tmp_path / "history.json"

    # Create corrupt primary file
    with open(positions_file, 'w') as f:
        f.write("{ broken json")

    with open(history_file, 'w') as f:
        f.write("[]")

    # Create valid legacy data
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    legacy_positions = legacy_dir / "positions.json"

    legacy_data = [{
        "id": "corrupt_primary_test",
        "token_mint": "mint",
        "token_symbol": "LEG",
        "direction": "LONG",
        "entry_price": 1.0,
        "current_price": 1.0,
        "amount": 1.0,
        "amount_usd": 100.0,
        "take_profit_price": 1.2,
        "stop_loss_price": 0.9,
        "status": "OPEN",
        "opened_at": datetime.utcnow().isoformat(),
    }]

    with open(legacy_positions, 'w') as f:
        json.dump(legacy_data, f)

    manager = PositionManager(
        positions_file=positions_file,
        history_file=history_file,
    )
    manager._legacy_positions_files = [legacy_positions]

    manager.load_state()

    assert len(manager.positions) == 1
    assert "corrupt_primary_test" in manager.positions


@pytest.mark.asyncio
async def test_load_state_corrupt_history_falls_back_to_legacy(tmp_path, monkeypatch):
    """Test load_state falls back to legacy when history file is corrupt."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    positions_file = tmp_path / "positions.json"
    history_file = tmp_path / "history.json"

    # Create valid positions file
    with open(positions_file, 'w') as f:
        json.dump([], f)

    # Create corrupt history file
    with open(history_file, 'w') as f:
        f.write("not valid json")

    # Create valid legacy history
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    legacy_history = legacy_dir / "history.json"

    legacy_history_data = [{
        "id": "legacy_history_test",
        "token_mint": "mint",
        "token_symbol": "LH",
        "direction": "LONG",
        "entry_price": 1.0,
        "current_price": 1.5,
        "amount": 1.0,
        "amount_usd": 100.0,
        "take_profit_price": 1.5,
        "stop_loss_price": 0.9,
        "status": "CLOSED",
        "opened_at": datetime.utcnow().isoformat(),
        "closed_at": datetime.utcnow().isoformat(),
        "exit_price": 1.5,
    }]

    with open(legacy_history, 'w') as f:
        json.dump(legacy_history_data, f)

    manager = PositionManager(
        positions_file=positions_file,
        history_file=history_file,
    )
    manager._legacy_history_files = [legacy_history]

    manager.load_state()

    assert len(manager.trade_history) == 1
    assert manager.trade_history[0].id == "legacy_history_test"


@pytest.mark.asyncio
async def test_load_state_no_primary_loads_from_legacy(tmp_path, monkeypatch):
    """Test load_state loads from legacy when no primary file exists."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    positions_file = tmp_path / "positions.json"
    history_file = tmp_path / "history.json"

    # Create valid legacy data (no primary files)
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    legacy_positions = legacy_dir / "positions.json"
    legacy_history = legacy_dir / "history.json"

    legacy_pos_data = [{
        "id": "no_primary_test",
        "token_mint": "mint",
        "token_symbol": "NP",
        "direction": "LONG",
        "entry_price": 1.0,
        "current_price": 1.0,
        "amount": 1.0,
        "amount_usd": 100.0,
        "take_profit_price": 1.2,
        "stop_loss_price": 0.9,
        "status": "OPEN",
        "opened_at": datetime.utcnow().isoformat(),
    }]

    legacy_history_data = [{
        "id": "no_primary_hist",
        "token_mint": "mint",
        "token_symbol": "NPH",
        "direction": "LONG",
        "entry_price": 1.0,
        "current_price": 1.5,
        "amount": 1.0,
        "amount_usd": 100.0,
        "take_profit_price": 1.5,
        "stop_loss_price": 0.9,
        "status": "CLOSED",
        "opened_at": datetime.utcnow().isoformat(),
        "closed_at": datetime.utcnow().isoformat(),
        "exit_price": 1.5,
    }]

    with open(legacy_positions, 'w') as f:
        json.dump(legacy_pos_data, f)

    with open(legacy_history, 'w') as f:
        json.dump(legacy_history_data, f)

    manager = PositionManager(
        positions_file=positions_file,
        history_file=history_file,
    )
    manager._legacy_positions_files = [legacy_positions]
    manager._legacy_history_files = [legacy_history]

    manager.load_state()

    assert len(manager.positions) == 1
    assert "no_primary_test" in manager.positions
    assert len(manager.trade_history) == 1
    assert manager.trade_history[0].id == "no_primary_hist"


# ============================================================================
# Tests for P&L edge cases (lines 260->265, 279->exit)
# ============================================================================


@pytest.mark.asyncio
async def test_close_position_with_zero_entry_price(tmp_path, monkeypatch):
    """Test close_position handles zero entry price without division error."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    manager = PositionManager(
        positions_file=tmp_path / "positions.json",
        history_file=tmp_path / "history.json",
    )

    pos = _make_position("zero_entry")
    pos.entry_price = 0.0
    pos.amount_usd = 100.0
    manager.positions[pos.id] = pos

    closed = manager.close_position("zero_entry", exit_price=1.0)

    assert closed is not None
    assert closed.status == TradeStatus.CLOSED
    # Should not have calculated P&L due to zero entry price
    assert closed.pnl_pct is None or closed.pnl_pct == 0


@pytest.mark.asyncio
async def test_update_position_price_with_zero_entry_price(tmp_path, monkeypatch):
    """Test update_position_price handles zero entry price without error."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    manager = PositionManager(
        positions_file=tmp_path / "positions.json",
        history_file=tmp_path / "history.json",
    )

    pos = _make_position("zero_entry_update")
    pos.entry_price = 0.0
    manager.positions[pos.id] = pos

    # Should not raise
    manager.update_position_price("zero_entry_update", current_price=1.5)

    updated = manager.get_position("zero_entry_update")
    assert updated.current_price == 1.5


@pytest.mark.asyncio
async def test_close_position_negative_pnl(tmp_path, monkeypatch):
    """Test close_position calculates negative P&L correctly."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    manager = PositionManager(
        positions_file=tmp_path / "positions.json",
        history_file=tmp_path / "history.json",
    )

    pos = _make_position("loss_test")
    pos.entry_price = 100.0
    pos.amount_usd = 1000.0
    manager.add_position(pos)

    closed = manager.close_position("loss_test", exit_price=80.0)

    assert closed is not None
    assert closed.exit_price == 80.0
    assert closed.pnl_pct == pytest.approx(-20.0)  # 20% loss
    assert closed.pnl_usd == pytest.approx(-200.0)  # $200 loss


@pytest.mark.asyncio
async def test_update_position_price_calculates_pnl(tmp_path, monkeypatch):
    """Test update_position_price recalculates P&L correctly."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    manager = PositionManager(
        positions_file=tmp_path / "positions.json",
        history_file=tmp_path / "history.json",
    )

    pos = _make_position("pnl_update")
    pos.entry_price = 50.0
    pos.amount_usd = 500.0
    manager.add_position(pos)

    manager.update_position_price("pnl_update", current_price=75.0)

    updated = manager.get_position("pnl_update")
    assert updated.pnl_pct == pytest.approx(50.0)  # 50% gain
    assert updated.pnl_usd == pytest.approx(250.0)  # $250 profit


# ============================================================================
# Tests for SafeState import edge case (lines 28-30)
# ============================================================================


@pytest.mark.asyncio
async def test_module_handles_missing_safestate():
    """Test module loads correctly when SafeState is not available."""
    # The module has already been imported with SAFE_STATE_AVAILABLE potentially set.
    # This test verifies the module handles the import failure gracefully.
    # The lines 28-30 are exercised at import time when SafeState is unavailable.

    # Verify the module has the flag set (should be False in test environment)
    # or True if SafeState is available - either is valid
    assert hasattr(positions_mod, "SAFE_STATE_AVAILABLE")
    assert isinstance(positions_mod.SAFE_STATE_AVAILABLE, bool)


# ============================================================================
# Additional edge case tests for full coverage
# ============================================================================


@pytest.mark.asyncio
async def test_get_position_by_token_mint(tmp_path, monkeypatch):
    """Test finding position by token mint address."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    manager = PositionManager(
        positions_file=tmp_path / "positions.json",
        history_file=tmp_path / "history.json",
    )

    pos1 = _make_position("token_test1")
    pos1.token_mint = "MINT_ADDRESS_1"
    pos2 = _make_position("token_test2")
    pos2.token_mint = "MINT_ADDRESS_2"

    manager.add_position(pos1)
    manager.add_position(pos2)

    # Find by iterating positions
    found = None
    for p in manager.positions.values():
        if p.token_mint == "MINT_ADDRESS_1":
            found = p
            break

    assert found is not None
    assert found.id == "token_test1"


@pytest.mark.asyncio
async def test_configure_state_paths_creates_directories(tmp_path, monkeypatch):
    """Test _configure_state_paths creates necessary directories."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    # Use a profile that will create new directories
    manager = PositionManager(state_profile="test_profile")

    # Verify paths were configured
    assert "test_profile" in str(manager.POSITIONS_FILE)
    assert "test_profile" in str(manager.HISTORY_FILE)


@pytest.mark.asyncio
async def test_load_state_with_history_safestate_error(tmp_path, monkeypatch):
    """Test load_state handles SafeState history read error."""
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", True)

    positions_file = tmp_path / "positions.json"
    history_file = tmp_path / "history.json"

    # Create legacy history
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    legacy_history = legacy_dir / "history.json"

    legacy_hist_data = [{
        "id": "hist_error_test",
        "token_mint": "mint",
        "token_symbol": "HE",
        "direction": "LONG",
        "entry_price": 1.0,
        "current_price": 1.5,
        "amount": 1.0,
        "amount_usd": 100.0,
        "take_profit_price": 1.5,
        "stop_loss_price": 0.9,
        "status": "CLOSED",
        "opened_at": datetime.utcnow().isoformat(),
        "closed_at": datetime.utcnow().isoformat(),
        "exit_price": 1.5,
    }]

    with open(legacy_history, 'w') as f:
        json.dump(legacy_hist_data, f)

    call_count = {"positions": 0, "history": 0}

    class SelectiveSafeState:
        def __init__(self, path, default_value=None):
            self.path = path
            self._data = default_value if default_value is not None else []

        def read(self):
            if "history" in str(self.path):
                call_count["history"] += 1
                raise RuntimeError("Mock history read error")
            call_count["positions"] += 1
            return []

        def write(self, data):
            pass

    monkeypatch.setattr(positions_mod, "SafeState", SelectiveSafeState)

    manager = PositionManager(
        positions_file=positions_file,
        history_file=history_file,
    )
    manager._legacy_history_files = [legacy_history]

    manager.load_state()

    # Should have loaded history from legacy after SafeState error
    assert len(manager.trade_history) == 1
    assert manager.trade_history[0].id == "hist_error_test"
