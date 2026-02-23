from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _write_payload(path: Path, comparison_status: str) -> None:
    payload = {
        "pybroker": {"available": True, "status": "completed"},
        "comparisons": {
            "fixed_sl_tp_trend": {
                "status": comparison_status,
                "delta_total_return_pct": 10.0,
                "tolerance_pct": 5.0,
            }
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_assert_script_strict_ignores_parity_when_not_enforced(tmp_path: Path):
    artifact = tmp_path / "comparison.json"
    _write_payload(artifact, comparison_status="fail")

    proc = subprocess.run(
        [
            sys.executable,
            "scripts/backtesting/assert_pybroker_comparison.py",
            "--artifact-file",
            str(artifact),
            "--strict",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0


def test_assert_script_strict_fails_when_parity_enforced(tmp_path: Path):
    artifact = tmp_path / "comparison.json"
    _write_payload(artifact, comparison_status="fail")

    proc = subprocess.run(
        [
            sys.executable,
            "scripts/backtesting/assert_pybroker_comparison.py",
            "--artifact-file",
            str(artifact),
            "--strict",
            "--enforce-parity",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    assert "comparison parity failures beyond tolerance" in proc.stderr
