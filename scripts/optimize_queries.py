#!/usr/bin/env python3
"""
Analyze database queries and generate optimization recommendations.

Usage:
    python scripts/optimize_queries.py
    python scripts/optimize_queries.py --db data/jarvis.db
    python scripts/optimize_queries.py --metrics data/performance/metrics.jsonl

Generates a report with:
- Slow queries (>100ms by default)
- Missing index recommendations
- Query pattern analysis
- Optimization suggestions
"""
import argparse
import json
import sqlite3
import sys
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class QueryAnalyzer:
    """Analyze queries for optimization opportunities."""

    def __init__(
        self,
        db_path: str = "data/jarvis.db",
        slow_threshold_ms: float = 100.0
    ):
        """
        Args:
            db_path: Path to SQLite database
            slow_threshold_ms: Threshold for slow queries (in milliseconds)
        """
        self.db_path = db_path
        self.slow_threshold_ms = slow_threshold_ms
        self.query_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "count": 0,
            "total_ms": 0.0,
            "max_ms": 0.0,
            "min_ms": float('inf'),
            "samples": []
        })

    def load_metrics(self, metrics_path: str) -> int:
        """
        Load query metrics from JSONL file.

        Args:
            metrics_path: Path to metrics JSONL file

        Returns:
            Number of query metrics loaded
        """
        if not Path(metrics_path).exists():
            return 0

        count = 0
        with open(metrics_path) as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if entry.get("type") == "query_time":
                        query = entry.get("query", "")
                        duration = entry.get("duration_ms", 0)
                        self._record_query(query, duration)
                        count += 1
                except (json.JSONDecodeError, KeyError):
                    continue

        return count

    def _record_query(self, query: str, duration_ms: float):
        """Record a query execution."""
        normalized = self._normalize_query(query)
        stats = self.query_stats[normalized]

        stats["count"] += 1
        stats["total_ms"] += duration_ms
        stats["max_ms"] = max(stats["max_ms"], duration_ms)
        stats["min_ms"] = min(stats["min_ms"], duration_ms)

        # Keep only recent samples
        if len(stats["samples"]) < 10:
            stats["samples"].append(duration_ms)

    def _normalize_query(self, query: str) -> str:
        """Normalize query for grouping."""
        # Replace string literals
        normalized = re.sub(r"'[^']*'", "'?'", query)
        # Replace numbers
        normalized = re.sub(r"\b\d+\b", "?", normalized)
        # Normalize whitespace
        return " ".join(normalized.split())

    def get_slow_queries(self) -> List[Tuple[str, Dict[str, Any]]]:
        """Get queries slower than threshold."""
        slow = []
        for query, stats in self.query_stats.items():
            avg_ms = stats["total_ms"] / stats["count"] if stats["count"] > 0 else 0
            if avg_ms > self.slow_threshold_ms:
                slow.append((query, {
                    **stats,
                    "avg_ms": avg_ms
                }))

        return sorted(slow, key=lambda x: x[1]["avg_ms"], reverse=True)

    def analyze_query(self, query: str) -> Dict[str, Any]:
        """
        Analyze a query for optimization opportunities.

        Args:
            query: SQL query to analyze

        Returns:
            Analysis results with suggestions
        """
        suggestions = []
        query_upper = query.upper()

        # Check for SELECT *
        if "SELECT *" in query_upper:
            suggestions.append({
                "type": "select_star",
                "severity": "medium",
                "message": "Avoid SELECT * - specify only needed columns to reduce data transfer"
            })

        # Check for missing WHERE/LIMIT
        if "WHERE" not in query_upper and "LIMIT" not in query_upper:
            if "SELECT" in query_upper:
                suggestions.append({
                    "type": "no_filter",
                    "severity": "high",
                    "message": "Query has no WHERE clause or LIMIT - may return excessive rows"
                })

        # Check for leading wildcard LIKE
        if re.search(r"LIKE\s+'%", query, re.IGNORECASE):
            suggestions.append({
                "type": "leading_wildcard",
                "severity": "high",
                "message": "Leading wildcard in LIKE prevents index usage - consider full-text search"
            })

        # Check for multiple JOINs
        join_count = query_upper.count("JOIN")
        if join_count > 2:
            suggestions.append({
                "type": "multiple_joins",
                "severity": "medium",
                "message": f"{join_count} JOINs detected - consider query restructuring or denormalization"
            })

        # Check for OR conditions in WHERE
        if " OR " in query_upper and "WHERE" in query_upper:
            suggestions.append({
                "type": "or_condition",
                "severity": "low",
                "message": "OR conditions may prevent index usage - consider UNION for better performance"
            })

        # Check for ORDER BY without index hints
        if "ORDER BY" in query_upper and "INDEXED" not in query_upper:
            suggestions.append({
                "type": "unindexed_sort",
                "severity": "low",
                "message": "ORDER BY may cause filesort - ensure index covers sort columns"
            })

        # Check for subqueries
        if query_upper.count("SELECT") > 1:
            suggestions.append({
                "type": "subquery",
                "severity": "low",
                "message": "Subquery detected - consider JOIN or CTE for potential performance improvement"
            })

        return {
            "query": query,
            "suggestions": suggestions,
            "suggestion_count": len(suggestions)
        }

    def suggest_indexes(self, table: str) -> List[str]:
        """
        Suggest indexes for a table based on common patterns.

        Args:
            table: Table name

        Returns:
            List of CREATE INDEX statements
        """
        suggestions = []

        if not Path(self.db_path).exists():
            return suggestions

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get existing indexes
            cursor.execute(f"PRAGMA index_list({table})")
            existing = {row[1] for row in cursor.fetchall()}

            # Get table columns
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [row[1] for row in cursor.fetchall()]

            # Suggest indexes for common patterns
            for col in columns:
                index_name = f"idx_{table}_{col}"
                if index_name not in existing:
                    # ID columns
                    if col.endswith("_id"):
                        suggestions.append(f"CREATE INDEX {index_name} ON {table}({col});")
                    # Timestamp columns
                    elif col.endswith("_at") or col.endswith("_time") or col == "timestamp":
                        suggestions.append(f"CREATE INDEX {index_name} ON {table}({col});")
                    # Status/type columns
                    elif col in ["status", "type", "state", "symbol", "token"]:
                        suggestions.append(f"CREATE INDEX {index_name} ON {table}({col});")

            conn.close()
        except sqlite3.Error as e:
            print(f"Warning: Could not analyze table {table}: {e}")

        return suggestions

    def get_all_tables(self) -> List[str]:
        """Get all table names from database."""
        if not Path(self.db_path).exists():
            return []

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            return tables
        except sqlite3.Error:
            return []


