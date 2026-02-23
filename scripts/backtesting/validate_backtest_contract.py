"""
Validate backtesting command contract and write governance artifacts.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PS1_PATH = ROOT / "scripts" / "backtesting" / "run_backtest_validation.ps1"
PACKAGE_JSON = ROOT / "jarvis-sniper" / "package.json"
ARTIFACT_DIR = ROOT / "artifacts" / "backtest_validation"
COMPARE_DIR = ROOT / "artifacts" / "backtest_compare"

EXPECTED_JS_TEST_COMMAND = (
    "npm --prefix jarvis-sniper run test -- "
    "src/__tests__/bags-backtest-api.test.ts "
    "src/__tests__/backtest-route-execution-realism.test.ts "
    "src/__tests__/backtest-campaign-orchestrator.test.ts"
)
EXPECTED_PY_TEST_COMMAND = "python -m pytest tests/backtesting/test_backtest.py -q"


@dataclass(frozen=True)
class ContractCheck:
    name: str
    ok: bool
    details: str


def _utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def validate_contract() -> list[ContractCheck]:
    checks: list[ContractCheck] = []

    if not PS1_PATH.exists():
        checks.append(
            ContractCheck(
                name="ps1_exists",
                ok=False,
                details=f"Missing script: {PS1_PATH}",
            )
        )
    else:
        ps1 = _read_text(PS1_PATH)
        checks.append(
            ContractCheck(
                name="ps1_has_expected_js_command",
                ok=EXPECTED_JS_TEST_COMMAND in ps1,
                details="Expected canonical JS test invocation present",
            )
        )
        checks.append(
            ContractCheck(
                name="ps1_has_expected_py_command",
                ok=EXPECTED_PY_TEST_COMMAND in ps1,
                details="Expected canonical Python test invocation present",
            )
        )
        checks.append(
            ContractCheck(
                name="ps1_no_jest_flags",
                ok="--runInBand" not in ps1 and "--testPathPattern" not in ps1,
                details="Jest-only flags are absent",
            )
        )

    if not PACKAGE_JSON.exists():
        checks.append(
            ContractCheck(
                name="package_json_exists",
                ok=False,
                details=f"Missing package.json: {PACKAGE_JSON}",
            )
        )
    else:
        try:
            package_payload: dict[str, Any] = json.loads(_read_text(PACKAGE_JSON))
            test_script = str(package_payload.get("scripts", {}).get("test", "")).strip()
            checks.append(
                ContractCheck(
                    name="jarvis_sniper_test_is_vitest",
                    ok="vitest" in test_script and "jest" not in test_script,
                    details=f'jarvis-sniper test script="{test_script}"',
                )
            )
        except Exception as exc:  # pragma: no cover - defensive parse guard
            checks.append(
                ContractCheck(
                    name="package_json_parse",
                    ok=False,
                    details=f"Failed to parse package.json: {exc}",
                )
            )

    return checks


def write_artifacts(checks: list[ContractCheck], strict: bool) -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    COMPARE_DIR.mkdir(parents=True, exist_ok=True)

    stamp = _utc_stamp()
    output_path = ARTIFACT_DIR / f"contract_validation_{stamp}.json"
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "strict_mode": strict,
        "overall_ok": all(item.ok for item in checks),
        "checks": [
            {
                "name": item.name,
                "ok": item.ok,
                "details": item.details,
            }
            for item in checks
        ],
    }
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    compare_index = COMPARE_DIR / "latest.json"
    compare_index.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "contract_artifact": str(output_path.relative_to(ROOT)).replace("\\", "/"),
                "status": "pass" if payload["overall_ok"] else "fail",
                "notes": "Backtest compare artifact placeholder for local/CI governance.",
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate backtesting command contract.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--strict", action="store_true", help="Return non-zero exit code on contract failure.")
    mode.add_argument("--warning", action="store_true", help="Warning-only mode (always exits 0).")
    args = parser.parse_args()

    strict = bool(args.strict)
    checks = validate_contract()
    artifact = write_artifacts(checks, strict=strict)

    failed = [check for check in checks if not check.ok]
    print(f"[backtest-contract] artifact: {artifact}")
    for check in checks:
        status = "PASS" if check.ok else "FAIL"
        print(f"[{status}] {check.name}: {check.details}")

    if failed and strict:
        print(f"[backtest-contract] strict mode failed ({len(failed)} checks).")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
