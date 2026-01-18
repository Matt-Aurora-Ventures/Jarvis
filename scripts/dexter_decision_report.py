#!/usr/bin/env python3
"""
Dexter Decision Report Generator

Generates comprehensive HTML report summarizing:
- Total decisions evaluated
- Decision breakdown (BUY %, HOLD %, SELL %)
- Accuracy vs price movement (5min, 1h, 4h)
- Average confidence scores
- Cost efficiency analysis
- Comparison to existing system

Usage:
    python scripts/dexter_decision_report.py --paper-trades data/dexter/paper_trades/session_trades.jsonl
    python scripts/dexter_decision_report.py --costs data/dexter/costs/costs.jsonl
    python scripts/dexter_decision_report.py --generate-sample
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class DecisionMetrics:
    """Aggregate decision metrics."""
    total_decisions: int = 0
    buy_count: int = 0
    sell_count: int = 0
    hold_count: int = 0
    error_count: int = 0
    buy_pct: float = 0.0
    sell_pct: float = 0.0
    hold_pct: float = 0.0


@dataclass
class AccuracyMetrics:
    """Accuracy metrics at different timeframes."""
    accuracy_5min: float = 0.0
    accuracy_1h: float = 0.0
    accuracy_4h: float = 0.0
    total_trades_evaluated: int = 0
    winning_trades: int = 0
    losing_trades: int = 0


@dataclass
class ConfidenceMetrics:
    """Confidence score metrics."""
    avg_confidence: float = 0.0
    avg_grok_score: float = 0.0
    high_confidence_count: int = 0  # >= 85%
    medium_confidence_count: int = 0  # 70-84%
    low_confidence_count: int = 0  # < 70%


@dataclass
class CostMetrics:
    """Cost efficiency metrics."""
    total_cost: float = 0.0
    avg_cost_per_decision: float = 0.0
    cost_target: float = 0.20
    within_budget_pct: float = 0.0
    p50_cost: float = 0.0
    p95_cost: float = 0.0


@dataclass
class ComparisonMetrics:
    """System comparison metrics."""
    agreement_rate: float = 0.0
    dexter_better_count: int = 0
    pipeline_better_count: int = 0
    equal_count: int = 0


class DecisionReportGenerator:
    """Generate comprehensive Dexter decision report."""

    def __init__(self, output_dir: str = "reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Data storage
        self.paper_trades: List[Dict] = []
        self.cost_entries: List[Dict] = []
        self.comparison_results: List[Dict] = []

        # Calculated metrics
        self.decision_metrics = DecisionMetrics()
        self.accuracy_metrics = AccuracyMetrics()
        self.confidence_metrics = ConfidenceMetrics()
        self.cost_metrics = CostMetrics()
        self.comparison_metrics = ComparisonMetrics()

    def load_paper_trades(self, filepath: str) -> int:
        """Load paper trades from JSONL file."""
        path = Path(filepath)
        if not path.exists():
            logger.warning(f"Paper trades file not found: {filepath}")
            return 0

        with open(path) as f:
            for line in f:
                if line.strip():
                    self.paper_trades.append(json.loads(line))

        logger.info(f"Loaded {len(self.paper_trades)} paper trades")
        return len(self.paper_trades)

    def load_cost_data(self, filepath: str) -> int:
        """Load cost data from JSONL file."""
        path = Path(filepath)
        if not path.exists():
            logger.warning(f"Cost data file not found: {filepath}")
            return 0

        with open(path) as f:
            for line in f:
                if line.strip():
                    self.cost_entries.append(json.loads(line))

        logger.info(f"Loaded {len(self.cost_entries)} cost entries")
        return len(self.cost_entries)

    def load_comparison_results(self, filepath: str) -> int:
        """Load comparison results from JSON file."""
        path = Path(filepath)
        if not path.exists():
            logger.warning(f"Comparison file not found: {filepath}")
            return 0

        with open(path) as f:
            data = json.load(f)
            self.comparison_results = data.get("results", [])

        logger.info(f"Loaded {len(self.comparison_results)} comparison results")
        return len(self.comparison_results)

    def calculate_metrics(self):
        """Calculate all metrics from loaded data."""
        self._calculate_decision_metrics()
        self._calculate_accuracy_metrics()
        self._calculate_confidence_metrics()
        self._calculate_cost_metrics()
        self._calculate_comparison_metrics()

    def _calculate_decision_metrics(self):
        """Calculate decision breakdown metrics."""
        if not self.paper_trades:
            return

        metrics = self.decision_metrics
        metrics.total_decisions = len(self.paper_trades)

        for trade in self.paper_trades:
            decision = trade.get("decision", "").upper()
            if "BUY" in decision:
                metrics.buy_count += 1
            elif "SELL" in decision:
                metrics.sell_count += 1
            elif "HOLD" in decision:
                metrics.hold_count += 1
            else:
                metrics.error_count += 1

        total = metrics.total_decisions
        if total > 0:
            metrics.buy_pct = (metrics.buy_count / total) * 100
            metrics.sell_pct = (metrics.sell_count / total) * 100
            metrics.hold_pct = (metrics.hold_count / total) * 100

    def _calculate_accuracy_metrics(self):
        """Calculate accuracy vs price movement."""
        if not self.paper_trades:
            return

        metrics = self.accuracy_metrics

        # Filter trades with accuracy data
        trades_5min = [t for t in self.paper_trades if t.get("accurate_5min") is not None]
        trades_1h = [t for t in self.paper_trades if t.get("accurate_1h") is not None]
        trades_4h = [t for t in self.paper_trades if t.get("accurate_4h") is not None]

        if trades_5min:
            metrics.accuracy_5min = (sum(1 for t in trades_5min if t["accurate_5min"]) / len(trades_5min)) * 100

        if trades_1h:
            metrics.accuracy_1h = (sum(1 for t in trades_1h if t["accurate_1h"]) / len(trades_1h)) * 100

        if trades_4h:
            metrics.accuracy_4h = (sum(1 for t in trades_4h if t["accurate_4h"]) / len(trades_4h)) * 100

        # Count winning/losing trades
        actionable = [t for t in self.paper_trades if t.get("decision", "").upper() not in ["HOLD", ""]]
        metrics.total_trades_evaluated = len(actionable)

        for t in actionable:
            pnl = t.get("pnl_pct_1h") or t.get("pnl_pct_5min") or 0
            if pnl > 0:
                metrics.winning_trades += 1
            elif pnl < 0:
                metrics.losing_trades += 1

    def _calculate_confidence_metrics(self):
        """Calculate confidence score metrics."""
        if not self.paper_trades:
            return

        metrics = self.confidence_metrics

        confidences = [t.get("confidence", 0) for t in self.paper_trades]
        grok_scores = [t.get("grok_sentiment_score", 0) for t in self.paper_trades]

        if confidences:
            metrics.avg_confidence = sum(confidences) / len(confidences)

        if grok_scores:
            metrics.avg_grok_score = sum(grok_scores) / len(grok_scores)

        for conf in confidences:
            if conf >= 85:
                metrics.high_confidence_count += 1
            elif conf >= 70:
                metrics.medium_confidence_count += 1
            else:
                metrics.low_confidence_count += 1

    def _calculate_cost_metrics(self):
        """Calculate cost efficiency metrics."""
        if not self.cost_entries:
            return

        metrics = self.cost_metrics

        costs = [e.get("cost_usd", 0) for e in self.cost_entries]

        if costs:
            metrics.total_cost = sum(costs)
            metrics.avg_cost_per_decision = metrics.total_cost / len(costs)

            sorted_costs = sorted(costs)
            n = len(sorted_costs)
            metrics.p50_cost = sorted_costs[int(n * 0.5)] if n > 0 else 0
            metrics.p95_cost = sorted_costs[int(n * 0.95) - 1] if n > 1 else sorted_costs[-1]

            within_budget = sum(1 for c in costs if c <= metrics.cost_target)
            metrics.within_budget_pct = (within_budget / len(costs)) * 100

    def _calculate_comparison_metrics(self):
        """Calculate system comparison metrics."""
        if not self.comparison_results:
            return

        metrics = self.comparison_metrics

        agreements = sum(1 for r in self.comparison_results if r.get("agreement"))
        metrics.agreement_rate = (agreements / len(self.comparison_results)) * 100

        # Would need actual P&L data to determine which system is better
        # For now, use confidence as a proxy
        for r in self.comparison_results:
            dexter_conf = r.get("dexter", {}).get("confidence", 0)
            pipeline_conf = r.get("sentiment_pipeline", {}).get("confidence", 0)

            if dexter_conf > pipeline_conf + 5:
                metrics.dexter_better_count += 1
            elif pipeline_conf > dexter_conf + 5:
                metrics.pipeline_better_count += 1
            else:
                metrics.equal_count += 1

    def generate_html_report(self) -> str:
        """Generate comprehensive HTML report."""
        self.calculate_metrics()

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filepath = self.output_dir / f"dexter_decision_report_{timestamp}.html"

        dm = self.decision_metrics
        am = self.accuracy_metrics
        cm = self.confidence_metrics
        cost = self.cost_metrics
        comp = self.comparison_metrics

        # Determine overall status
        overall_status = "READY" if am.accuracy_1h >= 60 and cost.avg_cost_per_decision <= 0.20 else "NEEDS REVIEW"
        status_color = "#00ff88" if overall_status == "READY" else "#ffaa00"

        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Dexter Decision Report - {timestamp}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #eee;
            min-height: 100vh;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{
            color: #00d4ff;
            border-bottom: 3px solid #00d4ff;
            padding-bottom: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        h2 {{ color: #00ff88; margin-top: 30px; }}
        .status-badge {{
            font-size: 18px;
            padding: 8px 20px;
            border-radius: 20px;
            background: {status_color}20;
            border: 2px solid {status_color};
            color: {status_color};
        }}
        .card {{
            background: #16213e;
            border-radius: 12px;
            padding: 25px;
            margin: 20px 0;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }}
        .metric {{
            background: #0f3460;
            border-radius: 8px;
            padding: 15px;
            text-align: center;
        }}
        .metric-label {{ color: #888; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; }}
        .metric-value {{ font-size: 32px; font-weight: bold; margin: 10px 0; }}
        .metric-sub {{ color: #666; font-size: 11px; }}
        .green {{ color: #00ff88; }}
        .red {{ color: #ff4444; }}
        .yellow {{ color: #ffaa00; }}
        .blue {{ color: #00d4ff; }}
        .progress-bar {{
            background: #0a0a1a;
            border-radius: 10px;
            height: 20px;
            overflow: hidden;
            margin: 10px 0;
        }}
        .progress-fill {{
            height: 100%;
            border-radius: 10px;
            transition: width 0.5s ease;
        }}
        .progress-buy {{ background: linear-gradient(90deg, #00ff88, #00cc66); }}
        .progress-hold {{ background: linear-gradient(90deg, #ffaa00, #ff8800); }}
        .progress-sell {{ background: linear-gradient(90deg, #ff4444, #cc3333); }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #333; }}
        th {{ background: #0f3460; color: #00d4ff; }}
        .footer {{ text-align: center; margin-top: 40px; color: #666; font-size: 12px; }}
        .recommendation {{
            background: #0f3460;
            border-left: 4px solid #00d4ff;
            padding: 15px 20px;
            margin: 20px 0;
            border-radius: 0 8px 8px 0;
        }}
        .chart-placeholder {{
            background: #0a0a1a;
            border-radius: 8px;
            height: 200px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #666;
            margin: 20px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>
            Dexter Decision Report
            <span class="status-badge">{overall_status}</span>
        </h1>
        <p style="color: #888;">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>

        <!-- Decision Breakdown -->
        <div class="card">
            <h2>Decision Breakdown</h2>
            <div class="metrics-grid">
                <div class="metric">
                    <div class="metric-label">Total Decisions</div>
                    <div class="metric-value blue">{dm.total_decisions}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">BUY Signals</div>
                    <div class="metric-value green">{dm.buy_count}</div>
                    <div class="metric-sub">{dm.buy_pct:.1f}% of total</div>
                </div>
                <div class="metric">
                    <div class="metric-label">HOLD Signals</div>
                    <div class="metric-value yellow">{dm.hold_count}</div>
                    <div class="metric-sub">{dm.hold_pct:.1f}% of total</div>
                </div>
                <div class="metric">
                    <div class="metric-label">SELL Signals</div>
                    <div class="metric-value red">{dm.sell_count}</div>
                    <div class="metric-sub">{dm.sell_pct:.1f}% of total</div>
                </div>
            </div>

            <h3 style="color: #888; margin-top: 20px;">Decision Distribution</h3>
            <div class="progress-bar" style="height: 30px;">
                <div class="progress-fill progress-buy" style="width: {dm.buy_pct}%; display: inline-block;"></div>
                <div class="progress-fill progress-hold" style="width: {dm.hold_pct}%; display: inline-block;"></div>
                <div class="progress-fill progress-sell" style="width: {dm.sell_pct}%; display: inline-block;"></div>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 12px; color: #888;">
                <span>BUY {dm.buy_pct:.1f}%</span>
                <span>HOLD {dm.hold_pct:.1f}%</span>
                <span>SELL {dm.sell_pct:.1f}%</span>
            </div>
        </div>

        <!-- Accuracy vs Price Movement -->
        <div class="card">
            <h2>Accuracy vs Price Movement</h2>
            <div class="metrics-grid">
                <div class="metric">
                    <div class="metric-label">5-Minute Accuracy</div>
                    <div class="metric-value {'green' if am.accuracy_5min >= 60 else 'yellow' if am.accuracy_5min >= 50 else 'red'}">{am.accuracy_5min:.1f}%</div>
                </div>
                <div class="metric">
                    <div class="metric-label">1-Hour Accuracy</div>
                    <div class="metric-value {'green' if am.accuracy_1h >= 60 else 'yellow' if am.accuracy_1h >= 50 else 'red'}">{am.accuracy_1h:.1f}%</div>
                </div>
                <div class="metric">
                    <div class="metric-label">4-Hour Accuracy</div>
                    <div class="metric-value {'green' if am.accuracy_4h >= 60 else 'yellow' if am.accuracy_4h >= 50 else 'red'}">{am.accuracy_4h:.1f}%</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Win/Loss</div>
                    <div class="metric-value">{am.winning_trades}/{am.losing_trades}</div>
                    <div class="metric-sub">{am.total_trades_evaluated} trades evaluated</div>
                </div>
            </div>

            <div class="recommendation">
                <strong>Target:</strong> 60%+ accuracy for production use.
                {'Current accuracy meets target.' if am.accuracy_1h >= 60 else 'Needs improvement before production.'}
            </div>
        </div>

        <!-- Confidence Scores -->
        <div class="card">
            <h2>Confidence Analysis</h2>
            <div class="metrics-grid">
                <div class="metric">
                    <div class="metric-label">Avg Confidence</div>
                    <div class="metric-value blue">{cm.avg_confidence:.1f}%</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Avg Grok Score</div>
                    <div class="metric-value blue">{cm.avg_grok_score:.1f}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">High Conf (85%+)</div>
                    <div class="metric-value green">{cm.high_confidence_count}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Low Conf (&lt;70%)</div>
                    <div class="metric-value yellow">{cm.low_confidence_count}</div>
                </div>
            </div>

            <h3 style="color: #888; margin-top: 20px;">Confidence Distribution</h3>
            <table>
                <tr>
                    <th>Confidence Level</th>
                    <th>Count</th>
                    <th>Action</th>
                </tr>
                <tr>
                    <td>High (85%+)</td>
                    <td class="green">{cm.high_confidence_count}</td>
                    <td>Full position size</td>
                </tr>
                <tr>
                    <td>Medium (70-84%)</td>
                    <td class="yellow">{cm.medium_confidence_count}</td>
                    <td>Reduced position size</td>
                </tr>
                <tr>
                    <td>Low (&lt;70%)</td>
                    <td class="red">{cm.low_confidence_count}</td>
                    <td>Skip or minimal position</td>
                </tr>
            </table>
        </div>

        <!-- Cost Efficiency -->
        <div class="card">
            <h2>Cost Efficiency</h2>
            <div class="metrics-grid">
                <div class="metric">
                    <div class="metric-label">Total Cost</div>
                    <div class="metric-value">${cost.total_cost:.2f}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Avg Cost/Decision</div>
                    <div class="metric-value {'green' if cost.avg_cost_per_decision <= 0.20 else 'red'}">${cost.avg_cost_per_decision:.4f}</div>
                    <div class="metric-sub">Target: &lt;$0.20</div>
                </div>
                <div class="metric">
                    <div class="metric-label">P50 Cost</div>
                    <div class="metric-value">${cost.p50_cost:.4f}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">P95 Cost</div>
                    <div class="metric-value">${cost.p95_cost:.4f}</div>
                </div>
            </div>

            <div class="recommendation">
                <strong>Budget Compliance:</strong> {cost.within_budget_pct:.1f}% of decisions within $0.20 target.
                {'Cost efficiency is excellent.' if cost.within_budget_pct >= 90 else 'Review high-cost decisions.'}
            </div>
        </div>

        <!-- System Comparison -->
        <div class="card">
            <h2>Comparison: Dexter vs Sentiment Pipeline</h2>
            <div class="metrics-grid">
                <div class="metric">
                    <div class="metric-label">Agreement Rate</div>
                    <div class="metric-value blue">{comp.agreement_rate:.1f}%</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Dexter Better</div>
                    <div class="metric-value green">{comp.dexter_better_count}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Pipeline Better</div>
                    <div class="metric-value yellow">{comp.pipeline_better_count}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Equal</div>
                    <div class="metric-value">{comp.equal_count}</div>
                </div>
            </div>

            <div class="recommendation">
                <strong>Insight:</strong>
                {'High agreement suggests Dexter aligns well with existing system.' if comp.agreement_rate >= 70 else 'Low agreement - Dexter provides different perspective.'}
                {' Dexter shows higher confidence on average.' if comp.dexter_better_count > comp.pipeline_better_count else ''}
            </div>
        </div>

        <!-- Production Readiness -->
        <div class="card">
            <h2>Production Readiness Checklist</h2>
            <table>
                <tr>
                    <th>Criteria</th>
                    <th>Status</th>
                    <th>Value</th>
                    <th>Target</th>
                </tr>
                <tr>
                    <td>1-Hour Accuracy</td>
                    <td>{'<span class="green">PASS</span>' if am.accuracy_1h >= 60 else '<span class="red">FAIL</span>'}</td>
                    <td>{am.accuracy_1h:.1f}%</td>
                    <td>&ge;60%</td>
                </tr>
                <tr>
                    <td>Cost per Decision</td>
                    <td>{'<span class="green">PASS</span>' if cost.avg_cost_per_decision <= 0.20 else '<span class="red">FAIL</span>'}</td>
                    <td>${cost.avg_cost_per_decision:.4f}</td>
                    <td>&le;$0.20</td>
                </tr>
                <tr>
                    <td>Decision Variety</td>
                    <td>{'<span class="green">PASS</span>' if dm.buy_pct < 80 else '<span class="red">FAIL</span>'}</td>
                    <td>{dm.buy_pct:.1f}% BUY</td>
                    <td>&lt;80% BUY</td>
                </tr>
                <tr>
                    <td>Confidence Calibration</td>
                    <td>{'<span class="green">PASS</span>' if cm.avg_confidence >= 60 else '<span class="yellow">WARN</span>'}</td>
                    <td>{cm.avg_confidence:.1f}%</td>
                    <td>&ge;60%</td>
                </tr>
                <tr>
                    <td>Total Decisions Tested</td>
                    <td>{'<span class="green">PASS</span>' if dm.total_decisions >= 50 else '<span class="yellow">WARN</span>'}</td>
                    <td>{dm.total_decisions}</td>
                    <td>&ge;50</td>
                </tr>
            </table>
        </div>

        <div class="footer">
            <p>Dexter ReAct Agent - Decision Quality Report</p>
            <p>Generated by Jarvis LifeOS | {datetime.now().year}</p>
        </div>
    </div>
</body>
</html>
"""

        with open(filepath, 'w') as f:
            f.write(html)

        logger.info(f"Report generated: {filepath}")
        return str(filepath)

    def generate_sample_data(self, count: int = 50):
        """Generate sample paper trades for testing."""
        import random

        symbols = ["SOL", "BTC", "ETH", "JUP", "BONK", "WIF", "PYTH", "ORCA", "RAY", "RENDER"]
        decisions = ["BUY", "SELL", "HOLD"]

        for i in range(count):
            symbol = random.choice(symbols)
            decision = random.choices(decisions, weights=[0.35, 0.15, 0.50])[0]
            confidence = random.gauss(70, 15)
            confidence = max(30, min(95, confidence))

            grok_score = random.gauss(65, 12)
            grok_score = max(20, min(95, grok_score))

            entry_price = random.uniform(1, 200)

            # Simulate price movement
            pnl_5min = random.gauss(0, 2)
            pnl_1h = random.gauss(pnl_5min * 0.5, 3)
            pnl_4h = random.gauss(pnl_1h * 0.5, 5)

            trade = {
                "trade_id": f"sample_{i:04d}",
                "symbol": symbol,
                "decision": decision,
                "confidence": round(confidence, 1),
                "grok_sentiment_score": round(grok_score, 1),
                "entry_price": round(entry_price, 4),
                "pnl_pct_5min": round(pnl_5min, 2),
                "pnl_pct_1h": round(pnl_1h, 2),
                "pnl_pct_4h": round(pnl_4h, 2),
                "accurate_5min": (pnl_5min > 0) if decision == "BUY" else (pnl_5min < 0) if decision == "SELL" else True,
                "accurate_1h": (pnl_1h > 0) if decision == "BUY" else (pnl_1h < 0) if decision == "SELL" else True,
                "accurate_4h": (pnl_4h > 0) if decision == "BUY" else (pnl_4h < 0) if decision == "SELL" else True,
                "cost_usd": round(random.uniform(0.01, 0.08), 4),
            }

            self.paper_trades.append(trade)

            # Also add cost entry
            self.cost_entries.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "symbol": symbol,
                "decision": decision,
                "cost_usd": trade["cost_usd"],
                "input_tokens": random.randint(500, 2000),
                "output_tokens": random.randint(200, 800),
            })

        logger.info(f"Generated {count} sample trades")


