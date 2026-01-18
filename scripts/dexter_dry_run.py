#!/usr/bin/env python3
"""
Dexter ReAct Agent Dry Run Test Script

Execute with:
    python scripts/dexter_dry_run.py --symbol SOL --iterations 5
    python scripts/dexter_dry_run.py --symbol BTC --debug --html
    python scripts/dexter_dry_run.py --symbol ETH --cost-limit 0.25

Options:
    --symbol TOKEN      Which token to analyze (default: SOL)
    --iterations N      Number of iterations through ReAct loop (default: 5)
    --debug             Enable debug logging
    --html              Generate HTML report
    --cost-limit USD    Max cost per decision (default: $0.50)
    --compare           Compare with existing sentiment pipeline
    --multi TOKENS      Analyze multiple tokens (comma-separated)

Output:
    - Console: Formatted dry run results
    - Scratchpad: data/dexter/scratchpad_dryrun_{timestamp}.jsonl
    - Costs: data/dexter/costs_dryrun.jsonl
    - HTML Report: reports/dexter_dryrun_{timestamp}.html (if --html)
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.dexter.agent import DexterAgent, DecisionType, ReActDecision
from core.dexter.config import DexterConfig
from core.dexter.scratchpad import Scratchpad
from core.dexter.context import ContextManager


# Configure logging
def setup_logging(debug: bool = False):
    """Configure logging for dry run."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    # Reduce noise from other loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


logger = logging.getLogger(__name__)


@dataclass
class IterationResult:
    """Result of a single ReAct iteration."""
    iteration: int
    reasoning: str
    tool_called: str
    tool_args: Dict[str, Any]
    tool_result: str
    elapsed_ms: float
    cost_usd: float


