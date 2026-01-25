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
