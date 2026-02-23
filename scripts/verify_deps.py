#!/usr/bin/env python3
"""Verify dependency lock integrity and signer profile policy."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

REQ_DIR = Path(__file__).resolve().parents[1] / "requirements"
LOCKSUM = REQ_DIR / "lockfile.sha256"
SIGNER_IN = REQ_DIR / "signer.in"
SIGNER_TXT = REQ_DIR / "signer.txt"

FORBIDDEN_SIGNER_PACKAGES = {
    "flask",
    "fastapi",
    "uvicorn",
    "gunicorn",
    "pandas",
    "numpy",
    "xgboost",
    "scikit-learn",
    "redis",
    "ccxt",
    "freqtrade",
    "langgraph",
    "langchain",
    "openai",
    "anthropic",
    "@solana/kit",
    "@solana/web3.js",
    "bun",
    "openclaw",
    "node",
}

PIN_RE = re.compile(r"^([A-Za-z0-9_.\-\[\]]+)==([^\s]+)")


def parse_pins(path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = PIN_RE.match(line)
        if not match:
            continue
        name = match.group(1).split("[")[0].lower()
        version = match.group(2)
        pins[name] = version
    return pins


def verify_in_txt_alignment() -> list[str]:
    errors: list[str] = []
    for in_file in sorted(REQ_DIR.glob("*.in")):
        txt_file = REQ_DIR / f"{in_file.stem}.txt"
        if not txt_file.exists():
            errors.append(f"Missing lockfile for profile: {txt_file.name}")
            continue

        direct_pins = parse_pins(in_file)
        lock_pins = parse_pins(txt_file)

        for package, version in direct_pins.items():
            if package not in lock_pins:
                errors.append(f"{txt_file.name} missing package from {in_file.name}: {package}")
                continue
            if lock_pins[package] != version:
                errors.append(
                    f"Version drift for {package}: {in_file.name}={version} {txt_file.name}={lock_pins[package]}"
                )
    return errors


def verify_lock_checksum() -> list[str]:
    errors: list[str] = []
    if not LOCKSUM.exists():
        return ["requirements/lockfile.sha256 is missing"]

    lines = [line.strip() for line in LOCKSUM.read_text(encoding="utf-8").splitlines() if line.strip()]
    expected: dict[str, str] = {}
    for line in lines:
        parts = line.split()
        if len(parts) != 2:
            errors.append(f"Invalid checksum line: {line}")
            continue
        expected[parts[1]] = parts[0]

    for txt_file in sorted(REQ_DIR.glob("*.txt")):
        digest = hashlib.sha256(txt_file.read_bytes()).hexdigest()
        recorded = expected.get(txt_file.name)
        if recorded is None:
            errors.append(f"Missing checksum entry for {txt_file.name}")
            continue
        if recorded.lower() != digest.lower():
            errors.append(f"Checksum mismatch for {txt_file.name}")
    return errors


def verify_signer_policy(max_count: int) -> list[str]:
    errors: list[str] = []
    direct_signer = parse_pins(SIGNER_IN)
    if len(direct_signer) > max_count:
        errors.append(
            f"Signer profile exceeds package count threshold: {len(direct_signer)} > {max_count}"
        )

    signer_lock = parse_pins(SIGNER_TXT)
    lower_lock_names = {name.lower() for name in signer_lock}

    for forbidden in FORBIDDEN_SIGNER_PACKAGES:
        if forbidden.lower() in lower_lock_names:
            errors.append(f"Forbidden package found in signer.txt: {forbidden}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify dependency lock governance")
    parser.add_argument("--max-signer-packages", type=int, default=10)
    args = parser.parse_args()

    all_errors: list[str] = []
    all_errors.extend(verify_in_txt_alignment())
    all_errors.extend(verify_lock_checksum())
    all_errors.extend(verify_signer_policy(args.max_signer_packages))

    if all_errors:
        print("Dependency verification failed:")
        for err in all_errors:
            print(f"- {err}")
        return 1

    print("Dependency verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
