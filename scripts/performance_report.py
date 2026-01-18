#!/usr/bin/env python3
"""
Performance Report Generator

Generates HTML report with:
- Latency trends over time
- Cache hit rates by API
- Slowest endpoints
- Recommendations for optimization

Usage:
    python scripts/performance_report.py
    python scripts/performance_report.py --output reports/perf.html
    python scripts/performance_report.py --json
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.cache.api_cache import get_api_cache, DEFAULT_TTLS
from core.performance.profiler import get_profiler_results, get_performance_tracker


def collect_cache_data() -> Dict[str, Any]:
    """Collect cache statistics."""
    cache = get_api_cache()
    return {
        "stats": cache.get_stats(),
        "info": cache.get_info(),
        "default_ttls": DEFAULT_TTLS
    }


def collect_profiler_data() -> Dict[str, Any]:
    """Collect profiler statistics."""
    profiler_results = get_profiler_results()
    tracker = get_performance_tracker()
    tracker_stats = tracker.get_all_stats()

    return {
        "profiler": profiler_results,
        "tracker": tracker_stats
    }


def generate_recommendations(
    cache_data: Dict[str, Any],
    profiler_data: Dict[str, Any]
) -> List[Dict[str, str]]:
    """Generate optimization recommendations."""
    recommendations = []

    # Cache recommendations
    stats = cache_data["stats"]
    if stats["hit_rate"] < 0.5:
        recommendations.append({
            "category": "Cache",
            "severity": "high",
            "message": f"Low cache hit rate ({stats['hit_rate']:.1%}). Consider increasing TTLs or pre-warming cache.",
            "action": "Run: python scripts/cache_management.py ttl <api> <higher_seconds>"
        })

    # Per-API cache recommendations
    for api_name, api_stats in stats.get("by_api", {}).items():
        if api_stats["hits"] > 0 or api_stats["misses"] > 0:
            api_rate = api_stats["hit_rate"]
            if api_rate < 0.3 and api_stats["misses"] > 10:
                recommendations.append({
                    "category": "Cache",
                    "severity": "medium",
                    "message": f"{api_name} cache hit rate is low ({api_rate:.1%}). Current TTL: {api_stats['ttl_seconds']}s",
                    "action": f"Consider increasing TTL: python scripts/cache_management.py ttl {api_name} {api_stats['ttl_seconds'] * 2}"
                })

    # Profiler recommendations
    profiler = profiler_data.get("profiler", {})
    for name, data in profiler.items():
        avg_ms = data.get("avg_duration_ms", 0)
        if avg_ms > 1000:  # Over 1 second
            recommendations.append({
                "category": "Performance",
                "severity": "high",
                "message": f"Slow operation: {name} averages {avg_ms:.0f}ms",
                "action": "Consider caching result, parallelizing, or optimizing query"
            })
        elif avg_ms > 500:
            recommendations.append({
                "category": "Performance",
                "severity": "medium",
                "message": f"Moderate latency: {name} averages {avg_ms:.0f}ms",
                "action": "Monitor for regression"
            })

    # Tracker recommendations
    tracker = profiler_data.get("tracker", {})
    for name, data in tracker.items():
        p95 = data.get("p95_ms")
        if p95 and p95 > 2000:
            recommendations.append({
                "category": "Performance",
                "severity": "high",
                "message": f"High p95 latency: {name} has p95 of {p95:.0f}ms",
                "action": "Investigate slow requests and add timeout handling"
            })

    if not recommendations:
        recommendations.append({
            "category": "Status",
            "severity": "low",
            "message": "No significant issues detected",
            "action": "Continue monitoring"
        })

    return recommendations


def generate_html_report(
    cache_data: Dict[str, Any],
    profiler_data: Dict[str, Any],
    recommendations: List[Dict[str, str]]
) -> str:
    """Generate HTML performance report."""
    stats = cache_data["stats"]
    info = cache_data["info"]
    profiler = profiler_data.get("profiler", {})
    tracker = profiler_data.get("tracker", {})

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build cache table rows
    cache_rows = ""
    for api_name, api_stats in sorted(stats.get("by_api", {}).items()):
        if api_stats["hits"] > 0 or api_stats["misses"] > 0 or api_stats["entries"] > 0:
            rate_class = "good" if api_stats["hit_rate"] >= 0.7 else "warning" if api_stats["hit_rate"] >= 0.4 else "bad"
            cache_rows += f"""
            <tr>
                <td>{api_name}</td>
                <td>{api_stats['hits']:,}</td>
                <td>{api_stats['misses']:,}</td>
                <td>{api_stats['entries']:,}</td>
                <td class="{rate_class}">{api_stats['hit_rate']:.1%}</td>
                <td>{api_stats['ttl_seconds']}s</td>
            </tr>
            """

    # Build profiler table rows
    profiler_rows = ""
    sorted_profiler = sorted(profiler.items(), key=lambda x: x[1].get("duration_ms", 0), reverse=True)
    for name, data in sorted_profiler[:20]:  # Top 20 slowest
        avg_ms = data.get("avg_duration_ms", 0)
        time_class = "bad" if avg_ms > 1000 else "warning" if avg_ms > 500 else "good"
        profiler_rows += f"""
        <tr>
            <td>{name}</td>
            <td class="{time_class}">{data.get('duration_ms', 0):.2f}ms</td>
            <td>{avg_ms:.2f}ms</td>
            <td>{data.get('call_count', 0):,}</td>
            <td>{data.get('exception_count', 0)}</td>
        </tr>
        """

    # Build tracker table rows
    tracker_rows = ""
    sorted_tracker = sorted(tracker.items(), key=lambda x: x[1].get("avg_ms", 0), reverse=True)
    for name, data in sorted_tracker[:20]:
        avg_ms = data.get("avg_ms", 0)
        time_class = "bad" if avg_ms > 1000 else "warning" if avg_ms > 500 else "good"
        p95 = data.get("p95_ms", "-")
        p99 = data.get("p99_ms", "-")
        tracker_rows += f"""
        <tr>
            <td>{name}</td>
            <td>{data.get('count', 0):,}</td>
            <td>{data.get('min_ms', 0):.2f}</td>
            <td class="{time_class}">{avg_ms:.2f}</td>
            <td>{data.get('max_ms', 0):.2f}</td>
            <td>{p95 if p95 == '-' else f'{p95:.2f}'}</td>
            <td>{p99 if p99 == '-' else f'{p99:.2f}'}</td>
        </tr>
        """

    # Build recommendations rows
    rec_rows = ""
    for rec in recommendations:
        severity_class = rec["severity"]
        rec_rows += f"""
        <tr class="{severity_class}">
            <td>{rec['category']}</td>
            <td>{rec['severity'].upper()}</td>
            <td>{rec['message']}</td>
            <td><code>{rec['action']}</code></td>
        </tr>
        """

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Jarvis Performance Report - {timestamp}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: #1a1a2e;
            color: #eee;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        h1, h2 {{
            color: #00d4ff;
        }}
        h1 {{
            border-bottom: 2px solid #00d4ff;
            padding-bottom: 10px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .card {{
            background: #16213e;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
        }}
        .card h3 {{
            margin: 0;
            font-size: 14px;
            color: #888;
        }}
        .card .value {{
            font-size: 32px;
            font-weight: bold;
            color: #00d4ff;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background: #16213e;
            border-radius: 10px;
            overflow: hidden;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #2a2a4e;
        }}
        th {{
            background: #0f3460;
            color: #00d4ff;
        }}
        tr:hover {{
            background: #1a1a3e;
        }}
        .good {{ color: #4caf50; }}
        .warning {{ color: #ff9800; }}
        .bad {{ color: #f44336; }}
        tr.high {{ background: rgba(244, 67, 54, 0.1); }}
        tr.medium {{ background: rgba(255, 152, 0, 0.1); }}
        tr.low {{ background: rgba(76, 175, 80, 0.1); }}
        code {{
            background: #0f3460;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 12px;
        }}
        .timestamp {{
            color: #666;
            font-size: 12px;
        }}
        .section {{
            margin: 40px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Jarvis Performance Report</h1>
        <p class="timestamp">Generated: {timestamp}</p>

        <div class="summary">
            <div class="card">
                <h3>Cache Hit Rate</h3>
                <div class="value">{stats['hit_rate']:.1%}</div>
            </div>
            <div class="card">
                <h3>Total Cache Entries</h3>
                <div class="value">{stats['total_entries']:,}</div>
            </div>
            <div class="card">
                <h3>Memory Usage</h3>
                <div class="value">{info['memory_usage_bytes'] / 1024:.1f} KB</div>
            </div>
            <div class="card">
                <h3>Profiled Operations</h3>
                <div class="value">{len(profiler)}</div>
            </div>
        </div>

        <div class="section">
            <h2>Cache Statistics by API</h2>
            <table>
                <thead>
                    <tr>
                        <th>API</th>
                        <th>Hits</th>
                        <th>Misses</th>
                        <th>Entries</th>
                        <th>Hit Rate</th>
                        <th>TTL</th>
                    </tr>
                </thead>
                <tbody>
                    {cache_rows if cache_rows else '<tr><td colspan="6">No cache data yet</td></tr>'}
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>Profiled Operations (Slowest)</h2>
            <table>
                <thead>
                    <tr>
                        <th>Operation</th>
                        <th>Total Time</th>
                        <th>Avg Time</th>
                        <th>Calls</th>
                        <th>Errors</th>
                    </tr>
                </thead>
                <tbody>
                    {profiler_rows if profiler_rows else '<tr><td colspan="5">No profiler data yet</td></tr>'}
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>Tracked Operations (Latency Distribution)</h2>
            <table>
                <thead>
                    <tr>
                        <th>Operation</th>
                        <th>Count</th>
                        <th>Min</th>
                        <th>Avg</th>
                        <th>Max</th>
                        <th>p95</th>
                        <th>p99</th>
                    </tr>
                </thead>
                <tbody>
                    {tracker_rows if tracker_rows else '<tr><td colspan="7">No tracker data yet</td></tr>'}
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>Recommendations</h2>
            <table>
                <thead>
                    <tr>
                        <th>Category</th>
                        <th>Severity</th>
                        <th>Issue</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>
                    {rec_rows}
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>Default TTL Configuration</h2>
            <table>
                <thead>
                    <tr>
                        <th>API</th>
                        <th>TTL (seconds)</th>
                        <th>TTL (minutes)</th>
                        <th>Use Case</th>
                    </tr>
                </thead>
                <tbody>
                    <tr><td>jupiter</td><td>300</td><td>5</td><td>Price quotes - change frequently</td></tr>
                    <tr><td>solscan</td><td>3600</td><td>60</td><td>On-chain data - relatively stable</td></tr>
                    <tr><td>coingecko</td><td>1800</td><td>30</td><td>Market data - moderate stability</td></tr>
                    <tr><td>grok</td><td>7200</td><td>120</td><td>AI analysis - sentiment stable</td></tr>
                    <tr><td>birdeye</td><td>600</td><td>10</td><td>Token metrics</td></tr>
                    <tr><td>binance</td><td>120</td><td>2</td><td>Real-time prices</td></tr>
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
    """

    return html