@dataclass
class DryRunResult:
    """Complete dry run result."""
    symbol: str
    decision: str
    confidence: float
    rationale: str
    iterations: List[IterationResult]
    total_elapsed_ms: float
    total_cost_usd: float
    grok_sentiment_score: float
    within_budget: bool
    reasoning_quality: str
    decision_fitness: str
    tp_price: Optional[float] = None
    sl_price: Optional[float] = None
    position_size_pct: Optional[float] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MockGrokClient:
    """Mock Grok client for dry run testing."""

    # Simulated responses for different tokens
    RESPONSES = {
        "SOL": {
            "initial": "SENTIMENT_SCORE: 78\nCONFIDENCE: 75\nInitial analysis shows bullish momentum for SOL with strong volume support.",
            "research": "Market data shows SOL at $142.50 with 24h volume of $2.5B. Liquidity is strong at $500M. Key support at $135, resistance at $155.",
            "sentiment": "Grok sentiment: 75/100 bullish. Twitter: 60/100. News: 55/100. Overall social sentiment is positive with increasing engagement.",
            "final": "SENTIMENT_SCORE: 82\nCONFIDENCE: 85\nRECOMMENDATION: BUY\n\nStrong BUY signal. Bullish sentiment (67.5 avg), golden cross forming, whale accumulation detected. Entry: $142, TP: $213 (50%), SL: $121 (15%)."
        },
        "BTC": {
            "initial": "SENTIMENT_SCORE: 65\nCONFIDENCE: 60\nBTC showing mixed signals. Need more data on institutional flows.",
            "research": "BTC at $95,200 with 24h volume of $28B. Strong support at $90K, resistance at $100K. Fear & Greed: 55 (neutral).",
            "sentiment": "Grok sentiment: 62/100. Twitter: 58/100. News: 65/100. Cautiously optimistic but awaiting clear breakout.",
            "final": "SENTIMENT_SCORE: 68\nCONFIDENCE: 65\nRECOMMENDATION: HOLD\n\nHOLD recommendation. Market is consolidating. Wait for clear breakout above $100K before entry."
        },
        "ETH": {
            "initial": "SENTIMENT_SCORE: 72\nCONFIDENCE: 70\nETH showing positive momentum with L2 adoption growth.",
            "research": "ETH at $3,450 with 24h volume of $12B. Strong staking demand. Gas fees elevated but sustainable.",
            "sentiment": "Grok sentiment: 70/100. Twitter: 65/100. News: 72/100. Positive sentiment around upcoming updates.",
            "final": "SENTIMENT_SCORE: 75\nCONFIDENCE: 78\nRECOMMENDATION: BUY\n\nModerate BUY signal. Good entry point below $3,500. TP: $4,500 (30%), SL: $3,100 (10%)."
        },
        "WIF": {
            "initial": "SENTIMENT_SCORE: 85\nCONFIDENCE: 70\nWIF showing strong meme coin momentum with viral potential.",
            "research": "WIF at $2.45 with explosive 24h volume. High volatility. Whale activity detected.",
            "sentiment": "Grok sentiment: 82/100. Twitter: 90/100 (trending). News: 40/100 (limited coverage). Social momentum is peak.",
            "final": "SENTIMENT_SCORE: 88\nCONFIDENCE: 72\nRECOMMENDATION: BUY\n\nSpeculative BUY. High risk/reward. TP: $3.70 (50%), SL: $1.80 (25%). Position size: small due to volatility."
        },
        "BONK": {
            "initial": "SENTIMENT_SCORE: 70\nCONFIDENCE: 65\nBONK stable but showing fatigue after recent pump.",
            "research": "BONK at $0.000023 with moderate volume. Some profit-taking detected.",
            "sentiment": "Grok sentiment: 65/100. Twitter: 68/100. News: 35/100. Sentiment cooling but still positive.",
            "final": "SENTIMENT_SCORE: 67\nCONFIDENCE: 62\nRECOMMENDATION: HOLD\n\nHOLD. Wait for pullback to $0.000020 for better entry."
        }
    }

    # Cost simulation per call (rough estimate)
    COST_PER_CALL = 0.015

    def __init__(self):
        self.call_count = 0
        self.total_cost = 0.0
        self.call_history = []

    async def analyze_sentiment(self, symbol: str, prompt: str) -> str:
        """Simulate Grok analysis with realistic response."""
        self.call_count += 1
        self.total_cost += self.COST_PER_CALL
        self.call_history.append({
            "symbol": symbol,
            "prompt": prompt[:100],
            "cost": self.COST_PER_CALL,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        # Simulate API latency
        await asyncio.sleep(0.05)  # 50ms simulated latency

        # Get response based on context
        responses = self.RESPONSES.get(symbol.upper(), self.RESPONSES["SOL"])

        # Route based on prompt content - order matters!
        # "Final decision" takes priority over "analyze"
        if "final decision" in prompt.lower() or "decision:" in prompt.lower():
            return responses["final"]
        elif "research" in prompt.lower() or "market data" in prompt.lower():
            return responses["research"]
        elif "sentiment" in prompt.lower() and "sources" in prompt.lower():
            return responses["sentiment"]
        elif "analyze" in prompt.lower() or "initial" in prompt.lower():
            return responses["initial"]
        else:
            return responses["final"]


class MockSentimentAggregator:
    """Mock sentiment aggregator for comparison."""

    SCORES = {
        "SOL": 75.0,
        "BTC": 58.0,
        "ETH": 68.0,
        "WIF": 80.0,
        "BONK": 62.0,
        "JUP": 70.0,
        "PYTH": 65.0,
    }

    def get_sentiment_score(self, symbol: str) -> float:
        """Return sentiment score for symbol."""
        return self.SCORES.get(symbol.upper(), 50.0)

    def get_sentiment_leaders(self, count: int = 10):
        """Return top sentiment leaders."""
        sorted_items = sorted(self.SCORES.items(), key=lambda x: x[1], reverse=True)
        return sorted_items[:count]


class DexterDryRun:
    """Dexter ReAct Agent Dry Run Controller."""

    def __init__(
        self,
        cost_limit: float = 0.50,
        max_iterations: int = 5,
        debug: bool = False
    ):
        self.cost_limit = cost_limit
        self.max_iterations = max_iterations
        self.debug = debug

        # Initialize mocks
        self.grok = MockGrokClient()
        self.sentiment = MockSentimentAggregator()

        # Results storage
        self.results: List[DryRunResult] = []
        self.costs: List[Dict] = []

        # Paths
        self.data_dir = ROOT / "data" / "dexter"
        self.reports_dir = ROOT / "reports"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    async def run_dry_run(self, symbol: str) -> DryRunResult:
        """Execute a single dry run for a symbol."""
        print(f"\n{'='*55}")
        print(f"Dexter ReAct Dry Run Test")
        print(f"{'='*55}\n")

        # Print configuration
        print("Configuration:")
        print(f"|-- Symbol: {symbol}")
        print(f"|-- Max Iterations: {self.max_iterations}")
        print(f"|-- Cost Limit: ${self.cost_limit:.2f}")
        print(f"|-- Feature Flags: DEXTER_ENABLED=true")
        print(f"`-- Require Confirmation: false (dry run mode)\n")

        # Initialize agent
        agent = DexterAgent(
            grok_client=self.grok,
            sentiment_aggregator=self.sentiment
        )

        # Initialize scratchpad
        session_id = f"dryrun_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        scratchpad = Scratchpad(session_id, scratchpad_dir=str(self.data_dir / "scratchpad"))
        scratchpad.start_session(f"Dry run analysis for {symbol}", symbol=symbol)

        print(f"ReAct Loop Execution:")
        print(f"{'-'*55}\n")

        # Track iterations
        iterations: List[IterationResult] = []
        start_time = time.time()

        # Run the analysis
        result = await agent.analyze_trading_opportunity(symbol)

        # Process scratchpad entries into iterations
        iter_num = 0
        for entry in agent.scratchpad:
            if entry["type"] == "reasoning":
                iter_num += 1
                iter_result = IterationResult(
                    iteration=iter_num,
                    reasoning=entry.get("thought", ""),
                    tool_called="reasoning",
                    tool_args={},
                    tool_result="",
                    elapsed_ms=50,  # Simulated
                    cost_usd=0.0
                )
                iterations.append(iter_result)
                self._print_iteration(iter_result)

            elif entry["type"] == "action":
                if iterations:
                    iterations[-1].tool_called = entry.get("tool", "unknown")
                    iterations[-1].tool_args = entry.get("args", {})
                    iterations[-1].tool_result = entry.get("result", "")[:100]
                    iterations[-1].cost_usd = self.grok.COST_PER_CALL
                    self._print_iteration(iterations[-1])

        total_elapsed = (time.time() - start_time) * 1000

        # Calculate decision metrics
        within_budget = self.grok.total_cost <= self.cost_limit
        reasoning_quality = self._assess_reasoning_quality(result.confidence)
        decision_fitness = self._assess_decision_fitness(result)

        # Create dry run result
        dry_result = DryRunResult(
            symbol=symbol,
            decision=result.decision.value,
            confidence=result.confidence,
            rationale=result.rationale,
            iterations=iterations,
            total_elapsed_ms=total_elapsed,
            total_cost_usd=self.grok.total_cost,
            grok_sentiment_score=result.grok_sentiment_score,
            within_budget=within_budget,
            reasoning_quality=reasoning_quality,
            decision_fitness=decision_fitness,
            position_size_pct=5.0 if result.decision == DecisionType.TRADE_BUY else None
        )

        # Extract TP/SL from rationale if present
        if "TP:" in result.rationale:
            dry_result.tp_price = self._extract_price(result.rationale, "TP:")
        if "SL:" in result.rationale:
            dry_result.sl_price = self._extract_price(result.rationale, "SL:")

        # Print final decision
        self._print_final_decision(dry_result)

        # Save scratchpad
        for entry in agent.scratchpad:
            if entry["type"] == "reasoning":
                scratchpad.log_reasoning(entry.get("thought", ""), iteration=iter_num)
            elif entry["type"] == "action":
                scratchpad.log_action(entry.get("tool", ""), entry.get("args", {}), entry.get("result", ""))
            elif entry["type"] == "decision":
                scratchpad.log_decision(
                    entry.get("action", ""),
                    entry.get("symbol", ""),
                    entry.get("rationale", ""),
                    result.confidence
                )
        scratchpad.save_to_disk()

        # Save cost data
        self._save_cost_data(dry_result)

        self.results.append(dry_result)
        return dry_result

    def _print_iteration(self, iter_result: IterationResult):
        """Print a single iteration result."""
        print(f"Iteration {iter_result.iteration}:")
        print(f"|-- Reasoning: \"{iter_result.reasoning[:60]}{'...' if len(iter_result.reasoning) > 60 else ''}\"")
        print(f"|-- Tool Called: {iter_result.tool_called}")
        if iter_result.tool_args:
            print(f"|-- Tool Args: {json.dumps(iter_result.tool_args)[:60]}")
        if iter_result.tool_result:
            print(f"|-- Tool Result: \"{iter_result.tool_result[:50]}{'...' if len(iter_result.tool_result) > 50 else ''}\"")
        print(f"`-- Elapsed: {iter_result.elapsed_ms:.0f}ms, Cost: ${iter_result.cost_usd:.3f}\n")

    def _print_final_decision(self, result: DryRunResult):
        """Print final decision summary."""
        print(f"\nFinal Decision:")
        print(f"{'='*55}")
        print(f"Action: {result.decision}")
        print(f"Symbol: {result.symbol}")
        if result.position_size_pct:
            print(f"Position Size: {result.position_size_pct}%")
        print(f"Confidence: {result.confidence:.0f}/100")
        print(f"Rationale: \"{result.rationale[:100]}{'...' if len(result.rationale) > 100 else ''}\"")
        if result.tp_price:
            print(f"TP: ${result.tp_price:.2f}")
        if result.sl_price:
            print(f"SL: ${result.sl_price:.2f}")

        print(f"\nExecution Summary:")
        print(f"{'-'*55}")
        print(f"Total Iterations: {len(result.iterations)}")
        print(f"Total Elapsed: {result.total_elapsed_ms:.0f}ms")
        print(f"Total Cost: ${result.total_cost_usd:.3f}")
        print(f"Average Cost/Iteration: ${result.total_cost_usd/max(len(result.iterations), 1):.4f}")
        print(f"Within Budget: {'YES' if result.within_budget else 'NO'} (${self.cost_limit:.2f} limit)")
        print(f"Reasoning Quality: {result.reasoning_quality}")
        print(f"Decision Fitness: {result.decision_fitness}")

    def _assess_reasoning_quality(self, confidence: float) -> str:
        """Assess quality of reasoning based on confidence."""
        if confidence >= 85:
            return "HIGH (85%+ confidence)"
        elif confidence >= 70:
            return "MEDIUM (70-84% confidence)"
        elif confidence >= 50:
            return "LOW (50-69% confidence)"
        else:
            return "UNCERTAIN (<50% confidence)"

    def _assess_decision_fitness(self, result: ReActDecision) -> str:
        """Assess fitness of the decision."""
        if result.decision == DecisionType.ERROR:
            return "ERROR"
        elif result.decision == DecisionType.HOLD:
            return "HOLD - Wait for better signal"
        elif result.confidence >= 85:
            return f"STRONG {result.decision.value.replace('TRADE_', '')}"
        elif result.confidence >= 70:
            return f"MODERATE {result.decision.value.replace('TRADE_', '')}"
        else:
            return f"WEAK {result.decision.value.replace('TRADE_', '')}"

    def _extract_price(self, text: str, prefix: str) -> Optional[float]:
        """Extract price from text."""
        import re
        pattern = rf'{prefix}\s*\$?([\d,]+\.?\d*)'
        match = re.search(pattern, text)
        if match:
            return float(match.group(1).replace(',', ''))
        return None

    def _save_cost_data(self, result: DryRunResult):
        """Save cost data to JSONL file."""
        cost_file = self.data_dir / "costs_dryrun.jsonl"
        cost_entry = {
            "timestamp": result.timestamp,
            "symbol": result.symbol,
            "total_cost_usd": result.total_cost_usd,
            "iterations": len(result.iterations),
            "decision": result.decision,
            "confidence": result.confidence,
            "within_budget": result.within_budget
        }
        self.costs.append(cost_entry)

        with open(cost_file, "a") as f:
            f.write(json.dumps(cost_entry) + "\n")

    async def run_multi_dry_run(self, symbols: List[str]) -> List[DryRunResult]:
        """Run dry runs on multiple symbols."""
        results = []
        for symbol in symbols:
            # Reset grok costs between runs
            self.grok = MockGrokClient()
            result = await self.run_dry_run(symbol)
            results.append(result)
        return results

    async def run_comparison(self, symbol: str) -> Dict:
        """Compare Dexter decision with existing sentiment pipeline."""
        print(f"\n{'='*55}")
        print(f"Dexter vs Sentiment Pipeline Comparison")
        print(f"{'='*55}\n")

        # Run Dexter
        dexter_result = await self.run_dry_run(symbol)

        # Get sentiment pipeline score
        sentiment_score = self.sentiment.get_sentiment_score(symbol)

        # Compare
        comparison = {
            "symbol": symbol,
            "dexter": {
                "decision": dexter_result.decision,
                "confidence": dexter_result.confidence,
                "grok_score": dexter_result.grok_sentiment_score,
                "cost": dexter_result.total_cost_usd
            },
            "sentiment_pipeline": {
                "score": sentiment_score,
                "decision": "BUY" if sentiment_score >= 70 else ("SELL" if sentiment_score <= 30 else "HOLD")
            },
            "alignment": abs(dexter_result.grok_sentiment_score - sentiment_score) < 15,
            "dexter_override": dexter_result.grok_sentiment_score != sentiment_score
        }

        print(f"\nComparison Results for {symbol}:")
        print(f"{'-'*55}")
        print(f"Dexter Decision: {comparison['dexter']['decision']} (Confidence: {comparison['dexter']['confidence']:.0f}%)")
        print(f"Sentiment Pipeline: {comparison['sentiment_pipeline']['decision']} (Score: {comparison['sentiment_pipeline']['score']:.0f})")
        print(f"Alignment: {'YES' if comparison['alignment'] else 'NO (>15 point difference)'}")

        return comparison

    def generate_html_report(self, results: List[DryRunResult]) -> str:
        """Generate HTML report for dry run results."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = self.reports_dir / f"dexter_dryrun_{timestamp}.html"

        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Dexter ReAct Dry Run Report - {timestamp}</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 20px; background: #1a1a2e; color: #eee; }}
        h1 {{ color: #00d4ff; border-bottom: 2px solid #00d4ff; padding-bottom: 10px; }}
        h2 {{ color: #00ff88; }}
        .result-card {{ background: #16213e; border-radius: 8px; padding: 20px; margin: 20px 0; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }}
        .buy {{ border-left: 4px solid #00ff88; }}
        .sell {{ border-left: 4px solid #ff4444; }}
        .hold {{ border-left: 4px solid #ffaa00; }}
        .error {{ border-left: 4px solid #ff0000; }}
        .metric {{ display: inline-block; margin: 10px 20px 10px 0; }}
        .metric-label {{ color: #888; font-size: 12px; }}
        .metric-value {{ font-size: 24px; font-weight: bold; }}
        .green {{ color: #00ff88; }}
        .red {{ color: #ff4444; }}
        .yellow {{ color: #ffaa00; }}
        table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #333; }}
        th {{ background: #0f3460; color: #00d4ff; }}
        tr:hover {{ background: #1f4068; }}
        .iteration {{ background: #0f3460; border-radius: 4px; padding: 10px; margin: 5px 0; }}
        .summary {{ background: #0f3460; border-radius: 8px; padding: 20px; margin: 20px 0; }}
    </style>
</head>
<body>
    <h1>Dexter ReAct Agent Dry Run Report</h1>
    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

    <div class="summary">
        <h2>Summary</h2>
        <div class="metric">
            <div class="metric-label">Total Runs</div>
            <div class="metric-value">{len(results)}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Avg Cost</div>
            <div class="metric-value">${sum(r.total_cost_usd for r in results)/max(len(results),1):.3f}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Avg Confidence</div>
            <div class="metric-value">{sum(r.confidence for r in results)/max(len(results),1):.0f}%</div>
        </div>
        <div class="metric">
            <div class="metric-label">BUY Signals</div>
            <div class="metric-value green">{len([r for r in results if 'BUY' in r.decision])}</div>
        </div>
        <div class="metric">
            <div class="metric-label">HOLD Signals</div>
            <div class="metric-value yellow">{len([r for r in results if 'HOLD' in r.decision])}</div>
        </div>
    </div>
"""

        for result in results:
            decision_class = 'buy' if 'BUY' in result.decision else ('sell' if 'SELL' in result.decision else ('hold' if 'HOLD' in result.decision else 'error'))
            html += f"""
    <div class="result-card {decision_class}">
        <h2>{result.symbol}</h2>
        <div class="metric">
            <div class="metric-label">Decision</div>
            <div class="metric-value {'green' if 'BUY' in result.decision else ('red' if 'SELL' in result.decision else 'yellow')}">{result.decision}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Confidence</div>
            <div class="metric-value">{result.confidence:.0f}%</div>
        </div>
        <div class="metric">
            <div class="metric-label">Grok Score</div>
            <div class="metric-value">{result.grok_sentiment_score:.0f}/100</div>
        </div>
        <div class="metric">
            <div class="metric-label">Cost</div>
            <div class="metric-value">${result.total_cost_usd:.3f}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Elapsed</div>
            <div class="metric-value">{result.total_elapsed_ms:.0f}ms</div>
        </div>

        <h3>Reasoning Quality: {result.reasoning_quality}</h3>
        <h3>Decision Fitness: {result.decision_fitness}</h3>

        <p><strong>Rationale:</strong> {result.rationale}</p>

        <h3>Iterations</h3>
        <table>
            <tr>
                <th>#</th>
                <th>Reasoning</th>
                <th>Tool</th>
                <th>Cost</th>
            </tr>
"""
            for iter_r in result.iterations:
                html += f"""
            <tr>
                <td>{iter_r.iteration}</td>
                <td>{iter_r.reasoning[:50]}...</td>
                <td>{iter_r.tool_called}</td>
                <td>${iter_r.cost_usd:.3f}</td>
            </tr>
"""
            html += """
        </table>
    </div>
"""

        html += """
</body>
</html>
"""

        with open(report_path, "w") as f:
            f.write(html)

        print(f"\nHTML Report saved to: {report_path}")
        return str(report_path)

    def print_cost_analysis(self):
        """Print cost analysis summary."""
        if not self.costs:
            print("\nNo cost data available.")
            return

        costs = [c["total_cost_usd"] for c in self.costs]
        sorted_costs = sorted(costs)
        n = len(sorted_costs)

        p50_idx = int(n * 0.50) - 1
        p95_idx = int(n * 0.95) - 1
        p99_idx = int(n * 0.99) - 1

        print(f"\n{'='*55}")
        print("Cost Analysis")
        print(f"{'='*55}")
        print(f"Total Decisions: {n}")
        print(f"P50 Cost: ${sorted_costs[max(p50_idx, 0)]:.3f}")
        print(f"P95 Cost: ${sorted_costs[max(p95_idx, 0)]:.3f}")
        print(f"P99 Cost: ${sorted_costs[max(p99_idx, 0)]:.3f}")
        print(f"Average Cost: ${sum(costs)/n:.3f}")
        print(f"Max Cost: ${max(costs):.3f}")
        print(f"Min Cost: ${min(costs):.3f}")


async def main():
    """Main entry point for dry run."""
    parser = argparse.ArgumentParser(
        description="Dexter ReAct Agent Dry Run Test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("--symbol", default="SOL", help="Token symbol to analyze (default: SOL)")
    parser.add_argument("--iterations", type=int, default=5, help="Max iterations (default: 5)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--html", action="store_true", help="Generate HTML report")
    parser.add_argument("--cost-limit", type=float, default=0.50, help="Max cost per decision (default: $0.50)")
    parser.add_argument("--compare", action="store_true", help="Compare with sentiment pipeline")
    parser.add_argument("--multi", help="Analyze multiple tokens (comma-separated)")

    args = parser.parse_args()

    setup_logging(args.debug)

    runner = DexterDryRun(
        cost_limit=args.cost_limit,
        max_iterations=args.iterations,
        debug=args.debug
    )

    try:
        if args.multi:
            symbols = [s.strip().upper() for s in args.multi.split(",")]
            results = await runner.run_multi_dry_run(symbols)
        elif args.compare:
            await runner.run_comparison(args.symbol.upper())
            results = runner.results
        else:
            result = await runner.run_dry_run(args.symbol.upper())
            results = [result]

        # Print cost analysis
        runner.print_cost_analysis()

        # Generate HTML report if requested
        if args.html:
            runner.generate_html_report(results)

        print(f"\n{'='*55}")
        print("Dry run completed successfully!")
        print(f"Scratchpad saved to: {runner.data_dir / 'scratchpad'}")
        print(f"Cost data saved to: {runner.data_dir / 'costs_dryrun.jsonl'}")
        print(f"{'='*55}")

    except KeyboardInterrupt:
        print("\n\nDry run interrupted by user.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Dry run failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
