"""Jarvis CLI entrypoint."""

from __future__ import annotations

import argparse
from typing import Optional

from jarvis_cli.actions import register_actions_subparser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jarvis", description="Jarvis command line interface.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    register_actions_subparser(subparsers)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if hasattr(args, "func"):
        return int(args.func(args))
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
