#!/usr/bin/env python3
"""
Verification runner for audit v1.

Steps:
1) Demo golden tests
2) Unit tests
3) Restart simulation (state persistence)
4) Single-instance (Telegram polling lock) checks
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


def _run(cmd: list[str], label: str) -> None:
    print(f"\n=== {label} ===")
    print(" ".join(cmd))
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def _restart_simulation() -> None:
    print("\n=== Restart Simulation ===")
    from bots.treasury import trading as trading_mod

    tmp_root = Path(tempfile.mkdtemp())
    data_dir = tmp_root / "data" / "trader"
    data_dir.mkdir(parents=True, exist_ok=True)

    def configure(engine) -> None:
        engine.POSITIONS_FILE = data_dir / "positions.json"
        engine.HISTORY_FILE = data_dir / "trade_history.json"
        engine.DAILY_VOLUME_FILE = data_dir / "daily_volume.json"
        engine.AUDIT_LOG_FILE = tmp_root / "logs" / "audit.jsonl"
        engine.POSITIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        engine.HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        engine.DAILY_VOLUME_FILE.parent.mkdir(parents=True, exist_ok=True)
        engine.AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        engine._legacy_history_files = []
        engine._legacy_positions_files = []

    trade = {
        "id": "restart-1",
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

    # Avoid SafeState to keep the simulation minimal
    original_safe_state = trading_mod.SAFE_STATE_AVAILABLE
    trading_mod.SAFE_STATE_AVAILABLE = False

    original_load = trading_mod.TradingEngine._load_state
    trading_mod.TradingEngine._load_state = lambda self: None
    try:
        engine = trading_mod.TradingEngine(
            wallet=None,
            jupiter=None,
            admin_user_ids=[],
            dry_run=True,
            enable_signals=False,
        )
        configure(engine)
        engine.trade_history = [trading_mod.Position.from_dict(trade)]
        engine.positions = {}
        engine._save_state()

        engine2 = trading_mod.TradingEngine(
            wallet=None,
            jupiter=None,
            admin_user_ids=[],
            dry_run=True,
            enable_signals=False,
        )
        configure(engine2)
        original_load(engine2)

        if len(engine2.trade_history) != 1 or engine2.trade_history[0].id != "restart-1":
            raise SystemExit("Restart simulation failed: trade history not restored")
        print("Restart simulation passed")
    finally:
        trading_mod.TradingEngine._load_state = original_load
        trading_mod.SAFE_STATE_AVAILABLE = original_safe_state


def main() -> int:
    python = sys.executable

    _run([python, "-m", "pytest", "tests/demo_golden", "-q"], "Demo Golden Tests")
    _run([python, "-m", "pytest", "tests/unit", "-q"], "Unit Tests")
    _restart_simulation()
    _run(
        [python, "-m", "pytest", "tests/unit/test_instance_lock.py", "tests/integration/test_telegram_polling_lock.py", "-q"],
        "Telegram Single-Instance Checks",
    )
    print("\nAll verification steps completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
