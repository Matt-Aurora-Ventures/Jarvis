"""Validate pybroker comparison artifacts for strict or warning-only CI modes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


BLOCKED_STATUSES = {"pending", "skipped", "error"}


def _latest_comparison_file(root: Path) -> Path:
    if not root.exists():
        raise FileNotFoundError(f"Artifact root does not exist: {root}")
    candidates = sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name)
    if not candidates:
        raise FileNotFoundError(f"No comparison artifact directories under: {root}")
    latest = candidates[-1]
    path = latest / "comparison.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing comparison.json in latest artifact dir: {latest}")
    return path


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _collect_findings(payload: dict[str, Any], *, enforce_parity: bool) -> list[str]:
    findings: list[str] = []
    py = payload.get("pybroker", {}) if isinstance(payload, dict) else {}
    comparisons = payload.get("comparisons", {}) if isinstance(payload, dict) else {}

    available = bool(py.get("available"))
    status = str(py.get("status", "")).strip().lower()
    if available and status in BLOCKED_STATUSES:
        findings.append(
            f"pybroker status is blocked in available environment: status={status!r}"
        )

    if available and isinstance(comparisons, dict):
        skipped = [name for name, info in comparisons.items() if str((info or {}).get("status", "")).lower() == "skipped"]
        if skipped:
            findings.append(f"comparison scenarios skipped in available environment: {', '.join(sorted(skipped))}")
        if enforce_parity:
            failed = []
            for name, info in comparisons.items():
                status_i = str((info or {}).get("status", "")).lower()
                if status_i != "fail":
                    continue
                delta = (info or {}).get("delta_total_return_pct")
                tolerance = (info or {}).get("tolerance_pct")
                failed.append(f"{name}(delta={delta}, tolerance={tolerance})")
            if failed:
                findings.append(
                    "comparison parity failures beyond tolerance: "
                    + ", ".join(sorted(failed))
                )

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact-root",
        default="artifacts/backtest_compare",
        help="Root directory containing timestamped comparison artifacts.",
    )
    parser.add_argument(
        "--artifact-file",
        default="",
        help="Optional explicit path to comparison.json. Overrides --artifact-root.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail non-zero on blocked statuses/findings. Default mode logs warnings only.",
    )
    parser.add_argument(
        "--enforce-parity",
        action="store_true",
        help="Also treat comparison tolerance failures as findings.",
    )
    args = parser.parse_args()

    try:
        artifact_path = Path(args.artifact_file) if args.artifact_file else _latest_comparison_file(Path(args.artifact_root))
        payload = _load(artifact_path)
    except Exception as exc:
        print(f"[pybroker-assert] unable to load comparison artifact: {exc}", file=sys.stderr)
        return 1 if args.strict else 0

    findings = _collect_findings(payload, enforce_parity=args.enforce_parity)
    mode = "STRICT" if args.strict else "WARN"
    print(f"[pybroker-assert] mode={mode} artifact={artifact_path}")
    if findings:
        for finding in findings:
            print(f"[pybroker-assert] {finding}", file=sys.stderr if args.strict else sys.stdout)
        if args.strict:
            return 1
        return 0

    print("[pybroker-assert] checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
