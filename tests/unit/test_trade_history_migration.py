import json
from datetime import datetime
from pathlib import Path

from bots.treasury import trading as trading_mod


ORIG_LOAD_STATE = trading_mod.TradingEngine._load_state


def _sample_trade(trade_id: str) -> dict:
    return {
        "id": trade_id,
        "token_mint": "So11111111111111111111111111111111111111112",
        "token_symbol": "SOL",
        "direction": "LONG",
        "entry_price": 10.0,
        "current_price": 10.0,
        "amount": 1.0,
        "amount_usd": 10.0,
        "take_profit_price": 12.0,
        "stop_loss_price": 8.0,
        "status": "CLOSED",
        "opened_at": datetime.utcnow().isoformat(),
        "closed_at": datetime.utcnow().isoformat(),
        "exit_price": 10.5,
        "pnl_usd": 0.5,
        "pnl_pct": 5.0,
        "sentiment_grade": "B",
        "sentiment_score": 0.4,
    }


def _configure_engine_paths(engine, root: Path) -> None:
    engine.POSITIONS_FILE = root / "data" / "trader" / "positions.json"
    engine.HISTORY_FILE = root / "data" / "trader" / "trade_history.json"
    engine.DAILY_VOLUME_FILE = root / "data" / "trader" / "daily_volume.json"
    engine.AUDIT_LOG_FILE = root / "logs" / "audit.jsonl"
    engine.POSITIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    engine.HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    engine.DAILY_VOLUME_FILE.parent.mkdir(parents=True, exist_ok=True)
    engine.AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)


def _build_engine(monkeypatch, root: Path):
    monkeypatch.setattr(trading_mod.TradingEngine, "_load_state", lambda self: None)
    engine = trading_mod.TradingEngine(
        wallet=None,
        jupiter=None,
        admin_user_ids=[],
        dry_run=True,
        enable_signals=False,
    )
    _configure_engine_paths(engine, root)
    return engine


def test_trade_history_migrates_from_legacy(tmp_path, monkeypatch):
    monkeypatch.setattr(trading_mod, "SAFE_STATE_AVAILABLE", False)

    engine = _build_engine(monkeypatch, tmp_path)

    legacy_history = tmp_path / "legacy" / ".trade_history.json"
    legacy_history.parent.mkdir(parents=True, exist_ok=True)
    legacy_history.write_text(json.dumps([_sample_trade("legacy-1")]), encoding="utf-8")

    engine._legacy_history_files = [legacy_history]
    engine._legacy_positions_files = []

    ORIG_LOAD_STATE(engine)

    assert len(engine.trade_history) == 1
    assert engine.HISTORY_FILE.exists()
    saved = json.loads(engine.HISTORY_FILE.read_text(encoding="utf-8"))
    assert len(saved) == 1
    assert saved[0]["id"] == "legacy-1"


def test_trade_history_persists_across_restart(tmp_path, monkeypatch):
    monkeypatch.setattr(trading_mod, "SAFE_STATE_AVAILABLE", False)

    engine = _build_engine(monkeypatch, tmp_path)
    engine.trade_history = [trading_mod.Position.from_dict(_sample_trade("persist-1"))]
    engine.positions = {}
    engine._save_state()

    # Simulate restart
    engine2 = _build_engine(monkeypatch, tmp_path)
    ORIG_LOAD_STATE(engine2)

    assert len(engine2.trade_history) == 1
    assert engine2.trade_history[0].id == "persist-1"
