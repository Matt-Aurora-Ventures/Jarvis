"""
Memory Compression Utilities

Helps agents compress and summarize information for efficient storage.
"""
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def compress_log_entries(entries: List[str], max_length: int = 500) -> str:
    """
    Compress a list of log entries into a summary.

    This is a simple implementation - agents can use AI for better compression.
    """
    if not entries:
        return ""

    # Count occurrences
    counts: Dict[str, int] = {}
    for entry in entries:
        # Extract first 50 chars as key
        key = entry[:50].strip()
        counts[key] = counts.get(key, 0) + 1

    # Build summary
    summary_parts = []
    for key, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
        if count > 1:
            summary_parts.append(f"{key}... (x{count})")
        else:
            summary_parts.append(key)

        # Check length
        current = "\n".join(summary_parts)
        if len(current) > max_length:
            summary_parts = summary_parts[:-1]
            break

    return "\n".join(summary_parts)


def compress_error_pattern(errors: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compress multiple errors into a pattern.

    Returns:
        Dict with pattern info: type, count, first_seen, last_seen, sample
    """
    if not errors:
        return {}

    error_types: Dict[str, List[Dict]] = {}
    for error in errors:
        error_type = error.get("type", "unknown")
        error_types.setdefault(error_type, []).append(error)

    # Find most common type
    most_common_type = max(error_types.items(), key=lambda x: len(x[1]))
    error_list = most_common_type[1]

    return {
        "pattern_type": most_common_type[0],
        "count": len(error_list),
        "first_seen": min(e.get("timestamp", "") for e in error_list),
        "last_seen": max(e.get("timestamp", "") for e in error_list),
        "sample": error_list[0] if error_list else {},
    }


def summarize_insights(insights: List[Dict[str, Any]]) -> str:
    """
    Summarize a list of insights into a compressed format.
    """
    if not insights:
        return "No insights"

    # Group by type
    by_type: Dict[str, List] = {}
    for insight in insights:
        itype = insight.get("insight_type", "unknown")
        by_type.setdefault(itype, []).append(insight)

    # Build summary
    summary_lines = []
    for itype, items in by_type.items():
        summary_lines.append(f"{itype.upper()}: {len(items)} insights")
        # Add high-confidence items
        high_conf = [i for i in items if i.get("confidence", 0) > 0.8]
        if high_conf:
            for item in high_conf[:3]:  # Max 3
                summary = item.get("summary", "No summary")
                summary_lines.append(f"  - {summary}")

    return "\n".join(summary_lines)
