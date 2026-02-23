#!/usr/bin/env python3
"""Validate forbidden-term quarantine for execution-path artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "policies" / "execution_path_quarantine.json"


def load_policy(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_protected_files(globs: list[str]) -> list[Path]:
    files: set[Path] = set()
    for pattern in globs:
        for path in ROOT.glob(pattern):
            if path.is_file():
                files.add(path)
    return sorted(files)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate execution-path quarantine policy")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    args = parser.parse_args()

    policy = load_policy(args.policy)
    protected_globs = policy.get("protected_globs", [])
    forbidden_terms = [term.lower() for term in policy.get("forbidden_terms", [])]

    files = iter_protected_files(protected_globs)
    violations: list[str] = []

    for file_path in files:
        content = file_path.read_text(encoding="utf-8", errors="ignore").lower()
        for term in forbidden_terms:
            if term in content:
                violations.append(f"{file_path.relative_to(ROOT)} contains forbidden term: {term}")

    if violations:
        print("Execution path quarantine validation failed:")
        for violation in violations:
            print(f"- {violation}")
        return 1

    print(f"Execution path quarantine validation passed ({len(files)} files checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
