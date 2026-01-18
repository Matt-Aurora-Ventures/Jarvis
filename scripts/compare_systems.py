#!/usr/bin/env python3
"""
Compare Dexter ReAct Agent vs Existing Sentiment Pipeline

Runs both systems on the same token set and generates a comparison matrix.
Shows agreement/disagreement between systems.

Usage:
    python scripts/compare_systems.py --tokens SOL,BTC,ETH,JUP,BONK
    python scripts/compare_systems.py --all --html
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.dexter.agent import DexterAgent, DecisionType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class SystemDecision:
    """Decision from a single system."""
    system: str
    decision: str
    confidence: float
    sentiment_score: float
    position_size_recommendation: str = "N/A"
    risk_level: str = "MEDIUM"
    rationale: str = ""


@dataclass
class ComparisonResult:
    """Comparison result for a single token."""
    symbol: str
    timestamp: str
    dexter: SystemDecision
    sentiment_pipeline: SystemDecision
    agreement: bool
    confidence_diff: float
    sentiment_diff: float
    recommendation: str = ""


@dataclass
class ComparisonSummary:
    """Summary of all comparisons."""
    total_tokens: int = 0
    agreements: int = 0
    disagreements: int = 0
    agreement_rate: float = 0.0
    avg_confidence_diff: float = 0.0
    avg_sentiment_diff: float = 0.0
    dexter_buy_count: int = 0
    dexter_hold_count: int = 0
    dexter_sell_count: int = 0
    pipeline_buy_count: int = 0
    pipeline_hold_count: int = 0
    pipeline_sell_count: int = 0
    timestamp: str = ""


class MockGrokClient:
    """Mock Grok client for comparison testing."""

    RESPONSES = {
        "SOL": "SENTIMENT_SCORE: 82\nCONFIDENCE: 85\nRECOMMENDATION: BUY\nStrong bullish signal",
        "BTC": "SENTIMENT_SCORE: 58\nCONFIDENCE: 55\nRECOMMENDATION: HOLD\nUncertain market",
        "ETH": "SENTIMENT_SCORE: 75\nCONFIDENCE: 78\nRECOMMENDATION: BUY\nGood momentum",
        "JUP": "SENTIMENT_SCORE: 70\nCONFIDENCE: 72\nRECOMMENDATION: BUY\nPositive sentiment",
        "BONK": "SENTIMENT_SCORE: 62\nCONFIDENCE: 58\nRECOMMENDATION: HOLD\nConsolidating",
        "WIF": "SENTIMENT_SCORE: 78\nCONFIDENCE: 70\nRECOMMENDATION: BUY\nMeme momentum",
        "PYTH": "SENTIMENT_SCORE: 65\nCONFIDENCE: 62\nRECOMMENDATION: HOLD\nNeeds confirmation",
        "ORCA": "SENTIMENT_SCORE: 55\nCONFIDENCE: 50\nRECOMMENDATION: HOLD\nNeutral",
        "RAY": "SENTIMENT_SCORE: 68\nCONFIDENCE: 65\nRECOMMENDATION: HOLD\nWaiting for breakout",
        "RENDER": "SENTIMENT_SCORE: 72\nCONFIDENCE: 74\nRECOMMENDATION: BUY\nAI narrative strong",
    }

    DEFAULT = "SENTIMENT_SCORE: 50\nCONFIDENCE: 50\nRECOMMENDATION: HOLD\nNo clear signal"

    async def analyze_sentiment(self, symbol: str, prompt: str) -> str:
        await asyncio.sleep(0.01)
        return self.RESPONSES.get(symbol.upper(), self.DEFAULT)


class MockSentimentAggregator:
    """Mock sentiment aggregator representing existing pipeline."""

    SCORES = {
        "SOL": 78.0,
        "BTC": 55.0,
        "ETH": 70.0,
        "JUP": 65.0,
        "BONK": 58.0,
        "WIF": 72.0,
        "PYTH": 60.0,
        "ORCA": 52.0,
        "RAY": 62.0,
        "RENDER": 68.0,
    }

    def get_sentiment_score(self, symbol: str) -> float:
        return self.SCORES.get(symbol.upper(), 50.0)

    def get_sentiment_leaders(self, count: int = 10) -> List[tuple]:
        sorted_items = sorted(self.SCORES.items(), key=lambda x: x[1], reverse=True)
        return sorted_items[:count]


class SystemComparator:
    """Compare Dexter vs Sentiment Pipeline decisions."""

    def __init__(self, output_dir: str = "data/dexter/comparisons"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.grok = MockGrokClient()
        self.sentiment_agg = MockSentimentAggregator()

        self.results: List[ComparisonResult] = []
        self.timestamp = datetime.now(timezone.utc).isoformat()

    async def compare_token(self, symbol: str) -> ComparisonResult:
        """
        Compare both systems on a single token.

        Args:
            symbol: Token symbol to analyze

        Returns:
            ComparisonResult with both decisions
        """
        symbol = symbol.upper()
        logger.info(f"Comparing systems for {symbol}...")

        # Run Dexter
        dexter_agent = DexterAgent(
            grok_client=self.grok,
            sentiment_aggregator=self.sentiment_agg
        )
        dexter_result = await dexter_agent.analyze_trading_opportunity(symbol)

        dexter_decision = SystemDecision(
            system="Dexter ReAct",
            decision=dexter_result.decision.value,
            confidence=dexter_result.confidence,
            sentiment_score=dexter_result.grok_sentiment_score,
            position_size_recommendation=self._get_position_size(dexter_result.confidence),
            risk_level=self._get_risk_level(dexter_result.confidence),
            rationale=dexter_result.rationale[:100] if dexter_result.rationale else ""
        )

        # Run Sentiment Pipeline
        pipeline_score = self.sentiment_agg.get_sentiment_score(symbol)
        pipeline_decision_str = self._score_to_decision(pipeline_score)
        pipeline_confidence = self._score_to_confidence(pipeline_score)

        pipeline_decision = SystemDecision(
            system="Sentiment Pipeline",
            decision=pipeline_decision_str,
            confidence=pipeline_confidence,
            sentiment_score=pipeline_score,
            position_size_recommendation=self._get_position_size(pipeline_confidence),
            risk_level=self._get_risk_level(pipeline_confidence),
            rationale=f"Aggregated sentiment score: {pipeline_score:.1f}/100"
        )

        # Compare
        agreement = self._decisions_agree(
            dexter_decision.decision,
            pipeline_decision.decision
        )
        confidence_diff = abs(dexter_decision.confidence - pipeline_decision.confidence)
        sentiment_diff = abs(dexter_decision.sentiment_score - pipeline_decision.sentiment_score)

        result = ComparisonResult(
            symbol=symbol,
            timestamp=self.timestamp,
            dexter=dexter_decision,
            sentiment_pipeline=pipeline_decision,
            agreement=agreement,
            confidence_diff=confidence_diff,
            sentiment_diff=sentiment_diff,
            recommendation=self._generate_recommendation(dexter_decision, pipeline_decision)
        )

        self.results.append(result)
        return result

    async def compare_all(self, symbols: List[str]) -> List[ComparisonResult]:
        """
        Compare both systems on multiple tokens.

        Args:
            symbols: List of token symbols

        Returns:
            List of ComparisonResult objects
        """
        results = []
        for symbol in symbols:
            result = await self.compare_token(symbol)
            results.append(result)
        return results

    def get_summary(self) -> ComparisonSummary:
        """Generate summary statistics."""
        summary = ComparisonSummary()
        summary.timestamp = self.timestamp
        summary.total_tokens = len(self.results)

        if not self.results:
            return summary

        # Count agreements
        summary.agreements = sum(1 for r in self.results if r.agreement)
        summary.disagreements = summary.total_tokens - summary.agreements
        summary.agreement_rate = (summary.agreements / summary.total_tokens) * 100

        # Average differences
        summary.avg_confidence_diff = sum(r.confidence_diff for r in self.results) / len(self.results)
        summary.avg_sentiment_diff = sum(r.sentiment_diff for r in self.results) / len(self.results)

        # Count by decision type
        for r in self.results:
            if "BUY" in r.dexter.decision:
                summary.dexter_buy_count += 1
            elif "HOLD" in r.dexter.decision:
                summary.dexter_hold_count += 1
            elif "SELL" in r.dexter.decision:
                summary.dexter_sell_count += 1

            if "BUY" in r.sentiment_pipeline.decision:
                summary.pipeline_buy_count += 1
            elif "HOLD" in r.sentiment_pipeline.decision:
                summary.pipeline_hold_count += 1
            elif "SELL" in r.sentiment_pipeline.decision:
                summary.pipeline_sell_count += 1

        return summary

    def print_comparison_matrix(self):
        """Print comparison matrix to console."""
        print("\n" + "=" * 80)
        print("             DEXTER vs SENTIMENT PIPELINE COMPARISON")
        print("=" * 80)
        print(f"\n{'Symbol':<10} {'Dexter':<15} {'Pipeline':<15} {'Agree?':<10} {'Conf Diff':<12}")
        print("-" * 80)

        for r in self.results:
            agree_str = "YES" if r.agreement else "NO"
            dexter_str = f"{r.dexter.decision} ({r.dexter.confidence:.0f}%)"
            pipeline_str = f"{r.sentiment_pipeline.decision} ({r.sentiment_pipeline.confidence:.0f}%)"

            print(f"{r.symbol:<10} {dexter_str:<15} {pipeline_str:<15} {agree_str:<10} {r.confidence_diff:>6.1f}%")

        print("-" * 80)

        summary = self.get_summary()
        print(f"\nSUMMARY:")
        print(f"  Total Tokens: {summary.total_tokens}")
        print(f"  Agreement Rate: {summary.agreement_rate:.1f}%")
        print(f"  Avg Confidence Diff: {summary.avg_confidence_diff:.1f}%")
        print(f"  Avg Sentiment Diff: {summary.avg_sentiment_diff:.1f}")
        print(f"\nDEXTER: {summary.dexter_buy_count} BUY, {summary.dexter_hold_count} HOLD, {summary.dexter_sell_count} SELL")
        print(f"PIPELINE: {summary.pipeline_buy_count} BUY, {summary.pipeline_hold_count} HOLD, {summary.pipeline_sell_count} SELL")
        print("=" * 80)

    def save_results(self) -> str:
        """Save results to JSON file."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filepath = self.output_dir / f"comparison_{timestamp}.json"

        data = {
            "timestamp": self.timestamp,
            "summary": asdict(self.get_summary()),
            "results": [
                {
                    "symbol": r.symbol,
                    "dexter": asdict(r.dexter),
                    "sentiment_pipeline": asdict(r.sentiment_pipeline),
                    "agreement": r.agreement,
                    "confidence_diff": r.confidence_diff,
                    "sentiment_diff": r.sentiment_diff,
                    "recommendation": r.recommendation
                }
                for r in self.results
            ]
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Results saved to {filepath}")
        return str(filepath)

    def generate_html_report(self) -> str:
        """Generate HTML comparison report."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filepath = self.output_dir / f"comparison_{timestamp}.html"
        summary = self.get_summary()

        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Dexter vs Sentiment Pipeline Comparison</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 20px; background: #1a1a2e; color: #eee; }}
        h1 {{ color: #00d4ff; border-bottom: 2px solid #00d4ff; padding-bottom: 10px; }}
        h2 {{ color: #00ff88; }}
        .summary {{ background: #16213e; border-radius: 8px; padding: 20px; margin: 20px 0; }}
        .metric {{ display: inline-block; margin: 10px 20px 10px 0; }}
        .metric-label {{ color: #888; font-size: 12px; }}
        .metric-value {{ font-size: 24px; font-weight: bold; }}
        .agree {{ color: #00ff88; }}
        .disagree {{ color: #ff4444; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #333; }}
        th {{ background: #0f3460; color: #00d4ff; }}
        tr:hover {{ background: #1f4068; }}
        .buy {{ color: #00ff88; font-weight: bold; }}
        .sell {{ color: #ff4444; font-weight: bold; }}
        .hold {{ color: #ffaa00; font-weight: bold; }}
        .recommendation {{ background: #0f3460; padding: 10px; margin: 5px 0; border-radius: 4px; }}
    </style>
</head>
<body>
    <h1>Dexter vs Sentiment Pipeline Comparison</h1>
    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

    <div class="summary">
        <h2>Summary</h2>
        <div class="metric">
            <div class="metric-label">Total Tokens</div>
            <div class="metric-value">{summary.total_tokens}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Agreement Rate</div>
            <div class="metric-value {'agree' if summary.agreement_rate > 70 else 'disagree'}">{summary.agreement_rate:.1f}%</div>
        </div>
        <div class="metric">
            <div class="metric-label">Avg Conf Diff</div>
            <div class="metric-value">{summary.avg_confidence_diff:.1f}%</div>
        </div>
        <div class="metric">
            <div class="metric-label">Avg Sentiment Diff</div>
            <div class="metric-value">{summary.avg_sentiment_diff:.1f}</div>
        </div>
    </div>

    <div class="summary">
        <h2>Decision Distribution</h2>
        <table style="width: 50%;">
            <tr>
                <th></th>
                <th>BUY</th>
                <th>HOLD</th>
                <th>SELL</th>
            </tr>
            <tr>
                <td>Dexter</td>
                <td class="buy">{summary.dexter_buy_count}</td>
                <td class="hold">{summary.dexter_hold_count}</td>
                <td class="sell">{summary.dexter_sell_count}</td>
            </tr>
            <tr>
                <td>Pipeline</td>
                <td class="buy">{summary.pipeline_buy_count}</td>
                <td class="hold">{summary.pipeline_hold_count}</td>
                <td class="sell">{summary.pipeline_sell_count}</td>
            </tr>
        </table>
    </div>

    <h2>Detailed Comparison</h2>
    <table>
        <tr>
            <th>Symbol</th>
            <th>Dexter Decision</th>
            <th>Pipeline Decision</th>
            <th>Agreement</th>
            <th>Confidence Diff</th>
            <th>Recommendation</th>
        </tr>
"""

        for r in self.results:
            dexter_class = 'buy' if 'BUY' in r.dexter.decision else ('sell' if 'SELL' in r.dexter.decision else 'hold')
            pipeline_class = 'buy' if 'BUY' in r.sentiment_pipeline.decision else ('sell' if 'SELL' in r.sentiment_pipeline.decision else 'hold')
            agree_class = 'agree' if r.agreement else 'disagree'

            html += f"""
        <tr>
            <td><strong>{r.symbol}</strong></td>
            <td class="{dexter_class}">{r.dexter.decision} ({r.dexter.confidence:.0f}%)</td>
            <td class="{pipeline_class}">{r.sentiment_pipeline.decision} ({r.sentiment_pipeline.confidence:.0f}%)</td>
            <td class="{agree_class}">{'YES' if r.agreement else 'NO'}</td>
            <td>{r.confidence_diff:.1f}%</td>
            <td>{r.recommendation}</td>
        </tr>
"""

        html += """
    </table>
</body>
</html>
"""

        with open(filepath, 'w') as f:
            f.write(html)

        logger.info(f"HTML report saved to {filepath}")
        return str(filepath)

    def _score_to_decision(self, score: float) -> str:
        """Convert sentiment score to decision."""
        if score >= 70:
            return "TRADE_BUY"
        elif score <= 30:
            return "TRADE_SELL"
        else:
            return "HOLD"

    def _score_to_confidence(self, score: float) -> float:
        """Convert sentiment score to confidence."""
        # Higher deviation from 50 = higher confidence
        deviation = abs(score - 50)
        return min(50 + deviation, 95)

    def _decisions_agree(self, d1: str, d2: str) -> bool:
        """Check if two decisions agree."""
        d1_type = "BUY" if "BUY" in d1 else ("SELL" if "SELL" in d1 else "HOLD")
        d2_type = "BUY" if "BUY" in d2 else ("SELL" if "SELL" in d2 else "HOLD")
        return d1_type == d2_type

    def _get_position_size(self, confidence: float) -> str:
        """Get position size recommendation based on confidence."""
        if confidence >= 85:
            return "5% (Large)"
        elif confidence >= 70:
            return "3% (Medium)"
        elif confidence >= 55:
            return "1% (Small)"
        else:
            return "0% (Skip)"

    def _get_risk_level(self, confidence: float) -> str:
        """Get risk level based on confidence."""
        if confidence >= 85:
            return "LOW"
        elif confidence >= 70:
            return "MEDIUM"
        elif confidence >= 55:
            return "HIGH"
        else:
            return "VERY HIGH"

    def _generate_recommendation(
        self,
        dexter: SystemDecision,
        pipeline: SystemDecision
    ) -> str:
        """Generate recommendation based on both systems."""
        if self._decisions_agree(dexter.decision, pipeline.decision):
            if "BUY" in dexter.decision:
                return "Strong BUY - Both systems agree"
            elif "SELL" in dexter.decision:
                return "Strong SELL - Both systems agree"
            else:
                return "Wait - Both systems neutral"
        else:
            if dexter.confidence > pipeline.confidence + 10:
                return f"Follow Dexter ({dexter.decision}) - Higher confidence"
            elif pipeline.confidence > dexter.confidence + 10:
                return f"Follow Pipeline ({pipeline.decision}) - Higher confidence"
            else:
                return "Conflicting signals - Wait for clarity"


async def main():
    parser = argparse.ArgumentParser(
        description="Compare Dexter vs Sentiment Pipeline decisions"
    )
    parser.add_argument(
        "--tokens",
        default="SOL,BTC,ETH,JUP,BONK",
        help="Comma-separated list of tokens (default: SOL,BTC,ETH,JUP,BONK)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Analyze all available tokens"
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Generate HTML report"
    )

    args = parser.parse_args()

    comparator = SystemComparator()

    if args.all:
        symbols = ["SOL", "BTC", "ETH", "JUP", "BONK", "WIF", "PYTH", "ORCA", "RAY", "RENDER"]
    else:
        symbols = [s.strip().upper() for s in args.tokens.split(",")]

    print(f"\nComparing systems for {len(symbols)} tokens: {', '.join(symbols)}")

    await comparator.compare_all(symbols)
    comparator.print_comparison_matrix()

    # Save results
    json_path = comparator.save_results()
    print(f"\nResults saved to: {json_path}")

    if args.html:
        html_path = comparator.generate_html_report()
        print(f"HTML report saved to: {html_path}")


if __name__ == "__main__":
    asyncio.run(main())
