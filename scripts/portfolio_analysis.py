#!/usr/bin/env python3
"""
Portfolio Analysis Dashboard

Displays portfolio metrics, allocation, correlation matrix, and efficient frontier.
Run standalone or import for programmatic access.

Prompts #293: Multi-Asset Support and Portfolio Optimization
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.portfolio import (
    CorrelationMatrix,
    PortfolioOptimizer,
    MultiAssetRiskCalculator,
    Rebalancer,
    SectorRotation,
    get_portfolio_tracker,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PortfolioAnalysisDashboard:
    """
    Portfolio Analysis Dashboard

    Provides comprehensive portfolio analytics including:
    - Current allocation breakdown
    - Correlation matrix heatmap
    - Efficient frontier
    - Risk metrics
    - Rebalancing recommendations
    - Sector analysis
    """

    def __init__(
        self,
        positions_file: Optional[str] = None,
        price_data_file: Optional[str] = None
    ):
        """
        Initialize dashboard.

        Args:
            positions_file: Path to positions JSON file
            price_data_file: Path to historical price data
        """
        self.positions_file = positions_file or str(PROJECT_ROOT / "bots/treasury/.positions.json")
        self.price_data_file = price_data_file

        # Initialize components
        self.correlation = CorrelationMatrix()
        self.optimizer = PortfolioOptimizer()
        self.risk_calc = MultiAssetRiskCalculator()
        self.rebalancer = Rebalancer()
        self.sector_rotation = SectorRotation()

        # Data storage
        self.positions: Dict[str, Any] = {}
        self.price_history: Dict[str, List[float]] = {}
        self.returns: Dict[str, List[float]] = {}

    def load_positions(self) -> Dict[str, Any]:
        """Load positions from treasury file."""
        try:
            if Path(self.positions_file).exists():
                with open(self.positions_file) as f:
                    data = json.load(f)

                self.positions = {}
                for pos in data:
                    token = pos.get('token_symbol', pos.get('id', 'UNKNOWN'))
                    self.positions[token] = {
                        'amount': pos.get('amount', 0),
                        'amount_usd': pos.get('amount_usd', 0),
                        'current_price': pos.get('current_price', pos.get('entry_price', 0)),
                        'entry_price': pos.get('entry_price', 0),
                        'value': pos.get('amount', 0) * pos.get('current_price', pos.get('entry_price', 0)),
                        'pnl_pct': pos.get('pnl_pct', 0),
                        'status': pos.get('status', 'OPEN')
                    }

                logger.info(f"Loaded {len(self.positions)} positions")
            else:
                logger.warning(f"Positions file not found: {self.positions_file}")
                self.positions = {}

        except Exception as e:
            logger.error(f"Failed to load positions: {e}")
            self.positions = {}

        return self.positions

    def load_price_history(self, source: str = "mock") -> Dict[str, List[float]]:
        """
        Load historical price data.

        Args:
            source: 'mock' for sample data, 'file' for file-based

        Returns:
            Dict mapping token to price history
        """
        if source == "mock":
            import numpy as np
            np.random.seed(42)

            # Generate mock price history for tokens
            tokens = list(self.positions.keys()) if self.positions else ['SOL', 'ETH', 'BTC']

            for token in tokens:
                base_price = self.positions.get(token, {}).get('current_price', 100)
                # Random walk
                returns = np.random.normal(0.001, 0.03, 100)
                prices = [base_price]
                for r in returns:
                    prices.append(prices[-1] * (1 + r))
                self.price_history[token] = prices

        elif source == "file" and self.price_data_file:
            try:
                with open(self.price_data_file) as f:
                    self.price_history = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load price history: {e}")

        # Calculate returns from prices
        for token, prices in self.price_history.items():
            if len(prices) > 1:
                self.returns[token] = [
                    (prices[i] - prices[i-1]) / prices[i-1]
                    for i in range(1, len(prices))
                ]

        return self.price_history

    def get_allocation_summary(self) -> Dict[str, Any]:
        """Get current allocation breakdown."""
        if not self.positions:
            return {'error': 'No positions loaded'}

        total_value = sum(p.get('value', 0) for p in self.positions.values())

        allocation = []
        for token, pos in self.positions.items():
            value = pos.get('value', 0)
            allocation.append({
                'token': token,
                'value': round(value, 2),
                'weight': round(value / total_value, 4) if total_value > 0 else 0,
                'weight_pct': round(value / total_value * 100, 2) if total_value > 0 else 0,
                'pnl_pct': round(pos.get('pnl_pct', 0), 2)
            })

        # Sort by value
        allocation.sort(key=lambda x: x['value'], reverse=True)

        return {
            'total_value': round(total_value, 2),
            'position_count': len(self.positions),
            'allocation': allocation,
            'top_3_concentration': sum(a['weight'] for a in allocation[:3]) if len(allocation) >= 3 else 1.0
        }

    def get_correlation_matrix(self) -> Dict[str, Any]:
        """Get correlation matrix heatmap data."""
        if not self.price_history:
            self.load_price_history()

        matrix = self.correlation.calculate(self.price_history)
        heatmap = self.correlation.get_heatmap_data()

        high_corr = self.correlation.get_high_correlation_pairs(0.7)
        low_corr = self.correlation.get_low_correlation_pairs(0.3)

        return {
            'matrix': matrix,
            'heatmap': heatmap,
            'high_correlation_pairs': high_corr[:5],
            'low_correlation_pairs': low_corr[:5],
            'warnings': [
                f"High correlation between {a} and {b}: {c:.2f}"
                for a, b, c in high_corr
            ]
        }

    def get_efficient_frontier(self, n_points: int = 10) -> Dict[str, Any]:
        """Calculate efficient frontier."""
        if not self.returns:
            self.load_price_history()

        frontier = self.optimizer.get_efficient_frontier(self.returns, n_points)

        # Find optimal (max Sharpe) portfolio
        optimal = max(frontier, key=lambda p: p['sharpe']) if frontier else None

        return {
            'frontier': frontier,
            'optimal_portfolio': optimal,
            'current_weights': self._get_current_weights(),
        }

    def _get_current_weights(self) -> Dict[str, float]:
        """Get current portfolio weights."""
        if not self.positions:
            return {}

        total_value = sum(p.get('value', 0) for p in self.positions.values())
        if total_value == 0:
            return {}

        return {
            token: pos.get('value', 0) / total_value
            for token, pos in self.positions.items()
        }

    def get_risk_metrics(self) -> Dict[str, Any]:
        """Calculate portfolio risk metrics."""
        if not self.returns:
            self.load_price_history()

        weights = self._get_current_weights()

        if not weights or not self.returns:
            return {'error': 'Insufficient data'}

        # Use first token as market proxy
        market_returns = list(self.returns.values())[0] if self.returns else None

        summary = self.risk_calc.get_risk_summary(
            self.returns,
            weights,
            market_returns,
            portfolio_value=sum(p.get('value', 0) for p in self.positions.values())
        )

        return summary

    def get_rebalancing_recommendations(
        self,
        target_weights: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """Get rebalancing recommendations."""
        current_weights = self._get_current_weights()

        if not current_weights:
            return {'error': 'No current positions'}

        # Default to equal weights if no target specified
        if target_weights is None:
            target_weights = self.optimizer.get_equal_weights(list(current_weights.keys()))

        portfolio_value = sum(p.get('value', 0) for p in self.positions.values())

        trades = self.rebalancer.calculate_rebalance_trades(
            current_weights,
            target_weights,
            portfolio_value
        )

        drift_report = self.rebalancer.calculate_drift_report(current_weights, target_weights)
        cost_estimate = self.rebalancer.estimate_rebalance_cost(trades)

        return {
            'trades': trades,
            'drift_report': drift_report,
            'cost_estimate': cost_estimate,
            'current_weights': current_weights,
            'target_weights': target_weights
        }

    def get_sector_analysis(self) -> Dict[str, Any]:
        """Get sector breakdown and recommendations."""
        if not self.positions:
            return {'error': 'No positions loaded'}

        # Convert positions to format expected by sector rotation
        positions_for_sector = {
            token: {'value': pos.get('value', 0)}
            for token, pos in self.positions.items()
        }

        sector_weights = self.sector_rotation.calculate_sector_weights(positions_for_sector)
        sector_report = self.sector_rotation.get_sector_report(positions_for_sector)

        # Mock sentiment for demo
        sentiment = {
            'DeFi': 0.6,
            'Infrastructure': 0.7,
            'Meme': 0.4,
            'Gaming': 0.5,
            'Layer2': 0.65,
        }

        recommendations = self.sector_rotation.get_recommendations(positions_for_sector, sentiment)

        return {
            'sector_weights': sector_weights,
            'report': sector_report,
            'recommendations': recommendations,
            'sentiment': sentiment
        }

    def generate_full_report(self) -> Dict[str, Any]:
        """Generate comprehensive portfolio analysis report."""
        self.load_positions()
        self.load_price_history()

        report = {
            'generated_at': datetime.now().isoformat(),
            'allocation': self.get_allocation_summary(),
            'risk_metrics': self.get_risk_metrics(),
            'correlation': self.get_correlation_matrix(),
            'efficient_frontier': self.get_efficient_frontier(),
            'rebalancing': self.get_rebalancing_recommendations(),
            'sector_analysis': self.get_sector_analysis(),
        }

        return report

    def print_dashboard(self):
        """Print formatted dashboard to console."""
        report = self.generate_full_report()

        print("\n" + "="*60)
        print("PORTFOLIO ANALYSIS DASHBOARD")
        print("="*60)
        print(f"Generated: {report['generated_at']}")

        # Allocation
        print("\n--- ALLOCATION ---")
        alloc = report['allocation']
        print(f"Total Value: ${alloc.get('total_value', 0):,.2f}")
        print(f"Positions: {alloc.get('position_count', 0)}")
        print(f"Top 3 Concentration: {alloc.get('top_3_concentration', 0)*100:.1f}%")
        print("\nTop Holdings:")
        for a in alloc.get('allocation', [])[:5]:
            print(f"  {a['token']:8s} ${a['value']:>10,.2f} ({a['weight_pct']:>5.1f}%)")

        # Risk Metrics
        print("\n--- RISK METRICS ---")
        risk = report['risk_metrics']
        if 'error' not in risk:
            print(f"Portfolio Volatility: {risk.get('volatility_pct', 0):.1f}%")
            print(f"VaR (95%): ${risk.get('var_95', 0):,.2f}")
            print(f"VaR (99%): ${risk.get('var_99', 0):,.2f}")
            print(f"Diversification Benefit: {risk.get('diversification_benefit_pct', 0):.1f}%")
            print(f"Max Drawdown: {risk.get('max_drawdown_pct', 0):.1f}%")
            print(f"Beta: {risk.get('beta', 0):.2f}")

        # Correlation Warnings
        print("\n--- CORRELATION WARNINGS ---")
        corr = report['correlation']
        warnings = corr.get('warnings', [])
        if warnings:
            for w in warnings[:3]:
                print(f"  ! {w}")
        else:
            print("  No high correlations detected")

        # Efficient Frontier
        print("\n--- OPTIMAL PORTFOLIO ---")
        frontier = report['efficient_frontier']
        optimal = frontier.get('optimal_portfolio')
        if optimal:
            print(f"Expected Return: {optimal['return']*100:.1f}%")
            print(f"Risk: {optimal['risk']*100:.1f}%")
            print(f"Sharpe Ratio: {optimal['sharpe']:.2f}")
            print("Weights:")
            for token, weight in optimal.get('weights', {}).items():
                print(f"  {token:8s}: {weight*100:.1f}%")

        # Rebalancing
        print("\n--- REBALANCING ---")
        rebal = report['rebalancing']
        if rebal.get('trades'):
            print("Recommended trades:")
            for t in rebal['trades'][:5]:
                action = t['action'].upper()
                print(f"  {action:4s} {t['asset']:8s} ${t['amount_usd']:>8,.2f}")
            cost = rebal.get('cost_estimate', {})
            print(f"Estimated cost: ${cost.get('total_fees', 0):.2f}")
        else:
            print("  No rebalancing needed")

        # Sector Analysis
        print("\n--- SECTOR ANALYSIS ---")
        sector = report['sector_analysis']
        sector_report = sector.get('report', {})
        print(f"Diversification Score: {sector_report.get('diversification_score', 0)}/100")
        print("\nSector Weights:")
        for s in sector_report.get('sectors', [])[:5]:
            status = s['status'].upper()[:3]
            print(f"  {s['sector']:15s} {s['current_weight']*100:>5.1f}% [{status}]")

        print("\n" + "="*60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Portfolio Analysis Dashboard")
    parser.add_argument('--positions', type=str, help='Path to positions file')
    parser.add_argument('--prices', type=str, help='Path to price history file')
    parser.add_argument('--output', type=str, help='Output JSON file')
    parser.add_argument('--format', choices=['text', 'json'], default='text', help='Output format')

    args = parser.parse_args()

    dashboard = PortfolioAnalysisDashboard(
        positions_file=args.positions,
        price_data_file=args.prices
    )

    if args.format == 'json':
        report = dashboard.generate_full_report()
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"Report saved to {args.output}")
        else:
            print(json.dumps(report, indent=2))
    else:
        dashboard.print_dashboard()


if __name__ == "__main__":
    main()