def generate_json_report(
    cache_data: Dict[str, Any],
    profiler_data: Dict[str, Any],
    recommendations: List[Dict[str, str]]
) -> str:
    """Generate JSON performance report."""
    report = {
        "timestamp": datetime.now().isoformat(),
        "cache": cache_data,
        "profiler": profiler_data,
        "recommendations": recommendations
    }
    return json.dumps(report, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Generate performance report"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output file path (default: stdout for JSON, reports/performance.html for HTML)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of HTML"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress status messages"
    )

    args = parser.parse_args()

    # Collect data
    if not args.quiet:
        print("Collecting cache data...")
    cache_data = collect_cache_data()

    if not args.quiet:
        print("Collecting profiler data...")
    profiler_data = collect_profiler_data()

    if not args.quiet:
        print("Generating recommendations...")
    recommendations = generate_recommendations(cache_data, profiler_data)

    # Generate report
    if args.json:
        report = generate_json_report(cache_data, profiler_data, recommendations)
        if args.output:
            Path(args.output).write_text(report)
            if not args.quiet:
                print(f"JSON report saved to: {args.output}")
        else:
            print(report)
    else:
        report = generate_html_report(cache_data, profiler_data, recommendations)
        output_path = args.output or ROOT / "reports" / "performance.html"
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report)
        if not args.quiet:
            print(f"HTML report saved to: {output_path}")
            print(f"Open in browser: file://{output_path.absolute()}")


if __name__ == "__main__":
    main()
