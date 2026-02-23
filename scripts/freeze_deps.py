#!/usr/bin/env python3
"""Compile requirement profiles and refresh lockfile checksums."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

REQ_DIR = Path(__file__).resolve().parents[1] / "requirements"
DEFAULT_PROFILES = ("signer", "core", "ai", "ci", "dev")


def run_compile(profile: str) -> None:
    in_file = REQ_DIR / f"{profile}.in"
    out_file = REQ_DIR / f"{profile}.txt"
    if not in_file.exists():
        raise FileNotFoundError(f"Missing {in_file}")

    cmd = [
        sys.executable,
        "-m",
        "piptools",
        "compile",
        "--generate-hashes",
        "--allow-unsafe",
        "--resolver=backtracking",
        "--output-file",
        str(out_file),
        str(in_file),
    ]
    subprocess.run(cmd, check=True)


def write_lock_checksum() -> None:
    txt_files = sorted(REQ_DIR.glob("*.txt"))
    lines: list[str] = []
    for file_path in txt_files:
        digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {file_path.name}")
    (REQ_DIR / "lockfile.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze dependency lockfiles")
    parser.add_argument(
        "--profiles",
        nargs="+",
        default=list(DEFAULT_PROFILES),
        help="Requirement profiles to compile",
    )
    args = parser.parse_args()

    for profile in args.profiles:
        run_compile(profile)

    write_lock_checksum()
    print("Dependency profiles compiled and lockfile.sha256 refreshed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
