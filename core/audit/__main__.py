"""CLI entrypoint for audit suite."""

from __future__ import annotations

import argparse
import json

from core.audit.runner import run_all


def main() -> None:
    parser = argparse.ArgumentParser(description="LifeOS audit suite")
    parser.add_argument("command", nargs="?", default="run_all")
    args = parser.parse_args()

    if args.command == "run_all":
        report = run_all()
        print(json.dumps(report, indent=2))
        return

    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
