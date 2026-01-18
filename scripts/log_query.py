#!/usr/bin/env python3
"""
Log Query CLI - Query structured JSON logs.

Usage:
    python scripts/log_query.py --level ERROR --since "1 hour ago"
    python scripts/log_query.py --service trading --symbol SOL
    python scripts/log_query.py --correlation-id trade-abc123
    python scripts/log_query.py --user-id 8527130908
    python scripts/log_query.py --flag DEXTER_ENABLED

Examples:
    # Get all errors from the last hour
    python scripts/log_query.py --level ERROR --since "1 hour ago"

    # Get trading logs for SOL
    python scripts/log_query.py --service trading_engine --context-key symbol --context-value SOL

    # Get logs by correlation ID
    python scripts/log_query.py --correlation-id trade-abc123-def456

    # Count logs by level
    python scripts/log_query.py --level INFO --format count
"""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def parse_relative_time(time_str: str) -> Optional[datetime]:
    """
    Parse a relative time string like "1 hour ago" or "30 minutes ago".

    Also handles absolute ISO8601 timestamps.

    Args:
        time_str: Time string to parse

    Returns:
        datetime object or None if parsing fails
    """
    if not time_str:
        return None

    time_str = time_str.strip().lower()

    # Try parsing as ISO8601 first
    try:
        # Handle Z suffix
        if time_str.endswith("z"):
            time_str = time_str[:-1] + "+00:00"
        return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
    except ValueError:
        pass

    # Try parsing as relative time
    now = datetime.now(timezone.utc)

    # Patterns: "1 hour ago", "30 minutes ago", "2 days ago"
    patterns = [
        (r"(\d+)\s*hours?\s*ago", lambda m: now - timedelta(hours=int(m.group(1)))),
        (r"(\d+)\s*minutes?\s*ago", lambda m: now - timedelta(minutes=int(m.group(1)))),
        (r"(\d+)\s*days?\s*ago", lambda m: now - timedelta(days=int(m.group(1)))),
        (r"(\d+)\s*weeks?\s*ago", lambda m: now - timedelta(weeks=int(m.group(1)))),
        (r"(\d+)\s*seconds?\s*ago", lambda m: now - timedelta(seconds=int(m.group(1)))),
    ]

    for pattern, handler in patterns:
        match = re.match(pattern, time_str)
        if match:
            return handler(match)

    # Try parsing various date formats
    formats = [
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(time_str, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    return None


def load_log_file(log_file: Path) -> List[Dict[str, Any]]:
    """
    Load a JSONL log file.

    Args:
        log_file: Path to the log file

    Returns:
        List of log entry dictionaries
    """
    entries = []
    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def query_logs(
    log_dir: Path,
    level: Optional[str] = None,
    service: Optional[str] = None,
    correlation_id: Optional[str] = None,
    user_id: Optional[str] = None,
    flag: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    context_key: Optional[str] = None,
    context_value: Optional[str] = None,
    logger_name: Optional[str] = None,
    limit: int = 1000,
) -> List[Dict[str, Any]]:
    """
    Query log files with filters.

    Args:
        log_dir: Directory containing log files
        level: Filter by log level (INFO, ERROR, etc.)
        service: Filter by service name
        correlation_id: Filter by correlation ID (supports partial match)
        user_id: Filter by user ID (supports partial match)
        flag: Filter by active flag
        since: Only logs since this time
        until: Only logs until this time
        context_key: Filter by context key
        context_value: Filter by context value (requires context_key)
        logger_name: Filter by logger name
        limit: Maximum results to return

    Returns:
        List of matching log entries
    """
    log_dir = Path(log_dir)
    results = []

    # Parse time filters
    since_dt = parse_relative_time(since) if since else None
    until_dt = parse_relative_time(until) if until else None

    # Find all log files
    log_files = sorted(log_dir.glob("*.jsonl"), reverse=True)

    for log_file in log_files:
        if len(results) >= limit:
            break

        entries = load_log_file(log_file)

        for entry in entries:
            if len(results) >= limit:
                break

            # Apply filters
            if level and entry.get("level") != level:
                continue

            if service and entry.get("service") != service:
                continue

            if correlation_id:
                entry_corr = entry.get("correlation_id", "")
                if correlation_id not in str(entry_corr):
                    continue

            if user_id:
                entry_user = entry.get("user_id", "")
                if user_id not in str(entry_user):
                    continue

            if flag:
                entry_flags = entry.get("active_flags", [])
                if flag not in entry_flags:
                    continue

            if logger_name:
                if logger_name not in entry.get("logger", ""):
                    continue

            # Time filters
            if since_dt or until_dt:
                entry_time_str = entry.get("timestamp", "")
                try:
                    if entry_time_str.endswith("Z"):
                        entry_time_str = entry_time_str[:-1] + "+00:00"
                    entry_time = datetime.fromisoformat(entry_time_str)
                except ValueError:
                    continue

                if since_dt and entry_time < since_dt:
                    continue
                if until_dt and entry_time > until_dt:
                    continue

            # Context filter
            if context_key:
                entry_context = entry.get("context", {})
                if context_key not in entry_context:
                    continue
                if context_value and str(entry_context[context_key]) != context_value:
                    continue

            results.append(entry)

    return results


def format_output(
    results: List[Dict[str, Any]],
    format: str = "json",
) -> str:
    """
    Format query results.

    Args:
        results: List of log entries
        format: Output format ("json", "text", "count")

    Returns:
        Formatted output string
    """
    if format == "count":
        return str(len(results))

    if format == "text":
        lines = []
        for entry in results:
            ts = entry.get("timestamp", "")[:19]
            level = entry.get("level", "?")
            logger = entry.get("logger", "?")
            msg = entry.get("message", "")

            line = f"{ts} [{level:8}] {logger}: {msg}"

            # Add error info if present
            if entry.get("error"):
                line += f"\n  ERROR: {entry['error']}"

            # Add context
            if entry.get("context"):
                ctx_str = json.dumps(entry["context"])
                line += f"\n  Context: {ctx_str}"

            lines.append(line)

        return "\n".join(lines)

    # Default: JSON
    return json.dumps(results, indent=2, default=str)


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for CLI."""
    parser = argparse.ArgumentParser(
        description="Query structured JSON logs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --level ERROR --since "1 hour ago"
  %(prog)s --service trading_engine --symbol SOL
  %(prog)s --correlation-id trade-abc123
  %(prog)s --user-id 8527130908
  %(prog)s --flag DEXTER_ENABLED
        """,
    )

    parser.add_argument(
        "--log-dir",
        default="logs",
        help="Directory containing log files (default: logs)",
    )

    # Filter options
    parser.add_argument(
        "--level",
        "-l",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Filter by log level",
    )

    parser.add_argument(
        "--service",
        "-s",
        help="Filter by service name",
    )

    parser.add_argument(
        "--correlation-id",
        "-c",
        dest="correlation_id",
        help="Filter by correlation ID (partial match supported)",
    )

    parser.add_argument(
        "--user-id",
        "-u",
        dest="user_id",
        help="Filter by user ID (partial match supported)",
    )

    parser.add_argument(
        "--flag",
        "-f",
        help="Filter by active feature flag",
    )

    parser.add_argument(
        "--logger",
        help="Filter by logger name (partial match)",
    )

    # Time filters
    parser.add_argument(
        "--since",
        help='Only logs since this time (e.g., "1 hour ago", "2026-01-18")',
    )

    parser.add_argument(
        "--until",
        help='Only logs until this time (e.g., "30 minutes ago")',
    )

    # Context filters
    parser.add_argument(
        "--context-key",
        dest="context_key",
        help="Filter by context key",
    )

    parser.add_argument(
        "--context-value",
        dest="context_value",
        help="Filter by context value (requires --context-key)",
    )

    # Output options
    parser.add_argument(
        "--format",
        choices=["json", "text", "count"],
        default="json",
        help="Output format (default: json)",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="Maximum number of results (default: 1000)",
    )

    return parser


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # Resolve log directory
    log_dir = Path(args.log_dir)
    if not log_dir.is_absolute():
        # Try relative to script location, then cwd
        script_dir = Path(__file__).parent.parent
        if (script_dir / args.log_dir).exists():
            log_dir = script_dir / args.log_dir
        else:
            log_dir = Path.cwd() / args.log_dir

    if not log_dir.exists():
        print(f"Error: Log directory not found: {log_dir}", file=sys.stderr)
        sys.exit(1)

    # Query logs
    results = query_logs(
        log_dir=log_dir,
        level=args.level,
        service=args.service,
        correlation_id=args.correlation_id,
        user_id=args.user_id,
        flag=args.flag,
        since=args.since,
        until=args.until,
        context_key=args.context_key,
        context_value=args.context_value,
        logger_name=args.logger,
        limit=args.limit,
    )

    # Output results
    output = format_output(results, format=args.format)
    print(output)

    # Exit with error code if no results (useful for scripting)
    if not results and args.format != "count":
        sys.exit(1)


if __name__ == "__main__":
    main()
