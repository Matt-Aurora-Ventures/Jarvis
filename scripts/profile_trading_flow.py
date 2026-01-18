#!/usr/bin/env python3
"""
Profile the complete trading flow and generate performance reports.

Usage:
    python scripts/profile_trading_flow.py
    python scripts/profile_trading_flow.py --html
    python scripts/profile_trading_flow.py --output reports/trading_profile.html

Generates a detailed breakdown of trading execution phases:
- Signal Detection (liquidation, MA analysis, sentiment)
- Position Sizing
- Risk Checks
- Jupiter Quote
- Execution
"""
import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.performance.profiler import (
    profile_block,
    get_profiler_results,
    reset_profiler,
    export_results_json,
    export_results_table
)
from core.performance.metrics_collector import (
    MetricsCollector,
    PerformanceBaselines,
    generate_regression_report
)


# Default performance baselines (targets in milliseconds)
DEFAULT_BASELINES = {
    "signal_detection": {"target_ms": 50},
    "signal_detection.liquidation": {"target_ms": 20},
    "signal_detection.ma_analysis": {"target_ms": 15},
    "signal_detection.sentiment": {"target_ms": 25},
    "signal_detection.decision_matrix": {"target_ms": 5},
    "position_sizing": {"target_ms": 10},
    "risk_checks": {"target_ms": 5},
    "jupiter_quote": {"target_ms": 200},  # External dependency
    "execution": {"target_ms": 100},  # External dependency
    "full_trade": {"target_ms": 400}  # Total (includes external)
}


class TradingFlowProfiler:
    """Profile the complete trading flow."""

    def __init__(self, mock_mode: bool = True):
        """
        Args:
            mock_mode: If True, use mock implementations. If False, use real components.
        """
        self.mock_mode = mock_mode
        self.metrics_collector = MetricsCollector()
        self.results: Dict[str, Any] = {}

    async def profile_signal_detection(self) -> Dict[str, Any]:
        """Profile signal detection phase."""
        with profile_block("signal_detection"):
            # Liquidation analysis
            with profile_block("signal_detection.liquidation"):
                if self.mock_mode:
                    await asyncio.sleep(0.015)  # ~15ms mock
                else:
                    # Real implementation would go here
                    pass

            # MA calculation
            with profile_block("signal_detection.ma_analysis"):
                if self.mock_mode:
                    await asyncio.sleep(0.008)  # ~8ms mock
                else:
                    pass

            # Sentiment scoring
            with profile_block("signal_detection.sentiment"):
                if self.mock_mode:
                    await asyncio.sleep(0.018)  # ~18ms mock
                else:
                    pass

            # Decision matrix
            with profile_block("signal_detection.decision_matrix"):
                if self.mock_mode:
                    await asyncio.sleep(0.002)  # ~2ms mock
                else:
                    pass

        return {"phase": "signal_detection", "status": "complete"}

    async def profile_position_sizing(self) -> Dict[str, Any]:
        """Profile position sizing phase."""
        with profile_block("position_sizing"):
            if self.mock_mode:
                await asyncio.sleep(0.008)  # ~8ms mock
            else:
                pass

        return {"phase": "position_sizing", "status": "complete"}

    async def profile_risk_checks(self) -> Dict[str, Any]:
        """Profile risk check phase."""
        with profile_block("risk_checks"):
            if self.mock_mode:
                await asyncio.sleep(0.004)  # ~4ms mock
            else:
                pass

        return {"phase": "risk_checks", "status": "complete"}

    async def profile_jupiter_quote(self) -> Dict[str, Any]:
        """Profile Jupiter quote phase."""
        with profile_block("jupiter_quote"):
            if self.mock_mode:
                # Simulate variable network latency
                await asyncio.sleep(0.12 + (time.time() % 0.05))  # 120-170ms mock
            else:
                pass

        return {"phase": "jupiter_quote", "status": "complete"}

    async def profile_execution(self) -> Dict[str, Any]:
        """Profile trade execution phase."""
        with profile_block("execution"):
            if self.mock_mode:
                await asyncio.sleep(0.08)  # ~80ms mock
            else:
                pass

        return {"phase": "execution", "status": "complete"}

    async def run_full_profile(self, iterations: int = 5) -> Dict[str, Any]:
        """
        Run complete trading flow profile.

        Args:
            iterations: Number of iterations to average

        Returns:
            Profiling results
        """
        reset_profiler()

        print(f"Running {iterations} profiling iterations...")

        for i in range(iterations):
            with profile_block("full_trade"):
                await self.profile_signal_detection()
                await self.profile_position_sizing()
                await self.profile_risk_checks()
                await self.profile_jupiter_quote()
                await self.profile_execution()

            print(f"  Iteration {i + 1}/{iterations} complete")

        self.results = get_profiler_results()

        # Compute averages
        for name, data in self.results.items():
            data["avg_duration_ms"] = data["duration_ms"] / data["call_count"]

        return self.results