def generate_report(
    analyzer: QueryAnalyzer,
    output_path: str,
    format: str = "markdown"
) -> str:
    """
    Generate optimization report.

    Args:
        analyzer: QueryAnalyzer instance with loaded metrics
        output_path: Path to write report
        format: Output format ("markdown" or "html")

    Returns:
        Path to generated report
    """
    slow_queries = analyzer.get_slow_queries()
    tables = analyzer.get_all_tables()

    if format == "markdown":
        report = generate_markdown_report(analyzer, slow_queries, tables)
    else:
        report = generate_html_report_queries(analyzer, slow_queries, tables)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(report)

    return output_path


def generate_markdown_report(
    analyzer: QueryAnalyzer,
    slow_queries: List[Tuple[str, Dict[str, Any]]],
    tables: List[str]
) -> str:
    """Generate markdown report."""
    lines = [
        "# Query Optimization Report",
        f"Generated: {datetime.now().isoformat()}",
        "",
        "## Summary",
        f"- Slow queries (>{analyzer.slow_threshold_ms}ms): {len(slow_queries)}",
        f"- Tables analyzed: {len(tables)}",
        "",
    ]

    # Slow queries section
    lines.append("## Slow Queries")
    lines.append("")

    if slow_queries:
        for query, stats in slow_queries[:20]:  # Top 20
            avg_ms = stats["avg_ms"]
            lines.append(f"### Query (avg: {avg_ms:.1f}ms)")
            lines.append("```sql")
            lines.append(query)
            lines.append("```")
            lines.append(f"- Count: {stats['count']}x")
            lines.append(f"- Avg Time: {avg_ms:.2f}ms")
            lines.append(f"- Max Time: {stats['max_ms']:.2f}ms")
            lines.append("")

            # Analyze and add suggestions
            analysis = analyzer.analyze_query(query)
            if analysis["suggestions"]:
                lines.append("**Recommendations:**")
                for suggestion in analysis["suggestions"]:
                    severity_icon = {
                        "high": "!",
                        "medium": "-",
                        "low": "."
                    }.get(suggestion["severity"], "-")
                    lines.append(f"  {severity_icon} [{suggestion['severity'].upper()}] {suggestion['message']}")
                lines.append("")
    else:
        lines.append("No slow queries detected.")
        lines.append("")

    # Index recommendations section
    lines.append("## Index Recommendations")
    lines.append("")

    all_index_suggestions = []
    for table in tables:
        suggestions = analyzer.suggest_indexes(table)
        all_index_suggestions.extend(suggestions)

    if all_index_suggestions:
        lines.append("```sql")
        for suggestion in all_index_suggestions:
            lines.append(suggestion)
        lines.append("```")
    else:
        lines.append("No additional indexes recommended.")

    lines.append("")

    # Query patterns section
    lines.append("## Query Pattern Analysis")
    lines.append("")

    # Group by pattern
    patterns = defaultdict(int)
    for query, stats in analyzer.query_stats.items():
        if query.upper().startswith("SELECT"):
            patterns["SELECT"] += stats["count"]
        elif query.upper().startswith("INSERT"):
            patterns["INSERT"] += stats["count"]
        elif query.upper().startswith("UPDATE"):
            patterns["UPDATE"] += stats["count"]
        elif query.upper().startswith("DELETE"):
            patterns["DELETE"] += stats["count"]

    if patterns:
        lines.append("| Pattern | Count |")
        lines.append("|---------|-------|")
        for pattern, count in sorted(patterns.items(), key=lambda x: -x[1]):
            lines.append(f"| {pattern} | {count:,} |")
    else:
        lines.append("No query patterns recorded.")

    return "\n".join(lines)


