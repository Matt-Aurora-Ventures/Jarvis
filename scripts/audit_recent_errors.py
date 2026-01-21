"""Utility to audit the most recent error records across Jarvis logs."""

from __future__ import annotations

import argparse
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Tuple


LOG_FILES = [
    Path("logs/telegram_bot_errors.log"),
    Path("logs/treasury_bot_errors.log"),
    Path("logs/supervisor.log"),
    Path("logs/bots.log"),
]


def tail_lines(path: Path, maxlen: int = 8000) -> List[str]:
    """Return the last `maxlen` lines of the given file (safe for large files)."""
    if not path.exists():
        return []

    buffer = deque(maxlen=maxlen)
    with path.open(encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            buffer.append(line.rstrip("\n"))
    return list(buffer)


def parse_timestamp(line: str) -> datetime | None:
    """Parse the timestamp at the beginning of a log line."""
    try:
        ts = line[:23]
        return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S,%f")
    except ValueError:
        return None


def collect_recent_errors(path: Path, since: datetime) -> List[Tuple[datetime, str]]:
    """Collect errors from the log file that occurred after `since`."""
    records: List[Tuple[datetime, str]] = []

    for line in tail_lines(path):
        ts = parse_timestamp(line)
        if ts is None or ts < since:
            continue
        if "ERROR" in line or "CRITICAL" in line:
            records.append((ts, line))

    return records


def print_summary(records: List[Tuple[datetime, str]], path: Path, hours: float) -> None:
    """Print a concise summary of the recent error arrivals."""
    if not records:
        return

    print(f"\n{path.name}: {len(records)} errors in the last {hours:.1f} hours")
    print("-" * 80)
    for ts, line in records[-5:]:
        print(f"{ts.isoformat()} | {line}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit the last N hours of Jarvis errors.")
    parser.add_argument(
        "--hours",
        "-H",
        type=float,
        default=12.0,
        help="How many hours of errors to audit (default: 12)",
    )
    parser.add_argument(
        "--files",
        "-f",
        nargs="*",
        help="Additional log files to scan",
    )

    args = parser.parse_args()
    since = datetime.now(timezone.utc) - timedelta(hours=args.hours)
    threshold = since.astimezone(timezone.utc).replace(tzinfo=None)
    targets = list(LOG_FILES)
    if args.files:
        targets.extend(Path(f) for f in args.files)

    print(f"Auditing errors since {since.isoformat()} across {len(targets)} log files...")

    any_errors = False
    for path in targets:
        records = collect_recent_errors(path, threshold)
        if records:
            any_errors = True
            print_summary(records, path, args.hours)

    if not any_errors:
        print("No recent errors detected in the selected logs.")


if __name__ == "__main__":
    main()
