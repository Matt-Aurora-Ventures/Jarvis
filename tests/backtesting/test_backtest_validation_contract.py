from pathlib import Path


def test_backtest_validation_script_uses_vitest_contract() -> None:
    root = Path(__file__).resolve().parents[2]
    script = (root / "scripts" / "backtesting" / "run_backtest_validation.ps1").read_text(
        encoding="utf-8", errors="ignore"
    )

    assert "npm --prefix jarvis-sniper run test --" in script
    assert "src/__tests__/bags-backtest-api.test.ts" in script
    assert "--runInBand" not in script
    assert "--testPathPattern" not in script


def test_contract_validator_targets_expected_files() -> None:
    root = Path(__file__).resolve().parents[2]
    validator = (
        root / "scripts" / "backtesting" / "validate_backtest_contract.py"
    ).read_text(encoding="utf-8", errors="ignore")

    assert "EXPECTED_JS_TEST_COMMAND" in validator
    assert "EXPECTED_PY_TEST_COMMAND" in validator
    assert "jarvis-sniper" in validator
