import importlib.util
import json
from pathlib import Path


def _load_migration_module():
    path = Path("data_migrations") / "001_state_consolidation.py"
    spec = importlib.util.spec_from_file_location("state_migration_001", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_state_migration_idempotent(tmp_path, monkeypatch):
    module = _load_migration_module()

    root = tmp_path / "repo"
    trader_dir = root / "data" / "trader"
    trader_dir.mkdir(parents=True, exist_ok=True)

    canonical_history = trader_dir / "trade_history.json"
    legacy_history = root / "bots" / "treasury" / ".trade_history.json"
    legacy_history.parent.mkdir(parents=True, exist_ok=True)

    canonical_history.write_text(json.dumps([{"id": "canon-1"}]), encoding="utf-8")
    legacy_history.write_text(json.dumps([{"id": "legacy-1"}]), encoding="utf-8")

    module.ROOT = root
    module.DATA_DIR = root / "data"
    module.TRADER_DIR = trader_dir
    module.MIGRATION_REPORT = tmp_path / "migration_report.json"

    monkeypatch.setattr(module.Path, "home", lambda: tmp_path / "home")

    report = {}
    module.migrate_trading_state(report)
    first = json.loads(canonical_history.read_text(encoding="utf-8"))

    report2 = {}
    module.migrate_trading_state(report2)
    second = json.loads(canonical_history.read_text(encoding="utf-8"))

    assert len(first) == 2
    assert len(second) == 2
    assert {entry.get("id") for entry in second} == {"canon-1", "legacy-1"}
