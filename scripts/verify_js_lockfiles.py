#!/usr/bin/env python3
"""Verify every tracked JS app has a tracked package-lock.json."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _git_lines(*args: str) -> list[str]:
    proc = subprocess.run(
        ["git", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _is_tracked(path: str) -> bool:
    proc = subprocess.run(
        ["git", "ls-files", "--error-unmatch", path],
        check=False,
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def main() -> int:
    package_json_files = _git_lines("ls-files", "**/package.json")
    if not package_json_files:
        print("No package.json files tracked; nothing to verify.")
        return 0

    errors: list[str] = []
    for package_json in package_json_files:
        lockfile = str(Path(package_json).with_name("package-lock.json"))
        if not Path(lockfile).exists():
            errors.append(f"Missing package-lock.json for {package_json}")
            continue
        if not _is_tracked(lockfile):
            errors.append(f"package-lock.json exists but is not tracked: {lockfile}")

    if errors:
        print("JS lockfile verification failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"JS lockfile verification passed for {len(package_json_files)} package.json files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