def generate_html_report(
    results: Dict[str, Any],
    baselines: Dict[str, Dict[str, Any]],
    output_path: str
) -> str:
    """
    Generate an HTML performance report.

    Args:
        results: Profiling results
        baselines: Performance baselines
        output_path: Path to write HTML report

    Returns:
        Path to generated report
    """
    # Build hierarchical structure
    phases = []
    for name, data in sorted(results.items()):
        avg_ms = data.get("avg_duration_ms", data["duration_ms"])
        baseline = baselines.get(name, {}).get("target_ms")

        status = "ok"
        if baseline:
            if avg_ms > baseline * 1.1:
                status = "slow"
            elif avg_ms < baseline * 0.9:
                status = "fast"

        phases.append({
            "name": name,
            "avg_ms": round(avg_ms, 2),
            "total_ms": round(data["duration_ms"], 2),
            "calls": data["call_count"],
            "memory_mb": round(data.get("memory_mb", 0), 2),
            "baseline_ms": baseline,
            "status": status,
            "depth": name.count(".")
        })

    # Calculate total and bottleneck
    total_time = sum(p["avg_ms"] for p in phases if p["depth"] == 0)
    bottleneck = max(phases, key=lambda p: p["avg_ms"] if p["depth"] == 0 else 0)

    # Generate HTML
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Trade Execution Profiling Report</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, sans-serif; margin: 20px; background: #1a1a2e; color: #eee; }}
        h1 {{ color: #00d4ff; }}
        .report {{ background: #16213e; padding: 20px; border-radius: 8px; max-width: 900px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #333; }}
        th {{ background: #0f3460; color: #00d4ff; }}
        tr:hover {{ background: #1f4068; }}
        .ok {{ color: #00ff88; }}
        .slow {{ color: #ff6b6b; font-weight: bold; }}
        .fast {{ color: #4ecdc4; }}
        .indent-1 {{ padding-left: 30px; }}
        .indent-2 {{ padding-left: 60px; }}
        .summary {{ background: #0f3460; padding: 15px; border-radius: 4px; margin-bottom: 20px; }}
        .bottleneck {{ color: #ff6b6b; font-weight: bold; }}
        .timestamp {{ color: #888; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="report">
        <h1>Trade Execution Profiling Report</h1>
        <p class="timestamp">Generated: {datetime.now().isoformat()}</p>

        <div class="summary">
            <h3>Summary</h3>
            <p>Total Trade Time: <strong>{total_time:.2f}ms</strong></p>
            <p class="bottleneck">Bottleneck: {bottleneck['name']} ({bottleneck['avg_ms']:.2f}ms, {(bottleneck['avg_ms']/total_time*100):.0f}% of total)</p>
        </div>

        <table>
            <thead>
                <tr>
                    <th>Phase</th>
                    <th>Time (ms)</th>
                    <th>Memory (MB)</th>
                    <th>Calls</th>
                    <th>Baseline</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
"""

    for phase in phases:
        indent_class = f"indent-{phase['depth']}" if phase['depth'] > 0 else ""
        name_display = phase['name'].split('.')[-1] if phase['depth'] > 0 else phase['name']
        prefix = "|- " if phase['depth'] > 0 else ""

        baseline_str = f"{phase['baseline_ms']}ms" if phase['baseline_ms'] else "-"

        html += f"""                <tr>
                    <td class="{indent_class}">{prefix}{name_display}</td>
                    <td>{phase['avg_ms']:.2f}</td>
                    <td>{phase['memory_mb']:.2f}</td>
                    <td>{phase['calls']}</td>
                    <td>{baseline_str}</td>
                    <td class="{phase['status']}">{phase['status'].upper()}</td>
                </tr>
"""

    html += """            </tbody>
        </table>

        <h3>Recommendations</h3>
        <ul>
"""

    # Add recommendations based on results
    for phase in phases:
        if phase['status'] == 'slow' and phase['baseline_ms']:
            diff = phase['avg_ms'] - phase['baseline_ms']
            html += f"            <li><strong>{phase['name']}</strong>: {diff:.1f}ms over baseline. Consider optimization.</li>\n"

    if bottleneck['name'] == 'jupiter_quote':
        html += "            <li>Jupiter quote is the bottleneck - this is an external API call. Consider caching or parallel fetching.</li>\n"

    html += """        </ul>
    </div>
</body>
</html>"""

    # Write report
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)

    return output_path


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Profile trading flow execution")
    parser.add_argument("--iterations", "-n", type=int, default=5, help="Number of iterations")
    parser.add_argument("--html", action="store_true", help="Generate HTML report")
    parser.add_argument("--output", "-o", type=str, default="reports/trading_flow_profile.html", help="Output path for HTML report")
    parser.add_argument("--json", action="store_true", help="Output JSON results")
    parser.add_argument("--baselines", type=str, help="Path to baselines config")
    parser.add_argument("--real", action="store_true", help="Use real implementations (not mock)")

    args = parser.parse_args()

    # Load baselines
    baselines = DEFAULT_BASELINES.copy()
    if args.baselines:
        try:
            with open(args.baselines) as f:
                baselines.update(json.load(f))
        except Exception as e:
            print(f"Warning: Could not load baselines from {args.baselines}: {e}")

    # Run profiling
    profiler = TradingFlowProfiler(mock_mode=not args.real)
    results = await profiler.run_full_profile(iterations=args.iterations)

    # Output results
    print("\n" + "=" * 70)
    print(export_results_table())
    print("=" * 70)

    # Check for regressions
    actual_stats = {
        name: {"avg_ms": data["duration_ms"] / data["call_count"]}
        for name, data in results.items()
    }
    regression_report = generate_regression_report(baselines, actual_stats)

    if regression_report["has_regressions"]:
        print("\nWARNING: Performance regressions detected!")
        for op, data in regression_report["regressions"].items():
            print(f"  - {op}: {data['actual_ms']:.1f}ms vs {data['target_ms']:.1f}ms baseline (+{data['diff_pct']:.0f}%)")
    else:
        print("\nNo performance regressions detected.")

    # Generate outputs
    if args.json:
        print("\nJSON Results:")
        print(export_results_json())

    if args.html:
        report_path = generate_html_report(results, baselines, args.output)
        print(f"\nHTML report written to: {report_path}")

    return 0 if not regression_report["has_regressions"] else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