def generate_html_report_queries(
    analyzer: QueryAnalyzer,
    slow_queries: List[Tuple[str, Dict[str, Any]]],
    tables: List[str]
) -> str:
    """Generate HTML report."""
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Query Optimization Report</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, sans-serif; margin: 20px; background: #1a1a2e; color: #eee; }}
        h1, h2, h3 {{ color: #00d4ff; }}
        .report {{ background: #16213e; padding: 20px; border-radius: 8px; max-width: 1000px; }}
        .query-block {{ background: #0f3460; padding: 15px; border-radius: 4px; margin: 15px 0; }}
        .query-sql {{ background: #1a1a2e; padding: 10px; font-family: monospace; overflow-x: auto; }}
        .stats {{ color: #888; }}
        .recommendation {{ padding: 5px 10px; margin: 5px 0; border-left: 3px solid; }}
        .high {{ border-color: #ff6b6b; background: rgba(255, 107, 107, 0.1); }}
        .medium {{ border-color: #ffd93d; background: rgba(255, 217, 61, 0.1); }}
        .low {{ border-color: #6bcb77; background: rgba(107, 203, 119, 0.1); }}
        .index-sql {{ background: #0f3460; padding: 15px; font-family: monospace; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #333; }}
        th {{ background: #0f3460; }}
        .timestamp {{ color: #888; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="report">
        <h1>Query Optimization Report</h1>
        <p class="timestamp">Generated: {datetime.now().isoformat()}</p>

        <h2>Summary</h2>
        <ul>
            <li>Slow queries (>{analyzer.slow_threshold_ms}ms): <strong>{len(slow_queries)}</strong></li>
            <li>Tables analyzed: <strong>{len(tables)}</strong></li>
        </ul>

        <h2>Slow Queries</h2>
"""

    if slow_queries:
        for query, stats in slow_queries[:20]:
            avg_ms = stats["avg_ms"]
            analysis = analyzer.analyze_query(query)

            html += f"""
        <div class="query-block">
            <h3>Average: {avg_ms:.1f}ms</h3>
            <div class="query-sql">{query}</div>
            <p class="stats">Count: {stats['count']}x | Max: {stats['max_ms']:.2f}ms</p>
"""
            if analysis["suggestions"]:
                html += "<div class='recommendations'>"
                for s in analysis["suggestions"]:
                    html += f"<div class='recommendation {s['severity']}'>[{s['severity'].upper()}] {s['message']}</div>"
                html += "</div>"

            html += "</div>"
    else:
        html += "<p>No slow queries detected.</p>"

    # Index recommendations
    html += "<h2>Index Recommendations</h2>"

    all_index_suggestions = []
    for table in tables:
        suggestions = analyzer.suggest_indexes(table)
        all_index_suggestions.extend(suggestions)

    if all_index_suggestions:
        html += "<div class='index-sql'>"
        for suggestion in all_index_suggestions:
            html += f"{suggestion}<br>"
        html += "</div>"
    else:
        html += "<p>No additional indexes recommended.</p>"

    html += """
    </div>
</body>
</html>"""

    return html


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Analyze database queries for optimization")
    parser.add_argument("--db", type=str, default="data/jarvis.db", help="Path to SQLite database")
    parser.add_argument("--metrics", type=str, default="data/performance/metrics.jsonl", help="Path to metrics JSONL")
    parser.add_argument("--output", "-o", type=str, default="reports/query_optimization.md", help="Output report path")
    parser.add_argument("--threshold", type=float, default=100.0, help="Slow query threshold (ms)")
    parser.add_argument("--html", action="store_true", help="Generate HTML report instead of Markdown")

    args = parser.parse_args()

    # Initialize analyzer
    analyzer = QueryAnalyzer(
        db_path=args.db,
        slow_threshold_ms=args.threshold
    )

    # Load metrics
    metrics_loaded = analyzer.load_metrics(args.metrics)
    print(f"Loaded {metrics_loaded} query metrics from {args.metrics}")

    # If no metrics, add some sample analysis
    if metrics_loaded == 0:
        print("No metrics found. Running with sample data for demonstration.")
        # Add sample slow queries for demonstration
        analyzer._record_query("SELECT * FROM positions WHERE user_id = ?", 45.2)
        analyzer._record_query("SELECT * FROM positions WHERE user_id = ?", 48.1)
        analyzer._record_query("SELECT * FROM logs WHERE service = ? ORDER BY timestamp DESC", 156.3)
        analyzer._record_query("SELECT * FROM logs WHERE service = ? ORDER BY timestamp DESC", 162.8)

    # Generate report
    output_format = "html" if args.html else "markdown"
    if args.html and not args.output.endswith(".html"):
        args.output = args.output.replace(".md", ".html")

    report_path = generate_report(analyzer, args.output, format=output_format)
    print(f"\nReport written to: {report_path}")

    # Print summary
    slow_queries = analyzer.get_slow_queries()
    print(f"\nSlow queries found: {len(slow_queries)}")
    if slow_queries:
        print("\nTop slow queries:")
        for query, stats in slow_queries[:5]:
            print(f"  - {stats['avg_ms']:.1f}ms avg ({stats['count']}x): {query[:60]}...")

    return 0


if __name__ == "__main__":
    sys.exit(main())