def main():
    parser = argparse.ArgumentParser(
        description="Generate Dexter Decision Report"
    )
    parser.add_argument(
        "--paper-trades",
        help="Path to paper trades JSONL file"
    )
    parser.add_argument(
        "--costs",
        help="Path to cost data JSONL file"
    )
    parser.add_argument(
        "--comparison",
        help="Path to comparison results JSON file"
    )
    parser.add_argument(
        "--generate-sample",
        action="store_true",
        help="Generate sample data for testing"
    )
    parser.add_argument(
        "--sample-count",
        type=int,
        default=50,
        help="Number of sample trades to generate (default: 50)"
    )
    parser.add_argument(
        "--output-dir",
        default="reports",
        help="Output directory for reports"
    )

    args = parser.parse_args()

    generator = DecisionReportGenerator(output_dir=args.output_dir)

    if args.generate_sample:
        generator.generate_sample_data(args.sample_count)
    else:
        if args.paper_trades:
            generator.load_paper_trades(args.paper_trades)
        if args.costs:
            generator.load_cost_data(args.costs)
        if args.comparison:
            generator.load_comparison_results(args.comparison)

    if not generator.paper_trades and not args.generate_sample:
        logger.warning("No data loaded. Use --generate-sample or provide data files.")
        print("\nUsage examples:")
        print("  python scripts/dexter_decision_report.py --generate-sample")
        print("  python scripts/dexter_decision_report.py --paper-trades data/dexter/paper_trades/trades.jsonl")
        return

    report_path = generator.generate_html_report()
    print(f"\nReport generated: {report_path}")


if __name__ == "__main__":
    main()
